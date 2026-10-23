from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
TESTS=[
    'test_forge.py',
    'test_hf_adapter.py',
    'test_text_teacher.py',
    'test_db_migration_v02.py',
    'test_language_evidence.py',
    'test_teacher_behavior.py',
    'test_tiny_causal_runtime.py',
]
for name in TESTS:
    subprocess.run([sys.executable, str(ROOT/'tests'/name)], check=True, cwd=ROOT)
print('FORGE_V05_ALL_TESTS_OK')
