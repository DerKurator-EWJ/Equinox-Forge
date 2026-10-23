# Equinox Forge v0.30 — Engineering Freeze

## Purpose

v0.30 is the reproducibility boundary after the v0.22–v0.29 mechanism sequence. It adds no new inference, hierarchy, specificity or exception behavior. The goal is to make the existing system installable, testable and measurable before the permanent benchmark and ablation work begins.

## Changes

### Packaging

- Added a PEP 517 `setuptools` build configuration.
- Restricted package discovery to `equinox_forge*`; repository directories such as `out`, `tests`, `examples` and top-level `adapters` are no longer mistaken for Python packages.
- Added package metadata for the README.
- Added `equinox-forge` as a readable alias for the existing `eqforge` command.
- Packaged GPT-2, Qwen2 and DeepSeek-V3 adapter specifications inside `equinox_forge/adapters`.
- Changed adapter auto-detection to use those packaged adapters when no external adapter directory is supplied.

### Verification

- Added `eqforge --version`.
- Added `eqforge self-test`, which checks canonical identity, IR validation and a temporary SQLite compile round-trip using only installed package resources.
- Reworked `tests/run_all.py` to discover all `test_*.py` regressions, execute each in isolation, report timing and optionally write JSON.
- Added `tools/verify_release.py` to enforce version consistency, compile the source, run the package smoke test, execute regressions and optionally build distributions.
- Added a GitHub Actions workflow for Python 3.10 and 3.12.
- Added focused Ruff checks for syntax errors, invalid control flow and undefined names.

### Version alignment

- `pyproject.toml`: `0.30.0`
- `equinox_forge.__version__`: `0.30.0`
- README main milestone: `v0.30`
- regression report marker: `FORGE_V30_ALL_TESTS_OK`

## Verification commands

```bash
python -m pip install -e ".[dev]"
ruff check .
eqforge --version
eqforge self-test
python tests/run_all.py --report out/v030-regression-report.json
python tools/verify_release.py --build
```

For a fast metadata, syntax and installed-package check:

```bash
python tools/verify_release.py --skip-regression
```

## Compatibility

v0.30 does not change the `.eqbase` binary format, runtime cognition policies, database schema or v0.29 exception lifecycle semantics. Existing v0.29 research fixtures are expected to produce the same behavioral results.

## Explicit non-claims

- v0.30 does not establish large-scale Teacher-to-Equinox retention.
- v0.30 does not add active probe selection.
- v0.30 does not provide the permanent benchmark planned for v0.31.
- v0.30 does not provide the mechanism ablation suite planned for v0.32.
- CI and passing regressions demonstrate internal reproducibility, not external scientific validity.

## Next milestone

v0.31 should define the permanent, versioned benchmark contract: fixed train/evaluation partitions, unknown rejection, exception and transfer cases, work counters, BASE size, compile cost and teacher-query accounting.
