from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.hidden_state import HiddenStateSample, HiddenStateConfig, load_probe_dataset, extract_contextual_hidden_evidence
from equinox_forge.database import CanonicalDB
from equinox_forge.ir import RelationEvidence, RelationType, SourceRef
from equinox_forge.sense_compiler import SenseCompilePolicy, FusionWeights, compile_provisional_senses, find_text_surface_id
from equinox_forge.consensus import ConsensusPolicy, track_hypothesis_run, list_hypothesis_states
from equinox_forge.io import save_document

class StructureBackend:
    backend_id='consensus-demo-structure'
    def manifest(self): return {'backend_id':self.backend_id,'dimension':4}
    def contextual_state(self,text,target_start,target_end,layers,pooling):
        return [HiddenStateSample(layer=l,vector=[1.0,0.0,0.0,0.0],token_count=1,metadata={}) for l in layers]

probes=load_probe_dataset([ROOT/'examples'/'probes'/'bank_senses.jsonl'])
doc,_,_=extract_contextual_hidden_evidence(StructureBackend(),probes,'demo-use','1',HiddenStateConfig(layers=(-1,),top_k=6,min_cosine=-1.0))
doc.evidence=[e for e in doc.evidence if e.relation_type==RelationType.CONTEXTUAL_USE.value]
labels={p.probe_id:p.label for p in probes}
ctx_label={e.to_id:labels[e.metadata['probe_id']] for e in doc.evidence}
finance=sorted(c for c,l in ctx_label.items() if l=='finance')
seat=sorted(c for c,l in ctx_label.items() if l=='seat')

def add_source(db,name,inside,cross=None):
    src=SourceRef(name,'1','contextual_hidden_similarity')
    for group in (finance,seat):
        for i,a in enumerate(group):
            for b in group[i+1:]:
                db.add_evidence(RelationEvidence(a,b,RelationType.CONTEXTUAL_SIMILARITY.value,inside,1.0,src,{'demo':True}))
    if cross is not None:
        for a in finance:
            for b in seat:
                db.add_evidence(RelationEvidence(a,b,RelationType.CONTEXTUAL_SIMILARITY.value,cross,1.0,src,{'demo':True,'conflict':True}))

sp=SenseCompilePolicy(threshold=.75,min_channels=1,min_contexts=2,weights=FusionWeights(hidden_similarity=1.0,lexical_overlap=0.0,semantic_similarity=0.0,substitution=0.0,transition=0.0,prediction_signature=0.0))
cp=ConsensusPolicy(source_vote_threshold=.58,source_vote_margin=.08,stable_min_sources=2,stable_min_runs=2,stable_consensus=.75,quarantine_conflicts=2)
out=ROOT/'out'; out.mkdir(exist_ok=True)
dbp=out/'consensus_demo.sqlite'
if dbp.exists(): dbp.unlink()
reports=[]
with CanonicalDB(dbp) as db:
    for n in doc.nodes: db.upsert_node(n)
    for e in doc.evidence: db.add_evidence(e)
    add_source(db,'teacher-A',.95); add_source(db,'teacher-B',.93); db.commit()
    target=find_text_surface_id(db.db,'Bank')
    for stage in ['candidate','stable']:
        derived,_=compile_provisional_senses(db.db,target,sp)
        rep=track_hypothesis_run(db.db,derived,target,sp,cp)
        reports.append({'stage':stage,'report':rep.to_dict()})
    add_source(db,'teacher-C',.58,.70); db.commit()
    derived,_=compile_provisional_senses(db.db,target,sp)
    reports.append({'stage':'contested','report':track_hypothesis_run(db.db,derived,target,sp,cp).to_dict()})
    add_source(db,'teacher-D',.58,.70); db.commit()
    derived,_=compile_provisional_senses(db.db,target,sp)
    final=track_hypothesis_run(db.db,derived,target,sp,cp)
    reports.append({'stage':'quarantined','report':final.to_dict()})
    save_document(derived,out/'consensus_demo.eqir.json')
    states=list_hypothesis_states(db.db,target)
    (out/'consensus_demo.states.json').write_text(json.dumps(states,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(out/'consensus_demo.timeline.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print('FORGE_V08_CONSENSUS_DEMO_OK', dbp)
