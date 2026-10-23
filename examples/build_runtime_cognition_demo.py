from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from equinox_forge.database import CanonicalDB
from equinox_forge.language_evidence import LanguageEvidenceConfig, build_controlled_language_evidence
from equinox_forge.macro_discovery import MacroDiscoveryPolicy
from equinox_forge.runtime_compression import MacroPromotionPolicy, compile_runtime_compression
from equinox_forge.runtime_pack import compile_base_pack
from equinox_forge.runtime_cognition import RuntimeCognition, RuntimeCognitionPolicy, load_prediction_cases, benchmark_predictions

OUT=Path(__file__).parent/'runtime_cognition_demo'
OUT.mkdir(exist_ok=True)
db=OUT/'demo.sqlite'; pack=OUT/'demo.eqbase'; report_path=OUT/'benchmark.json'
if db.exists(): db.unlink()
texts=[
 'Der Hund ist ein Tier.','Der Hund ist ein Tier.','Die Katze ist ein Tier.',
 'Der Hund kann bellen.','Der Hund kann bellen.',
 'Die Katze kann miauen.','Die Katze kann miauen.'
]
doc,_=build_controlled_language_evidence(texts,'demo-corpus','1',LanguageEvidenceConfig(max_context=3,min_phrase_count=2,evidence_confidence=.9))
with CanonicalDB(db) as c:
 for n in doc.nodes: c.upsert_node(n)
 for e in doc.evidence: c.add_evidence(e)
 c.commit()
 cr=compile_runtime_compression(c.db,
  MacroDiscoveryPolicy(min_pattern_size=2,max_pattern_size=4,min_occurrences=999,min_parent_structures=999,definition_overhead=1,min_net_savings=1,min_compression_ratio=0,prune_dominated=True),
  MacroPromotionPolicy(min_realized_occurrences=999,min_realized_parent_structures=999,definition_overhead=1,min_realized_net_savings=1,min_realized_compression_ratio=0,max_promotions=1),persist=True,materialize=True)
 manifest=compile_base_pack(c.db,pack,pack_id='v016-cognition-demo',pack_version=16,compression_run_id=cr.compression_run_id,include_metadata=False,persist=False,verify_roundtrip=True)
policy=RuntimeCognitionPolicy(max_recall_nodes=64,max_recall_depth=3,max_predictions=6)
cog=RuntimeCognition.from_path(pack,policy)
predictions={ctx:cog.predict(ctx).to_dict() for ctx in ['Der Hund ist ein','Der Hund kann','Die Katze kann']}
bench=benchmark_predictions(pack,load_prediction_cases([OUT/'cases.jsonl']),policy=policy,top_k=3)
payload={'manifest':manifest.to_dict(),'benchmark':bench.to_dict(),'predictions':predictions}
report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'pack':str(pack),'pack_bytes':pack.stat().st_size,'node_count':manifest.node_count,'relation_count':manifest.relation_count,'benchmark':bench.to_dict()},ensure_ascii=False,indent=2,sort_keys=True))
