from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.generalization import compile_and_benchmark_heldout_generalization

class DemoTeacher:
    backend_id='v019-demo-teacher'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':True}
    def next_token(self,prompt,top_k,temperature):
        if prompt.endswith('Hund ist ein'): vals=[(' Tier',.70),(' Haustier',.20),(' Wesen',.10)]
        elif prompt.endswith('Hund kann'): vals=[(' bellen',.70),(' laufen',.20),(' schlafen',.10)]
        elif prompt.endswith('Katze kann'): vals=[(' miauen',.70),(' schlafen',.20),(' laufen',.10)]
        elif prompt.endswith('Vogel kann'): vals=[(' fliegen',.70),(' laufen',.20),(' schlafen',.10)]
        else: raise KeyError(prompt)
        return [TeacherCandidate(i+1,s,s,p,4.0-i) for i,(s,p) in enumerate(vals[:top_k])]

out=ROOT/'out'/'v019_generalization_demo'
report=compile_and_benchmark_heldout_generalization(
    DemoTeacher(),
    ['Hund ist ein','Hund kann','Katze kann'],
    ['Der Hund ist ein','Mein Hund kann','Die Katze kann','Vogel kann'],
    out,'v019-demo','1',
    probe_cfg=BehaviourProbeConfig(top_k=3,min_probability=0.0),
    cognition_policy=RuntimeCognitionPolicy(max_recall_nodes=64,max_recall_depth=3,max_predictions=3,min_prediction_score=0.0),
    runtime_top_k=3,
)
summary={
    'pack_bytes':report.pack_bytes,
    'pack_nodes':report.pack_nodes,
    'pack_relations':report.pack_relations,
    'train_top1':report.train_replay['top1_retention'],
    'heldout_top1':report.heldout_full_runtime['top1_retention'],
    'heldout_direct_top1':report.heldout_direct_replay['top1_retention'],
    'proper_suffix_transfer_rate':report.heldout_proper_suffix_transfer_rate,
    'lexical_only_rate':report.heldout_lexical_only_rate,
    'top1_known_in_pack_rate':report.heldout_teacher_top1_known_in_pack_rate,
    'mean_known_token_coverage':report.mean_known_token_coverage,
    'coverage_buckets':report.coverage_buckets,
}
print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
