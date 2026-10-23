from __future__ import annotations

from pathlib import Path
import json
import sys

from equinox_forge.database import CanonicalDB
from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig, extract_teacher_behaviour
from equinox_forge.frame_induction import FrameInductionPolicy, induce_relation_frames, persist_frame_document
from equinox_forge.prototype_hierarchy import PrototypeHierarchyPolicy, induce_prototype_hierarchy
from equinox_forge.hierarchical_frame_transfer import HierarchicalFrameTransferPolicy, promote_frames_to_higher_concepts
from equinox_forge.exception_induction import ExceptionInductionPolicy, induce_exception_overrides
from equinox_forge.exception_benchmark import ExceptionCase, benchmark_exception_overrides
from equinox_forge.canonical import make_text_surface
from equinox_forge.ir import ForgeDocument, RelationEvidence, RelationType, SourceRef
from equinox_forge.generalization import _pass_through_compression
from equinox_forge.compiler import CompilePolicy
from equinox_forge.runtime_pack import compile_base_pack, load_base_pack
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.io import save_document


class BaselineTeacher:
    backend_id = 'demo-v028-baseline'
    def manifest(self): return {'backend_id': self.backend_id, 'fixture': True}
    def next_token(self, prompt, top_k, temperature):
        table = {
            'Hund atmet': [(' Luft', .92), (' Sauerstoff', .08)],
            'Katze atmet': [(' Luft', .92), (' Sauerstoff', .08)],
            'Adler fliegt': [(' Himmel', .91), (' hoch', .09)],
            'Falke fliegt': [(' Himmel', .91), (' hoch', .09)],
        }
        return [TeacherCandidate(i+1,s,s,p,3-i) for i,(s,p) in enumerate(table[prompt.strip()][:top_k])]


class ExceptionTeacher:
    backend_id = 'demo-v028-exceptions'
    def manifest(self): return {'backend_id': self.backend_id, 'fixture': True}
    def next_token(self, prompt, top_k, temperature):
        table = {
            'Adler atmet': [(' Sauerstoff', .86), (' Luft', .14)],
            'Falke atmet': [(' Sauerstoff', .84), (' Luft', .16)],
        }
        return [TeacherCandidate(100+i,s,s,p,4-i) for i,(s,p) in enumerate(table[prompt.strip()][:top_k])]


def semantic_doc():
    names=['Hund','Katze','Adler','Falke','Eule','Stein']; nodes={}; surfaces={}
    for text in names:
        qs,n=make_text_surface(text)
        for q in qs: nodes[q.node_id]=q
        nodes[n.node_id]=n; surfaces[text]=n
    src=SourceRef('demo-v028-semantic','1','independent_semantic_fixture')
    pairs=[('Hund','Katze',.98),('Adler','Falke',.98),('Hund','Adler',.91),('Hund','Falke',.90),('Katze','Adler',.90),('Katze','Falke',.91),('Eule','Adler',.97),('Eule','Falke',.96),('Eule','Hund',.90),('Eule','Katze',.90),('Stein','Hund',.05),('Stein','Katze',.04),('Stein','Adler',.03),('Stein','Falke',.04)]
    ev=[RelationEvidence(surfaces[a].node_id,surfaces[b].node_id,RelationType.SEMANTIC_SIMILARITY.value,score,.99,src,{'independent_of_teacher':True}) for a,b,score in pairs]
    return ForgeDocument(nodes=sorted(nodes.values(),key=lambda n:(n.level,n.node_id)),evidence=ev)


def main(out_dir: str):
    root=Path(out_dir); root.mkdir(parents=True,exist_ok=True)
    db_path=root/'master.sqlite'; pack_path=root/'exception-demo.eqbase'
    if db_path.exists(): db_path.unlink()
    cfg=BehaviourProbeConfig(top_k=2,min_probability=0.0)
    base_doc,_,_=extract_teacher_behaviour(BaselineTeacher(),['Hund atmet','Katze atmet','Adler fliegt','Falke fliegt'],'demo-base','1',cfg)
    exc_doc,_,_=extract_teacher_behaviour(ExceptionTeacher(),['Adler atmet','Falke atmet'],'demo-exception','1',cfg)
    with CanonicalDB(db_path) as db:
        for doc in (base_doc,semantic_doc()):
            for n in doc.nodes: db.upsert_node(n)
            for e in doc.evidence: db.add_evidence(e)
        db.commit()
        fdoc,frep=induce_relation_frames(db.db,FrameInductionPolicy(enable_semantic_slot_typing=True,min_filler_coherence_score=.95,min_filler_pair_fraction=1.0,require_typed_slot=True,enable_latent_slot_prototype=True,prototype_classify_candidates=True,prototype_min_admission_score=.95,prototype_min_support_fillers=2,prototype_membership_confidence=1.0))
        persist_frame_document(db.db,fdoc); db.db.commit()
        hdoc,hrep=induce_prototype_hierarchy(db.db,PrototypeHierarchyPolicy(max_depth=1,min_cross_leaf_score=.85,score_decay_per_depth=0.0,min_score_floor=.85,min_cross_leaf_pair_fraction=1.0,membership_confidence=.95))
        persist_frame_document(db.db,hdoc); db.db.commit()
        tdoc,trep=promote_frames_to_higher_concepts(db.db,HierarchicalFrameTransferPolicy(min_ancestor_hops=1,max_ancestor_hops=2,min_path_edge_quality=.50,hierarchical_admission_min_path_score=.70))
        persist_frame_document(db.db,tdoc); db.db.commit()
        for n in exc_doc.nodes: db.upsert_node(n)
        for e in exc_doc.evidence: db.add_evidence(e)
        db.commit()
        odoc,orep=induce_exception_overrides(db.db,ExceptionInductionPolicy(min_exception_target_score=.70,min_disagreement_margin=.50,min_membership_quality=.80,min_prototype_path_quality=.50,max_prototype_hops=2))
        save_document(odoc,root/'exception-overrides.eqir.json')
        (root/'exception-overrides.report.json').write_text(json.dumps(orep.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        persist_frame_document(db.db,odoc); db.db.commit()
        comp=_pass_through_compression(db.db)
        manifest=compile_base_pack(db.db,pack_path,pack_id='v028-demo',pack_version=28,compression_run_id=comp.compression_run_id,include_metadata=True,relation_policy=CompilePolicy(min_score=0,min_confidence=0,min_sources=1))
        db_stats=db.stats()
    pack=load_base_pack(pack_path)
    policy=RuntimeCognitionPolicy(max_recall_nodes=64,max_recall_depth=2,max_predictions=4,min_prediction_score=0.0,enable_exact_context=False,enable_suffix_context=False,enable_lexical_seeds=False,enable_parent_routing=False,enable_relation_recall=False,enable_transition_prediction=False,enable_recalled_context_prediction=False,enable_direct_context_prediction=True,enable_frame_schema_matching=True,enable_semantic_slot_admission=True,enable_slot_prototype_admission=True,enable_hierarchical_slot_admission=True,enable_frame_specificity_override=True)
    bench=benchmark_exception_overrides(pack,[ExceptionCase('Eule atmet','Sauerstoff','held-out frame instance'),ExceptionCase('Hund atmet','Luft','general-rule control')],policy=policy)
    (root/'exception-benchmark.json').write_text(json.dumps(bench.to_dict(),ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    summary={'frames_initial':frep.accepted_frames,'recursive_concepts':hrep.generated_concepts,'hierarchical_frames':trep.frames_promoted,'exception_overrides':orep.overrides_induced,'baseline_accuracy':bench.baseline_top1_accuracy,'exception_accuracy':bench.exception_top1_accuracy,'improved_cases':bench.improved_cases,'regressed_cases':bench.regressed_cases,'runtime_nodes':len(pack.nodes),'runtime_relations':len(pack.relations),'base_bytes':pack_path.stat().st_size,'db_stats':db_stats,'roundtrip_valid':manifest.roundtrip_valid}
    (root/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))


if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else 'v028_exception_demo')
