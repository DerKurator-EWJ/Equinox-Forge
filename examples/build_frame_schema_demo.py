from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig, load_prompts
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.frame_induction import FrameInductionPolicy
from equinox_forge.frame_schema_benchmark import load_frame_eval_jsonl, compile_and_benchmark_frame_schemas

class DemoTeacher:
    backend_id='scripted-frame-demo'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':True}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Hund ist ein':[(' Tier',.82),(' Haustier',.12),(' Wesen',.06)],
            'Katze ist ein':[(' Tier',.82),(' Haustier',.12),(' Wesen',.06)],
            'Hund kann':[(' bellen',.80),(' rennen',.12),(' springen',.08)],
            'Katze kann':[(' miauen',.80),(' schnurren',.12),(' klettern',.08)],
            'Wolf ist ein':[(' Tier',.84),(' Wesen',.10),(' Raubtier',.06)],
            'Fuchs ist ein':[(' Tier',.84),(' Wesen',.10),(' Raubtier',.06)],
            'Mein Wolf ist ein':[(' Tier',.84),(' Wesen',.10),(' Raubtier',.06)],
            'Stein ist ein':[(' Objekt',.80),(' Material',.12),(' Ding',.08)],
        }
        vals=table[prompt.strip()][:top_k]
        return [TeacherCandidate(i+1,s,s,p,4.0-i) for i,(s,p) in enumerate(vals)]

base=Path(__file__).resolve().parent/'frame_schema'
out=base/'demo_out'
report=compile_and_benchmark_frame_schemas(
    DemoTeacher(),load_prompts([base/'train.txt']),load_frame_eval_jsonl(base/'eval.jsonl'),out,
    'scripted-frame-demo','1',
    probe_cfg=BehaviourProbeConfig(top_k=3,min_probability=0.0,evidence_confidence=.95),
    frame_policy=FrameInductionPolicy(min_target_context_fraction=1.0),
    cognition_policy=RuntimeCognitionPolicy(max_predictions=3,min_prediction_score=0.0),
    runtime_top_k=3,
)
print(json.dumps({
    'frames':report.induced_frames,
    'patterns':[x['pattern'] for x in report.frame_induction['frames']],
    'pack_bytes':report.pack_bytes,
    'frame_only_top1':report.frame_only['top1_retention'],
    'no_frame_top1':report.no_frame['top1_retention'],
    'applicability_precision':report.frame_applicability_precision,
    'applicability_recall':report.frame_applicability_recall,
    'detail':[x.to_dict() for x in report.details],
},ensure_ascii=False,indent=2))
