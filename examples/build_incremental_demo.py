from pathlib import Path
import json

from equinox_forge.database import CanonicalDB
from equinox_forge.ir import IRNode, RelationEvidence, RelationType, SourceRef, NodeKind, Modality
from equinox_forge.sense_compiler import SenseCompilePolicy, FusionWeights
from equinox_forge.consensus import ConsensusPolicy
from equinox_forge.rebuild import rebuild_senses, set_source_policy
from equinox_forge.dependency import register_manual_dependency, register_build_target, refresh_dependency_index, ArtifactRef, impact_from_roots
from equinox_forge.incremental import incremental_rebuild_from_sources

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out'; OUT.mkdir(exist_ok=True)
DB=OUT/'incremental_demo.sqlite'
if DB.exists(): DB.unlink()

def node(db,nid,kind,level=1,surface=None,members=None):
    db.upsert_node(IRNode(nid,Modality.TEXT.value,kind,level,surface,members or [],{}))

def ev(db,a,b,t,s,c,src):
    db.add_evidence(RelationEvidence(a,b,t,s,c,SourceRef(src,'1','demo'),{}))

def fixture(db,target,prefix,teacher):
    node(db,target,NodeKind.SURFACE.value,1,target.title())
    ctx=[f'{prefix}{i}' for i in range(1,5)]
    for x in ctx:
        node(db,x,NodeKind.COMPOSITE.value,2,None,[target])
        ev(db,target,x,RelationType.CONTEXTUAL_USE.value,1,1,f'use-{target}')
    ev(db,ctx[0],ctx[1],RelationType.CONTEXTUAL_SIMILARITY.value,.95,1,teacher)
    ev(db,ctx[2],ctx[3],RelationType.CONTEXTUAL_SIMILARITY.value,.94,1,teacher)

sense=SenseCompilePolicy(
    threshold=.75,min_channels=1,min_contexts=2,
    weights=FusionWeights(hidden_similarity=1.0,lexical_overlap=0.0,semantic_similarity=0.0,substitution=0.0,transition=0.0,prediction_signature=0.0),
)
cons=ConsensusPolicy(stable_min_sources=1,stable_min_runs=1,stable_min_support_weight=.5)

with CanonicalDB(DB) as db:
    fixture(db,'bank','b','teacher-bank')
    fixture(db,'kran','k','teacher-kran')
    db.commit()
    rebuild_senses(db.db,'bank',sense,cons)
    rebuild_senses(db.db,'kran',sense,cons)

    register_manual_dependency(db.db,'artifact','macro-bank','build_target','bank','demo')
    register_manual_dependency(db.db,'artifact','domain-bank','artifact','macro-bank','demo')
    register_build_target(db.db,'future-macro-bank','macro',{'demo':True})
    register_manual_dependency(db.db,'build_target','future-macro-bank','build_target','bank','demo')
    refresh_dependency_index(db.db)

    impact=impact_from_roots(db.db,[ArtifactRef('source','teacher-bank@1')],refresh=False)
    set_source_policy(db.db,'teacher-bank','1',trust_weight=.5)
    report=incremental_rebuild_from_sources(db.db,['teacher-bank@1'],output_dir=OUT/'incremental_outputs')
    stats=db.stats()

payload={'impact':impact.to_dict(),'incremental_rebuild':report.to_dict(),'db_stats':stats}
path=OUT/'incremental_demo.report.json'
path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(path)
