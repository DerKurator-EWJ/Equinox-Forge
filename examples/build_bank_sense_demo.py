from pathlib import Path
import sys, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.hidden_state import HiddenStateSample, HiddenStateConfig, load_probe_dataset, extract_contextual_hidden_evidence
from equinox_forge.database import CanonicalDB
from equinox_forge.ir import RelationEvidence, RelationType, SourceRef, NodeKind
from equinox_forge.sense_compiler import SenseCompilePolicy, FusionWeights, compile_provisional_senses, find_text_surface_id
from equinox_forge.io import save_document

class DemoBackend:
    backend_id='demo-hidden-fixture'
    def manifest(self): return {'backend_id':self.backend_id,'dimension':4}
    def contextual_state(self,text,target_start,target_end,layers,pooling):
        lo=text.lower()
        base=[1.0,.04,0,0] if any(k in lo for k in ['geld','kredit','konto','überweist']) else [.04,1.0,0,0]
        return [HiddenStateSample(layer=l,vector=base,token_count=1,metadata={'demo_fixture':True}) for l in layers]

out=ROOT/'out'; out.mkdir(exist_ok=True)
dbp=out/'bank_sense_demo.sqlite'
if dbp.exists(): dbp.unlink()
probes=load_probe_dataset([ROOT/'examples'/'probes'/'bank_senses.jsonl'])
doc,_,_=extract_contextual_hidden_evidence(DemoBackend(),probes,'demo-hidden','1',HiddenStateConfig(layers=(-1,),top_k=3,min_cosine=.2))
node_by_surface={n.surface:n for n in doc.nodes if n.kind==NodeKind.SURFACE.value and n.surface}
sem_pairs=[('Geld','Kredit'),('Kredit','Konto'),('Geld','Konto'),('Park','Baum'),('Baum','See'),('Park','See')]
with CanonicalDB(dbp) as db:
    for n in doc.nodes: db.upsert_node(n)
    for e in doc.evidence: db.add_evidence(e)
    src=SourceRef('demo-static','1','embedding_neighbours')
    for a,b in sem_pairs:
        for x,y in [(a,b),(b,a)]:
            db.add_evidence(RelationEvidence(node_by_surface[x].node_id,node_by_surface[y].node_id,RelationType.SEMANTIC_SIMILARITY.value,.9,.9,src,{'demo_fixture':True}))
    db.commit()
    target=find_text_surface_id(db.db,'Bank')
    policy=SenseCompilePolicy(threshold=.62,min_channels=2,min_contexts=2,weights=FusionWeights(hidden_similarity=.65,lexical_overlap=.05,semantic_similarity=.25,substitution=0,transition=0,prediction_signature=.05))
    senses,report=compile_provisional_senses(db.db,target,policy)
    save_document(senses,out/'bank_senses_v07.eqir.json')
    (out/'bank_senses_v07.report.json').write_text(json.dumps(report.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'db':str(dbp),'contexts':report.contexts_found,'clusters':report.clusters_created,'unresolved':report.unresolved_contexts,'sense_ids':[c['sense_id'] for c in report.clusters]},indent=2))
