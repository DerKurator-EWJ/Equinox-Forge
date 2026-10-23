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
RUNTIME_COGNITION_VERSION = "0.16"


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
        if not 0 <= self.min_activation <= 1: raise ValueError("min_activation must be in [0,1]")
        if not 0 <= self.min_prediction_score <= 1: raise ValueError("min_prediction_score must be in [0,1]")
        if not 0 < self.depth_decay <= 1: raise ValueError("depth_decay must be in (0,1]")


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

    @classmethod
    def from_path(cls, path: str | Path, policy: RuntimeCognitionPolicy | None = None) -> "RuntimeCognition":
        return cls(load_base_pack(path), policy)

    def _resolve_context(self, context: str) -> tuple[list[str], list[str], list[str]]:
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
        if not self.policy.enable_lexical_seeds:
            lexical = []
        return exact_context or fallback, lexical, tokens

    def _relation_quality(self, rel: CompiledRelation, weight: float) -> float:
        # source_count is only a mild confidence bonus; it never substitutes for
        # independent-source tracking upstream in Forge.
        source_bonus = 0.90 + 0.10 * min(1.0, rel.source_count / 2.0)
        return max(0.0, min(1.0, rel.score * rel.confidence * weight * source_bonus))

    def recall(self, context: str) -> tuple[list[RecallTrace], dict[str, Any]]:
        context_ids, lexical_ids, tokens = self._resolve_context(context)
        seeds: list[tuple[str, float, str]] = []
        for nid in context_ids:
            seeds.append((nid, 1.0, "exact_or_suffix_context"))
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
            "work": {
                "recall_nodes": len(traces),
                "queue_pops": popped,
                "relation_checks": relation_checks,
                "parent_checks": parent_checks,
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
        if self.policy.enable_direct_context_prediction:
            for cid in meta["resolved_context_ids"]:
                for rel in self.index.relations_from.get(cid, []):
                    if rel.relation_type == RelationType.PREDICTION.value:
                        add(rel, 1.0, self.policy.exact_context_prediction_weight, True)

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
            asdict(self.policy),
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
