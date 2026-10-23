from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .ir import IRNode, RelationEvidence

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS nodes(
  node_id TEXT PRIMARY KEY,
  modality TEXT NOT NULL,
  kind TEXT NOT NULL,
  level INTEGER NOT NULL,
  surface TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS node_members(
  parent_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  child_id TEXT NOT NULL,
  PRIMARY KEY(parent_id, position),
  FOREIGN KEY(parent_id) REFERENCES nodes(node_id),
  FOREIGN KEY(child_id) REFERENCES nodes(node_id)
);
CREATE TABLE IF NOT EXISTS evidence(
  evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  score REAL NOT NULL,
  confidence REAL NOT NULL,
  source_id TEXT NOT NULL,
  source_version TEXT NOT NULL,
  extraction TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_evidence_relation ON evidence(from_id,to_id,relation_type);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id,source_version);
CREATE TABLE IF NOT EXISTS source_aliases(
  source_id TEXT NOT NULL,
  source_version TEXT NOT NULL,
  external_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  PRIMARY KEY(source_id,source_version,external_id)
);
"""

class CanonicalDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def upsert_node(self, node: IRNode):
        self.db.execute(
            "INSERT OR IGNORE INTO nodes(node_id,modality,kind,level,surface,metadata_json) VALUES(?,?,?,?,?,?)",
            (node.node_id,node.modality,node.kind,node.level,node.surface,json.dumps(node.metadata,ensure_ascii=False,sort_keys=True)),
        )
        existing = self.db.execute("SELECT modality,kind,level,surface FROM nodes WHERE node_id=?",(node.node_id,)).fetchone()
        expected = (node.modality,node.kind,node.level,node.surface)
        if tuple(existing) != expected:
            raise ValueError(f"canonical collision for {node.node_id}: {existing} != {expected}")
        for pos, child in enumerate(node.members):
            self.db.execute("INSERT OR IGNORE INTO node_members(parent_id,position,child_id) VALUES(?,?,?)",(node.node_id,pos,child))

    def add_evidence(self, e: RelationEvidence):
        self.db.execute(
            "INSERT INTO evidence(from_id,to_id,relation_type,score,confidence,source_id,source_version,extraction,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (e.from_id,e.to_id,e.relation_type,float(e.score),float(e.confidence),e.source.source_id,e.source.source_version,e.source.extraction,json.dumps(e.metadata,ensure_ascii=False,sort_keys=True)),
        )

    def alias(self, source_id: str, source_version: str, external_id: str, node_id: str):
        self.db.execute("INSERT OR REPLACE INTO source_aliases VALUES(?,?,?,?)",(source_id,source_version,external_id,node_id))

    def commit(self): self.db.commit()

    def stats(self):
        q = lambda sql: self.db.execute(sql).fetchone()[0]
        return {"nodes":q("SELECT COUNT(*) FROM nodes"),"evidence":q("SELECT COUNT(*) FROM evidence"),"sources":q("SELECT COUNT(DISTINCT source_id||'@'||source_version) FROM evidence")}
