from __future__ import annotations
import argparse, json
from dataclasses import asdict
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
from .consensus import ConsensusPolicy, track_hypothesis_run, list_hypothesis_states
from .rebuild import set_source_policy, clear_source_policy, replace_source_version, list_source_policies, rebuild_senses
from .dependency import ArtifactRef, impact_from_roots, source_roots, refresh_dependency_index, register_manual_dependency
from .incremental import incremental_rebuild_from_sources
from .artifact_store import list_artifacts
from .macro_builder import MacroCompilePolicy, rebuild_macro
from .macro_discovery import MacroDiscoveryPolicy, discover_and_optionally_materialize
from .runtime_compression import MacroPromotionPolicy, compile_runtime_compression
from .runtime_pack import compile_base_pack, load_base_pack, verify_base_pack
from .runtime_query import query_runtime_pack, benchmark_runtime_pack


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
            consensus_report = None
            if args.track_stability:
                consensus_policy = ConsensusPolicy(
                    source_vote_threshold=args.source_vote_threshold,
                    source_vote_margin=args.source_vote_margin,
                    min_observed_pairs=args.min_observed_pairs,
                    stable_min_sources=args.stable_min_sources,
                    stable_min_runs=args.stable_min_runs,
                    stable_consensus=args.stable_consensus,
                    quarantine_conflicts=args.quarantine_conflicts,
                    quarantine_after_misses=args.quarantine_after_misses,
                )
                consensus_report = track_hypothesis_run(c.db, doc, target_id, policy, consensus_policy)
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
        consensus_path = None
        if consensus_report is not None:
            consensus_path = Path(args.consensus_report) if args.consensus_report else Path(args.output).with_suffix('.consensus.json')
            consensus_path.write_text(json.dumps(consensus_report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        if args.ingest_derived:
            for n in doc.nodes: c.upsert_node(n)
            for e in doc.evidence: c.add_evidence(e)
            c.commit()
        result={"output":str(Path(args.output)),"report":str(report_path),"sense_compile":report.to_dict()}
        if consensus_report is not None:
            result["consensus_report"] = str(consensus_path)
            result["consensus"] = consensus_report.to_dict()
        if args.ingest_derived or args.track_stability: result["db_stats"]=c.stats()
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


def _source_policy_set(args) -> int:
    enabled = not args.disable
    with CanonicalDB(args.db) as c:
        policy = set_source_policy(
            c.db, args.source_id, args.source_version,
            enabled=enabled, trust_weight=args.weight,
            note=args.note or "", metadata={"set_via": "eqforge-v0.11"},
        )
        print(json.dumps({"policy": {
            "source_id": policy.source_id,
            "source_version": policy.source_version,
            "enabled": policy.enabled,
            "trust_weight": policy.trust_weight,
            "note": policy.note,
        }, "db_stats": c.stats()}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _source_policy_clear(args) -> int:
    with CanonicalDB(args.db) as c:
        clear_source_policy(c.db, args.source_id, args.source_version)
        print(json.dumps({"cleared": f"{args.source_id}@{args.source_version}", "policies": list_source_policies(c.db)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _source_policy_replace(args) -> int:
    with CanonicalDB(args.db) as c:
        old, new = replace_source_version(c.db, args.source_id, args.old_version, args.new_version, new_trust_weight=args.weight, note=args.note or "")
        print(json.dumps({"disabled": f"{old.source_id}@{old.source_version}", "enabled": f"{new.source_id}@{new.source_version}", "new_weight": new.trust_weight, "policies": list_source_policies(c.db)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _source_policy_list(args) -> int:
    with CanonicalDB(args.db) as c:
        print(json.dumps(list_source_policies(c.db, include_defaults=not args.explicit_only), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _rebuild_senses(args) -> int:
    weights = FusionWeights(
        hidden_similarity=args.w_hidden, lexical_overlap=args.w_lexical,
        semantic_similarity=args.w_semantic, substitution=args.w_substitution,
        transition=args.w_transition, prediction_signature=args.w_prediction,
    )
    sense_policy = SenseCompilePolicy(
        threshold=args.threshold, min_channels=args.min_channels,
        min_contexts=args.min_contexts, include_singletons=args.include_singletons,
        weights=weights,
    )
    consensus_policy = ConsensusPolicy(
        source_vote_threshold=args.source_vote_threshold,
        source_vote_margin=args.source_vote_margin,
        min_observed_pairs=args.min_observed_pairs,
        stable_min_sources=args.stable_min_sources,
        stable_min_runs=args.stable_min_runs,
        stable_consensus=args.stable_consensus,
        stable_min_support_weight=args.stable_min_support_weight,
        quarantine_conflicts=args.quarantine_conflicts,
        quarantine_conflict_weight=args.quarantine_conflict_weight,
        quarantine_after_misses=args.quarantine_after_misses,
    )
    with CanonicalDB(args.db) as c:
        try:
            target_id = args.target_id or find_text_surface_id(c.db, args.surface)
            doc, report = rebuild_senses(
                c.db, target_id, sense_policy, consensus_policy,
                track_stability=not args.no_track_stability,
            )
        except Exception as exc:
            print(f"ERROR: rebuild failed: {exc}")
            return 3
        issues = validate_document(doc)
        errors = [x for x in issues if x.severity == "error"]
        if errors:
            for x in issues: print(f"{x.severity.upper()}: {x.message}")
            return 2
        save_document(doc, args.output)
        report_path = Path(args.report) if args.report else Path(args.output).with_suffix('.rebuild.json')
        report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        if args.ingest_derived:
            for n in doc.nodes: c.upsert_node(n)
            for e in doc.evidence: c.add_evidence(e)
            c.commit()
        print(json.dumps({
            "output": str(Path(args.output)),
            "report": str(report_path),
            "rebuild": report.to_dict(),
            "db_stats": c.stats(),
        }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

def _dependency_impact(args) -> int:
    with CanonicalDB(args.db) as c:
        try:
            roots = source_roots(args.changed_source) + [ArtifactRef("node", n) for n in (args.changed_node or [])]
            stats = refresh_dependency_index(c.db)
            impact = impact_from_roots(c.db, roots, refresh=False)
        except Exception as exc:
            print(f"ERROR: dependency impact failed: {exc}")
            return 3
        print(json.dumps({"dependency_stats": stats, "impact": impact.to_dict()}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _incremental_rebuild(args) -> int:
    with CanonicalDB(args.db) as c:
        try:
            report = incremental_rebuild_from_sources(
                c.db, args.changed_source, output_dir=args.output_dir,
                dry_run=args.dry_run, ingest_derived=args.ingest_derived,
            )
        except Exception as exc:
            print(f"ERROR: incremental rebuild failed: {exc}")
            return 3
        report_path = Path(args.report) if args.report else None
        if report_path:
            report_path.write_text(json.dumps(report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"incremental_rebuild": report.to_dict(), "report": None if report_path is None else str(report_path), "db_stats": c.stats()}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_macro(args) -> int:
    policy = MacroCompilePolicy(
        input_build_targets=list(args.input_target or []),
        input_nodes=list(args.input_node or []),
        allowed_statuses=list(args.allowed_status or ["stable", "active"]),
        min_members=args.min_members,
        ordered_members=args.ordered_members,
        modality=args.modality,
        kind=args.kind,
        surface=args.surface,
    )
    with CanonicalDB(args.db) as c:
        try:
            doc, report = rebuild_macro(c.db, args.target_id, policy, record_store=True)
        except Exception as exc:
            print(f"ERROR: macro build failed: {exc}")
            return 3
        issues = validate_document(doc) if doc.nodes else []
        errors = [x for x in issues if x.severity == "error"]
        if errors:
            for x in issues: print(f"{x.severity.upper()}: {x.message}")
            return 2
        save_document(doc, args.output)
        report_path = Path(args.report) if args.report else Path(args.output).with_suffix('.macro.json')
        report_path.write_text(json.dumps(report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if args.ingest_derived:
            for n in doc.nodes: c.upsert_node(n)
            for e in doc.evidence: c.add_evidence(e)
            c.commit()
        print(json.dumps({
            "output": str(Path(args.output)), "report": str(report_path),
            "macro": report.to_dict(), "db_stats": c.stats(),
        }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0



def _discover_macros(args) -> int:
    policy = MacroDiscoveryPolicy(
        min_pattern_size=args.min_pattern_size,
        max_pattern_size=args.max_pattern_size,
        min_occurrences=args.min_occurrences,
        min_parent_structures=args.min_parent_structures,
        definition_overhead=args.definition_overhead,
        min_net_savings=args.min_net_savings,
        min_compression_ratio=args.min_compression_ratio,
        max_candidates=args.max_candidates,
        include_canonical=not args.no_canonical,
        include_derived=not args.no_derived,
        derived_statuses=list(args.derived_status or ["stable","active"]),
        prune_dominated=not args.no_prune_dominated,
    )
    with CanonicalDB(args.db) as c:
        try:
            report, run_id = discover_and_optionally_materialize(
                c.db, policy, materialize=args.materialize,
                materialize_limit=args.materialize_limit, persist=not args.no_persist,
            )
        except Exception as exc:
            print(f"ERROR: macro discovery failed: {exc}")
            return 3
        payload={"discovery_run_id":run_id,"macro_discovery":report.to_dict(),"db_stats":c.stats()}
        if args.report:
            Path(args.report).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


def _compress_runtime(args) -> int:
    discovery_policy = MacroDiscoveryPolicy(
        min_pattern_size=args.min_pattern_size,
        max_pattern_size=args.max_pattern_size,
        min_occurrences=args.min_occurrences,
        min_parent_structures=args.min_parent_structures,
        definition_overhead=args.discovery_definition_overhead,
        min_net_savings=args.discovery_min_net_savings,
        min_compression_ratio=args.discovery_min_compression_ratio,
        max_candidates=args.max_candidates,
        include_canonical=not args.no_canonical,
        include_derived=not args.no_derived,
        derived_statuses=list(args.derived_status or ["stable","active"]),
        prune_dominated=not args.no_prune_dominated,
    )
    promotion_policy = MacroPromotionPolicy(
        min_realized_occurrences=args.min_realized_occurrences,
        min_realized_parent_structures=args.min_realized_parent_structures,
        definition_overhead=args.definition_overhead,
        min_realized_net_savings=args.min_realized_net_savings,
        min_realized_compression_ratio=args.min_realized_compression_ratio,
        max_promotions=args.max_promotions,
    )
    with CanonicalDB(args.db) as c:
        try:
            report = compile_runtime_compression(
                c.db, discovery_policy, promotion_policy,
                persist=not args.no_persist, materialize=not args.plan_only,
            )
        except Exception as exc:
            print(f"ERROR: runtime compression failed: {exc}")
            return 3
        payload={"runtime_compression":report.to_dict(),"db_stats":c.stats()}
        if args.output:
            Path(args.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0

def _compile_base(args) -> int:
    with CanonicalDB(args.db) as c:
        try:
            manifest = compile_base_pack(
                c.db, args.output,
                pack_id=args.pack_id, pack_version=args.pack_version,
                compression_run_id=args.compression_run_id,
                include_metadata=not args.strip_metadata,
                persist=not args.no_persist,
                verify_roundtrip=not args.no_verify,
            )
        except Exception as exc:
            print(f"ERROR: BASE pack compilation failed: {exc}")
            return 3
        payload = {"runtime_base_pack": manifest.to_dict(), "db_stats": c.stats()}
        if args.report:
            Path(args.report).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


def _inspect_base(args) -> int:
    try:
        loaded = load_base_pack(args.pack, verify_hash=not args.no_verify)
    except Exception as exc:
        print(f"ERROR: BASE pack load failed: {exc}")
        return 3
    payload = dict(loaded.manifest)
    payload["sample_nodes"] = [asdict(n) for n in loaded.nodes[:args.sample_nodes]]
    payload["sample_relations"] = [r.__dict__ for r in loaded.relations[:args.sample_relations]]
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


def _verify_base(args) -> int:
    try:
        report = verify_base_pack(args.pack)
    except Exception as exc:
        print(f"ERROR: BASE pack verify failed: {exc}")
        return 3
    print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if report.get("valid") else 2



def _query_base(args) -> int:
    try:
        payload = query_runtime_pack(
            args.pack, node_id=args.node, surface=args.surface, parents_of=args.parents,
            expand=args.expand, relations_from=args.relations_from, relations_to=args.relations_to,
            relation_type=args.relation_type, timing_repeat=args.timing_repeat,
        )
    except Exception as exc:
        print(f"ERROR: BASE query failed: {exc}")
        return 3
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


def _benchmark_base(args) -> int:
    try:
        report = benchmark_runtime_pack(
            args.pack, sample_nodes=args.sample_nodes, sample_macros=args.sample_macros,
            timing_repeat=args.timing_repeat, max_expanded_symbols=args.max_expanded_symbols,
        )
        payload = report.to_dict()
    except Exception as exc:
        print(f"ERROR: BASE benchmark failed: {exc}")
        return 3
    if args.output:
        Path(args.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0

def _list_artifacts(args) -> int:
    with CanonicalDB(args.db) as c:
        rows = list_artifacts(c.db, build_target_id=args.target_id, statuses=args.status or None)
        print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
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
    sc.add_argument("--track-stability",action="store_true",help="persist cross-source consensus and rebuild stability state")
    sc.add_argument("--consensus-report")
    sc.add_argument("--source-vote-threshold",type=float,default=0.58)
    sc.add_argument("--source-vote-margin",type=float,default=0.08)
    sc.add_argument("--min-observed-pairs",type=int,default=1)
    sc.add_argument("--stable-min-sources",type=int,default=2)
    sc.add_argument("--stable-min-runs",type=int,default=2)
    sc.add_argument("--stable-consensus",type=float,default=0.75)
    sc.add_argument("--quarantine-conflicts",type=int,default=2)
    sc.add_argument("--quarantine-after-misses",type=int,default=2)

    hl=sub.add_parser("hypotheses", help="list persisted derived-hypothesis lifecycle states")
    hl.add_argument("db")
    hl.add_argument("--target-id")

    di=sub.add_parser("dependency-impact", help="show transitive invalidation from changed sources/nodes")
    di.add_argument("db")
    di.add_argument("--changed-source", action="append", default=[], help="SOURCE@VERSION; repeatable")
    di.add_argument("--changed-node", action="append", default=[], help="canonical node id; repeatable")

    irb=sub.add_parser("incremental-rebuild", help="rebuild only registered compiler targets affected by source changes")
    irb.add_argument("db")
    irb.add_argument("--changed-source", action="append", required=True, help="SOURCE@VERSION; repeatable")
    irb.add_argument("--output-dir")
    irb.add_argument("--report")
    irb.add_argument("--dry-run", action="store_true")
    irb.add_argument("--ingest-derived", action="store_true")

    bm=sub.add_parser("build-macro", help="build a higher Equinox macro from current derived artifacts/nodes")
    bm.add_argument("db"); bm.add_argument("output"); bm.add_argument("--target-id", required=True)
    bm.add_argument("--input-target", action="append", default=[], help="upstream build target; repeatable")
    bm.add_argument("--input-node", action="append", default=[], help="explicit canonical/derived node; repeatable")
    bm.add_argument("--allowed-status", action="append", default=[], help="eligible artifact status; repeatable")
    bm.add_argument("--min-members", type=int, default=2)
    bm.add_argument("--ordered-members", action="store_true")
    bm.add_argument("--modality")
    bm.add_argument("--kind", default="composite")
    bm.add_argument("--surface")
    bm.add_argument("--report")
    bm.add_argument("--ingest-derived", action="store_true")

    dm=sub.add_parser("discover-macros", help="discover repeated ordered substructures and score potential structural compression")
    dm.add_argument("db")
    dm.add_argument("--report")
    dm.add_argument("--min-pattern-size",type=int,default=2)
    dm.add_argument("--max-pattern-size",type=int,default=6)
    dm.add_argument("--min-occurrences",type=int,default=2)
    dm.add_argument("--min-parent-structures",type=int,default=2)
    dm.add_argument("--definition-overhead",type=float,default=1.0)
    dm.add_argument("--min-net-savings",type=float,default=1.0)
    dm.add_argument("--min-compression-ratio",type=float,default=0.05)
    dm.add_argument("--max-candidates",type=int,default=100)
    dm.add_argument("--derived-status",action="append",default=[])
    dm.add_argument("--no-canonical",action="store_true")
    dm.add_argument("--no-derived",action="store_true")
    dm.add_argument("--no-prune-dominated",action="store_true")
    dm.add_argument("--materialize",action="store_true",help="build top eligible candidates as derived macro artifacts")
    dm.add_argument("--materialize-limit",type=int,default=10)
    dm.add_argument("--no-persist",action="store_true")

    cr=sub.add_parser("compress-runtime", help="promote compatible discovered macros and compile a realized parent-rewrite runtime view")
    cr.add_argument("db")
    cr.add_argument("--output", help="optional JSON compression plan/report")
    cr.add_argument("--min-pattern-size",type=int,default=2)
    cr.add_argument("--max-pattern-size",type=int,default=6)
    cr.add_argument("--min-occurrences",type=int,default=2)
    cr.add_argument("--min-parent-structures",type=int,default=2)
    cr.add_argument("--discovery-definition-overhead",type=float,default=1.0)
    cr.add_argument("--discovery-min-net-savings",type=float,default=1.0)
    cr.add_argument("--discovery-min-compression-ratio",type=float,default=0.05)
    cr.add_argument("--max-candidates",type=int,default=100)
    cr.add_argument("--derived-status",action="append",default=[])
    cr.add_argument("--no-canonical",action="store_true")
    cr.add_argument("--no-derived",action="store_true")
    cr.add_argument("--no-prune-dominated",action="store_true")
    cr.add_argument("--min-realized-occurrences",type=int,default=2)
    cr.add_argument("--min-realized-parent-structures",type=int,default=2)
    cr.add_argument("--definition-overhead",type=float,default=1.0)
    cr.add_argument("--min-realized-net-savings",type=float,default=1.0)
    cr.add_argument("--min-realized-compression-ratio",type=float,default=0.0)
    cr.add_argument("--max-promotions",type=int,default=32)
    cr.add_argument("--plan-only",action="store_true",help="derive deterministic rewrite ids without materializing macro artifacts")
    cr.add_argument("--no-persist",action="store_true")

    cb=sub.add_parser("compile-base", help="compile a persisted v0.13 runtime compression run into a compact binary .eqbase pack")
    cb.add_argument("db"); cb.add_argument("output")
    cb.add_argument("--pack-id",default="equinox-base")
    cb.add_argument("--pack-version",type=int,default=1)
    cb.add_argument("--compression-run-id",type=int)
    cb.add_argument("--strip-metadata",action="store_true")
    cb.add_argument("--no-verify",action="store_true")
    cb.add_argument("--no-persist",action="store_true")
    cb.add_argument("--report")

    ib=sub.add_parser("inspect-base", help="load a binary .eqbase pack and print manifest/sample records")
    ib.add_argument("pack"); ib.add_argument("--no-verify",action="store_true")
    ib.add_argument("--sample-nodes",type=int,default=5)
    ib.add_argument("--sample-relations",type=int,default=5)

    vb=sub.add_parser("verify-base", help="verify hash, references, and structural integrity of a binary .eqbase pack")
    vb.add_argument("pack")

    qb=sub.add_parser("query-base", help="query the compiled .eqbase runtime using secondary indexes")
    qb.add_argument("pack")
    qbg=qb.add_mutually_exclusive_group(required=True)
    qbg.add_argument("--node")
    qbg.add_argument("--surface")
    qbg.add_argument("--parents")
    qbg.add_argument("--expand")
    qbg.add_argument("--relations-from")
    qbg.add_argument("--relations-to")
    qb.add_argument("--relation-type")
    qb.add_argument("--timing-repeat",type=int,default=0)

    bb=sub.add_parser("benchmark-base", help="benchmark indexed runtime queries and hierarchical routing on a compiled .eqbase pack")
    bb.add_argument("pack")
    bb.add_argument("--sample-nodes",type=int,default=128)
    bb.add_argument("--sample-macros",type=int,default=16)
    bb.add_argument("--timing-repeat",type=int,default=50)
    bb.add_argument("--max-expanded-symbols",type=int,default=2000000)
    bb.add_argument("--output")

    ar=sub.add_parser("artifacts", help="list current derived compiler artifacts")
    ar.add_argument("db"); ar.add_argument("--target-id"); ar.add_argument("--status", action="append", default=[])

    sp=sub.add_parser("source-policy", help="set, clear, or list persistent source trust/ablation policy")
    sps=sp.add_subparsers(dest="source_policy_cmd", required=True)
    spset=sps.add_parser("set")
    spset.add_argument("db"); spset.add_argument("source_id"); spset.add_argument("source_version")
    spset.add_argument("--weight", type=float, default=1.0)
    spset.add_argument("--disable", action="store_true")
    spset.add_argument("--note")
    spclear=sps.add_parser("clear")
    spclear.add_argument("db"); spclear.add_argument("source_id"); spclear.add_argument("source_version")
    sprep=sps.add_parser("replace")
    sprep.add_argument("db"); sprep.add_argument("source_id"); sprep.add_argument("old_version"); sprep.add_argument("new_version")
    sprep.add_argument("--weight",type=float,default=1.0); sprep.add_argument("--note")
    splist=sps.add_parser("list")
    splist.add_argument("db"); splist.add_argument("--explicit-only", action="store_true")

    rb=sub.add_parser("rebuild-senses", help="recompile derived senses using persistent source ablation/reweighting policies")
    rb.add_argument("db"); rb.add_argument("output")
    rbt=rb.add_mutually_exclusive_group(required=True)
    rbt.add_argument("--surface"); rbt.add_argument("--target-id")
    rb.add_argument("--report")
    rb.add_argument("--threshold",type=float,default=0.62)
    rb.add_argument("--min-channels",type=int,default=2)
    rb.add_argument("--min-contexts",type=int,default=2)
    rb.add_argument("--include-singletons",action="store_true")
    rb.add_argument("--ingest-derived",action="store_true")
    rb.add_argument("--no-track-stability",action="store_true")
    rb.add_argument("--w-hidden",type=float,default=0.55)
    rb.add_argument("--w-lexical",type=float,default=0.05)
    rb.add_argument("--w-semantic",type=float,default=0.15)
    rb.add_argument("--w-substitution",type=float,default=0.10)
    rb.add_argument("--w-transition",type=float,default=0.05)
    rb.add_argument("--w-prediction",type=float,default=0.10)
    rb.add_argument("--source-vote-threshold",type=float,default=0.58)
    rb.add_argument("--source-vote-margin",type=float,default=0.08)
    rb.add_argument("--min-observed-pairs",type=int,default=1)
    rb.add_argument("--stable-min-sources",type=int,default=2)
    rb.add_argument("--stable-min-runs",type=int,default=2)
    rb.add_argument("--stable-consensus",type=float,default=0.75)
    rb.add_argument("--stable-min-support-weight",type=float,default=1.5)
    rb.add_argument("--quarantine-conflicts",type=int,default=2)
    rb.add_argument("--quarantine-conflict-weight",type=float,default=1.5)
    rb.add_argument("--quarantine-after-misses",type=int,default=2)

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
    elif a.cmd=="hypotheses":
        with CanonicalDB(a.db) as db:
            print(json.dumps(list_hypothesis_states(db.db,a.target_id),ensure_ascii=False,indent=2,sort_keys=True))
    elif a.cmd=="dependency-impact":
        raise SystemExit(_dependency_impact(a))
    elif a.cmd=="incremental-rebuild":
        raise SystemExit(_incremental_rebuild(a))
    elif a.cmd=="build-macro":
        raise SystemExit(_build_macro(a))
    elif a.cmd=="discover-macros":
        raise SystemExit(_discover_macros(a))
    elif a.cmd=="compress-runtime":
        raise SystemExit(_compress_runtime(a))
    elif a.cmd=="compile-base":
        raise SystemExit(_compile_base(a))
    elif a.cmd=="inspect-base":
        raise SystemExit(_inspect_base(a))
    elif a.cmd=="verify-base":
        raise SystemExit(_verify_base(a))
    elif a.cmd=="query-base":
        raise SystemExit(_query_base(a))
    elif a.cmd=="benchmark-base":
        raise SystemExit(_benchmark_base(a))
    elif a.cmd=="artifacts":
        raise SystemExit(_list_artifacts(a))
    elif a.cmd=="source-policy":
        if a.source_policy_cmd=="set": raise SystemExit(_source_policy_set(a))
        if a.source_policy_cmd=="clear": raise SystemExit(_source_policy_clear(a))
        if a.source_policy_cmd=="replace": raise SystemExit(_source_policy_replace(a))
        if a.source_policy_cmd=="list": raise SystemExit(_source_policy_list(a))
    elif a.cmd=="rebuild-senses":
        raise SystemExit(_rebuild_senses(a))
    elif a.cmd=="compile-senses":
        raise SystemExit(_compile_senses(a))

if __name__=="__main__": main()
