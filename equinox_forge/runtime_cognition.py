from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
import heapq
import json
import math

from .ir import CompiledRelation, NodeKind, RelationType
from .runtime_pack import LoadedRuntimePack, RuntimeNode, load_base_pack
from .runtime_query import RuntimeIndex

RUNTIME_COGNITION_FORMAT = "equinox-runtime-cognition-v1"
RUNTIME_COGNITION_VERSION = "0.26"


@dataclass
class RuntimeCognitionPolicy:
    max_recall_nodes: int = 96
    max_recall_depth: int = 3
    max_relation_neighbors: int = 24
    max_structural_parents: int = 24
    max_predictions: int = 8
    min_activation: float = 0.06
    min_prediction_score: float = 0.01
    depth_decay: float = 0.82
    parent_weight: float = 0.72
    transition_weight: float = 0.72
    recalled_prediction_weight: float = 0.72
    exact_context_prediction_weight: float = 1.0
    seed_recent_word_weight: float = 0.82
    seed_older_word_weight: float = 0.48
    # Runtime mechanism switches. Defaults preserve v0.16-v0.20 behavior.
    enable_exact_context: bool = True
    enable_suffix_context: bool = True
    enable_lexical_seeds: bool = True
    enable_parent_routing: bool = True
    enable_relation_recall: bool = True
    enable_direct_context_prediction: bool = True
    enable_transition_prediction: bool = True
    enable_recalled_context_prediction: bool = True
    # v0.22: explicit induced frame schemas such as [SLOT_0] ist ein.
    enable_frame_schema_matching: bool = True
    # v0.23: if an induced slot carries a compiled semantic admission profile,
    # enforce it before the frame can become a predictive context.
    enable_semantic_slot_admission: bool = True
    # v0.24: prefer a compiled latent class membership edge (candidate -> prototype)
    # over re-evaluating pairwise candidate-to-filler similarity at runtime.
    enable_slot_prototype_admission: bool = True
    # v0.26: allow a slot to admit a candidate through a compiled multi-hop IS_A
    # chain into a higher recursive latent concept.
    enable_hierarchical_slot_admission: bool = True
    max_hierarchical_slot_hops: int = 8
    frame_match_weight: float = 0.82
    max_frame_matches: int = 8
    # Relation weights are recall routing priors, not learned semantics.
    relation_weights: dict[str, float] = field(default_factory=lambda: {
        RelationType.ASSOCIATION.value: 0.55,
        RelationType.SEMANTIC_SIMILARITY.value: 0.50,
        RelationType.SUBSTITUTION.value: 0.42,
        RelationType.IS_A.value: 0.50,
        RelationType.PROPERTY.value: 0.46,
        RelationType.ACTION.value: 0.46,
        RelationType.CROSSMODAL.value: 0.44,
        RelationType.CONTEXTUAL_USE.value: 0.45,
        RelationType.CONTEXTUAL_SIMILARITY.value: 0.48,
    })

    def validate(self) -> None:
        if self.max_recall_nodes < 1: raise ValueError("max_recall_nodes must be >= 1")
        if self.max_recall_depth < 0: raise ValueError("max_recall_depth must be >= 0")
        if self.max_relation_neighbors < 1: raise ValueError("max_relation_neighbors must be >= 1")
        if self.max_structural_parents < 1: raise ValueError("max_structural_parents must be >= 1")
        if self.max_predictions < 1: raise ValueError("max_predictions must be >= 1")
        if self.max_frame_matches < 1: raise ValueError("max_frame_matches must be >= 1")
        if self.max_hierarchical_slot_hops < 1: raise ValueError("max_hierarchical_slot_hops must be >= 1")
        if not 0 <= self.min_activation <= 1: raise ValueError("min_activation must be in [0,1]")
        if not 0 <= self.min_prediction_score <= 1: raise ValueError("min_prediction_score must be in [0,1]")
        if not 0 < self.depth_decay <= 1: raise ValueError("depth_decay must be in (0,1]")
        if not 0 < self.frame_match_weight <= 1: raise ValueError("frame_match_weight must be in (0,1]")


@dataclass
class RecallTrace:
    node_id: str
    surface: str | None
    kind: str
    level: int
    activation: float
    depth: int
    via: str
    from_node_id: str | None

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class PredictionContribution:
    from_node_id: str
    from_surface: str | None
    relation_type: str
    relation_score: float
    relation_confidence: float
    source_count: int
    context_activation: float
    channel_weight: float
    contribution: float
    direct_context: bool

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class PredictionCandidate:
    node_id: str
    surface: str | None
    score: float
    direct_score: float
    recalled_score: float
    transition_score: float
    contribution_count: int
    contributions: list[PredictionContribution]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["contributions"] = [c.to_dict() for c in self.contributions]
        return d


@dataclass
class RuntimePredictionReport:
    format: str
    version: str
    context: str
    resolved_context_ids: list[str]
    lexical_seed_ids: list[str]
    recall: list[RecallTrace]
    predictions: list[PredictionCandidate]
    work: dict[str, int]
    policy: dict[str, Any]
    frame_admission: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "version": self.version,
            "context": self.context,
            "resolved_context_ids": self.resolved_context_ids,
            "lexical_seed_ids": self.lexical_seed_ids,
            "recall": [x.to_dict() for x in self.recall],
            "predictions": [x.to_dict() for x in self.predictions],
            "work": dict(self.work),
            "policy": self.policy,
            "frame_admission": list(self.frame_admission),
        }


@dataclass
class PredictionBenchmarkCase:
    context: str
    expected: str


@dataclass
class PredictionBenchmarkReport:
    format: str
    version: str
    cases: int
    hit_at_1: float
    hit_at_k: float
    mean_reciprocal_rank: float
    unresolved_contexts: int
    expected_not_in_pack: int
    average_recall_nodes: float
    average_relation_checks: float
    top_k: int
    details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]: return asdict(self)


def _surface_tokens(text: str) -> list[str]:
    # Runtime context matching intentionally stays tokenizer-independent. This first
    # text consumer uses whitespace-delimited surfaces already present in the pack.
    return [x for x in text.strip().split() if x]


def _node_preference(node: RuntimeNode) -> tuple[int, int, str]:
    # Predictive templates first, then composites/concepts, then lexical surfaces.
    kind_rank = {
        NodeKind.TEMPLATE.value: 0,
        NodeKind.COMPOSITE.value: 1,
        NodeKind.CONCEPT.value: 2,
        NodeKind.SURFACE.value: 3,
        NodeKind.QUANT.value: 9,
    }.get(node.kind, 5)
    return (kind_rank, -node.level, node.node_id)


def _noisy_or(values: Iterable[float]) -> float:
    product = 1.0
    seen = False
    for v in values:
        seen = True
        product *= 1.0 - max(0.0, min(1.0, float(v)))
    return 0.0 if not seen else 1.0 - product


class RuntimeCognition:
    """Bounded read-only recall and prediction over a compiled .eqbase graph.

    Recall may use structural and associative relations to expose relevant contexts.
    A prediction candidate, however, is emitted only from a compiled directed
    PREDICTION or TRANSITION relation. Semantic similarity never becomes a next-word
    claim by itself.
    """

    def __init__(self, pack: LoadedRuntimePack, policy: RuntimeCognitionPolicy | None = None):
        self.pack = pack
        self.index = RuntimeIndex(pack)
        self.policy = policy or RuntimeCognitionPolicy()
        self.policy.validate()
        # Frame schemas are an explicit compiled abstraction, not inferred ad hoc at
        # query time. Build a tiny width index once when the pack is opened.
        self._frames_by_width: dict[int, list[tuple[str, list[str], int, bool, set[str], list[str]]]] = {}
        for node in pack.nodes:
            meta = node.metadata or {}
            if meta.get("role") != "induced_frame_schema":
                continue
            pattern = meta.get("pattern_tokens")
            if not isinstance(pattern, list) or not pattern or not all(isinstance(x, str) for x in pattern):
                continue
            support = int(meta.get("support_count", 0) or 0)
            open_slot = bool(meta.get("open_text_slots", True))
            allowed_fillers: set[str] = set()
            for slot_id in meta.get("slot_node_ids", []) or []:
                slot_node = self.index.node_by_id.get(slot_id)
                if slot_node is not None:
                    allowed_fillers.update(str(x) for x in ((slot_node.metadata or {}).get("filler_surfaces", []) or []))
            slot_ids = [str(x) for x in (meta.get("slot_node_ids", []) or [])]
            self._frames_by_width.setdefault(len(pattern), []).append((node.node_id, list(pattern), support, open_slot, allowed_fillers, slot_ids))
        for width in self._frames_by_width:
            self._frames_by_width[width].sort(key=lambda x: (-x[2], x[0]))

    @classmethod
    def from_path(cls, path: str | Path, policy: RuntimeCognitionPolicy | None = None) -> "RuntimeCognition":
        return cls(load_base_pack(path), policy)

    def _semantic_slot_admission(self, token: str, slot_node_id: str) -> dict[str, Any]:
        slot = self.index.node_by_id.get(slot_node_id)
        profile = dict((slot.metadata or {}).get("semantic_admission") or {}) if slot else {}
        result: dict[str, Any] = {
            "token": token, "slot_node_id": slot_node_id, "typed": bool(profile.get("enabled")),
            "admitted": True, "reason": "untyped_open_slot", "candidate_node_ids": [],
            "supporting_fillers": [], "best_scores": {},
        }
        if not profile.get("enabled") or not self.policy.enable_semantic_slot_admission:
            if profile.get("enabled") and not self.policy.enable_semantic_slot_admission:
                result["reason"] = "semantic_admission_disabled"
            return result
        filler_ids = {str(x) for x in profile.get("profile_filler_node_ids", []) or []}
        allowed_types = {str(x) for x in profile.get("relation_types", []) or []}
        min_score = float(profile.get("min_candidate_score", 0.0) or 0.0)
        min_support = int(profile.get("min_support_fillers", 1) or 1)
        candidate_ids = [nid for nid in self.index.surface_to_nodes.get(token, [])
                         if self.index.node_by_id[nid].kind == NodeKind.SURFACE.value]
        result["candidate_node_ids"] = sorted(candidate_ids)
        if not candidate_ids:
            result.update({"admitted": False, "reason": "candidate_surface_unknown", "required_support": min_support, "min_score": min_score})
            return result
        if filler_ids.intersection(candidate_ids):
            result.update({"admitted": True, "reason": "observed_filler", "supporting_fillers": sorted(filler_ids.intersection(candidate_ids)),
                           "required_support": min_support, "min_score": min_score})
            return result

        hierarchical_id = str(profile.get("hierarchical_prototype_node_id") or "")
        if hierarchical_id and self.policy.enable_hierarchical_slot_admission:
            relation_type = str(profile.get("hierarchical_membership_relation_type") or RelationType.IS_A.value)
            max_hops = min(
                int(profile.get("hierarchical_max_hops", self.policy.max_hierarchical_slot_hops) or self.policy.max_hierarchical_slot_hops),
                int(self.policy.max_hierarchical_slot_hops),
            )
            min_path_score = float(profile.get("hierarchical_min_path_score", 0.0) or 0.0)
            best_path = None
            total_index_lookups = 0
            total_relation_checks = 0
            for cid in candidate_ids:
                queue = [(cid, 0, 1.0, [cid])]
                seen_best = {cid: (0, 1.0)}
                pos = 0
                while pos < len(queue):
                    current, hops, quality, path = queue[pos]; pos += 1
                    if current == hierarchical_id and hops > 0:
                        candidate = (quality, -hops, cid, list(path))
                        if best_path is None or candidate[:3] > best_path[:3]:
                            best_path = candidate
                        continue
                    if hops >= max_hops:
                        continue
                    total_index_lookups += 1
                    bucket = self.index.relations_from.get(current, [])
                    total_relation_checks += len(bucket)
                    for rel in bucket:
                        if rel.relation_type != relation_type:
                            continue
                        nxt = rel.to_id
                        if nxt in path:
                            continue
                        edge_q = max(0.0, min(1.0, float(rel.score) * float(rel.confidence)))
                        nq = min(quality, edge_q)
                        nh = hops + 1
                        old = seen_best.get(nxt)
                        if old is not None and old[0] <= nh and old[1] >= nq - 1e-12:
                            continue
                        seen_best[nxt] = (nh, nq)
                        queue.append((nxt, nh, nq, path + [nxt]))
            if best_path is not None and best_path[0] + 1e-12 >= min_path_score:
                result.update({
                    "hierarchical_prototype_node_id": hierarchical_id,
                    "hierarchical_relation_type": relation_type,
                    "hierarchical_path_score": float(best_path[0]),
                    "hierarchical_hops": int(-best_path[1]),
                    "hierarchical_candidate_node_id": best_path[2],
                    "hierarchical_path": best_path[3],
                    "hierarchical_min_path_score": min_path_score,
                    "hierarchical_index_lookups": total_index_lookups,
                    "hierarchical_relation_checks": total_relation_checks,
                    "admitted": True,
                    "reason": "hierarchical_prototype_membership",
                })
                return result
            # Keep evaluating the direct base-prototype path below. This makes the
            # transferred frame backward-compatible for its original subtype.
            result.update({
                "hierarchical_prototype_node_id": hierarchical_id,
                "hierarchical_relation_type": relation_type,
                "hierarchical_path_score": float(best_path[0]) if best_path is not None else 0.0,
                "hierarchical_min_path_score": min_path_score,
                "hierarchical_index_lookups": total_index_lookups,
                "hierarchical_relation_checks": total_relation_checks,
            })

        prototype_id = str(profile.get("prototype_node_id") or "")
        if prototype_id and self.policy.enable_slot_prototype_admission:
            relation_type = str(profile.get("prototype_membership_relation_type") or RelationType.IS_A.value)
            prototype_min = float(profile.get("prototype_min_candidate_score", min_score) or min_score)
            best = 0.0
            matched_candidate = None
            prototype_index_lookups = 0
            for cid in candidate_ids:
                prototype_index_lookups += 1
                rel = self.index.relation_by_key.get((cid, prototype_id, relation_type))
                if rel is None:
                    continue
                q = max(0.0, min(1.0, float(rel.score) * float(rel.confidence)))
                if q > best:
                    best = q; matched_candidate = cid
            admitted = best + 1e-12 >= prototype_min
            result.update({
                "prototype_node_id": prototype_id,
                "prototype_relation_type": relation_type,
                "prototype_score": best,
                "prototype_min_score": prototype_min,
                "prototype_candidate_node_id": matched_candidate,
                "prototype_index_lookups": prototype_index_lookups,
                "admitted": admitted,
                "reason": "prototype_membership" if admitted else "insufficient_prototype_membership",
            })
            return result

        best_by_filler: dict[str, float] = {}
        for cid in candidate_ids:
            for rel in self.index.relations_from.get(cid, []):
                if rel.relation_type in allowed_types and rel.to_id in filler_ids:
                    q = max(0.0, min(1.0, float(rel.score) * float(rel.confidence)))
                    best_by_filler[rel.to_id] = max(best_by_filler.get(rel.to_id, 0.0), q)
            for rel in self.index.relations_to.get(cid, []):
                if rel.relation_type in allowed_types and rel.from_id in filler_ids:
                    q = max(0.0, min(1.0, float(rel.score) * float(rel.confidence)))
                    best_by_filler[rel.from_id] = max(best_by_filler.get(rel.from_id, 0.0), q)
        supporters = sorted(fid for fid, score in best_by_filler.items() if score + 1e-12 >= min_score)
        result.update({
            "best_scores": {k: best_by_filler[k] for k in sorted(best_by_filler)},
            "supporting_fillers": supporters, "required_support": min_support, "min_score": min_score,
            "admitted": len(supporters) >= min_support,
            "reason": "semantic_support" if len(supporters) >= min_support else "insufficient_semantic_support",
        })
        return result

    def _match_frame_schemas(self, tokens: list[str]) -> tuple[list[str], int, list[dict[str, Any]]]:
        if not self.policy.enable_frame_schema_matching or not tokens:
            return [], 0, []
        checks = 0
        diagnostics: list[dict[str, Any]] = []
        # Prefer the longest matching frame so a specific learned schema wins over
        # a shorter wildcard. Match against the live suffix, mirroring n-gram context
        # resolution while allowing a compiled slot to consume a novel surface.
        for width in sorted((w for w in self._frames_by_width if w <= len(tokens)), reverse=True):
            live = tokens[-width:]
            matches: list[tuple[int, str]] = []
            width_had_structural_match = False
            for node_id, pattern, support, open_slot, allowed_fillers, slot_ids in self._frames_by_width[width]:
                checks += 1
                ok = True
                slot_cursor = 0
                frame_diag = {"frame_node_id": node_id, "pattern": pattern, "live": list(live), "slot_checks": [], "structural_match": True, "admitted": False}
                for p, t in zip(pattern, live):
                    if p == "*":
                        sid = slot_ids[slot_cursor] if slot_cursor < len(slot_ids) else ""
                        slot_cursor += 1
                        if not open_slot and t not in allowed_fillers:
                            ok = False
                            frame_diag["slot_checks"].append({"token": t, "admitted": False, "reason": "closed_slot"})
                            break
                        if sid:
                            admission = self._semantic_slot_admission(t, sid)
                            frame_diag["slot_checks"].append(admission)
                            if not admission.get("admitted", False):
                                ok = False
                                break
                    elif p != t:
                        ok = False
                        frame_diag["structural_match"] = False
                        break
                if frame_diag["structural_match"]:
                    width_had_structural_match = True
                    frame_diag["admitted"] = ok
                    diagnostics.append(frame_diag)
                if ok:
                    matches.append((support, node_id))
            if matches:
                matches.sort(key=lambda x: (-x[0], x[1]))
                return [nid for _, nid in matches[:self.policy.max_frame_matches]], checks, diagnostics
            # If a structurally matching longest frame was rejected by typed admission,
            # do not silently fall through to a shorter, broader schema.
            if width_had_structural_match:
                return [], checks, diagnostics
        return [], checks, diagnostics

    def _resolve_context(self, context: str) -> tuple[list[str], list[str], list[str], int, list[dict[str, Any]]]:
        text = " ".join(_surface_tokens(context))
        exact = list(self.index.surface_to_nodes.get(text, [])) if text else []
        exact_nodes = sorted((self.index.node_by_id[x] for x in exact), key=_node_preference)
        exact_context = [n.node_id for n in exact_nodes if n.kind in {
            NodeKind.TEMPLATE.value, NodeKind.COMPOSITE.value, NodeKind.CONCEPT.value
        } and any(r.relation_type == RelationType.PREDICTION.value for r in self.index.relations_from.get(n.node_id, []))]

        tokens = _surface_tokens(context)
        lexical: list[str] = []
        for tok in tokens:
            ids = [x for x in self.index.surface_to_nodes.get(tok, [])
                   if self.index.node_by_id[x].kind == NodeKind.SURFACE.value]
            if ids:
                lexical.append(sorted(ids)[0])

        if not self.policy.enable_exact_context:
            exact_context = []

        # If an exact context label does not exist, use the longest known suffix
        # context. This makes n-gram BASE packs useful with longer live prompts.
        fallback: list[str] = []
        if not exact_context and self.policy.enable_suffix_context:
            for width in range(min(len(tokens), 8), 1, -1):
                label = " ".join(tokens[-width:])
                ids = [x for x in self.index.surface_to_nodes.get(label, [])
                       if self.index.node_by_id[x].kind in {NodeKind.TEMPLATE.value, NodeKind.COMPOSITE.value}
                       and any(r.relation_type == RelationType.PREDICTION.value for r in self.index.relations_from.get(x, []))]
                if ids:
                    fallback = sorted(ids, key=lambda x: _node_preference(self.index.node_by_id[x]))
                    break

        frames: list[str] = []
        frame_checks = 0
        frame_admission: list[dict[str, Any]] = []
        if not exact_context and not fallback:
            frames, frame_checks, frame_admission = self._match_frame_schemas(tokens)

        if not self.policy.enable_lexical_seeds:
            lexical = []
        return exact_context or fallback or frames, lexical, tokens, frame_checks, frame_admission

    def _relation_quality(self, rel: CompiledRelation, weight: float) -> float:
        # source_count is only a mild confidence bonus; it never substitutes for
        # independent-source tracking upstream in Forge.
        source_bonus = 0.90 + 0.10 * min(1.0, rel.source_count / 2.0)
        return max(0.0, min(1.0, rel.score * rel.confidence * weight * source_bonus))

    def recall(self, context: str) -> tuple[list[RecallTrace], dict[str, Any]]:
        context_ids, lexical_ids, tokens, frame_checks, frame_admission = self._resolve_context(context)
        seeds: list[tuple[str, float, str]] = []
        for nid in context_ids:
            node = self.index.node_by_id.get(nid)
            is_frame = bool(node and (node.metadata or {}).get("role") == "induced_frame_schema")
            seeds.append((nid, self.policy.frame_match_weight if is_frame else 1.0, "frame_schema" if is_frame else "exact_or_suffix_context"))
        for i, nid in enumerate(lexical_ids):
            if i == len(lexical_ids) - 1:
                act = self.policy.seed_recent_word_weight
            else:
                distance = (len(lexical_ids) - 1) - i
                act = self.policy.seed_older_word_weight * (self.policy.depth_decay ** max(0, distance - 1))
            seeds.append((nid, act, "lexical_seed"))

        best: dict[str, float] = {}
        best_meta: dict[str, tuple[int, str, str | None]] = {}
        heap: list[tuple[float, int, str, str, str | None]] = []
        serial = 0
        for nid, act, via in seeds:
            if act < self.policy.min_activation: continue
            if act > best.get(nid, -1.0):
                best[nid] = act
                best_meta[nid] = (0, via, None)
                heapq.heappush(heap, (-act, serial, nid, via, None)); serial += 1

        relation_checks = parent_checks = popped = 0
        while heap and len(best_meta) <= self.policy.max_recall_nodes:
            neg_act, _, nid, _, _ = heapq.heappop(heap)
            act = -neg_act
            if act + 1e-12 < best.get(nid, -1.0):
                continue
            depth, _, _ = best_meta[nid]
            popped += 1
            if depth >= self.policy.max_recall_depth:
                continue

            # Structural upward routing is central to Equinox: known lower nodes can
            # expose a bounded set of contexts/macros without scanning all parents.
            parents = (self.index.parents.get(nid, [])[:self.policy.max_structural_parents]
                       if self.policy.enable_parent_routing else [])
            parent_checks += 1 + len(parents)
            for pid in parents:
                pnode = self.index.node_by_id[pid]
                if pnode.kind == NodeKind.QUANT.value:
                    continue
                nxt = act * self.policy.parent_weight * self.policy.depth_decay
                if nxt < self.policy.min_activation:
                    continue
                if nxt > best.get(pid, -1.0) + 1e-12:
                    best[pid] = nxt
                    best_meta[pid] = (depth + 1, "parent", nid)
                    heapq.heappush(heap, (-nxt, serial, pid, "parent", nid)); serial += 1

            # Associative/semantic recall relations. PREDICTION and TRANSITION are
            # deliberately excluded here; they are output channels, not recall links.
            rels = self.index.relations_from.get(nid, []) if self.policy.enable_relation_recall else []
            relation_checks += 1 + len(rels)
            ranked_rels: list[tuple[float, CompiledRelation]] = []
            for rel in rels:
                weight = self.policy.relation_weights.get(rel.relation_type)
                if weight is None:
                    continue
                q = self._relation_quality(rel, weight)
                if q > 0:
                    ranked_rels.append((q, rel))
            ranked_rels.sort(key=lambda x: (-x[0], x[1].to_id, x[1].relation_type))
            for q, rel in ranked_rels[:self.policy.max_relation_neighbors]:
                target = self.index.node_by_id.get(rel.to_id)
                if target is None or target.kind == NodeKind.QUANT.value:
                    continue
                nxt = act * q * self.policy.depth_decay
                if nxt < self.policy.min_activation:
                    continue
                if nxt > best.get(rel.to_id, -1.0) + 1e-12:
                    best[rel.to_id] = nxt
                    best_meta[rel.to_id] = (depth + 1, f"relation:{rel.relation_type}", nid)
                    heapq.heappush(heap, (-nxt, serial, rel.to_id, f"relation:{rel.relation_type}", nid)); serial += 1

            if len(best_meta) >= self.policy.max_recall_nodes:
                break

        ordered = sorted(best, key=lambda n: (-best[n], best_meta[n][0], n))[:self.policy.max_recall_nodes]
        traces = [RecallTrace(
            n, self.index.node_by_id[n].surface, self.index.node_by_id[n].kind,
            self.index.node_by_id[n].level, best[n], best_meta[n][0], best_meta[n][1], best_meta[n][2]
        ) for n in ordered]
        meta = {
            "resolved_context_ids": context_ids,
            "lexical_seed_ids": lexical_ids,
            "tokens": tokens,
            "frame_admission": frame_admission,
            "work": {
                "recall_nodes": len(traces),
                "queue_pops": popped,
                "relation_checks": relation_checks,
                "parent_checks": parent_checks,
                "frame_match_checks": frame_checks,
                "frame_admission_checks": sum(len(x.get("slot_checks", [])) for x in frame_admission),
                "frame_admission_rejections": sum(1 for x in frame_admission if x.get("structural_match") and not x.get("admitted")),
            },
        }
        return traces, meta

    def predict(self, context: str) -> RuntimePredictionReport:
        recall, meta = self.recall(context)
        context_ids = set(meta["resolved_context_ids"])
        lexical_ids = list(meta["lexical_seed_ids"])
        recalled = {x.node_id: x for x in recall}
        contributions: dict[str, list[PredictionContribution]] = {}
        prediction_relations_checked = 0

        def add(rel: CompiledRelation, activation: float, weight: float, direct: bool) -> None:
            nonlocal prediction_relations_checked
            prediction_relations_checked += 1
            target = self.index.node_by_id.get(rel.to_id)
            if target is None or target.kind == NodeKind.QUANT.value:
                return
            c = max(0.0, min(1.0, activation * rel.score * rel.confidence * weight))
            if c < self.policy.min_prediction_score:
                return
            source = self.index.node_by_id.get(rel.from_id)
            contributions.setdefault(rel.to_id, []).append(PredictionContribution(
                rel.from_id, source.surface if source else None, rel.relation_type,
                rel.score, rel.confidence, rel.source_count, activation, weight, c, direct,
            ))

        # Exact/suffix predictive contexts get full-weight direct predictions.
        # Induced frame schemas are explicit compiled hypotheses and therefore use
        # the lower frame_match_weight even when they resolve the live context.
        if self.policy.enable_direct_context_prediction:
            for cid in meta["resolved_context_ids"]:
                node = self.index.node_by_id.get(cid)
                is_frame = bool(node and (node.metadata or {}).get("role") == "induced_frame_schema")
                activation = self.policy.frame_match_weight if is_frame else 1.0
                for rel in self.index.relations_from.get(cid, []):
                    if rel.relation_type == RelationType.PREDICTION.value:
                        add(rel, activation, self.policy.exact_context_prediction_weight, True)

        # Latest lexical item supplies bigram transition predictions.
        if lexical_ids and self.policy.enable_transition_prediction:
            last = lexical_ids[-1]
            act = recalled[last].activation if last in recalled else self.policy.seed_recent_word_weight
            for rel in self.index.relations_from.get(last, []):
                if rel.relation_type == RelationType.TRANSITION.value:
                    add(rel, act, self.policy.transition_weight, True)

        # Recalled contexts can contribute prediction evidence at a lower weight.
        if self.policy.enable_recalled_context_prediction:
            for trace in recall:
                if trace.node_id in context_ids:
                    continue
                for rel in self.index.relations_from.get(trace.node_id, []):
                    if rel.relation_type == RelationType.PREDICTION.value:
                        add(rel, trace.activation, self.policy.recalled_prediction_weight, False)

        candidates: list[PredictionCandidate] = []
        for target_id, cs in contributions.items():
            direct = _noisy_or(c.contribution for c in cs if c.relation_type == RelationType.PREDICTION.value and c.direct_context)
            recalled_score = _noisy_or(c.contribution for c in cs if c.relation_type == RelationType.PREDICTION.value and not c.direct_context)
            transition = _noisy_or(c.contribution for c in cs if c.relation_type == RelationType.TRANSITION.value)
            score = _noisy_or(c.contribution for c in cs)
            node = self.index.node_by_id[target_id]
            cs.sort(key=lambda c: (-c.contribution, c.relation_type, c.from_node_id))
            candidates.append(PredictionCandidate(
                target_id, node.surface, score, direct, recalled_score, transition, len(cs), cs,
            ))
        candidates.sort(key=lambda x: (-x.score, -x.direct_score, -x.transition_score, x.surface or "", x.node_id))
        candidates = candidates[:self.policy.max_predictions]

        work = dict(meta["work"])
        work["prediction_relation_checks"] = prediction_relations_checked
        work["prediction_candidates_before_limit"] = len(contributions)
        work["prediction_candidates_returned"] = len(candidates)
        return RuntimePredictionReport(
            RUNTIME_COGNITION_FORMAT, RUNTIME_COGNITION_VERSION, context,
            list(meta["resolved_context_ids"]), lexical_ids, recall, candidates, work,
            asdict(self.policy), list(meta.get("frame_admission", [])),
        )


def load_prediction_cases(paths: Iterable[str | Path]) -> list[PredictionBenchmarkCase]:
    out: list[PredictionBenchmarkCase] = []
    for p in paths:
        path = Path(p)
        if path.suffix.lower() == ".jsonl":
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip() or line.lstrip().startswith("#"): continue
                obj = json.loads(line)
                if not isinstance(obj, dict) or not obj.get("context") or not obj.get("expected"):
                    raise ValueError(f"{path}:{line_no}: expected JSON object with context + expected")
                out.append(PredictionBenchmarkCase(str(obj["context"]), str(obj["expected"])))
        else:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip() or line.lstrip().startswith("#"): continue
                if "\t" not in line:
                    raise ValueError(f"{path}:{line_no}: expected TAB-separated context and expected surface")
                context, expected = line.split("\t", 1)
                out.append(PredictionBenchmarkCase(context.strip(), expected.strip()))
    return out


def benchmark_predictions(
    pack: LoadedRuntimePack | str | Path,
    cases: list[PredictionBenchmarkCase],
    *,
    policy: RuntimeCognitionPolicy | None = None,
    top_k: int = 5,
) -> PredictionBenchmarkReport:
    if top_k < 1: raise ValueError("top_k must be >= 1")
    cog = RuntimeCognition.from_path(pack, policy) if isinstance(pack, (str, Path)) else RuntimeCognition(pack, policy)
    hit1 = hitk = unresolved = expected_missing = 0
    rr_total = 0.0
    recall_total = relation_total = 0
    details: list[dict[str, Any]] = []
    for case in cases:
        report = cog.predict(case.context)
        surfaces = [x.surface for x in report.predictions]
        rank = None
        for i, surface in enumerate(surfaces, 1):
            if surface == case.expected:
                rank = i; break
        if rank == 1: hit1 += 1
        if rank is not None and rank <= top_k: hitk += 1
        if rank is not None: rr_total += 1.0 / rank
        if not report.resolved_context_ids: unresolved += 1
        if not cog.index.surface_to_nodes.get(case.expected): expected_missing += 1
        recall_total += report.work.get("recall_nodes", 0)
        relation_total += report.work.get("relation_checks", 0) + report.work.get("prediction_relation_checks", 0)
        details.append({
            "context": case.context,
            "expected": case.expected,
            "rank": rank,
            "top_surfaces": surfaces[:top_k],
            "resolved_context_ids": report.resolved_context_ids,
            "recall_nodes": report.work.get("recall_nodes", 0),
            "relation_checks": report.work.get("relation_checks", 0) + report.work.get("prediction_relation_checks", 0),
        })
    n = len(cases)
    return PredictionBenchmarkReport(
        RUNTIME_COGNITION_FORMAT, RUNTIME_COGNITION_VERSION, n,
        (hit1 / n if n else 0.0), (hitk / n if n else 0.0), (rr_total / n if n else 0.0),
        unresolved, expected_missing,
        (recall_total / n if n else 0.0), (relation_total / n if n else 0.0), top_k, details,
    )
