from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.generalization_ladder import load_ladder_train_jsonl, load_ladder_eval_jsonl, compile_and_benchmark_generalization_ladder

class DemoTeacher:
    backend_id='scripted-ladder-demo'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':True}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Hund kann':[(' bellen',.78),(' laufen',.14),(' schlafen',.08)],
            'Mein Hund kann':[(' bellen',.78),(' laufen',.14),(' schlafen',.08)],
            'Hund jagt Maus':[(' heute',.72),(' schnell',.18),(' draußen',.10)],
            'Maus sieht Hund':[(' heute',.72),(' ruhig',.18),(' draußen',.10)],
            'Wolf ist ein':[(' Tier',.82),(' Wesen',.12),(' Haustier',.06)],
            'Hund wohnt in':[(' Haus',.80),(' Stadt',.12),(' Nähe',.08)],
            'Hund ist ein':[(' Tier',.82),(' Haustier',.12),(' Wesen',.06)],
            'Katze ist ein':[(' Tier',.82),(' Haustier',.12),(' Wesen',.06)],
            'Katze kann':[(' miauen',.78),(' schlafen',.14),(' laufen',.08)],
            'Katze jagt Maus':[(' heute',.72),(' schnell',.18),(' draußen',.10)],
            'Hund sieht Katze':[(' heute',.72),(' ruhig',.18),(' draußen',.10)],
            'Haus ist':[(' groß',.76),(' alt',.16),(' nah',.08)],
            'Vogel fliegt':[(' hoch',.76),(' schnell',.16),(' weit',.08)],
            'Katze wohnt':[(' hier',.76),(' ruhig',.16),(' allein',.08)],
            'Vogel fliegt in':[(' Luft',.76),(' Höhe',.16),(' Ferne',.08)],
        }
        vals=table[prompt.strip()][:top_k]
        return [TeacherCandidate(i+1,s,s,p,4.0-i) for i,(s,p) in enumerate(vals)]

base=Path(__file__).resolve().parent/'generalization_ladder'
out=base/'demo_out'
report=compile_and_benchmark_generalization_ladder(
    DemoTeacher(),load_ladder_train_jsonl(base/'train.jsonl'),load_ladder_eval_jsonl(base/'eval.jsonl'),out,
    'scripted-ladder-demo','1',probe_cfg=BehaviourProbeConfig(top_k=3,min_probability=0.0,evidence_confidence=0.95),
    cognition_policy=RuntimeCognitionPolicy(max_recall_nodes=96,max_recall_depth=3,max_predictions=3,min_prediction_score=0.0),runtime_top_k=3,
)
print(json.dumps({
  'pack_bytes':report.pack_bytes,
  'levels':[{ 'level':x.level,'name':x.level_name,'top1':x.top1_retention,'ndcg':x.mean_ndcg_at_k,'contract':x.structural_contract_pass_rate} for x in report.level_reports],
  'highest_any':report.highest_level_with_any_top1_success,
  'highest_full':report.highest_level_with_full_top1_success,
  'highest_contiguous_full':report.highest_contiguous_level_with_full_top1_success,
},ensure_ascii=False,indent=2))
