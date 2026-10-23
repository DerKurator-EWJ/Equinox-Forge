from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from equinox_forge.teacher_behavior import TeacherCandidate, BehaviourProbeConfig
from equinox_forge.runtime_cognition import RuntimeCognitionPolicy
from equinox_forge.frame_induction import FrameInductionPolicy
from equinox_forge.frame_schema_benchmark import FrameEvalCase, compile_and_benchmark_frame_schemas
from equinox_forge.canonical import make_text_surface
from equinox_forge.ir import ForgeDocument, RelationEvidence, RelationType, SourceRef
from equinox_forge.io import save_document

class Teacher:
    backend_id='typed-slot-demo-teacher'
    def manifest(self): return {'backend_id':self.backend_id,'fixture':True}
    def next_token(self,prompt,top_k,temperature):
        table={
            'Hund ist ein':[(' Tier',.82),(' Haustier',.12),(' Wesen',.06)],
            'Katze ist ein':[(' Tier',.82),(' Haustier',.12),(' Wesen',.06)],
            'Wolf ist ein':[(' Tier',.84),(' Wesen',.10),(' Raubtier',.06)],
            'Fuchs ist ein':[(' Tier',.84),(' Wesen',.10),(' Raubtier',.06)],
            'Mein Wolf ist ein':[(' Tier',.84),(' Wesen',.10),(' Raubtier',.06)],
            'Stein ist ein':[(' Objekt',.80),(' Material',.12),(' Ding',.08)],
        }
        vals=table[prompt.strip()][:top_k]
        return [TeacherCandidate(i+1,s,s,p,4.0-i) for i,(s,p) in enumerate(vals)]

def support_doc():
    nodes={}; surf={}
    for text in ['Hund','Katze','Wolf','Fuchs','Stein']:
        qs,n=make_text_surface(text)
        for q in qs:nodes[q.node_id]=q
        nodes[n.node_id]=n; surf[text]=n
    src=SourceRef('independent-semantic-graph','1','semantic_similarity_fixture')
    pairs=[('Hund','Katze',.92),('Wolf','Hund',.94),('Wolf','Katze',.90),('Fuchs','Hund',.91),('Fuchs','Katze',.89),('Stein','Hund',.08),('Stein','Katze',.06)]
    ev=[RelationEvidence(surf[a].node_id,surf[b].node_id,RelationType.SEMANTIC_SIMILARITY.value,score,.98,src,{'independent_of_frame_teacher':True}) for a,b,score in pairs]
    return ForgeDocument(nodes=sorted(nodes.values(),key=lambda n:(n.level,n.node_id)),evidence=ev)

out=ROOT/'examples'/'typed_slot_demo'
support=support_doc()
out.mkdir(parents=True,exist_ok=True)
save_document(support,out/'independent-semantic-support.eqir.json')
report=compile_and_benchmark_frame_schemas(
    Teacher(), ['Hund ist ein','Katze ist ein'],
    [FrameEvalCase('Wolf ist ein',True),FrameEvalCase('Fuchs ist ein',True),FrameEvalCase('Mein Wolf ist ein',True),FrameEvalCase('Stein ist ein',False)],
    out,'typed-slot-demo','1',
    probe_cfg=BehaviourProbeConfig(top_k=3,min_probability=0.0,evidence_confidence=.95),
    frame_policy=FrameInductionPolicy(enable_semantic_slot_typing=True,min_filler_coherence_score=.70,min_filler_pair_fraction=1.0,slot_admission_min_score=.70,slot_admission_min_support_fillers=2,require_typed_slot=True),
    cognition_policy=RuntimeCognitionPolicy(max_predictions=3,min_prediction_score=0.0,enable_semantic_slot_admission=True),
    runtime_top_k=3,support_documents=[support],pack_version=23,
)
print('pack_bytes',report.pack_bytes)
print('pack_nodes',report.pack_nodes)
print('pack_relations',report.pack_relations)
print('typed_precision',report.frame_applicability_precision)
print('typed_recall',report.frame_applicability_recall)
print('typed_top1',report.frame_only['top1_retention'])
print('open_top1',report.open_frame_baseline['top1_retention'])
for d in report.details:
    print(d.prompt,'teacher=',d.teacher_top1,'typed=',d.frame_only_top1,'open=',d.open_frame_top1,'matched=',d.frame_matched)
