from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.database import CanonicalDB
from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig, extract_teacher_behaviour
from equinox_forge.frame_induction import FrameInductionPolicy, induce_relation_frames, persist_frame_document
from equinox_forge.prototype_hierarchy import PrototypeHierarchyPolicy, induce_prototype_hierarchy
from equinox_forge.canonical import make_text_surface
from equinox_forge.ir import ForgeDocument, RelationEvidence, RelationType, SourceRef
from equinox_forge.io import save_document
from equinox_forge.generalization import _pass_through_compression
from equinox_forge.compiler import CompilePolicy
from equinox_forge.runtime_pack import compile_base_pack, load_base_pack
from equinox_forge.runtime_query import RuntimeIndex

class Teacher:
    backend_id='v025-demo-teacher'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':True}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Hund ist ein':[(' Tier',.90),(' Wesen',.10)], 'Katze ist ein':[(' Tier',.90),(' Wesen',.10)],
            'Adler kann':[(' fliegen',.90),(' jagen',.10)], 'Falke kann':[(' fliegen',.90),(' jagen',.10)],
            'Lachs lebt':[(' Wasser',.90),(' Fluss',.10)], 'Forelle lebt':[(' Wasser',.90),(' Fluss',.10)],
            'Eiche braucht':[(' Wasser',.90),(' Licht',.10)], 'Buche braucht':[(' Wasser',.90),(' Licht',.10)],
        }
        return [TeacherCandidate(i+1,s,s,p,3.0-i) for i,(s,p) in enumerate(table[prompt.strip()][:top_k])]

def support_doc():
    groups=[['Hund','Katze'],['Adler','Falke'],['Lachs','Forelle'],['Eiche','Buche']]
    nodes={}; surf={}
    for text in sum(groups,[]):
        qs,n=make_text_surface(text)
        for q in qs: nodes[q.node_id]=q
        nodes[n.node_id]=n; surf[text]=n
    pairs=[]
    for a,b in groups: pairs.append((a,b,.98))
    for ga,gb in ((groups[0],groups[1]),(groups[2],groups[3])):
        for a in ga:
            for b in gb: pairs.append((a,b,.90))
    for a in groups[0]+groups[1]:
        for b in groups[2]+groups[3]: pairs.append((a,b,.80))
    src=SourceRef('v025-independent-semantic','1','semantic_similarity_fixture')
    ev=[RelationEvidence(surf[a].node_id,surf[b].node_id,RelationType.SEMANTIC_SIMILARITY.value,score,.99,src,{'fixture':True}) for a,b,score in pairs]
    return ForgeDocument(nodes=sorted(nodes.values(),key=lambda n:(n.level,n.node_id)),evidence=ev)

out=ROOT/'out'/'v25-prototype-hierarchy-demo'
out.mkdir(parents=True,exist_ok=True)
for p in out.iterdir():
    if p.is_file(): p.unlink()
db_path=out/'master.sqlite'; pack_path=out/'hierarchy.eqbase'
prompts=['Hund ist ein','Katze ist ein','Adler kann','Falke kann','Lachs lebt','Forelle lebt','Eiche braucht','Buche braucht']
teacher_doc,_,_=extract_teacher_behaviour(Teacher(),prompts,'v025-demo-teacher','1',BehaviourProbeConfig(top_k=2,min_probability=0.0))
with CanonicalDB(db_path) as db:
    for doc in (teacher_doc,support_doc()):
        for n in doc.nodes: db.upsert_node(n)
        for e in doc.evidence: db.add_evidence(e)
    db.commit()
    fp=FrameInductionPolicy(enable_semantic_slot_typing=True,min_filler_coherence_score=.95,min_filler_pair_fraction=1.0,require_typed_slot=True,enable_latent_slot_prototype=True,prototype_classify_candidates=False,prototype_min_admission_score=.95)
    frame_doc,frame_report=induce_relation_frames(db.db,fp)
    persist_frame_document(db.db,frame_doc); db.db.commit()
    hp=PrototypeHierarchyPolicy(max_depth=4,min_cross_leaf_score=.88,score_decay_per_depth=.10,min_score_floor=.68,min_cross_leaf_pair_fraction=1.0,membership_confidence=.95)
    hierarchy_doc,hierarchy_report=induce_prototype_hierarchy(db.db,hp)
    save_document(hierarchy_doc,out/'prototype-hierarchy.eqir.json')
    (out/'prototype-hierarchy.report.json').write_text(json.dumps(hierarchy_report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    persist_frame_document(db.db,hierarchy_doc); db.db.commit()
    comp=_pass_through_compression(db.db)
    manifest=compile_base_pack(db.db,pack_path,pack_id='v025-prototype-hierarchy-demo',pack_version=25,compression_run_id=comp.compression_run_id,include_metadata=True,relation_policy=CompilePolicy(min_score=0.0,min_confidence=0.0,min_sources=1))
pack=load_base_pack(pack_path); idx=RuntimeIndex(pack)
root=next(n for n in pack.nodes if (n.metadata or {}).get('role')=='recursive_latent_concept' and int((n.metadata or {}).get('hierarchy_depth',0))==2)
base=[n for n in pack.nodes if (n.metadata or {}).get('role')=='latent_slot_prototype']
paths={}
for n in base:
    rows,metrics=idx.traverse_relation(n.node_id,RelationType.IS_A.value,max_depth=4)
    paths[n.surface]={'root_reached':root.node_id in {r['node_id'] for r in rows},'reachable':rows,'work':metrics.to_dict()}
summary={'base_prototypes':frame_report.generated_slot_prototypes,'recursive_concepts':hierarchy_report.generated_concepts,'hierarchy_depth':hierarchy_report.highest_hierarchy_depth,'membership_edges':hierarchy_report.generated_memberships,'pack_bytes':manifest.file_bytes,'pack_nodes':manifest.node_count,'pack_relations':manifest.relation_count,'root_node_id':root.node_id,'all_base_prototypes_reach_root':all(v['root_reached'] for v in paths.values()),'paths':paths}
(out/'demo-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
