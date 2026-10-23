from __future__ import annotations
import argparse, json
from pathlib import Path
from .io import load_document
from .validate import validate_document
from .database import CanonicalDB
from .compiler import aggregate_relations
from .export import export_runtime_snapshot
from .hf_adapter import load_adapter, validate_adapter, inspect_hf_model, build_extraction_plan, save_plan, auto_adapter_template, save_adapter
from .adapter_registry import choose_adapter

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
    av=sub.add_parser("validate-adapter"); av.add_argument("adapter")
    hi=sub.add_parser("inspect-hf"); hi.add_argument("model_dir")
    hp=sub.add_parser("plan-hf"); hp.add_argument("model_dir"); hp.add_argument("adapter"); hp.add_argument("--output")
    ha=sub.add_parser("auto-adapter"); ha.add_argument("model_dir"); ha.add_argument("output"); ha.add_argument("--adapter-id",default="generated-adapter")
    hd=sub.add_parser("detect-adapter"); hd.add_argument("model_dir"); hd.add_argument("--adapters",default="adapters")
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
    elif a.cmd=="validate-adapter":
        spec=load_adapter(a.adapter); errors=validate_adapter(spec)
        for x in errors: print("ERROR:",x)
        print(f"VALID={not errors} adapter={spec.adapter_id}")
        raise SystemExit(1 if errors else 0)
    elif a.cmd=="inspect-hf":
        print(json.dumps(inspect_hf_model(a.model_dir).to_dict(),ensure_ascii=False,indent=2,sort_keys=True))
    elif a.cmd=="plan-hf":
        manifest=inspect_hf_model(a.model_dir); spec=load_adapter(a.adapter); plan=build_extraction_plan(manifest,spec)
        if a.output: save_plan(plan,a.output)
        print(json.dumps(plan.to_dict(),ensure_ascii=False,indent=2,sort_keys=True))
        raise SystemExit(0 if plan.valid else 2)
    elif a.cmd=="auto-adapter":
        manifest=inspect_hf_model(a.model_dir); spec=auto_adapter_template(manifest,a.adapter_id); save_adapter(spec,a.output); print(a.output)
    elif a.cmd=="detect-adapter":
        result=choose_adapter(a.model_dir,a.adapters)
        if not result: print("NO_MATCH"); raise SystemExit(2)
        path,spec=result; print(json.dumps({"adapter":str(path),"adapter_id":spec.adapter_id},indent=2))

if __name__=="__main__": main()
