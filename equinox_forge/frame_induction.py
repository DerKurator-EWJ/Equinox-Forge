from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import hashlib
import json
import sqlite3

from .canonical import composite_id, normalize_surface
from .compiler import CompilePolicy, aggregate_relations
from .ir import ForgeDocument, IRNode, RelationEvidence, RelationType, SourceRef, NodeKind, Modality

FRAME_INDUCTION_FORMAT = "equinox-forge-frame-induction-v1"
FRAME_INDUCTION_VERSION = "0.22"


@dataclass(frozen=True)
class FrameInductionPolicy:
    min_contexts: int = 2
    min_unique_fillers: int = 2
    max_slots: int = 1
    min_target_context_fraction: float = 1.0
    min_target_score: float = 0.01
    evidence_confidence: float = 0.90
    allow_open_text_slot: bool = True
    require_same_width: bool = True

    def validate(self) -> None:
        if self.min_contexts < 2:
            raise ValueError("min_contexts must be >= 2")
        if self.min_unique_fillers < 2:
            raise ValueError("min_unique_fillers must be >= 2")
        if self.max_slots != 1:
            raise ValueError("v0.22 supports exactly one induced slot per frame")
        if not 0.0 <= self.min_target_context_fraction <= 1.0:
            raise ValueError("min_target_context_fraction must be in [0,1]")
        if not 0.0 <= self.min_target_score <= 1.0:
            raise ValueError("min_target_score must be in [0,1]")
        if not 0.0 <= self.evidence_confidence <= 1.0:
            raise ValueError("evidence_confidence must be in [0,1]")


@dataclass
class FrameCandidateReport:
    frame_node_id: str
    pattern: str
    slot_position: int
    context_count: int
    unique_fillers: int
    fillers: list[str]
    targets: list[dict[str, Any]]
    source_context_ids: list[str]
    provisional: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FrameInductionReport:
    format: str
    version: str
    contexts_considered: int
    candidate_groups: int
    accepted_frames: int
    rejected_insufficient_contexts: int
    rejected_insufficient_fillers: int
    rejected_no_shared_targets: int
    generated_nodes: int
    generated_prediction_evidence: int
    frames: list[FrameCandidateReport]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["frames"] = [x.to_dict() for x in self.frames]
        return d


def _stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _node_row(db: sqlite3.Connection, node_id: str) -> tuple | None:
    return db.execute(
        "SELECT node_id,modality,kind,level,surface,metadata_json FROM nodes WHERE node_id=?",
        (node_id,),
    ).fetchone()


def _load_node_recursive(db: sqlite3.Connection, node_id: str, out: dict[str, IRNode]) -> IRNode:
    if node_id in out:
        return out[node_id]
    row = _node_row(db, node_id)
    if row is None:
        raise KeyError(f"unknown canonical node {node_id}")
    members = [r[0] for r in db.execute(
        "SELECT child_id FROM node_members WHERE parent_id=? ORDER BY position", (node_id,)
    ).fetchall()]
    for child in members:
        _load_node_recursive(db, child, out)
    node = IRNode(
        node_id=row[0], modality=row[1], kind=row[2], level=int(row[3]), surface=row[4],
        members=members, metadata=json.loads(row[5] or "{}"),
    )
    out[node_id] = node
    return node


def _template_contexts(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rels = aggregate_relations(db, CompilePolicy(min_score=0.0, min_confidence=0.0, min_sources=1))
    preds: dict[str, list[Any]] = {}
    for rel in rels:
        if rel.relation_type == RelationType.PREDICTION.value:
            preds.setdefault(rel.from_id, []).append(rel)
    rows = db.execute(
        "SELECT node_id,surface FROM nodes WHERE modality=? AND kind=? ORDER BY node_id",
        (Modality.TEXT.value, NodeKind.TEMPLATE.value),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for node_id, surface in rows:
        if node_id not in preds:
            continue
        member_rows = db.execute(
            """
            SELECT m.position,n.node_id,n.kind,n.surface,n.level
            FROM node_members m JOIN nodes n ON n.node_id=m.child_id
            WHERE m.parent_id=? ORDER BY m.position
            """, (node_id,),
        ).fetchall()
        if not member_rows or any(r[2] != NodeKind.SURFACE.value or r[3] is None for r in member_rows):
            continue
        tokens = [normalize_surface(str(r[3])) for r in member_rows]
        out.append({
            "node_id": node_id,
            "surface": surface,
            "members": [r[1] for r in member_rows],
            "tokens": tokens,
            "predictions": preds[node_id],
        })
    return out


def _slot_node(pattern_tokens: list[str], slot_position: int, filler_nodes: list[IRNode], policy: FrameInductionPolicy) -> IRNode:
    filler_ids = sorted({n.node_id for n in filler_nodes})
    slot_label = f"[SLOT_{slot_position}]"
    slot_signature = {
        "pattern": pattern_tokens,
        "slot_position": slot_position,
        "fillers": filler_ids,
        "open_text_slot": bool(policy.allow_open_text_slot),
    }
    node_id = composite_id(Modality.TEXT.value, NodeKind.CONCEPT.value, filler_ids, label="slot:" + _stable_hash(slot_signature)[:16])
    level = max(n.level for n in filler_nodes) + 1
    return IRNode(
        node_id=node_id,
        modality=Modality.TEXT.value,
        kind=NodeKind.CONCEPT.value,
        level=level,
        surface=slot_label,
        members=filler_ids,
        metadata={
            "role": "induced_frame_slot",
            "provisional": True,
            "slot_position": slot_position,
            "open_text_slot": bool(policy.allow_open_text_slot),
            "filler_surfaces": sorted({str(n.surface) for n in filler_nodes if n.surface is not None}),
            "support_count": len(filler_ids),
            "forge_version": FRAME_INDUCTION_VERSION,
        },
    )


def induce_relation_frames(
    db: sqlite3.Connection,
    policy: FrameInductionPolicy | None = None,
    *,
    source_id: str = "derived:frame-induction",
    source_version: str = FRAME_INDUCTION_VERSION,
) -> tuple[ForgeDocument, FrameInductionReport]:
    policy = policy or FrameInductionPolicy()
    policy.validate()
    contexts = _template_contexts(db)

    groups: dict[tuple[int, int, tuple[str, ...]], list[dict[str, Any]]] = {}
    for ctx in contexts:
        tokens = ctx["tokens"]
        if len(tokens) < 2:
            continue
        for pos in range(len(tokens)):
            fixed = tuple(tok for i, tok in enumerate(tokens) if i != pos)
            groups.setdefault((len(tokens), pos, fixed), []).append(ctx)

    all_nodes: dict[str, IRNode] = {}
    evidence: list[RelationEvidence] = []
    frames: list[FrameCandidateReport] = []
    rej_contexts = rej_fillers = rej_targets = 0
    src = SourceRef(source_id, source_version, "frame_schema_induction_v1")

    for (width, slot_pos, fixed), rows in sorted(groups.items(), key=lambda x: x[0]):
        unique_contexts = {r["node_id"]: r for r in rows}
        rows = list(unique_contexts.values())
        if len(rows) < policy.min_contexts:
            rej_contexts += 1
            continue
        filler_pairs = {(r["tokens"][slot_pos], r["members"][slot_pos]) for r in rows}
        if len({x[0] for x in filler_pairs}) < policy.min_unique_fillers:
            rej_fillers += 1
            continue

        target_rows: dict[str, list[Any]] = {}
        for r in rows:
            seen_targets: set[str] = set()
            for rel in r["predictions"]:
                if rel.to_id in seen_targets:
                    continue
                seen_targets.add(rel.to_id)
                target_rows.setdefault(rel.to_id, []).append(rel)

        accepted_targets: list[tuple[str, float, float, float, int]] = []
        for target_id, rel_list in target_rows.items():
            support_fraction = len(rel_list) / len(rows)
            mean_score = sum(float(r.score) for r in rel_list) / len(rows)  # missing context => 0 below
            score = mean_score * support_fraction
            mean_conf = sum(float(r.confidence) for r in rel_list) / len(rel_list)
            if support_fraction + 1e-12 < policy.min_target_context_fraction:
                continue
            if score + 1e-12 < policy.min_target_score:
                continue
            accepted_targets.append((target_id, score, mean_conf, support_fraction, len(rel_list)))
        if not accepted_targets:
            rej_targets += 1
            continue

        pattern_tokens: list[str] = []
        fixed_iter = iter(fixed)
        for i in range(width):
            pattern_tokens.append("*" if i == slot_pos else next(fixed_iter))

        filler_nodes: list[IRNode] = []
        for _, nid in sorted(filler_pairs):
            filler_nodes.append(_load_node_recursive(db, nid, all_nodes))
        slot = _slot_node(pattern_tokens, slot_pos, filler_nodes, policy)
        all_nodes[slot.node_id] = slot

        frame_members: list[IRNode] = []
        representative = rows[0]
        for i in range(width):
            if i == slot_pos:
                frame_members.append(slot)
            else:
                fixed_node_id = representative["members"][i]
                frame_members.append(_load_node_recursive(db, fixed_node_id, all_nodes))
        label = " ".join(f"[SLOT_{slot_pos}]" if i == slot_pos else pattern_tokens[i] for i in range(width))
        frame_id = composite_id(Modality.TEXT.value, NodeKind.TEMPLATE.value, [n.node_id for n in frame_members], label=label)
        frame = IRNode(
            node_id=frame_id,
            modality=Modality.TEXT.value,
            kind=NodeKind.TEMPLATE.value,
            level=max(n.level for n in frame_members) + 1,
            surface=label,
            members=[n.node_id for n in frame_members],
            metadata={
                "role": "induced_frame_schema",
                "provisional": True,
                "pattern_tokens": pattern_tokens,
                "slot_positions": [slot_pos],
                "slot_node_ids": [slot.node_id],
                "open_text_slots": bool(policy.allow_open_text_slot),
                "support_context_ids": sorted(r["node_id"] for r in rows),
                "support_count": len(rows),
                "unique_fillers": len({x[0] for x in filler_pairs}),
                "forge_version": FRAME_INDUCTION_VERSION,
            },
        )
        all_nodes[frame.node_id] = frame

        targets_report: list[dict[str, Any]] = []
        for target_id, score, mean_conf, support_fraction, support_count in sorted(accepted_targets, key=lambda x: (-x[1], x[0])):
            target = _load_node_recursive(db, target_id, all_nodes)
            confidence = max(0.0, min(1.0, policy.evidence_confidence * mean_conf * support_fraction))
            evidence.append(RelationEvidence(
                from_id=frame.node_id,
                to_id=target.node_id,
                relation_type=RelationType.PREDICTION.value,
                score=max(0.0, min(1.0, score)),
                confidence=confidence,
                source=src,
                metadata={
                    "evidence_kind": "induced_frame_prediction",
                    "pattern": label,
                    "slot_position": slot_pos,
                    "support_contexts": len(rows),
                    "target_support_contexts": support_count,
                    "target_context_fraction": support_fraction,
                    "derived_from_context_ids": sorted(r["node_id"] for r in rows),
                    "provisional": True,
                },
            ))
            targets_report.append({
                "target_node_id": target_id,
                "target_surface": target.surface,
                "score": score,
                "confidence": confidence,
                "context_fraction": support_fraction,
                "support_contexts": support_count,
            })

        frames.append(FrameCandidateReport(
            frame_node_id=frame.node_id,
            pattern=label,
            slot_position=slot_pos,
            context_count=len(rows),
            unique_fillers=len({x[0] for x in filler_pairs}),
            fillers=sorted({x[0] for x in filler_pairs}),
            targets=targets_report,
            source_context_ids=sorted(r["node_id"] for r in rows),
        ))

    doc = ForgeDocument(
        nodes=sorted(all_nodes.values(), key=lambda n: (n.level, n.node_id)),
        evidence=sorted(evidence, key=lambda e: (e.from_id, e.to_id, e.relation_type, -e.score)),
    )
    report = FrameInductionReport(
        format=FRAME_INDUCTION_FORMAT,
        version=FRAME_INDUCTION_VERSION,
        contexts_considered=len(contexts),
        candidate_groups=len(groups),
        accepted_frames=len(frames),
        rejected_insufficient_contexts=rej_contexts,
        rejected_insufficient_fillers=rej_fillers,
        rejected_no_shared_targets=rej_targets,
        generated_nodes=len(doc.nodes),
        generated_prediction_evidence=len(doc.evidence),
        frames=frames,
        notes=[
            "v0.22 induces one-slot text frames from repeated predictive contexts that differ in exactly one member position.",
            "Slot labels are provisional structural variables, not semantic type claims such as ENTITY unless separate evidence supports such a type.",
            "Frame predictions are derived evidence with explicit source-context provenance; original teacher/corpus evidence remains unchanged.",
            "Open-slot runtime matching is intentionally auditable and can be disabled independently from lexical/parent routing.",
        ],
    )
    return doc, report


def persist_frame_document(db: sqlite3.Connection, doc: ForgeDocument) -> None:
    # Keep this helper low-level so callers can wrap it in CanonicalDB transactions.
    from .database import CanonicalDB
    # We cannot construct CanonicalDB around an existing connection. Reuse the same
    # SQL invariants directly and intentionally fail on canonical collision.
    for node in sorted(doc.nodes, key=lambda n: (n.level, n.node_id)):
        db.execute(
            "INSERT OR IGNORE INTO nodes(node_id,modality,kind,level,surface,metadata_json) VALUES(?,?,?,?,?,?)",
            (node.node_id,node.modality,node.kind,node.level,node.surface,json.dumps(node.metadata,ensure_ascii=False,sort_keys=True)),
        )
        row = db.execute("SELECT modality,kind,level,surface FROM nodes WHERE node_id=?", (node.node_id,)).fetchone()
        if tuple(row) != (node.modality,node.kind,node.level,node.surface):
            raise ValueError(f"canonical collision for {node.node_id}")
        for pos, child in enumerate(node.members):
            db.execute("INSERT OR IGNORE INTO node_members(parent_id,position,child_id) VALUES(?,?,?)", (node.node_id,pos,child))
    # Use a temporary CanonicalDB-style fingerprint implementation without reopening.
    for e in doc.evidence:
        metadata_json = json.dumps(e.metadata, ensure_ascii=False, sort_keys=True)
        raw = json.dumps({
            "from":e.from_id,"to":e.to_id,"type":e.relation_type,
            "score":float(e.score),"confidence":float(e.confidence),
            "source":e.source.source_id,"version":e.source.source_version,
            "extraction":e.source.extraction,"metadata":e.metadata,
        },ensure_ascii=False,separators=(",",":"),sort_keys=True).encode("utf-8")
        fp = hashlib.sha256(raw).hexdigest()
        db.execute(
            "INSERT OR IGNORE INTO evidence(evidence_fingerprint,from_id,to_id,relation_type,score,confidence,source_id,source_version,extraction,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (fp,e.from_id,e.to_id,e.relation_type,float(e.score),float(e.confidence),e.source.source_id,e.source.source_version,e.source.extraction,metadata_json),
        )
