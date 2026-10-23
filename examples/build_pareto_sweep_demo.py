from pathlib import Path
import json, shutil, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.pareto_sweep import ParetoSweepConfig, run_behaviour_pareto_sweep

class DemoTeacher:
    backend_id='v018-pareto-demo-teacher'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':'deterministic'}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Der Hund ist ein':[(1,'Tier',.60),(2,'Haustier',.25),(3,'Tierchen',.10),(4,'Freund',.05)],
            'Der Hund kann':[(5,'bellen',.65),(6,'laufen',.20),(7,'schlafen',.10),(8,'spielen',.05)],
            'Die Katze kann':[(9,'miauen',.60),(7,'schlafen',.20),(6,'laufen',.15),(8,'spielen',.05)],
        }
        return [TeacherCandidate(i,s,' '+s,p,p*6.0) for i,s,p in table[prompt][:top_k]]

OUT=Path(__file__).parent/'pareto_sweep_demo'
if OUT.exists(): shutil.rmtree(OUT)
report=run_behaviour_pareto_sweep(
    DemoTeacher(), ['Der Hund ist ein','Der Hund kann','Die Katze kann'], OUT,
    'pareto-demo-teacher','1',
    probe_cfg=BehaviourProbeConfig(top_k=4,min_probability=0.0,evidence_confidence=.95),
    base_cognition_policy=RuntimeCognitionPolicy(max_recall_nodes=48,max_recall_depth=2,max_predictions=4,min_prediction_score=0.0),
    sweep_cfg=ParetoSweepConfig(
        evidence_top_k_values=[1,2,4],
        min_relation_score_values=[0.0,0.11],
        max_recall_nodes_values=[16,48],
        max_recall_depth_values=[0,2],
        compression_modes=['none','auto'],
        max_points=64,
        runtime_top_k=4,
    ),
)
rows=report.results
summary={
    'points': report.points,
    'pareto_storage_ids': report.pareto_storage_ids,
    'pareto_runtime_ids': report.pareto_runtime_ids,
    'pareto_joint_ids': report.pareto_joint_ids,
    'smallest_pack': next(x.to_dict() for x in rows if x.point_id==report.smallest_pack_point),
    'highest_full_mass': next(x.to_dict() for x in rows if x.point_id==report.highest_full_mass_point),
    'lowest_relation_work': next(x.to_dict() for x in rows if x.point_id==report.lowest_relation_work_point),
}
print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
