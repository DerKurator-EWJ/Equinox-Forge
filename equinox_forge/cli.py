from __future__ import annotations
import argparse, json
from pathlib import Path
from .io import load_document, save_document
from .validate import validate_document
from .database import CanonicalDB
from .compiler import aggregate_relations
from .export import export_runtime_snapshot
from .hf_adapter import load_adapter, validate_adapter, inspect_hf_model, build_extraction_plan, save_plan, auto_adapter_template, save_adapter
from .adapter_registry import choose_adapter
from .text_teacher import TextExtractionConfig, extract_text_teacher
from .language_evidence import LanguageEvidenceConfig, build_controlled_language_evidence, load_text_inputs
from .teacher_behavior import BehaviourProbeConfig, TransformersCausalLMBackend, extract_teacher_behaviour, load_prompts
from .hidden_state import HiddenStateConfig, TransformersHiddenStateBackend, extract_contextual_hidden_evidence, load_probe_dataset
from .sense_compiler import SenseCompilePolicy, FusionWeights, compile_provisional_senses, find_text_surface_id


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


def _extract_text(args) -> int:
    manifest = inspect_hf_model(args.model_dir)
    spec = load_adapter(args.adapter)
    cfg = TextExtractionConfig(
        max_tokens=args.max_tokens,
        start_token_id=args.start_token_id,
        top_k=args.top_k,
        min_similarity=args.min_similarity,
        batch_size=args.batch_size,
        max_surface_chars=args.max_surface_chars,
        include_leading_space=args.include_leading_space,
        include_punctuation_only=args.include_punctuation_only,
        include_numeric_only=not args.exclude_numeric_only,
        evidence_confidence=args.evidence_confidence,
    )
    doc, report, surface_meta = extract_text_teacher(
        manifest, spec, args.source_id, args.source_version, cfg
    )
    issues = validate_document(doc)
    errors = [x for x in issues if x.severity == "error"]
    if errors:
        for x in issues: print(f"{x.severity.upper()}: {x.message}")
        return 2
    save_document(doc, args.output)
    report_path = Path(args.report) if args.report else Path(args.output).with_suffix(".report.json")
    report_path.write_text(json.dumps(report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    db_stats = None
    if args.db:
        plan = build_extraction_plan(manifest, spec)
        with CanonicalDB(args.db) as db:
            db.register_source_model(
                args.source_id, args.source_version, spec.adapter_id, plan.adapter_hash,
                manifest.model_type, manifest.to_dict(),
            )
            for n in sorted(doc.nodes,key=lambda n:(n.level,n.node_id)):
                db.upsert_node(n)
            for e in doc.evidence:
                db.add_evidence(e)
            # Keep teacher token IDs as provenance aliases; several token IDs may map
            # to the same canonical surface and therefore the same Equinox node.
            node_by_surface = {n.surface:n for n in doc.nodes if n.kind == "surface" and n.surface is not None}
            for surface, entries in surface_meta.items():
                node = node_by_surface[surface]
                for entry in entries:
                    db.alias(
                        args.source_id,args.source_version,f"token:{entry.token_id}",node.node_id,
                        {"raw_token":entry.raw_token,"surface":entry.surface},
                    )
            db.commit()
            db_stats = db.stats()
    result = {"output":str(Path(args.output)),"report":str(report_path),"extraction":report.to_dict()}
    if db_stats is not None: result["db_stats"] = db_stats
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0



def _extract_corpus(args) -> int:
    cfg = LanguageEvidenceConfig(
        lowercase=args.lowercase,
        include_punctuation=args.include_punctuation,
        max_context=args.max_context,
        min_transition_count=args.min_transition_count,
        min_prediction_count=args.min_prediction_count,
        min_phrase_count=args.min_phrase_count,
        max_phrase_words=args.max_phrase_words,
        max_substitutions_per_word=args.max_substitutions_per_word,
        min_substitution_score=args.min_substitution_score,
        evidence_confidence=args.evidence_confidence,
    )
    texts = load_text_inputs(args.inputs)
    doc, report = build_controlled_language_evidence(texts, args.source_id, args.source_version, cfg)
    issues = validate_document(doc)
    errors = [x for x in issues if x.severity == "error"]
    if errors:
        for x in issues: print(f"{x.severity.upper()}: {x.message}")
        return 2
    save_document(doc, args.output)
    report_path = Path(args.report) if args.report else Path(args.output).with_suffix(".report.json")
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    db_stats = None
    if args.db:
        with CanonicalDB(args.db) as db:
            for n in doc.nodes: db.upsert_node(n)
            for e in doc.evidence: db.add_evidence(e)
            db.commit()
            db_stats = db.stats()
    result = {"output":str(Path(args.output)), "report":str(report_path), "extraction":report.to_dict()}
    if db_stats is not None: result["db_stats"] = db_stats
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _probe_teacher(args) -> int:
    cfg = BehaviourProbeConfig(
        top_k=args.top_k,
        temperature=args.temperature,
        min_probability=args.min_probability,
        max_surface_chars=args.max_surface_chars,
        evidence_confidence=args.evidence_confidence,
        strip_leading_space=not args.keep_leading_space,
        include_punctuation_only=args.include_punctuation_only,
        include_numeric_only=not args.exclude_numeric_only,
        max_prompt_words=args.max_prompt_words,
    )
    prompts = load_prompts(args.prompts)
    try:
        backend = TransformersCausalLMBackend(
            args.model_dir,
            device=args.device,
            trust_remote_code=args.trust_remote_code,
            dtype=args.dtype,
        )
    except Exception as exc:
        print(f"ERROR: unable to initialize causal teacher backend: {exc}")
        return 3
    doc, report, _ = extract_teacher_behaviour(
        backend, prompts, args.source_id, args.source_version, cfg
    )
    issues = validate_document(doc)
    errors = [x for x in issues if x.severity == "error"]
    if errors:
        for x in issues: print(f"{x.severity.upper()}: {x.message}")
        return 2
    save_document(doc, args.output)
    report_path = Path(args.report) if args.report else Path(args.output).with_suffix(".report.json")
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    db_stats = None
    if args.db:
        manifest = inspect_hf_model(args.model_dir)
        spec = load_adapter(args.adapter) if args.adapter else None
        with CanonicalDB(args.db) as db:
            if spec is not None:
                plan = build_extraction_plan(manifest, spec)
                db.register_source_model(
                    args.source_id, args.source_version, spec.adapter_id, plan.adapter_hash,
                    manifest.model_type, {**manifest.to_dict(), "behaviour_backend": backend.manifest()},
                )
            for n in sorted(doc.nodes, key=lambda n:(n.level,n.node_id)):
                db.upsert_node(n)
            for e in doc.evidence:
                db.add_evidence(e)
            db.commit()
            db_stats = db.stats()
    result = {
        "output": str(Path(args.output)),
        "report": str(report_path),
        "backend": backend.manifest(),
        "extraction": report.to_dict(),
    }
    if db_stats is not None: result["db_stats"] = db_stats
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _probe_hidden(args) -> int:
    cfg = HiddenStateConfig(
        layers=tuple(args.layers),
        pooling=args.pooling,
        top_k=args.top_k,
        min_cosine=args.min_cosine,
        evidence_confidence=args.evidence_confidence,
        max_context_words=args.max_context_words,
        include_cross_surface=args.include_cross_surface,
        keep_vectors_in_report=args.keep_vectors_in_report,
    )
    try:
        probes = load_probe_dataset(args.datasets)
        backend = TransformersHiddenStateBackend(
            args.model_dir,
            device=args.device,
            trust_remote_code=args.trust_remote_code,
            dtype=args.dtype,
        )
    except Exception as exc:
        print(f"ERROR: unable to initialize contextual hidden-state probe: {exc}")
        return 3
    doc, report, records = extract_contextual_hidden_evidence(
        backend, probes, args.source_id, args.source_version, cfg
    )
    issues = validate_document(doc)
    errors = [x for x in issues if x.severity == "error"]
    if errors:
        for x in issues: print(f"{x.severity.upper()}: {x.message}")
        return 2
    save_document(doc, args.output)
    report_path = Path(args.report) if args.report else Path(args.output).with_suffix(".report.json")
    payload = {**report.to_dict(), "records": [r.__dict__ for r in records]}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    db_stats = None
    if args.db:
        manifest = inspect_hf_model(args.model_dir)
        spec = load_adapter(args.adapter) if args.adapter else None
        with CanonicalDB(args.db) as db:
            if spec is not None:
                plan = build_extraction_plan(manifest, spec)
                db.register_source_model(
                    args.source_id, args.source_version, spec.adapter_id, plan.adapter_hash,
                    manifest.model_type, {**manifest.to_dict(), "hidden_state_backend": backend.manifest()},
                )
            for n in sorted(doc.nodes, key=lambda n:(n.level,n.node_id)):
                db.upsert_node(n)
            for e in doc.evidence:
                db.add_evidence(e)
            db.commit()
            db_stats = db.stats()
    result = {
        "output": str(Path(args.output)),
        "report": str(report_path),
        "backend": backend.manifest(),
        "extraction": report.to_dict(),
    }
    if db_stats is not None: result["db_stats"] = db_stats
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0



def _compile_senses(args) -> int:
    weights = FusionWeights(
        hidden_similarity=args.w_hidden, lexical_overlap=args.w_lexical,
        semantic_similarity=args.w_semantic, substitution=args.w_substitution,
        transition=args.w_transition, prediction_signature=args.w_prediction,
    )
    policy = SenseCompilePolicy(
        threshold=args.threshold, min_channels=args.min_channels,
        min_contexts=args.min_contexts, include_singletons=args.include_singletons,
        weights=weights,
    )
    with CanonicalDB(args.db) as c:
        try:
            target_id = args.target_id or find_text_surface_id(c.db, args.surface)
            doc, report = compile_provisional_senses(c.db, target_id, policy)
        except Exception as exc:
            print(f"ERROR: sense compile failed: {exc}")
            return 3
        issues = validate_document(doc)
        errors = [x for x in issues if x.severity == "error"]
        if errors:
            for x in issues: print(f"{x.severity.upper()}: {x.message}")
            return 2
        save_document(doc,args.output)
        report_path=Path(args.report) if args.report else Path(args.output).with_suffix('.report.json')
        report_path.write_text(json.dumps(report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        if args.ingest_derived:
            for n in doc.nodes: c.upsert_node(n)
            for e in doc.evidence: c.add_evidence(e)
            c.commit()
        result={"output":str(Path(args.output)),"report":str(report_path),"sense_compile":report.to_dict()}
        if args.ingest_derived: result["db_stats"]=c.stats()
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0

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

    tx=sub.add_parser("extract-text", help="extract bounded static text evidence from a local HF Safetensors teacher")
    tx.add_argument("model_dir")
    tx.add_argument("adapter")
    tx.add_argument("output", help="output Canonical IR JSON")
    tx.add_argument("--source-id",required=True)
    tx.add_argument("--source-version",default="local")
    tx.add_argument("--report")
    tx.add_argument("--db", help="optional canonical SQLite DB to ingest atomically after extraction")
    tx.add_argument("--max-tokens",type=int,default=4096)
    tx.add_argument("--start-token-id",type=int,default=0)
    tx.add_argument("--top-k",type=int,default=8)
    tx.add_argument("--min-similarity",type=float,default=0.20)
    tx.add_argument("--batch-size",type=int,default=256)
    tx.add_argument("--max-surface-chars",type=int,default=64)
    tx.add_argument("--include-leading-space",action="store_true")
    tx.add_argument("--include-punctuation-only",action="store_true")
    tx.add_argument("--exclude-numeric-only",action="store_true")
    tx.add_argument("--evidence-confidence",type=float,default=0.55, help="trust in static embedding-neighbour evidence; separate from cosine score")


    lc=sub.add_parser("extract-corpus", help="extract directed controlled-language evidence from UTF-8 text files")
    lc.add_argument("inputs", nargs="+", help="one or more UTF-8 text files")
    lc.add_argument("output", help="output Canonical IR JSON")
    lc.add_argument("--source-id", required=True)
    lc.add_argument("--source-version", default="local")
    lc.add_argument("--report")
    lc.add_argument("--db", help="optional canonical SQLite DB")
    lc.add_argument("--lowercase", action="store_true")
    lc.add_argument("--include-punctuation", action="store_true")
    lc.add_argument("--max-context", type=int, default=3)
    lc.add_argument("--min-transition-count", type=int, default=1)
    lc.add_argument("--min-prediction-count", type=int, default=1)
    lc.add_argument("--min-phrase-count", type=int, default=2)
    lc.add_argument("--max-phrase-words", type=int, default=4)
    lc.add_argument("--max-substitutions-per-word", type=int, default=8)
    lc.add_argument("--min-substitution-score", type=float, default=0.10)
    lc.add_argument("--evidence-confidence", type=float, default=0.80)

    bp=sub.add_parser("probe-teacher", help="execute a local causal HF teacher and record next-token behaviour evidence")
    bp.add_argument("model_dir")
    bp.add_argument("prompts", nargs="+", help="UTF-8 files containing one controlled prompt per line")
    bp.add_argument("output", help="output Canonical IR JSON")
    bp.add_argument("--source-id", required=True)
    bp.add_argument("--source-version", default="local")
    bp.add_argument("--adapter", help="optional Forge adapter used for model registration/provenance")
    bp.add_argument("--report")
    bp.add_argument("--db", help="optional canonical SQLite DB")
    bp.add_argument("--top-k", type=int, default=8)
    bp.add_argument("--temperature", type=float, default=1.0)
    bp.add_argument("--min-probability", type=float, default=0.001)
    bp.add_argument("--max-surface-chars", type=int, default=64)
    bp.add_argument("--max-prompt-words", type=int, default=64)
    bp.add_argument("--evidence-confidence", type=float, default=0.95)
    bp.add_argument("--keep-leading-space", action="store_true")
    bp.add_argument("--include-punctuation-only", action="store_true")
    bp.add_argument("--exclude-numeric-only", action="store_true")
    bp.add_argument("--device", default="cpu")
    bp.add_argument("--dtype", default="auto")
    bp.add_argument("--trust-remote-code", action="store_true")

    hs=sub.add_parser("probe-hidden", help="extract contextual hidden-state evidence from a local HF teacher")
    hs.add_argument("model_dir")
    hs.add_argument("datasets", nargs="+", help="JSONL contextual probe datasets")
    hs.add_argument("output", help="output Canonical IR JSON")
    hs.add_argument("--source-id", required=True)
    hs.add_argument("--source-version", default="local")
    hs.add_argument("--adapter", help="optional Forge adapter for registered model provenance")
    hs.add_argument("--report")
    hs.add_argument("--db", help="optional canonical SQLite DB")
    hs.add_argument("--layers", type=int, nargs="+", default=[-1])
    hs.add_argument("--pooling", choices=["mean","first","last"], default="mean")
    hs.add_argument("--top-k", type=int, default=6)
    hs.add_argument("--min-cosine", type=float, default=0.25)
    hs.add_argument("--evidence-confidence", type=float, default=0.85)
    hs.add_argument("--max-context-words", type=int, default=96)
    hs.add_argument("--include-cross-surface", action="store_true")
    hs.add_argument("--keep-vectors-in-report", action="store_true")
    hs.add_argument("--device", default="cpu")
    hs.add_argument("--dtype", default="auto")
    hs.add_argument("--trust-remote-code", action="store_true")

    sc=sub.add_parser("compile-senses", help="fuse multi-channel evidence into provisional text sense concepts")
    sc.add_argument("db", help="canonical SQLite DB")
    sc.add_argument("output", help="derived Canonical IR JSON")
    tg=sc.add_mutually_exclusive_group(required=True)
    tg.add_argument("--surface", help="exact canonical text surface, e.g. Bank")
    tg.add_argument("--target-id", help="canonical surface node id")
    sc.add_argument("--report")
    sc.add_argument("--threshold",type=float,default=0.62)
    sc.add_argument("--min-channels",type=int,default=2)
    sc.add_argument("--min-contexts",type=int,default=2)
    sc.add_argument("--include-singletons",action="store_true")
    sc.add_argument("--ingest-derived",action="store_true",help="write provisional concepts/evidence back into the canonical DB")
    sc.add_argument("--w-hidden",type=float,default=0.55)
    sc.add_argument("--w-lexical",type=float,default=0.05)
    sc.add_argument("--w-semantic",type=float,default=0.15)
    sc.add_argument("--w-substitution",type=float,default=0.10)
    sc.add_argument("--w-transition",type=float,default=0.05)
    sc.add_argument("--w-prediction",type=float,default=0.10)

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
    elif a.cmd=="extract-text":
        raise SystemExit(_extract_text(a))
    elif a.cmd=="extract-corpus":
        raise SystemExit(_extract_corpus(a))
    elif a.cmd=="probe-teacher":
        raise SystemExit(_probe_teacher(a))
    elif a.cmd=="probe-hidden":
        raise SystemExit(_probe_hidden(a))
    elif a.cmd=="compile-senses":
        raise SystemExit(_compile_senses(a))

if __name__=="__main__": main()
