from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
OPTIONAL_TESTS = {
    "test_tiny_causal_runtime.py",
    "test_tiny_contextual_runtime.py",
    "test_tiny_retention_runtime.py",
}


def discover_tests() -> list[str]:
    return sorted(path.name for path in TEST_DIR.glob("test_*.py"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run every Equinox Forge regression in isolation.")
    parser.add_argument("--match", help="run only test filenames containing this text")
    parser.add_argument("--skip-optional", action="store_true", help="skip optional Torch integration tests")
    parser.add_argument("--list", action="store_true", help="list selected tests without running them")
    parser.add_argument("--report", type=Path, help="write a machine-readable JSON report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tests = discover_tests()
    if args.match:
        tests = [name for name in tests if args.match in name]
    if args.skip_optional:
        tests = [name for name in tests if name not in OPTIONAL_TESTS]
    if args.list:
        print("\n".join(tests))
        return 0
    if not tests:
        print("No tests selected.", file=sys.stderr)
        return 2

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    started = time.perf_counter()
    results: list[dict[str, object]] = []
    for index, name in enumerate(tests, start=1):
        print(f"[{index:02d}/{len(tests):02d}] {name}", flush=True)
        test_started = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, str(TEST_DIR / name)],
            cwd=ROOT,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
        duration = time.perf_counter() - test_started
        skipped = completed.returncode == 0 and "_SKIPPED_" in completed.stdout
        result = {
            "name": name,
            "status": "skipped" if skipped else ("passed" if completed.returncode == 0 else "failed"),
            "returncode": completed.returncode,
            "duration_seconds": round(duration, 3),
        }
        results.append(result)
        if completed.returncode != 0:
            report = _report(results, started, len(tests), "failed")
            _write_report(args.report, report)
            print(json.dumps(report, indent=2, sort_keys=True))
            return completed.returncode

    report = _report(results, started, len(tests), "passed")
    _write_report(args.report, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    print("FORGE_V30_ALL_TESTS_OK")
    return 0


def _report(
    results: list[dict[str, object]],
    started: float,
    selected: int,
    status: str,
) -> dict[str, object]:
    passed = sum(item["status"] == "passed" for item in results)
    skipped = sum(item["status"] == "skipped" for item in results)
    failed = sum(item["status"] == "failed" for item in results)
    return {
        "format": "equinox-forge-regression-report-v1",
        "forge_version": "0.30.0",
        "python": sys.version.split()[0],
        "status": status,
        "selected": selected,
        "completed": len(results),
        "passed": passed,
        "skipped": skipped,
        "failed": failed,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "tests": results,
    }


def _write_report(path: Path | None, report: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
