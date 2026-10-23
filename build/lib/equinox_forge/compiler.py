from __future__ import annotations
from dataclasses import dataclass
import math
import sqlite3
from .ir import CompiledRelation

@dataclass
class CompilePolicy:
    min_score: float = 0.05
    min_confidence: float = 0.05
    min_sources: int = 1


def aggregate_relations(db: sqlite3.Connection, policy: CompilePolicy = CompilePolicy()) -> list[CompiledRelation]:
    rows = db.execute("""
      SELECT from_id,to_id,relation_type,score,confidence,source_id,source_version
      FROM evidence
      ORDER BY from_id,to_id,relation_type,evidence_id
    """).fetchall()
    buckets: dict[tuple[str,str,str], list[tuple[float,float,str]]] = {}
    for a,b,t,s,c,src,ver in rows:
        buckets.setdefault((a,b,t),[]).append((float(s),float(c),f"{src}@{ver}"))
    out: list[CompiledRelation] = []
    for (a,b,t), evs in buckets.items():
        conf_sum = sum(c for _,c,_ in evs)
        if conf_sum <= 0: continue
        score = sum(s*c for s,c,_ in evs)/conf_sum
        # Independent-evidence confidence baseline. Deterministic and replaceable later.
        confidence = 1.0 - math.prod(1.0-c for _,c,_ in evs)
        source_count = len({src for _,_,src in evs})
        if score < policy.min_score or confidence < policy.min_confidence or source_count < policy.min_sources:
            continue
        out.append(CompiledRelation(a,b,t,score,confidence,source_count,len(evs)))
    return out
