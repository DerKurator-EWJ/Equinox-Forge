from __future__ import annotations
import argparse, json
from pathlib import Path
from .io import load_document
from .validate import validate_document
from .database import CanonicalDB
from .compiler import aggregate_relations
from .export import export_runtime_snapshot

def ingest(db_path: str, doc_path: str):
    doc = load_document(doc_path)
    issues = validate_document(doc)
    errors = [x for x in issues if x.severity == "error"]
    if errors:
        for x in issues: print(f"{x.severity.upper()}: {x.message}")
        raise SystemExit(2)
    with CanonicalDB(db_path) as c:
        for n in sorted(doc.nodes,key=lambda n:(n.level,n.node_id)): c.upsert_node(n)
        for e in doc.evidence: c.add_evidence(e)
        c.commit(); print(json.dumps(c.stats(),indent=2))

def main():
    p=argparse.ArgumentParser(prog="eqforge")
    sub=p.add_subparsers(dest="cmd",required=True)
    v=sub.add_parser("validate"); v.add_argument("document")
    i=sub.add_parser("ingest"); i.add_argument("db"); i.add_argument("document")
    s=sub.add_parser("stats"); s.add_argument("db")
    c=sub.add_parser("compile"); c.add_argument("db")
    e=sub.add_parser("export"); e.add_argument("db"); e.add_argument("output"); e.add_argument("--pack-id",default="forge-preview"); e.add_argument("--version",type=int,default=1)
    a=p.parse_args()
    if a.cmd=="validate":
        doc=load_document(a.document); issues=validate_document(doc)
        for x in issues: print(f"{x.severity.upper()}: {x.message}")
        print(f"VALID={not any(x.severity=='error' for x in issues)} nodes={len(doc.nodes)} evidence={len(doc.evidence)}")
        raise SystemExit(1 if any(x.severity=='error' for x in issues) else 0)
    if a.cmd=="ingest": ingest(a.db,a.document)
    elif a.cmd=="stats":
        with CanonicalDB(a.db) as db: print(json.dumps(db.stats(),indent=2))
    elif a.cmd=="compile":
        with CanonicalDB(a.db) as db:
            rel=aggregate_relations(db.db); print(json.dumps([r.__dict__ for r in rel],ensure_ascii=False,indent=2))
    elif a.cmd=="export":
        with CanonicalDB(a.db) as db: export_runtime_snapshot(db.db,a.output,a.pack_id,a.version)
        print(a.output)

if __name__=="__main__": main()
