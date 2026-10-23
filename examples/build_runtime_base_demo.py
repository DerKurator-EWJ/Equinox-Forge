from pathlib import Path
import json

from equinox_forge.database import CanonicalDB
from equinox_forge.runtime_pack import compile_base_pack, verify_base_pack

ROOT = Path(__file__).resolve().parents[1]
demo_dir = ROOT / "examples" / "runtime_compression_demo"
db_path = demo_dir / "compression.sqlite"
if not db_path.exists():
    raise SystemExit("Run examples/build_runtime_compression_demo.py first")

pack_path = demo_dir / "demo.eqbase"
report_path = demo_dir / "base-pack-report.json"
with CanonicalDB(db_path) as c:
    manifest = compile_base_pack(
        c.db, pack_path, pack_id="demo-base", pack_version=1,
        include_metadata=True, persist=True, verify_roundtrip=True,
    )
    verified = verify_base_pack(pack_path)
    payload = {"runtime_base_pack": manifest.to_dict(), "verification": verified, "db_stats": c.stats()}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({
        "pack": str(pack_path),
        "report": str(report_path),
        "file_bytes": manifest.file_bytes,
        "nodes": manifest.node_count,
        "relations": manifest.relation_count,
        "index_bytes": manifest.index_bytes,
        "roundtrip_valid": manifest.roundtrip_valid,
        "payload_sha256": manifest.payload_sha256,
    }, indent=2, sort_keys=True))
