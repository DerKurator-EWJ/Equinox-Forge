from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.30.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Equinox Forge v0.30 release contract.")
    parser.add_argument("--skip-regression", action="store_true", help="skip the 33-file regression suite")
    parser.add_argument("--build", action="store_true", help="also build sdist and wheel into out/dist")
    return parser.parse_args()


def run_command(name: str, command: list[str], env: dict[str, str]) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    duration = time.perf_counter() - started
    if completed.returncode != 0:
        raise SystemExit(f"{name} failed with exit code {completed.returncode}")
    return {"name": name, "status": "passed", "duration_seconds": round(duration, 3)}


def verify_metadata() -> dict[str, object]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = project["project"]["version"]
    init_text = (ROOT / "equinox_forge" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    package_version = match.group(1) if match else None
    readme_title = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
    release_exists = (ROOT / "RELEASE_V0_30.md").is_file()
    adapters = sorted(path.name for path in (ROOT / "equinox_forge" / "adapters").glob("*.json"))
    assert project_version == EXPECTED_VERSION
    assert package_version == EXPECTED_VERSION
    assert "v0.30" in readme_title
    assert release_exists
    assert adapters == ["deepseek_v3.json", "gpt2.json", "qwen2.json"]
    return {
        "name": "release_metadata",
        "status": "passed",
        "version": EXPECTED_VERSION,
        "packaged_adapters": adapters,
    }


def main() -> int:
    args = parse_args()
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    checks: list[dict[str, object]] = [verify_metadata()]
    checks.append(
        run_command(
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "equinox_forge", "tests", "tools"],
            env,
        )
    )
    checks.append(run_command("installed_smoke", [sys.executable, "-m", "equinox_forge.selftest"], env))
    if not args.skip_regression:
        checks.append(
            run_command(
                "full_regression",
                [sys.executable, "tests/run_all.py", "--report", "out/v030-regression-report.json"],
                env,
            )
        )
    if args.build:
        checks.append(run_command("package_build", [sys.executable, "-m", "build", "--outdir", "out/dist"], env))
    report = {"status": "passed", "version": EXPECTED_VERSION, "checks": checks}
    print(json.dumps(report, indent=2, sort_keys=True))
    print("FORGE_V30_RELEASE_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
