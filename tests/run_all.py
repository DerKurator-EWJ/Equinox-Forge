from pathlib import Path
import os, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
TESTS=[
    'test_forge.py',
    'test_hf_adapter.py',
    'test_text_teacher.py',
    'test_db_migration_v02.py',
    'test_language_evidence.py',
    'test_teacher_behavior.py',
    'test_tiny_causal_runtime.py',
    'test_hidden_state.py',
    'test_tiny_contextual_runtime.py',
    'test_sense_compiler.py',
    'test_consensus_stability.py',
    'test_rebuild_engine.py',
    'test_incremental_dependency.py',
    'test_derived_macro_hierarchy.py',
    'test_macro_discovery.py',
    'test_runtime_compression.py',
    'test_runtime_base_pack.py',
    'test_runtime_query_benchmark.py',
    'test_runtime_cognition.py',
    'test_behaviour_retention.py',
    'test_tiny_retention_runtime.py',
    'test_pareto_sweep.py',
    'test_generalization.py',
    'test_generalization_ladder.py',
    'test_mechanism_attribution.py',
]
env=os.environ.copy()
old=env.get('PYTHONPATH','')
env['PYTHONPATH']=str(ROOT)+(os.pathsep+old if old else '')
for name in TESTS:
    subprocess.run([sys.executable, str(ROOT/'tests'/name)], check=True, cwd=ROOT, env=env)
print('FORGE_V21_ALL_TESTS_OK')
