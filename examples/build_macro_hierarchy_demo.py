from pathlib import Path
import shutil

from equinox_forge.database import CanonicalDB
from equinox_forge.ir import IRNode, RelationEvidence, RelationType, SourceRef, NodeKind, Modality
from equinox_forge.sense_compiler import SenseCompilePolicy, FusionWeights
from equinox_forge.consensus import ConsensusPolicy
from equinox_forge.rebuild import rebuild_senses, set_source_policy
from equinox_forge.macro_builder import MacroCompilePolicy, rebuild_macro
from equinox_forge.incremental import incremental_rebuild_from_sources
from equinox_forge.artifact_store import list_artifacts

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out'/'v011_demo'
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)
DB=OUT/'master.sqlite'


def node(c,nid,kind,level=1,surface=None,members=None):
    c.upsert_node(IRNode(nid,Modality.TEXT.value,kind,level,surface,members or [],{}))

def ev(c,a,b,typ,score,source):
    c.add_evidence(RelationEvidence(a,b,typ,score,1.0,SourceRef(source,'1','demo'),{}))

def target(c,name,teacher):
    node(c,f'{name}-q',NodeKind.QUANT.value,0,name[:1])
    node(c,name,NodeKind.SURFACE.value,1,name.title(),[f'{name}-q'])
    ctx=[f'{name}-ctx-a',f'{name}-ctx-b']
    for x in ctx:
        node(c,x,NodeKind.COMPOSITE.value,2,None,[name])
        ev(c,name,x,RelationType.CONTEXTUAL_USE.value,1.0,f'use-{name}')
    ev(c,ctx[0],ctx[1],RelationType.CONTEXTUAL_SIMILARITY.value,.96,teacher)

with CanonicalDB(DB) as c:
    for name,teacher in [('bank','teacher-bank'),('kran','teacher-kran'),('hund','teacher-hund')]:
        target(c,name,teacher)
    c.commit()
    sp=SenseCompilePolicy(threshold=.75,min_channels=1,min_contexts=2,weights=FusionWeights(hidden_similarity=1.0,lexical_overlap=0.0,semantic_similarity=0.0,substitution=0.0,transition=0.0,prediction_signature=0.0))
    cp=ConsensusPolicy(stable_min_sources=1,stable_min_runs=1,stable_consensus=.5,stable_min_support_weight=.5)
    for name in ('bank','kran','hund'):
        rebuild_senses(c.db,name,sp,cp)
    rebuild_macro(c.db,'macro-pair',MacroCompilePolicy(input_build_targets=['bank','kran'],allowed_statuses=['stable'],surface='macro:bank+kran'))
    rebuild_macro(c.db,'macro-domain',MacroCompilePolicy(input_build_targets=['macro-pair','hund'],allowed_statuses=['active','stable'],surface='macro:domain'))
    before=list_artifacts(c.db)
    set_source_policy(c.db,'teacher-bank','1',enabled=False,trust_weight=0.0)
    report=incremental_rebuild_from_sources(c.db,['teacher-bank@1'],output_dir=OUT/'rebuild')
    after=list_artifacts(c.db)

(OUT/'before.json').write_text(__import__('json').dumps(before,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
(OUT/'after.json').write_text(__import__('json').dumps(after,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
(OUT/'incremental.json').write_text(__import__('json').dumps(report.to_dict(),indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
print(DB)
print('affected:', report.affected_build_targets)
print('rebuilt:', [(x['target_id'],x['status']) for x in report.rebuilt_targets])
