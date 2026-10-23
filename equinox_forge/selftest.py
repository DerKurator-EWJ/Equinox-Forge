from __future__ import annotations

import json
import platform
import tempfile
import time
from pathlib import Path
from typing import Callable

from . import __version__
from .canonical import make_text_surface, tier_name
from .compiler import aggregate_relations
from .database import CanonicalDB
from .demo_builder import build_demo
from .validate import validate_document


def _canonical_identity() -> dict[str, object]:
    _, first = make_text_surface("Hund")
    _, second = make_text_surface("Hund")
    _, plural = make_text_surface("Hunde")
    assert first.node_id == second.node_id
    assert first.node_id != plural.node_id
    assert tier_name(0) == "Q"
    assert tier_name(10) == "Ω"
    return {"node_id": first.node_id, "deterministic": True}


def _document_validation() -> dict[str, object]:
    document = build_demo()
    errors = [issue.message for issue in validate_document(document) if issue.severity == "error"]
    assert not errors, errors
    return {"nodes": len(document.nodes), "evidence": len(document.evidence)}


def _database_roundtrip() -> dict[str, object]:
    document = build_demo()
    with tempfile.TemporaryDirectory(prefix="eqforge-selftest-") as directory:
        db_path = Path(directory) / "forge.sqlite"
        with CanonicalDB(db_path) as database:
            for node in sorted(document.nodes, key=lambda item: (item.level, item.node_id)):
                database.upsert_node(node)
            for evidence in document.evidence:
                database.add_evidence(evidence)
            database.commit()
            stats = database.stats()
            compiled = aggregate_relations(database.db)
    assert stats["nodes"] == len({node.node_id for node in document.nodes})
    assert compiled
    return {"stats": stats, "compiled_relations": len(compiled)}


def run_self_test() -> dict[str, object]:
    checks: list[tuple[str, Callable[[], dict[str, object]]]] = [
        ("canonical_identity", _canonical_identity),
        ("document_validation", _document_validation),
        ("database_roundtrip", _database_roundtrip),
    ]
    started = time.perf_counter()
    results: list[dict[str, object]] = []
    for name, check in checks:
        check_started = time.perf_counter()
        details = check()
        results.append(
            {
                "name": name,
                "status": "passed",
                "duration_ms": round((time.perf_counter() - check_started) * 1000, 3),
                "details": details,
            }
        )
    return {
        "status": "passed",
        "version": __version__,
        "python": platform.python_version(),
        "checks": results,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def main() -> None:
    print(json.dumps(run_self_test(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
