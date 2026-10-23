from pathlib import Path
import json
import shutil

from equinox_forge.database import CanonicalDB
from equinox_forge.ir import IRNode, NodeKind, Modality, RelationEvidence, SourceRef, RelationType
from equinox_forge.macro_discovery import MacroDiscoveryPolicy
from equinox_forge.runtime_compression import MacroPromotionPolicy, compile_runtime_compression
from equinox_forge.runtime_pack import compile_base_pack
from equinox_forge.runtime_query import benchmark_runtime_pack

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "examples" / "runtime_query_demo"
out.mkdir(parents=True, exist_ok=True)
db_path = out / "demo.sqlite"
pack_path = out / "demo.eqbase"
report_path = out / "benchmark.json"
for p in (db_path, pack_path, report_path):
    if p.exists(): p.unlink()


def add(db, nid, level=1, members=None):
    db.upsert_node(IRNode(
        nid, Modality.TEXT.value,
        NodeKind.COMPOSITE.value if members else NodeKind.SURFACE.value,
        level, nid, members or [], {},
    ))

with CanonicalDB(db_path) as c:
    for nid in ("a", "b", "c"):
        add(c, nid)
    src = SourceRef("teacher-v015-demo", "1", "runtime_benchmark_demo")
    for i in range(80):
        left, right, parent = f"left-{i:03d}", f"right-{i:03d}", f"parent-{i:03d}"
        add(c, left); add(c, right); add(c, parent, 2, [left, "a", "b", "c", right])
        c.add_evidence(RelationEvidence("a", right, RelationType.PREDICTION.value, 0.55, 0.90, src, {"i": i}))
    c.commit()
    d = MacroDiscoveryPolicy(
        min_pattern_size=2, max_pattern_size=3, min_occurrences=3, min_parent_structures=3,
        definition_overhead=1.0, min_net_savings=1.0, min_compression_ratio=0.0, prune_dominated=True,
    )
    p = MacroPromotionPolicy(
        min_realized_occurrences=3, min_realized_parent_structures=3,
        definition_overhead=1.0, min_realized_net_savings=1.0,
        min_realized_compression_ratio=0.0, max_promotions=8,
    )
    comp = compile_runtime_compression(c.db, d, p, persist=True, materialize=True)
    manifest = compile_base_pack(
        c.db, pack_path, pack_id="v015-runtime-query-demo", pack_version=15,
        compression_run_id=comp.compression_run_id, include_metadata=False,
        persist=False, verify_roundtrip=True,
    )

report = benchmark_runtime_pack(pack_path, sample_nodes=128, sample_macros=8, timing_repeat=25)
report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({
    "pack": str(pack_path),
    "file_bytes": manifest.file_bytes,
    "node_count": manifest.node_count,
    "relation_count": manifest.relation_count,
    "index": report.index_stats,
    "node_lookup": report.node_lookup,
    "surface_lookup": report.surface_lookup,
    "parent_lookup": report.parent_lookup,
    "relation_adjacency": report.relation_adjacency,
    "routing_summary": report.routing_summary,
    "report": str(report_path),
}, ensure_ascii=False, indent=2, sort_keys=True))
