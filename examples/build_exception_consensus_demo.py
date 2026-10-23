from __future__ import annotations
from pathlib import Path
import json, sys

from equinox_forge.database import CanonicalDB
from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig, extract_teacher_behaviour
from equinox_forge.frame_induction import FrameInductionPolicy, induce_relation_frames, persist_frame_document
from equinox_forge.prototype_hierarchy import PrototypeHierarchyPolicy, induce_prototype_hierarchy
from equinox_forge.hierarchical_frame_transfer import HierarchicalFrameTransferPolicy, promote_frames_to_higher_concepts
from equinox_forge.exception_induction import ExceptionInductionPolicy, induce_exception_overrides
from equinox_forge.exception_consensus import ExceptionConsensusPolicy, track_exception_run
from equinox_forge.canonical import make_text_surface
from equinox_forge.ir import ForgeDocument, RelationEvidence, RelationType, SourceRef
from equinox_forge.io import save_document

class BaseTeacher:
    backend_id='v029-demo-base'
    def manifest(self): return {'backend_id':self.backend_id}
    def next_token(self,prompt,top_k,temperature):
        table={'Hund atmet':[(' Luft',.92),(' Sauerstoff',.08)],'Katze atmet':[(' Luft',.92),(' Sauerstoff',.08)],'Adler fliegt':[(' Himmel',.91),(' hoch',.09)],'Falke fliegt':[(' Himmel',.91),(' hoch',.09)]}
        return [TeacherCandidate(i+1,s,s,p,3-i) for i,(s,p) in enumerate(table[prompt.strip()][:top_k])]
class VoteTeacher:
    def __init__(self,support,name): self.support=support; self.backend_id=name
    def manifest(self): return {'backend_id':self.backend_id}
    def next_token(self,prompt,top_k,temperature):
        vals=[(' Sauerstoff',.86),(' Luft',.14)] if self.support else [(' Luft',.90),(' Sauerstoff',.10)]
        return [TeacherCandidate(100+i,s,s,p,4-i) for i,(s,p) in enumerate(vals[:top_k])]
def semantic_doc():
    names=['Hund','Katze','Adler','Falke','Eule']; nodes={}; surfaces={}
    for text in names:
        qs,n=make_text_surface(text)
        for q in qs:nodes[q.node_id]=q
        nodes[n.node_id]=n; surfaces[text]=n
    src=SourceRef('v029-demo-semantic','1','fixture')
    pairs=[('Hund','Katze',.98),('Adler','Falke',.98),('Hund','Adler',.91),('Hund','Falke',.90),('Katze','Adler',.90),('Katze','Falke',.91),('Eule','Adler',.97),('Eule','Falke',.96)]
    return ForgeDocument(nodes=sorted(nodes.values(),key=lambda n:(n.level,n.node_id)),evidence=[RelationEvidence(surfaces[a].node_id,surfaces[b].node_id,RelationType.SEMANTIC_SIMILARITY.value,v,.99,src,{}) for a,b,v in pairs])
def ingest(c,doc):
    for n in doc.nodes:c.upsert_node(n)
    for e in doc.evidence:c.add_evidence(e)
    c.commit()

def main(out_dir='v029_exception_consensus_demo'):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); dbp=out/'master.sqlite'
    if dbp.exists():dbp.unlink()
    cfg=BehaviourProbeConfig(top_k=2,min_probability=0.0)
    base,_,_=extract_teacher_behaviour(BaseTeacher(),['Hund atmet','Katze atmet','Adler fliegt','Falke fliegt'],'base','1',cfg)
    A,_,_=extract_teacher_behaviour(VoteTeacher(True,'A'),['Adler atmet','Falke atmet'],'support-A','1',cfg)
    B,_,_=extract_teacher_behaviour(VoteTeacher(True,'B'),['Adler atmet','Falke atmet'],'support-B','1',cfg)
    C,_,_=extract_teacher_behaviour(VoteTeacher(False,'C'),['Adler atmet','Falke atmet'],'conflict-C','1',cfg)
    D,_,_=extract_teacher_behaviour(VoteTeacher(False,'D'),['Adler atmet','Falke atmet'],'conflict-D','1',cfg)
    pol=ExceptionConsensusPolicy()
    lifecycle=[]
    with CanonicalDB(dbp) as c:
        ingest(c,base); ingest(c,semantic_doc())
        f,_=induce_relation_frames(c.db,FrameInductionPolicy(enable_semantic_slot_typing=True,min_filler_coherence_score=.95,min_filler_pair_fraction=1.0,require_typed_slot=True,enable_latent_slot_prototype=True,prototype_classify_candidates=True,prototype_min_admission_score=.95,prototype_min_support_fillers=2)); persist_frame_document(c.db,f); c.db.commit()
        h,_=induce_prototype_hierarchy(c.db,PrototypeHierarchyPolicy(max_depth=1,min_cross_leaf_score=.85,score_decay_per_depth=0,min_score_floor=.85,min_cross_leaf_pair_fraction=1.0)); persist_frame_document(c.db,h); c.db.commit()
        t,_=promote_frames_to_higher_concepts(c.db,HierarchicalFrameTransferPolicy(min_ancestor_hops=1,max_ancestor_hops=2,min_path_edge_quality=.5,hierarchical_admission_min_path_score=.7)); persist_frame_document(c.db,t); c.db.commit()
        ingest(c,A); ingest(c,B)
        odoc,_=induce_exception_overrides(c.db,ExceptionInductionPolicy(min_exception_target_score=.7,min_disagreement_margin=.5,min_membership_quality=.8,min_prototype_path_quality=.5,max_prototype_hops=2)); save_document(odoc,out/'overrides.eqir.json'); persist_frame_document(c.db,odoc); c.db.commit()
        for label in ('support-1','support-2'):
            r=track_exception_run(c.db,odoc,pol); lifecycle.append({'step':label,'status':r.assessments[0]['status']})
        ingest(c,C); r=track_exception_run(c.db,odoc,pol); lifecycle.append({'step':'conflict-1','status':r.assessments[0]['status']})
        ingest(c,D); r=track_exception_run(c.db,odoc,pol); lifecycle.append({'step':'conflict-2','status':r.assessments[0]['status']})
        for src in ('conflict-C','conflict-D'):
            c.db.execute("INSERT OR REPLACE INTO source_policies(source_id,source_version,enabled,trust_weight,note,metadata_json) VALUES(?,?,?,?,?,?)",(src,'1',0,1.0,'demo recovery','{}'))
        c.db.commit()
        for label in ('recovery-1','recovery-2'):
            r=track_exception_run(c.db,odoc,pol); lifecycle.append({'step':label,'status':r.assessments[0]['status']})
        stats=c.stats()
    payload={'lifecycle':lifecycle,'db_stats':stats}
    (out/'summary.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps(payload,indent=2,sort_keys=True))
if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else 'v029_exception_consensus_demo')
