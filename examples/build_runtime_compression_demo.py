from pathlib import Path
import json

from equinox_forge.database import CanonicalDB
from equinox_forge.ir import IRNode, NodeKind, Modality
from equinox_forge.macro_discovery import MacroDiscoveryPolicy
from equinox_forge.runtime_compression import MacroPromotionPolicy, compile_runtime_compression

ROOT = Path(__file__).resolve().parents[1]
out_dir = ROOT / "examples" / "runtime_compression_demo"
out_dir.mkdir(parents=True, exist_ok=True)
db_path = out_dir / "compression.sqlite"
if db_path.exists():
    db_path.unlink()


def add(db, nid, members=None):
    db.upsert_node(IRNode(
        nid, Modality.TEXT.value,
        NodeKind.COMPOSITE.value if members else NodeKind.SURFACE.value,
        2 if members else 1, nid, members or [], {},
    ))


with CanonicalDB(db_path) as c:
    for nid in ("a","b","c","d","e","f","x","y","q","r","m","n","o","u","v","w"):
        add(c, nid)
    parents = {
        "p1":["a","b","c","d","e"],
        "p2":["a","b","c","d","f"],
        "p3":["a","b","c","x"],
        "p4":["y","a","b","c","q"],
        "p5":["r","b","c","d","y"],
        "r1":["m","n","o","u"],
        "r2":["m","n","o","v"],
        "r3":["w","m","n","o"],
    }
    for nid, members in parents.items():
        add(c, nid, members)
    c.commit()

    discovery = MacroDiscoveryPolicy(
        min_pattern_size=2, max_pattern_size=4,
        min_occurrences=2, min_parent_structures=2,
        definition_overhead=1.0, min_net_savings=1.0,
        min_compression_ratio=0.0, prune_dominated=False,
    )
    promotion = MacroPromotionPolicy(
        min_realized_occurrences=2,
        min_realized_parent_structures=2,
        definition_overhead=1.0,
        min_realized_net_savings=1.0,
        min_realized_compression_ratio=0.0,
    )
    report = compile_runtime_compression(c.db, discovery, promotion)
    payload = {"runtime_compression": report.to_dict(), "db_stats": c.stats()}
    report_path = out_dir / "runtime-compression.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({
        "report": str(report_path),
        "promoted": report.promoted_count,
        "baseline_refs": report.baseline_parent_refs,
        "encoded_total_cost": report.encoded_total_cost,
        "realized_net_savings": report.realized_net_savings,
        "realized_compression_ratio": report.realized_compression_ratio,
    }, indent=2, sort_keys=True))
