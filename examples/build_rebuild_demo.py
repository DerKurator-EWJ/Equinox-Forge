from pathlib import Path
import json

from equinox_forge.database import CanonicalDB
from equinox_forge.ir import IRNode, RelationEvidence, RelationType, SourceRef, NodeKind, Modality
from equinox_forge.sense_compiler import SenseCompilePolicy, FusionWeights
from equinox_forge.consensus import ConsensusPolicy
from equinox_forge.rebuild import set_source_policy, rebuild_senses
from equinox_forge.io import save_document

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out'; OUT.mkdir(exist_ok=True)
DB=OUT/'rebuild_demo.sqlite'
if DB.exists(): DB.unlink()

def node(db,nid,kind,level=1,surface=None,members=None):
    db.upsert_node(IRNode(nid,Modality.TEXT.value,kind,level,surface,members or [],{}))

def ev(db,a,b,t,s,c,src):
    db.add_evidence(RelationEvidence(a,b,t,s,c,SourceRef(src,'1','demo'),{}))

sense=SenseCompilePolicy(
    threshold=.75,min_channels=1,min_contexts=2,
    weights=FusionWeights(hidden_similarity=1.0,lexical_overlap=0.0,semantic_similarity=0.0,substitution=0.0,transition=0.0,prediction_signature=0.0),
)
cons=ConsensusPolicy(stable_min_sources=2,stable_min_runs=2,stable_min_support_weight=1.5)
timeline=[]
with CanonicalDB(DB) as db:
    node(db,'q-bank',NodeKind.QUANT.value,0,'B')
    node(db,'bank',NodeKind.SURFACE.value,1,'Bank',['q-bank'])
    for i in range(1,5):
        node(db,f'ctx{i}',NodeKind.COMPOSITE.value,2,None,['bank'])
        ev(db,'bank',f'ctx{i}',RelationType.CONTEXTUAL_USE.value,1,1,'context-fixture')
    for src,score in [('teacher-A',.95),('teacher-B',.93)]:
        ev(db,'ctx1','ctx2',RelationType.CONTEXTUAL_SIMILARITY.value,score,1,src)
        ev(db,'ctx3','ctx4',RelationType.CONTEXTUAL_SIMILARITY.value,score,1,src)
    db.commit()

    for label,change in [
        ('full-trust-1',None),
        ('full-trust-2',None),
        ('teacher-B-weight-0.4',('teacher-B',True,.4)),
        ('teacher-A-disabled',('teacher-A',False,1.0)),
    ]:
        if change:
            set_source_policy(db.db,change[0],'1',enabled=change[1],trust_weight=change[2])
        doc,report=rebuild_senses(db.db,'bank',sense,cons)
        save_document(doc,OUT/f'rebuild_demo_{label}.eqir.json')
        timeline.append({
            'label':label,
            'source_policy_hash':report.source_policy_hash,
            'raw_evidence':report.raw_evidence_count,
            'effective_evidence':report.effective_evidence_count,
            'hypotheses':report.consensus_report['hypotheses'],
            'missing_hypotheses':report.consensus_report['missing_hypotheses'],
        })

(OUT/'rebuild_demo.timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(OUT/'rebuild_demo.timeline.json')
