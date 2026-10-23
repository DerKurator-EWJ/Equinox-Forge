from pathlib import Path
import json, shutil, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.behaviour_retention import compile_and_benchmark_teacher_behaviour

class DemoTeacher:
    backend_id='v017-scripted-demo-teacher'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':'deterministic'}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Der Hund ist ein':[(1,'Tier',.70),(2,'Haustier',.20),(3,'Tierchen',.10)],
            'Der Hund kann':[(4,'bellen',.80),(5,'laufen',.15),(6,'schlafen',.05)],
            'Die Katze kann':[(7,'miauen',.75),(6,'schlafen',.20),(5,'laufen',.05)],
        }
        return [TeacherCandidate(i,s,' '+s,p,p*6.0) for i,s,p in table[prompt][:top_k]]

OUT=Path(__file__).parent/'behaviour_retention_demo'
if OUT.exists(): shutil.rmtree(OUT)
report=compile_and_benchmark_teacher_behaviour(
    DemoTeacher(), ['Der Hund ist ein','Der Hund kann','Die Katze kann'], OUT,
    'demo-teacher','1',
    probe_cfg=BehaviourProbeConfig(top_k=3,min_probability=0.0,evidence_confidence=.95),
    cognition_policy=RuntimeCognitionPolicy(max_recall_nodes=48,max_recall_depth=2,max_predictions=3,min_prediction_score=.00001),
    runtime_top_k=3,
)
summary={
 'pack':str(OUT/'retention.eqbase'),
 'pack_bytes':report.pack_bytes,
 'pack_nodes':report.pack_nodes,
 'pack_relations':report.pack_relations,
 'direct_replay':report.direct_replay,
 'full_runtime':{
   'top1_retention':report.top1_retention,
   'mean_teacher_topk_recall':report.mean_teacher_topk_recall,
   'mean_teacher_probability_mass_retained_in_runtime_topk':report.mean_teacher_probability_mass_retained_in_runtime_topk,
   'mean_ndcg_at_k':report.mean_ndcg_at_k,
   'mean_conditional_js_divergence':report.mean_conditional_js_divergence,
   'average_recall_nodes':report.average_recall_nodes,
   'average_relation_checks':report.average_relation_checks,
 },
}
print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
