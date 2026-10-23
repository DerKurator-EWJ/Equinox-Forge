from pathlib import Path
import json, shutil

from equinox_forge.database import CanonicalDB
from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig, extract_teacher_behaviour
from equinox_forge.frame_induction import FrameInductionPolicy, induce_relation_frames, persist_frame_document
from equinox_forge.prototype_hierarchy import PrototypeHierarchyPolicy, induce_prototype_hierarchy
from equinox_forge.hierarchical_frame_transfer import HierarchicalFrameTransferPolicy, promote_frames_to_higher_concepts
from equinox_forge.canonical import make_text_surface
from equinox_forge.ir import ForgeDocument, RelationEvidence, RelationType, SourceRef
from equinox_forge.generalization import _pass_through_compression
from equinox_forge.compiler import CompilePolicy
from equinox_forge.runtime_pack import compile_base_pack, load_base_pack
from equinox_forge.runtime_cognition import RuntimeCognition, RuntimeCognitionPolicy

class Teacher:
    backend_id='v026-demo-teacher'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':True}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Hund atmet':[(' Luft',.92),(' Sauerstoff',.08)],
            'Katze atmet':[(' Luft',.92),(' Sauerstoff',.08)],
            'Adler fliegt':[(' Himmel',.91),(' hoch',.09)],
            'Falke fliegt':[(' Himmel',.91),(' hoch',.09)],
        }
        return [TeacherCandidate(i+1,s,s,p,3-i) for i,(s,p) in enumerate(table[prompt.strip()][:top_k])]

def support_doc():
    nodes={}; surf={}
    for text in ['Hund','Katze','Adler','Falke','Stein']:
        qs,n=make_text_surface(text)
        for q in qs: nodes[q.node_id]=q
        nodes[n.node_id]=n; surf[text]=n
    src=SourceRef('v026-independent-semantics','1','fixture')
    pairs=[('Hund','Katze',.98),('Adler','Falke',.98),('Hund','Adler',.91),('Hund','Falke',.90),('Katze','Adler',.90),('Katze','Falke',.91)]
    ev=[RelationEvidence(surf[a].node_id,surf[b].node_id,RelationType.SEMANTIC_SIMILARITY.value,s,.99,src) for a,b,s in pairs]
    return ForgeDocument(nodes=sorted(nodes.values(),key=lambda n:(n.level,n.node_id)),evidence=ev)

out=Path(__file__).resolve().parent/'hierarchical_frame_transfer_demo'
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True)
db_path=out/'master.sqlite'
teacher_doc,_,_=extract_teacher_behaviour(Teacher(),['Hund atmet','Katze atmet','Adler fliegt','Falke fliegt'],'v026-teacher','1',BehaviourProbeConfig(top_k=2,min_probability=0.0))
with CanonicalDB(db_path) as db:
    for doc in (teacher_doc,support_doc()):
        for n in doc.nodes: db.upsert_node(n)
        for e in doc.evidence: db.add_evidence(e)
    db.commit()
    frames,fr=induce_relation_frames(db.db,FrameInductionPolicy(enable_semantic_slot_typing=True,min_filler_coherence_score=.95,min_filler_pair_fraction=1.0,require_typed_slot=True,enable_latent_slot_prototype=True,prototype_classify_candidates=False,prototype_min_admission_score=.95,prototype_min_support_fillers=2))
    persist_frame_document(db.db,frames); db.db.commit()
    hierarchy,hr=induce_prototype_hierarchy(db.db,PrototypeHierarchyPolicy(max_depth=1,min_cross_leaf_score=.85,score_decay_per_depth=0,min_score_floor=.85,membership_confidence=.95))
    persist_frame_document(db.db,hierarchy); db.db.commit()
    transfer,tr=promote_frames_to_higher_concepts(db.db,HierarchicalFrameTransferPolicy(max_ancestor_hops=2,min_path_edge_quality=.5,hierarchical_admission_min_path_score=.7))
    persist_frame_document(db.db,transfer); db.db.commit()
    comp=_pass_through_compression(db.db)
    manifest=compile_base_pack(db.db,out/'transfer.eqbase',pack_id='v026-demo',pack_version=26,compression_run_id=comp.compression_run_id,include_metadata=True,relation_policy=CompilePolicy(min_score=0,min_confidence=0,min_sources=1))

pack=load_base_pack(out/'transfer.eqbase')
base=dict(max_recall_nodes=64,max_recall_depth=2,max_predictions=3,min_prediction_score=0.0,enable_exact_context=False,enable_suffix_context=False,enable_lexical_seeds=False,enable_parent_routing=False,enable_relation_recall=False,enable_transition_prediction=False,enable_recalled_context_prediction=False,enable_direct_context_prediction=True,enable_frame_schema_matching=True,enable_semantic_slot_admission=True,enable_slot_prototype_admission=True)
old=RuntimeCognition(pack,RuntimeCognitionPolicy(**base,enable_hierarchical_slot_admission=False))
new=RuntimeCognition(pack,RuntimeCognitionPolicy(**base,enable_hierarchical_slot_admission=True))
cases=[]
for prompt in ['Adler atmet','Falke atmet','Stein atmet']:
    a=old.predict(prompt); b=new.predict(prompt)
    checks=[sc for row in b.frame_admission for sc in row.get('slot_checks',[])]
    h=[sc for sc in checks if sc.get('reason')=='hierarchical_prototype_membership']
    cases.append({'prompt':prompt,'old_top1':a.predictions[0].surface if a.predictions else None,'v026_top1':b.predictions[0].surface if b.predictions else None,'hierarchical_path':h[0].get('hierarchical_path') if h else None,'hierarchical_hops':h[0].get('hierarchical_hops') if h else None})
report={'format':'equinox-forge-v026-demo','base_pack':manifest.to_dict(),'frame_induction':fr.to_dict(),'prototype_hierarchy':hr.to_dict(),'frame_transfer':tr.to_dict(),'cases':cases}
(out/'demo-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps({'pack_bytes':manifest.file_bytes,'nodes':manifest.node_count,'relations':manifest.relation_count,'promoted_frames':tr.frames_promoted,'cases':cases},ensure_ascii=False,indent=2))
