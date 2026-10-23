from pathlib import Path
import tempfile, json
from equinox_forge.database import CanonicalDB
from equinox_forge.ir import IRNode, NodeKind, Modality
from equinox_forge.macro_discovery import MacroDiscoveryPolicy, discover_and_optionally_materialize


def add(db,nid,level,members=None):
    db.upsert_node(IRNode(nid,Modality.TEXT.value,NodeKind.COMPOSITE.value if members else NodeKind.SURFACE.value,level,nid,members or [],{}))

with tempfile.TemporaryDirectory() as td:
    dbp=Path(td)/'macro_discovery_demo.sqlite'
    with CanonicalDB(dbp) as c:
        for x in ['der','hund','ist','ein','tier','katze','auch','gross']:
            add(c,x,1)
        add(c,'s1',2,['der','hund','ist','ein','tier'])
        add(c,'s2',2,['die-katze','hund','ist','ein','tier'] if False else ['katze','hund','ist','ein','tier'])
        add(c,'s3',2,['gross','hund','ist','ein','tier'])
        c.commit()
        policy=MacroDiscoveryPolicy(min_pattern_size=2,max_pattern_size=4,min_occurrences=2,min_parent_structures=2,min_net_savings=1,min_compression_ratio=.1)
        report,run_id=discover_and_optionally_materialize(c.db,policy,materialize=True,materialize_limit=1)
        print(json.dumps({'run_id':run_id,'report':report.to_dict()},ensure_ascii=False,indent=2))
