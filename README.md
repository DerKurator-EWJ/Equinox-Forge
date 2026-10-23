# Equinox Forge v0.37 — Source Lineage / Correlated Evidence

v0.37 attacks pseudo-consensus caused by correlated teachers. Different `source_id`s no longer automatically count as independent evidence for relation-composition induction or lifecycle promotion. Forge can now register explicit parent/child source ancestry, resolve transitive roots, cluster sources that share ancestry, and count those clusters as conservative independent lineage components.

Frozen controls:

```text
3 sibling source IDs -> 1 effective lineage -> no stable induction
3 sources across 2 disjoint roots -> 2 effective lineages -> stable induction allowed
multi-parent blend + its ancestor families -> 1 correlated component
```

Lifecycle novelty is lineage-aware as well:

```text
support_1               -> candidate
same-lineage aliases    -> candidate
new independent lineage -> stable
conflict_1              -> contested
same-lineage aliases    -> contested
new conflict lineage    -> quarantined
```

Unregistered sources remain backward-compatible and are treated as independent roots of themselves.

Run:

```bash
eqforge-source-lineage --out out/v0_37_source_lineage
```

See `RELEASE_V0_37.md` and `benchmarks/v0_37/`.

---

## Previous milestone — v0.36 Composition Hypothesis Lifecycle

v0.36 adds persistent governance for the relation-composition programs introduced in v0.35. A program that is strong in one induction rebuild is no longer automatically authoritative at runtime. Single-run induction status and persistent lifecycle status are now separate concepts.

The frozen lifecycle benchmark drives one automatically induced program through:

```text
support_1   -> candidate  -> runtime ABSTAIN
support_2   -> stable     -> Hund wohnt in -> Haus
conflict_1  -> contested  -> runtime ABSTAIN
conflict_2  -> quarantined-> runtime ABSTAIN
recovery_1  -> candidate  -> runtime ABSTAIN
recovery_2  -> stable     -> Hund wohnt in -> Haus
```

Promotion and quarantine require **source-novel evidence epochs**. Replaying the same support set does not manufacture stability, and replaying the same conflict set does not manufacture quarantine. Only lifecycle `stable` programs are exposed to the default runtime as executable relation-composition schemas.

Persistent state is stored in `composition_hypothesis_runs` and `composition_hypothesis_states`, including support/conflict streaks, missed rebuilds, source-set history, and stable hypothesis identity across rebuilds.

Run:

```bash
eqforge-composition-lifecycle --out out/v0_36_composition_lifecycle
```

See `RELEASE_V0_36.md` and `benchmarks/v0_36/`.

---

## Previous milestone — v0.35 Automatic Relation Composition Induction

v0.35 removes the fixture-authored composition schema used by v0.34. Forge now discovers a one-slot relation pattern and a reusable semantic path program from repeated direct observations plus an independently represented semantic graph.

The deterministic induction fixture observes only:

```text
Katze wohnt in     -> Haus
Kaninchen wohnt in -> Bau
Fuchs wohnt in     -> Bau
```

Forge is **not** given the schema `[SLOT_0] wohnt in` or the program `is_a -> property`. It groups prompts by invariant token structure, identifies the varying slot, searches graph paths from each filler to its observed target, and promotes only a dominant path signature that satisfies support, source-diversity, coverage and quality thresholds.

The positive run induces:

```text
[SLOT_0] wohnt in
    => is_a(out) -> property(out)
```

The direct observations are then left out of the evaluated runtime BASE. The induced schema plus the semantic graph transfer to the held-out entity:

```text
Hund --is_a--> Haustier --property--> Haus
Hund wohnt in  -> Haus
Stein wohnt in -> ABSTAIN
```

Frozen ladder result: **L0–L5 = 1.0**.

Necessary controls remain conservative:

- three examples attributed to the same source do not become `stable`;
- incomplete path coverage does not become `stable`;
- equally supported competing programs become `contested` rather than being selected arbitrarily;
- the held-out `Hund wohnt in` example is absent from the induction observations;
- direct induction observations are not compiled as runtime prediction edges.

Run:

```bash
eqforge-relation-induce --out out/v0_35_relation_composition_induction
```

See `RELEASE_V0_35.md` and `benchmarks/v0_35/`.

---

## Previous milestone — v0.34 Evidence-Backed Relation Composition

v0.34 attacks the frozen L5 relation-family case without allowing opaque zero-shot guessing. A relation family that was never compiled as direct `PREDICTION` evidence may execute only when the BASE already contains both an explicit stable **relation-composition schema** and the complete non-predictive semantic path required by that schema.

The deterministic fixture uses:

```text
query schema: [SLOT_0] wohnt in
semantic path: Hund --is_a--> Haustier --property--> Haus

Hund wohnt in  -> Haus
Stein wohnt in -> ABSTAIN
```

Against the v0.34 benchmark:

- L0–L4 remain `1.0`;
- the frozen L5 prompt rises from `0.0` to **`1.0`** only with schema + complete path;
- graph-only, schema-only and runtime-ablation controls remain `0.0`;
- an entity with an incomplete path (`Stein wohnt in`) abstains;
- an unmatched phrase (`Hund wohnt aus`) abstains.

This does **not** claim that Equinox can invent a genuinely unknown relation. The v0.34 schema is fixture-authored and compiled explicitly; automatic induction is a later research problem. L5 here means held out from direct predictive training, not absent from every representation in the BASE.

Run:

```bash
eqforge-relation-compose --out out/v0_34_relation_composition
```

See `RELEASE_V0_34.md` and `benchmarks/v0_34/`.

---

## Previous milestone — v0.33 Evidence-Backed Novel Entity Admission

v0.33 restored conservative L4 transfer by requiring independent compiled semantic evidence for a novel entity. `Wolf ist ein -> Tier` is admitted only when semantic support exists; `Stein ist ein` and a surface-only `Wolf` control abstain. The historical benchmark remains available through `eqforge-novel-entity`.

## Previous milestone — v0.32 Support-Gated Prediction

v0.32 separates **recall** from **prediction authority**. Associative recall may still surface related predictive contexts, but a recalled context may execute a `PREDICTION` relation only when the live query provides enough structural support.

The release directly attacks the v0.31 failure where known tokens in unsupported combinations produced confident-looking outputs. Against the unchanged v0.31 gauntlet cases:

- L0 exact replay: `1.0`
- L1 known-suffix transfer: `1.0`
- L2 known-parts recombination: `1.0`
- L3 novel order / known lexicon: `1.0`
- L4 lexical-only novel entity: `0.0` (intentionally no longer guessed)
- L5 held-out relation family: `0.0`
- unsupported-query rejection: `1.0` (was `0.25`)
- unsupported known/mixed recombination rejection: `1.0` (was `0.0`)
- typed-frame precision / recall: `1.0 / 1.0`

The important scientific correction is the pair `Wolf ist ein` vs. `Stein ist ein`: in the generic ladder pack both are one unseen entity plus the same known suffix `ist ein`. Without independent semantic admission, there is no runtime-visible justification for accepting one and rejecting the other. v0.32 abstains on both in lexical-only transfer. The separately typed frame/prototype path still admits semantically supported `Wolf`/`Fuchs` and rejects `Stein`.

Run the v0.32 benchmark with:

```bash
eqforge-support-gate --out out/v0_32_support_gate
```

The historical v0.31 baseline remains reproducible with:

```bash
eqforge-gauntlet --out out/v0_31_baseline_gauntlet
```

See `RELEASE_V0_32.md` and `benchmarks/v0_32/`.

---

## Previous milestone — v0.31 Baseline Gauntlet

v0.31 added no cognitive mechanism. It froze the adversarial benchmark that exposed unsupported lexical recombination false positives. The original case set and baseline metrics remain unchanged under `benchmarks/v0_31/`, and `eqforge-gauntlet` intentionally executes the historical v0.31 cognition semantics for reproducibility.

---


## Previous milestone — v0.30 Engineering Freeze

v0.30 deliberately adds **no new cognitive mechanism**. It freezes the v0.29 behaviour as a reproducible engineering baseline before the next scaling phase.

The release focuses on four things:

- deterministic package installation and explicit package discovery;
- a version-independent regression runner with per-test timing and failure reporting;
- a frozen benchmark contract for accuracy, generalization, rejection, runtime work, storage and compile cost;
- release-consistency checks so code, package metadata and benchmark definitions cannot silently drift.

The scientific purpose of this milestone is simple: from v0.30 onward, a change is not considered an improvement merely because it adds capability. It must be measured against an unchanged reference contract.

## Frozen v0.30 evaluation families

The benchmark contract defines the following families:

1. exact retention / replay control;
2. held-out surface transfer;
3. compositional / hierarchical transfer;
4. false-positive and unknown rejection;
5. specificity and exception handling;
6. consensus / conflict lifecycle;
7. runtime work and index routing;
8. pack size, compile time and knowledge retained per byte.

See `benchmarks/v0_30/benchmark_contract.json`. Later releases may **add** benchmark cases, but the frozen v0.30 cases/metric meanings must not be rewritten to make a newer system look better.

## Regression suite

```bash
python tests/run_all.py
```

The runner discovers every `test_*.py` file, executes each in a fresh Python process, records wall time, continues after failures, and exits non-zero if any test fails. A machine-readable summary can be written with:

```bash
python tests/run_all.py --json-out out/test_summary.json
```

## Installation

```bash
python -m pip install -e .
eqforge --help
```

v0.30 explicitly limits setuptools package discovery to `equinox_forge*`; repository directories such as `out/` and `adapters/` can no longer be mistaken for import packages.

For the milestone-specific release notes see `RELEASE_V0_30.md`. Historical documentation is retained below.

---

# Historical milestone documentation — v0.28 Automatic Exception / Override Induction

v0.28 learns **specific subtype overrides** from systematic residual behaviour against a broader hierarchical rule.

The key constraint is that the subtype must already exist independently in the compiled Equinox concept hierarchy. The exception target is not allowed to define its own class.

Example:

```text
existing broad rule:
Concept_ROOT / [SLOT] atmet → Luft

existing subtype from independent semantic evidence:
Adler ─┐
       ├→ Concept_Bird → Concept_ROOT
Falke ─┘

new concrete observations:
Adler atmet → Sauerstoff
Falke atmet → Sauerstoff

v0.28:
Concept_Bird / [SLOT] atmet → Sauerstoff   # provisional override
```

The general frame is retained unchanged. Runtime precedence is still handled by v0.27 specificity resolution, so the direct subtype override suppresses the broader inherited frame only for fillers admitted to that subtype.

## Default acceptance contract

An override requires:

- at least 2 concrete matching contexts;
- at least 2 unique fillers;
- an already compiled latent subtype prototype;
- an `IS_A` path from that subtype to the broad frame's higher concept;
- consistent target support across the subtype contexts;
- a configurable score margin over the broad rule's target inside the subtype;
- a different subtype Top-1 target by default.

A single anomaly therefore cannot create an exception under the default policy.

## Runtime ablation

`RuntimeCognitionPolicy.enable_exception_override_frames` can disable automatic exception frames on the same immutable `.eqbase`. Disabled exception frames are excluded from direct matching **and** parent/relation recall, so the baseline cannot leak through the same override node.

## CLI

```bash
eqforge induce-exceptions master.sqlite overrides.eqir.json \
  --min-contexts 2 \
  --min-unique-fillers 2 \
  --min-exception-target-score 0.50 \
  --min-disagreement-margin 0.20 \
  --persist
```

Benchmark the same pack with automatic exception frames disabled versus enabled:

```bash
eqforge benchmark-exceptions knowledge.eqbase cases.jsonl
```

## Deterministic fixture

The v0.28 fixture first compiles:

```text
Hund atmet  → Luft
Katze atmet → Luft

Adler/Falke form a separate latent subtype under the same higher concept.
```

Only after that hierarchy exists, two new observations are added:

```text
Adler atmet → Sauerstoff
Falke atmet → Sauerstoff
```

Forge induces one bird-subtype override. `Eule` is semantically known and already classified into the bird prototype, but **`Eule atmet` is never observed during induction**. With all alternate runtime routes disabled:

```text
without automatic exception frames:
Eule atmet → Luft
Hund atmet → Luft
accuracy = 50 %

with v0.28 exception frames:
Eule atmet → Sauerstoff
Hund atmet → Luft
accuracy = 100 %
```

The override itself is learned only from `Adler atmet` and `Falke atmet`. No held-out `Eule atmet` answer is used to define the subtype or the override, so this fixture tests transfer of the learned exception to a new member of the already known subtype.

## Non-claims

- v0.28 does not prove human-like exception learning.
- The induced override is provisional derived knowledge, not an asserted universal truth.
- This first implementation supports one-slot text frames and already compiled latent subtype prototypes.
- It does not yet model temporal exception decay, contradictory exception sources, or confidence hysteresis across repeated rebuilds.

---

## Previous milestone: v0.27

v0.27 adds explicit **specificity precedence** to compiled frame schemas. Once a general rule has been promoted to a higher latent concept, it must not drown out a more specific lower-concept rule merely because the general rule has a larger raw prediction score.

## Runtime precedence

The runtime already resolves an exact predictive context before frame matching. v0.27 now adds a second categorical precedence layer among equal-width frames:

```text
exact compiled context
        >
direct / lower-prototype frame
        >
hierarchically transferred frame
        >
untyped open frame
```

This is **override semantics**, not another score bonus. If a direct subtype frame and a broader inherited frame both admit the same live filler, the broader frame is suppressed and contributes no prediction score. Frames tied at the same specificity scope may still ensemble normally.

## Why this matters

A hierarchy becomes behaviorally useful only if it can express both inheritance and exceptions. In the deterministic fixture, the broad inherited frame predicts `Luft` with a higher raw score, while a bird-specific lower-scope frame predicts `Himmel` with a deliberately lower raw score.

Without v0.27 specificity resolution:

```text
Adler atmet → Luft      # broad rule wins by score
```

With v0.27:

```text
Adler → bird prototype
      → specific frame
      → Himmel           # specific rule overrides broader inherited rule
```

The same immutable `.eqbase` is used for both runs; only the runtime specificity switch changes.

## Auditability

Frame admission diagnostics now expose:

- `specificity_scope_class`;
- `specificity_scope_rank`;
- `specificity_ancestor_hops`;
- `suppressed_by_specificity`;
- `specificity_suppressed_by`;
- `specificity_winner_frame_ids`.

Runtime work metrics additionally report `frame_specificity_suppressed`.

## Benchmark CLI

```bash
eqforge benchmark-specificity knowledge.eqbase cases.jsonl \
  --disable-exact-context \
  --disable-suffix-context \
  --disable-lexical-seeds \
  --disable-parent-routing \
  --disable-relation-recall \
  --disable-transition-prediction \
  --disable-recalled-context-prediction
```

The benchmark compares legacy equal-width frame aggregation (`enable_frame_specificity_override=False`) against v0.27 resolution on the same pack and reports changed/improved/regressed Top-1 cases plus suppressed broader frames.

## Scope / non-claims

- v0.27 does not learn exceptions automatically; it resolves conflicts once specific and general compiled rules coexist.
- Scope rank is categorical runtime precedence, not a probability or truth score.
- Exact contexts retain priority because they are resolved before frame schemas.
- Equal-specificity conflicts remain an ensemble/ranking problem and are intentionally not silently collapsed.

---

## Previous milestone: v0.26
v0.26 is the first milestone that tests whether a recursively induced higher concept is **useful for behavior**, not merely representable.

## Core result

A frame learned only from one lower subtype can be promoted to an already-grounded higher latent concept:

```text
Hund / Katze  → Concept_A ─┐
                           ├─→ Concept_ROOT
Adler / Falke → Concept_B ─┘

original frame:
[SLOT:Concept_A] atmet → Luft

promoted frame:
[SLOT:Concept_ROOT] atmet → Luft
```

`Adler atmet` was never compiled as a predictive context. With ordinary v0.24 direct-prototype admission it remains unresolved. With v0.26 hierarchical admission the runtime follows:

```text
Adler --is_a→ Concept_B --is_a→ Concept_ROOT
```

and may therefore reuse the promoted `… atmet → Luft` frame.

A known lexical counterexample (`Stein`) that has no compiled path into the higher concept is rejected.

## What is new

- `hierarchical_frame_transfer.py`;
- non-destructive promotion of prototype-typed frames to reachable `recursive_latent_concept` ancestors;
- no new prediction targets are introduced during promotion;
- transferred slots persist their base prototype, selected higher concept, compile-time path and path quality;
- runtime multi-hop `IS_A` admission for frame slots;
- bounded hop count and minimum path-quality threshold;
- auditable runtime admission trace (`hierarchical_prototype_membership`);
- CLI: `promote-hierarchical-frames`;
- isolated v0.26 regression proving that the higher concept enables a transfer that the lower prototype alone cannot make.

## Deliberate limitation

A higher latent concept is still not automatically a human ontology label. v0.26 only shows that an evidence-grounded higher class can function as a reusable admission boundary for a frame. Whether that boundary is semantically useful at scale must be measured on broader held-out data.

## Controlled fixture

The v0.26 demo compiles only these predictive contexts:

```text
Hund atmet  → Luft
Katze atmet → Luft
Adler fliegt → Himmel
Falke fliegt → Himmel
```

Independent semantic evidence induces two lower prototypes and one shared higher concept. The `… atmet` frame is then promoted from the Hund/Katze prototype to the higher concept without adding any `Adler atmet` or `Falke atmet` prediction evidence.

Isolated runtime result (all exact/suffix/lexical/parent/relation recall paths disabled):

```text
old direct-prototype admission:
Adler atmet → unresolved
Falke atmet → unresolved

v0.26 hierarchical admission:
Adler atmet → Luft
Falke atmet → Luft
Stein atmet → abstain
```

For both successful transfers the runtime admission trace contains a two-hop path:

```text
surface → lower prototype → higher recursive concept
```

Demo pack:

```text
runtime nodes:      50
relations:          28
pack bytes:     16,068
promoted frames:     2
```

These values are fixture diagnostics, not a general performance or semantic-accuracy claim.

## CLI

```bash
eqforge promote-hierarchical-frames master.sqlite hierarchical-frames.eqir.json \
  --min-path-edge-quality 0.50 \
  --admission-min-path-score 0.70 \
  --persist
```


---

# Equinox Forge v0.25 — Prototype Hierarchy / Recursive Concept Induction

**Current milestone:** v0.25 lets Equinox concepts become the inputs of a higher abstraction step. v0.24 created a latent class from surface fillers; v0.25 can now merge independently supported latent classes into new concept nodes, then recursively repeat the same operation.

## Core transition

```text
Hund / Katze      → Concept_A ─┐
                              ├─→ Concept_AB ─┐
Adler / Falke      → Concept_B ─┘              │
                                             ├─→ Concept_ROOT
Lachs / Forelle    → Concept_C ─┐              │
                              ├─→ Concept_CD ─┘
Eiche / Buche      → Concept_D ─┘
```

The names remain intentionally latent (`Concept_*`). Forge does **not** assert labels such as `animal`, `organism`, or any other ontology term unless separate evidence grounds those labels.

## What v0.25 adds

- `recursive_latent_concept` nodes whose members are already-derived concept nodes;
- deterministic recursive concept IDs;
- complete-link concept merging: every child concept in a merge must be independently compatible with every other child concept;
- independent grounding through the underlying leaf fillers rather than concept names or graph position;
- depth-aware semantic thresholds with a hard configurable floor;
- explicit `child_concept --is_a→ parent_concept` evidence;
- full leaf-support provenance on every higher concept;
- non-overlapping leaf support by default, preventing a concept from "proving" a parent using the same leaves twice;
- recursive iteration until no further supported merge exists or `max_depth` is reached;
- generic `.eqbase` relation traversal through `RuntimeIndex.traverse_relation(...)`;
- CLI command `induce-prototype-hierarchy`;
- standalone hierarchy IR/report and a reproducible demo pack.

## Why the recursion is evidence-grounded

A higher concept is **not** created merely because two children are already `Concept_*` nodes.

For two child concepts `A` and `B`, Forge inspects their underlying leaf fillers and measures independent semantic support across the cross product:

```text
leaves(A) × leaves(B)
```

A merge requires:

```text
cross-pair support fraction >= configured minimum
and
mean cross-leaf score >= threshold(depth)
```

By default the threshold may relax with abstraction depth, but never below a hard floor:

```text
threshold(depth) = max(
    min_score_floor,
    min_cross_leaf_score - (depth-1) * score_decay_per_depth
)
```

This is a compiler policy, not an ontological claim. The full threshold and cross-leaf statistics are stored in node metadata and the induction report.

## Controlled recursive fixture

The v0.25 regression starts with **four** independently induced v0.24 prototypes. Independent semantic evidence is constructed so that:

- at depth 1, prototype A can merge only with B;
- prototype C can merge only with D;
- cross-group support is deliberately below the depth-1 threshold;
- at depth 2, the broader threshold admits the two parent concepts into one root.

Result:

```text
base prototypes:          4
recursive concepts:       3
  depth 1:                2
  depth 2:                1
derived IS_A memberships: 6
highest hierarchy depth:  2
```

The resulting demo `.eqbase` contains:

```text
71 runtime nodes
66 compiled relations
17,933 bytes
```

All four base prototypes reach the same root through two compiled `IS_A` steps.

For this synthetic fixture, indexed relation traversal reports:

```text
scan-style work model: 198 units
indexed traversal:       5 units
reduction:             97.47 %
```

That number is a deterministic fixture/work-unit comparison, **not** a general CPU, latency, or energy claim.

## CLI

```bash
eqforge induce-prototype-hierarchy master.sqlite hierarchy.eqir.json \
  --min-cross-leaf-score 0.88 \
  --score-decay-per-depth 0.10 \
  --min-score-floor 0.68 \
  --min-cross-leaf-pair-fraction 1.0 \
  --max-depth 4 \
  --persist
```

Optional `--relation-type` flags can select the independent semantic channels used to support recursive abstraction.

## Runtime traversal

The compiled BASE can now traverse a concept hierarchy without consulting SQLite:

```python
rows, metrics = runtime_index.traverse_relation(
    concept_id,
    "is_a",
    max_depth=4,
)
```

This primitive is generic and can later support other recursively compiled relation hierarchies.

## Boundary

v0.25 proves that the current Forge representation can **construct and navigate recursively composed concepts**. It does not yet show that the resulting latent hierarchy corresponds to human ontology, improves held-out reasoning, or is the optimal hierarchy for a large knowledge base.

The next scientific question is whether higher concepts become useful rather than merely structurally valid: can they support new frame admission, prediction, routing, and held-out transfer that lower concepts alone cannot provide?

---
# Equinox Forge v0.24 — Slot Prototype / Latent Class Induction

**Current milestone:** v0.24 turns a coherent typed slot filler cohort into a reusable provisional Equinox concept. Instead of asking at runtime whether a new filler is independently similar to every observed filler, Forge can compile a latent class once and preclassify independently known surfaces into it.

## Core transition

```text
Hund ─┐
Katze ├─→ Concept_X   (latent_slot_prototype)
      ┘

Wolf  --is_a→ Concept_X
Fuchs --is_a→ Concept_X
Stein          ✗

[SLOT:Concept_X] ist ein → Tier
[SLOT:Concept_X] braucht → Futter
```

The class is **provisional** and evidence-derived. `Concept_X` is not automatically renamed to a human ontology label such as `animal`; that would require additional independent evidence.

## What v0.24 adds

- `latent_slot_prototype` concept nodes derived from coherent slot fillers
- deterministic prototype IDs from the filler cohort and semantic relation schema
- prototype reuse across multiple frame schemas with the same filler cohort
- offline candidate classification from independent semantic relations
- compiled `candidate --is_a→ prototype` membership evidence
- slot metadata now optionally points to a single latent prototype instead of directly carrying all filler nodes as structural members
- runtime admission can use one indexed `(candidate, prototype, is_a)` lookup
- optional fallback to the v0.23 pairwise candidate↔filler admission path
- audit metadata for support fillers, thresholds, per-candidate support scores and provisional class membership
- no held-out teacher answers or evaluation labels participate in prototype induction

## Controlled fixture

Compile-time predictive contexts:

```text
Hund ist ein   → Tier
Katze ist ein  → Tier
Hund braucht   → Futter
Katze braucht  → Futter
```

Independent semantic knowledge links `Wolf` and `Fuchs` strongly to both observed fillers, while `Stein` is weakly related.

Forge derives **one** latent prototype and reuses it in both frames. It compiles four memberships:

```text
Hund  --is_a→ Concept_X
Katze --is_a→ Concept_X
Wolf  --is_a→ Concept_X
Fuchs --is_a→ Concept_X
```

No `Stein --is_a→ Concept_X` edge is emitted.

At runtime, `Wolf ist ein` is admitted via the prototype membership edge. `Stein ist ein` structurally matches the wildcard frame but is rejected with `insufficient_prototype_membership`.

## Why this is different from v0.23

v0.23 stores an admission profile over observed fillers and may evaluate a candidate against those fillers at runtime:

```text
Wolf ↔ Hund
Wolf ↔ Katze
```

v0.24 can move that work offline:

```text
compile time:
  Wolf ↔ {Hund, Katze}
        ↓
  Wolf --is_a→ Concept_X

runtime:
  lookup(Wolf, Concept_X, is_a)
```

The runtime therefore consumes an Equinox-native higher abstraction rather than replaying the original pairwise evidence every time.

## Boundary

A completely unknown surface still cannot be assigned to `Concept_X` from nothing. v0.24 classifies surfaces for which independent semantic evidence is already available at compile time. Dynamic/on-device extension of a latent class remains a later step.

## CLI

Frame induction can enable prototypes with:

```bash
eqforge induce-frames master.sqlite frames.eqir.json \
  --semantic-slot-typing \
  --require-typed-slot \
  --latent-slot-prototype \
  --prototype-min-admission-score 0.70 \
  --prototype-min-support-fillers 2 \
  --persist
```

The frame benchmark exposes the same compiler controls and additionally supports `--disable-slot-prototype-admission` to compare the same BASE against the v0.23 pairwise admission path.

## Verification

The v0.24 regression verifies:

- v0.22 open frame behavior remains compatible
- v0.23 typed pairwise admission remains compatible
- two frames with the same filler cohort share exactly one prototype
- `Wolf` and `Fuchs` receive compiled `is_a` memberships
- `Stein` receives no membership
- runtime admission uses the prototype path with one indexed membership lookup per resolved candidate surface
- the prototype path remains functional even when normal semantic-recall relation weights are disabled

---

# Equinox Forge v0.23 — Typed Slot Constraints / Semantic Admission

**Current milestone:** v0.23 keeps the explicit frame schemas from v0.22, but a slot can now carry a compiled, auditable **semantic admission profile**. Structural fit alone is no longer sufficient for a typed slot to fire.

The new path is:

```text
Hund ist ein  ─┐
                ├─ repeated frame ─→ [SLOT_0] ist ein → Tier
Katze ist ein ─┘                         │
                                        ├─ observed fillers: Hund, Katze
                                        ├─ semantic filler coherence
                                        ├─ min candidate score
                                        └─ min independent filler support

independent semantic BASE:
Wolf  ↔ Hund / Katze   strong
Fuchs ↔ Hund / Katze   strong
Stein ↔ Hund / Katze   weak

runtime:
Wolf ist ein  → admitted → Tier
Fuchs ist ein → admitted → Tier
Stein ist ein → rejected → abstain
```

The semantic evidence is deliberately **independent from the frame teacher**. The held-out answers (`Tier`, `Objekt`, etc.) are never used to decide slot admission.

## What v0.23 adds

- optional semantic typing during frame induction;
- compiled slot metadata containing:
  - profile filler node IDs and surfaces,
  - allowed semantic relation channels,
  - filler-coherence statistics,
  - minimum candidate compatibility,
  - minimum number of supporting fillers;
- current supported admission channels: `semantic_similarity`, `substitution`, `contextual_similarity` (configurable);
- runtime semantic admission before a structurally matching frame can become a predictive context;
- bidirectional relation checking, so a semantic edge may be stored from candidate→filler or filler→candidate;
- hard rejection when a typed slot filler is unknown or insufficiently supported;
- explicit runtime switch `enable_semantic_slot_admission`;
- per-query admission diagnostics, including support scores and rejection reason;
- `open_frame_baseline` on the same immutable BASE, allowing direct comparison with v0.22 behavior;
- optional independent `--support-ir` documents in the frame benchmark;
- CLI controls for coherence/admission thresholds and required support count.

## Important boundary

v0.23 does **not** claim that Equinox can type a concept that is completely absent from its knowledge base.

If `Wolf` is neither a known surface nor linked by any independent semantic evidence, the runtime cannot infer its class from nothing. The correct v0.23 experiment is therefore:

```text
known concept: Wolf
unseen relation-context: "Wolf ist ein"
```

rather than pretending that a totally unknown word is semantically understood.

This distinction is central to the benchmark.

## Deterministic typed-slot fixture

Frame teacher compile data:

```text
Hund ist ein  → Tier / Haustier / Wesen
Katze ist ein → Tier / Haustier / Wesen
```

Independent semantic support:

```text
Hund ↔ Katze       strong
Wolf → Hund/Katze  strong
Fuchs→ Hund/Katze  strong
Stein→ Hund/Katze  weak
```

Held-out predictive contexts:

```text
Wolf ist ein
Fuchs ist ein
Mein Wolf ist ein
Stein ist ein
```

The complete contexts above are **not** compiled as predictive contexts.

Measured fixture result:

```text
induced typed frames                 1
BASE nodes                          35
BASE relations                      16
BASE bytes                       3,509

typed slot applicability recall    100 %
typed slot applicability precision 100 %

Wolf ist ein       → Tier   ✓
Fuchs ist ein      → Tier   ✓
Mein Wolf ist ein  → Tier   ✓
Stein ist ein      → no frame prediction
```

For comparison, disabling only semantic admission on the **same BASE** restores the old open-slot behavior:

```text
Stein ist ein → Tier   ✗
```

The top-1 retention number remains 75% in both modes because v0.23 deliberately abstains on the negative case rather than inventing the teacher's unseen answer `Objekt`. The meaningful improvement here is therefore **false-positive suppression / applicability precision**, not fabricated answer coverage.

## Admission semantics

For a candidate filler, runtime compatibility is computed only from compiled semantic relations to the slot's observed fillers. In v0.23 the effective pair quality is:

```text
relation score × relation confidence
```

A candidate must reach `min_candidate_score` for at least `min_support_fillers` profile fillers.

Observed training fillers are admitted directly. A typed candidate that lacks enough semantic support is rejected even if the surface pattern itself matches perfectly.

The admission profile remains marked provisional; it is not an ontological truth label.

## CLI

Induce typed frames from an existing DB that already contains semantic evidence:

```bash
eqforge induce-frames master.sqlite frames.eqir.json \
  --semantic-slot-typing \
  --require-typed-slot \
  --min-filler-coherence-score 0.70 \
  --slot-admission-min-score 0.70 \
  --slot-admission-min-support-fillers 2 \
  --persist
```

Benchmark with a local teacher plus one or more independent support IR files:

```bash
eqforge benchmark-frames /path/to/model out/typed-frame-test \
  --train train-prompts.txt \
  --eval-jsonl frame-eval.jsonl \
  --support-ir semantic-support.eqir.json \
  --source-id teacher-A \
  --semantic-slot-typing \
  --require-typed-slot \
  --min-filler-coherence-score 0.70 \
  --slot-admission-min-score 0.70 \
  --slot-admission-min-support-fillers 2
```

For an explicit v0.22-style baseline on the same typed pack:

```bash
# benchmark report already includes open_frame_baseline
# or disable enforcement explicitly:
--disable-semantic-slot-admission
```

## What this proves — and what it does not

The deterministic fixture supports the narrow engineering claim that a compiled frame can use **independent semantic relations** to suppress structurally valid but semantically unsupported fillers.

It does not prove robust natural-language type induction, ontology learning, or broad semantic understanding. The next open problem is how to replace pairwise filler similarity with more stable learned **slot concepts / class prototypes**, especially when fillers are numerous, polysemous, cross-lingual, or only indirectly related.

---

Historical documentation from v0.22 and earlier remains below.

# Equinox Forge v0.22 — Relation / Frame Schema Induction

**Current milestone:** v0.22 turns repeated concrete predictive contexts into explicit provisional relational frames and makes those frames executable in the compiled `.eqbase` runtime.

The new path is:

```text
Hund ist ein  ─┐
                ├─ shared structure + shared prediction ─→ [SLOT_0] ist ein → Tier
Katze ist ein ─┘
                                                     ↓
                                             compiled .eqbase
                                                     ↓
                                             Wolf ist ein
                                                     ↓
                                                   Tier
```

The slot is deliberately called `SLOT_0`, **not `ENTITY`**. Two fillers such as `Hund` and `Katze` are enough to justify a structural variable in a repeated frame, but not enough to prove an ontological type. The frame remains marked `provisional` and preserves its source-context provenance.

## What v0.22 adds

- automatic one-slot frame induction from predictive `TEMPLATE` contexts;
- a required minimum number of supporting contexts and distinct fillers;
- target agreement thresholds so unrelated contexts do not automatically form a frame;
- explicit slot concept nodes with the concrete fillers that induced them;
- deterministic frame IDs and derived `prediction` evidence;
- provenance back to every concrete source context;
- runtime frame indexing by pattern width;
- suffix-aware wildcard matching against live text;
- an independent `enable_frame_schema_matching` runtime switch;
- lower `frame_match_weight` for provisional schemas;
- `induce-frames` CLI for existing Canonical DBs;
- `benchmark-frames` for held-out frame transfer and counterexample testing.

## Isolated transfer test

The bundled deterministic fixture compiles only:

```text
Hund ist ein  → Tier / Haustier / Wesen
Katze ist ein → Tier / Haustier / Wesen
```

It then disables exact lookup, suffix lookup, lexical seeds, parent routing, relation recall, transitions, and recalled-context prediction. With only the induced frame enabled:

```text
Wolf ist ein       → Tier   ✓
Fuchs ist ein      → Tier   ✓
Mein Wolf ist ein  → Tier   ✓   (frame matched on the live suffix)
```

None of `Wolf`, `Fuchs`, or the full held-out prompts are present in the compiled BASE.

The same test also includes the counterexample:

```text
Stein ist ein
Teacher top-1: Objekt
Open frame:    Tier    ✗
```

That negative result is intentional. An **untyped open slot overgeneralizes** because v0.22 knows the repeated structural frame but does not yet know the admissible semantic class of a novel filler.

Demo result:

```text
induced frames                  1
pattern                         [SLOT_0] ist ein
BASE bytes                      2,772
frame-only Top-1               75 %
no-frame isolated Top-1         0 %
frame applicability recall     100 %
frame applicability precision   75 %
```

This is therefore evidence for a narrower claim:

> A repeated predictive relation can be compiled into an explicit reusable schema that transfers to unseen surface fillers.

It is **not** evidence that Equinox already possesses reliable semantic slot typing. The false positive on `Stein` makes the next missing mechanism measurable instead of hiding it.

## CLI

Induce frames from an existing Canonical DB without mutating it:

```bash
eqforge induce-frames master.sqlite frames.eqir.json
```

Persist accepted frames explicitly:

```bash
eqforge induce-frames master.sqlite frames.eqir.json --persist
```

For a local Hugging Face teacher, benchmark held-out frame transfer:

```bash
eqforge benchmark-frames /path/to/model out/frame-test \
  --train train-prompts.txt \
  --eval-jsonl frame-eval.jsonl \
  --source-id teacher-A
```

Evaluation JSONL may contain an **evaluation-only** applicability annotation:

```json
{"prompt":"Wolf ist ein","expected_frame_applicable":true}
{"prompt":"Stein ist ein","expected_frame_applicable":false}
```

Those labels are never compiled into the BASE.

## Current limitation and next research question

v0.22 has deliberately exposed the next problem:

```text
structural slot
      ≠
semantic type constraint
```

The natural next milestone is a typed / constrained slot system that can use substitution, contextual similarity, concept evidence, or other independent support to decide whether a novel filler is admissible for a frame. The benchmark should then test whether `Wolf` remains accepted while `Stein` is rejected **without using held-out labels as training data**.

---

Historical documentation from the earlier Forge milestones remains below.

# Equinox Forge v0.20 — Generalization Ladder

**Current milestone:** v0.20 stratifies Equinox transfer from exact replay through progressively harder held-out structural conditions (L0–L5), validates each level assignment, and reports the exact point where the current runtime stops transferring successfully.

Historical documentation for v0.1–v0.19 remains below.

**Previous milestone context:** v0.18 turns the fixed v0.17 retention benchmark into a controlled multi-configuration efficiency experiment. The teacher is probed **once** at the largest requested top-k. Forge then recompiles that exact captured evidence across pruning, runtime-budget, and optional macro-compression settings and measures the resulting storage/behaviour trade-off.

```text
one Teacher probe set
        ↓
shared captured evidence
        ↓
┌ top-k pruning
├ relation-score pruning
├ optional structural compression
├ recall-node budget
└ recall-depth budget
        ↓
many independent .eqbase packs
        ↓
Direct Replay + Full Runtime Replay
        ↓
Pareto frontiers
```

## Why this matters

v0.17 could answer whether one compiled configuration retained captured teacher behaviour. It could not answer the more important engineering question:

> **How much captured teacher behaviour is retained per byte and per unit of runtime work?**

v0.18 makes that trade-off explicit instead of hiding it behind a single default.

## Controlled axes

Each sweep point is defined by:

- `evidence_top_k`: how many teacher-ranked candidates per prompt are retained before compilation;
- `min_relation_score`: probability/score pruning before node closure;
- `max_recall_nodes`: bounded runtime recall budget;
- `max_recall_depth`: maximum recall expansion depth;
- `compression_mode`: `none` or `auto`.

The teacher is **not rerun per point**. This is important: a smaller pack is compared against exactly the same captured teacher reference distribution.

## Real node pruning

v0.18 does not merely hide low-ranked relations while leaving all their target structures in the pack. After rank/score pruning, Forge computes the transitive member closure of the surviving relation endpoints. Candidate surfaces and Q-structure that are no longer reachable are excluded from that sweep point. Pack-size differences therefore reflect the actual compiled knowledge slice.

## Two evaluation layers remain

As in v0.17, every point is measured twice:

1. **Direct Replay** — recall depth is disabled to isolate compilation/serialization loss.
2. **Full Runtime Replay** — the configured Equinox recall budget is enabled.

Per point v0.18 records, among other fields:

- `.eqbase` bytes, nodes, relations;
- promoted macro count and realized structural compression ratio;
- Top-1 retention;
- teacher top-k recall;
- teacher probability mass retained;
- NDCG;
- conditional JS divergence;
- average recalled nodes;
- average relation checks;
- compile/evaluation diagnostics.

## Pareto labels

v0.18 computes three explicit non-dominance sets:

- **storage frontier** — pack bytes vs direct compiler-only retention;
- **runtime frontier** — relation work vs full-runtime retention;
- **joint frontier** — bytes + relation work vs full-runtime retention.

A point is Pareto-labelled only when no other point is at least as good on every relevant objective and strictly better on at least one. This is **not** an automatic recommendation or a claim that one point is universally best.

## Deterministic demo

The bundled demo sweeps 48 configurations over a four-candidate teacher distribution. A particularly clear storage/retention slice is:

```text
retained Teacher candidates   pack bytes   relations   Teacher mass   NDCG
1                             1,594        3           61.7%          0.740
2                             1,914        6           83.3%          0.904
4                             2,231        12          100.0%         1.000
```

Top-1 retention is still 100% at all three points. That is exactly why Top-1 alone is insufficient: the smallest pack has discarded roughly 38% of the captured teacher probability mass even though its most likely answer remains unchanged.

In this tiny language-behaviour fixture the automatic structural compression mode promotes no macros because no repeated subsequence passes the already established **net realized savings** criterion. That no-op is intentional and auditable; compression is never forced merely because the sweep requested it. Larger repeated structures can activate the same axis.

## Outputs

A sweep directory contains:

```text
teacher-behaviour-full.eqir.json
teacher-probe-report.json
pareto-report.json
pareto-points.csv
points/
  p0001-.../
    compiled-input.eqir.json
    point.sqlite
    runtime.eqbase
    point-report.json
  ...
```

`pareto-points.csv` is intentionally flat so the curve can be plotted or analysed without parsing the complete audit JSON.

## CLI

With the optional local Hugging Face runtime installed:

```bash
python -m equinox_forge.cli benchmark-pareto \
  /path/to/local/model \
  prompts.txt \
  pareto-out \
  --source-id my-teacher \
  --source-version 1 \
  --teacher-top-k 8 \
  --runtime-top-k 8 \
  --evidence-top-k 1,2,4,8 \
  --min-relation-score 0,0.02,0.05 \
  --recall-nodes 24,96 \
  --recall-depth 0,3 \
  --compression none,auto
```

`--max-points` prevents an accidental combinatorial explosion. Forge still uses `local_files_only=True`; this command does not silently download a model.

## Scope limitation

The evaluation remains **compiled probe replay**. The same prompts used for capture are replayed after compilation. v0.18 measures the efficiency frontier of captured behaviour; it does not yet establish held-out language generalization, equivalence to a Transformer, mobile energy savings, or superiority to quantization/distillation.

## Regression suite

```bash
PYTHONPATH=. python tests/test_pareto_sweep.py
```

Expected marker:

```text
FORGE_V18_PARETO_SWEEP_OK
```

The full historical regression runner now ends in:

```text
FORGE_V18_ALL_TESTS_OK
```

## Recommended next step — v0.19

**Held-out Generalization Split + Prefix/Context Coverage.** The next scientifically important question is no longer whether captured prompts replay efficiently, but whether compiled structure transfers to prompts that were **not** used during teacher extraction. A v0.19 benchmark should create explicit train/capture and held-out sets, report exact-context vs suffix-context coverage, and separate:

```text
memorized probe replay
        vs
structural transfer to unseen prompts
```

That is the next necessary step before making stronger claims about language capability.

---

# Historical v0.17 — Teacher → Equinox Behaviour Retention Benchmark

**Current milestone:** v0.17 closes the first controlled Teacher → Forge → `.eqbase` → Runtime comparison loop. The same controlled next-token probes are captured from a causal teacher, compiled into Equinox prediction relations, loaded from the binary runtime pack, and replayed with explicit retention metrics.

```text
causal teacher
    ↓ controlled prompts
next-token distributions
    ↓
canonical Equinox evidence
    ↓
.eqbase compilation
    ↓
Equinox runtime prediction
    ↓
Teacher ↔ Runtime retention report
```

## Two retention layers

v0.17 deliberately separates two questions that must not be conflated.

### 1. Direct Replay — compiler/serialization retention

Associative recall depth is disabled and accepted teacher top-k evidence is compiled with relation thresholds `min_score=0` and `min_confidence=0`. This isolates loss caused by canonicalization, relation aggregation, float32 pack representation, loading, and direct runtime ranking.

### 2. Full Runtime Replay — operational Equinox behaviour

The normal v0.16 recall/prediction policy is then restored. Related contexts may enter through hierarchical/associative recall and contribute additional prediction candidates. Any divergence here is therefore runtime cognition behaviour, not necessarily compiler information loss.

This split matters. A single aggregate score would make it impossible to tell whether a disagreement came from the compiler or from the runtime routing policy.

## Metrics

For every prompt v0.17 records separately:

- Teacher Top-1 and Equinox Top-1
- Teacher Top-1 runtime rank
- top-k set overlap / recall
- runtime precision against Teacher top-k
- captured Teacher probability mass
- Teacher probability mass retained in the runtime top-k
- NDCG using Teacher probabilities as relevance weights
- conditional Jensen–Shannon divergence
- conditional total-variation distance
- resolved context status
- recall-node count
- relation-check count

The divergence metrics are explicitly labelled **conditional**: Teacher probabilities and Equinox ranking scores are each renormalized on the compared top-k support. Equinox runtime scores are not claimed to be calibrated probabilities.

## Scope limitation

The current benchmark is intentionally:

```text
compiled_probe_replay
```

The same prompts used to extract teacher behaviour are replayed after compilation. This tests **behaviour preservation of captured probes**, not held-out language generalization. A good v0.17 result therefore does not imply that Equinox has reproduced the teacher's general language ability.

## Relation-threshold control

The normal relation compiler historically uses a `0.05` minimum score. That is useful production pruning, but it would silently delete low-probability Teacher top-k candidates before a retention benchmark. v0.17 therefore compiles its benchmark pack with:

```text
min_score      = 0
min_confidence = 0
min_sources    = 1
```

Pruning/size trade-offs are deliberately left for a separate Pareto benchmark rather than mixed into the base retention measurement.

## Deterministic demo result

The included scripted demo compiles three prompts and nine prediction relations into:

```text
38 runtime nodes
9 prediction relations
1,994 byte .eqbase
```

Direct Replay:

```text
Top-1 retention                    100.0%
Teacher top-k recall               100.0%
Teacher probability mass retained  100.0%
NDCG@3                              1.000
conditional JS divergence          ~0
```

With the configured normal recall policy:

```text
Top-1 retention                    100.0%
Teacher top-k recall                66.7%
Teacher probability mass retained   93.3%
NDCG@3                              0.946
conditional JS divergence           0.132
average recall nodes                 5.67
average relation checks             19.67
```

The difference is useful: the compiler preserved the captured distribution, while runtime recall deliberately exposed predictions from related contexts. v0.17 can now measure those effects separately.

A second integration test trains and executes a real tiny PyTorch GRU causal teacher locally, then compiles and replays its computed next-token distributions through the same path. This requires PyTorch; it is skipped cleanly when PyTorch is unavailable.

## CLI

With the optional local Hugging Face runtime installed:

```bash
python -m equinox_forge.cli benchmark-retention \
  /path/to/local/model \
  probes.txt \
  retention-out \
  --source-id my-teacher \
  --source-version 1 \
  --teacher-top-k 8 \
  --runtime-top-k 8 \
  --device cpu
```

Forge does not download the model automatically. The backend remains `local_files_only=True`.

The output directory contains:

```text
retention.sqlite
teacher-behaviour.eqir.json
teacher-probe-report.json
retention.eqbase
retention-report.json
```

## Regression suite

```bash
PYTHONPATH=. python tests/run_all.py
```

Expected final marker:

```text
FORGE_V17_ALL_TESTS_OK
```

## What v0.17 proves — and does not prove

v0.17 proves that Forge can quantitatively compare captured Teacher behaviour with behaviour reconstructed from an independently loaded `.eqbase`, and can distinguish pure compilation retention from changes introduced by Equinox recall/routing.

It does **not** yet prove:

- held-out generalization;
- equivalence to a large Transformer;
- useful capability per byte at scale;
- lower energy consumption;
- superiority over quantization/distillation/RAG;
- that the current runtime recall policy is optimally calibrated.

## Recommended next step — v0.18

**Behaviour / Size Pareto Sweep.** Recompile the same Teacher evidence across controlled pruning, top-k, confidence, macro-compression and runtime-budget settings, then plot/record the Pareto frontier:

```text
pack bytes / relation count / runtime work
                ↕
Top-1 retention / probability-mass retention / NDCG / JS divergence
```

That will answer a much more important question than whether one fixed configuration works: **how much Teacher behaviour can Equinox retain per byte and per unit of runtime work?**

---

# Historical v0.16 — Runtime Recall + Prediction Engine

**v0.16 milestone:** bounded recall and ranked prediction directly on the compiled `.eqbase` runtime, with a hard distinction between recall links and directed prediction channels.

## Previous milestone: v0.13 runtime compression plan

Forge v0.13 turns the **potential** compression reported by v0.12 into a concrete, auditable runtime encoding plan. Eligible repeated structures compete for actual parent positions, only a mutually non-overlapping set is promoted, promoted macros are materialized through the normal v0.11 Macro Builder, and every scanned parent receives a concrete rewritten member sequence.

```text
v0.12 candidates
      ↓
recompute marginal usable occurrences
      ↓
conflict-aware deterministic selection
      ↓
promote selected macros
      ↓
rewrite parent member sequences
      ↓
count actual parent refs + macro definitions + overhead
      ↓
realized compression
```

## Central rule: canonical knowledge is not rewritten

The canonical graph remains the semantic/source representation. v0.13 writes a separate **physical runtime encoding view**:

```text
canonical parent
[A, B, C, D, E]

runtime encoding
[M_ABC, D, E]
```

The runtime rewrite can therefore be rebuilt or discarded without destroying provenance or changing the meaning of the canonical parent.

## Conflict-aware promotion

v0.12 candidate scores cannot simply be added: two candidates may want to replace overlapping positions in the same parent. v0.13 uses deterministic greedy marginal-gain selection.

After each promotion Forge:

1. reserves the exact member positions consumed by that macro;
2. recomputes the still-usable occurrences of every remaining candidate;
3. recomputes independent parent count and marginal compression;
4. rejects candidates that no longer satisfy the realized thresholds;
5. chooses the next remaining candidate by realized net saving, ratio, reuse count, length, then stable candidate id.

The strategy is deliberately reported as:

```text
deterministic_greedy_marginal_gain
```

It is deterministic and conservative, but **is not claimed to be the globally optimal weighted packing solution**.

## Realized cost model

For each promoted macro of length `L` with `O` actually usable non-overlapping occurrences:

```text
parent_ref_savings = O * (L - 1)
definition_refs    = L
realized_net       = parent_ref_savings - definition_refs - definition_overhead
```

For the complete runtime view:

```text
baseline_parent_refs
rewritten_parent_refs
macro_definition_refs
definition_overhead_cost

encoded_total_cost = rewritten_parent_refs
                   + macro_definition_refs
                   + definition_overhead_cost

realized_net_savings = baseline_parent_refs - encoded_total_cost
realized_compression_ratio = realized_net_savings / baseline_parent_refs
```

Forge asserts that global realized saving exactly equals the sum of the promoted candidates' marginal savings. This catches overlap/accounting bugs instead of silently reporting optimistic compression.

## Self-feedback guard

Previously promoted build targets with the prefix:

```text
auto-macro:
```

are excluded from later runtime-compression discovery by default. They are compiled encodings, not new semantic observations. This prevents Forge from learning repeated patterns from its own previous compression output and makes repeated v0.13 runs stable.

## Persistent runtime compression data

v0.13 adds:

```text
runtime_compression_runs
runtime_promoted_macros
runtime_parent_rewrites
```

Each run stores the discovery/promotion policy, promoted macro ids, exact occurrence positions, original and rewritten parent sequences, and global realized metrics.

Promoted macros remain ordinary Derived Artifacts and therefore can be reused by later hierarchy and runtime-pack compilers.

## CLI

Compile a realized runtime compression plan:

```bash
python -m equinox_forge.cli compress-runtime master.sqlite \
  --min-pattern-size 2 \
  --max-pattern-size 6 \
  --min-occurrences 2 \
  --min-parent-structures 2 \
  --min-realized-occurrences 2 \
  --min-realized-parent-structures 2 \
  --min-realized-net-savings 1 \
  --definition-overhead 1 \
  --output runtime-compression.json
```

To calculate deterministic macro ids and rewrites without materializing new macro artifacts:

```bash
python -m equinox_forge.cli compress-runtime master.sqlite \
  --plan-only --no-persist \
  --output runtime-plan.json
```

## Regression fixture

The v0.13 hard test contains two useful repeated macros and one competing overlapping candidate.

The selected macros realize:

```text
baseline parent refs      36
rewritten parent refs     22
parent refs removed       14
macro definition refs      6
definition overhead        2
encoded total cost        30
realized net saving        6
realized ratio         16.67%
```

The overlapping candidate is rejected after the stronger macro reserves its shared positions.

Run everything with:

```bash
PYTHONPATH=. python tests/run_all.py
```

Expected final marker:

```text
FORGE_V13_ALL_TESTS_OK
```

## What v0.13 does NOT prove

v0.13 now proves **realized structural reference compression in the Forge cost model**, not just candidate-level potential savings. It still does not prove lower wall-clock latency, lower energy consumption, or unchanged downstream task quality on a device. Those require a real runtime pack and benchmark harness.

## Recommended next step — v0.14

**Runtime BASE Pack Compiler + Round-Trip Loader.** Take the promoted macro definitions and rewritten parent sequences from v0.13, serialize them into a compact deterministic pack with indexes, load the pack back independently of SQLite/Forge, and verify structural equivalence plus actual byte size. This is the point where Forge can start measuring compression in **bytes**, not only references.

---

# Historical v0.12 documentation

# Equinox Forge v0.12 — Automatic Macro Discovery + Structural Compression Metrics

Forge v0.12 removes the requirement that every higher macro boundary be specified manually. It scans existing ordered canonical and derived compositions for repeated contiguous substructures, scores their **potential structural compression**, and can explicitly materialize only eligible candidates as normal v0.11 macro artifacts.

```text
canonical / derived structures
        ↓
ordered repeated substructures
        ↓
non-overlapping occurrence count
        ↓
compression + search metrics
        ↓
threshold / dominance pruning
        ↓
proposed macro candidates
        ↓  optional explicit materialization
Derived Artifact Store
```

## Compression rule

For a candidate of member length `L` with `O` simultaneously usable, non-overlapping occurrences:

```text
baseline_refs = L * O
encoded_refs  = L + O
net_savings   = baseline_refs - encoded_refs - definition_overhead
compression_ratio = net_savings / baseline_refs
search_steps_saved = O * (L - 1)
```

A repeated structure is therefore **not automatically a macro**. It must satisfy configurable minimum occurrence, independent-parent, net-savings, and compression-ratio thresholds. Overlapping windows are greedily reduced to simultaneously usable occurrences before scoring.

Example: `[A,B,C]` appearing in three parent structures has `9` baseline refs. Defining it once and using three macro refs costs `6` refs; with definition overhead `1`, potential net savings are `2` (`22.2%`). `[A,B]` appearing three times has no net saving under the same overhead and is rejected.

Metrics in v0.12 are deliberately labelled **potential**: materializing a macro does not yet rewrite all parent structures/runtime encodings to consume it. `total_potential_net_savings` is therefore a candidate-level upper-bound style diagnostic, not a guarantee that all candidate savings can be realized jointly.

## Discovery command

```bash
python -m equinox_forge.cli discover-macros master.sqlite \
  --min-pattern-size 2 \
  --max-pattern-size 6 \
  --min-occurrences 2 \
  --min-parent-structures 2 \
  --min-net-savings 1 \
  --min-compression-ratio 0.05 \
  --report discovery.json
```

Discovery is non-destructive. To explicitly build the highest-ranked eligible candidates into the Derived Artifact Store:

```bash
python -m equinox_forge.cli discover-macros master.sqlite \
  --materialize --materialize-limit 10 \
  --report discovery.json
```

Each materialized candidate becomes a deterministic build target such as:

```text
auto-macro:mc_<content-hash>
```

and then uses the existing Macro Builder, Artifact Store, dependency graph, and incremental rebuild machinery.

## Persistent audit trail

v0.12 adds:

```text
macro_discovery_runs
macro_candidates
```

Every persisted discovery run records its policy, candidate members, usable occurrence count, parent count, compression metrics, rejection reasons, dominance status, and optional materialized target.

## Dominance pruning

A shorter eligible pattern can be suppressed when a longer pattern contains it while offering at least the same reuse count and at least as much net compression benefit. This prevents obvious nested duplicate suggestions from flooding the candidate set.

## Demo and tests

```bash
PYTHONPATH=. python examples/build_macro_discovery_demo.py
PYTHONPATH=. python tests/run_all.py
```

Expected final marker:

```text
FORGE_V12_ALL_TESTS_OK
```

## What v0.12 does NOT prove

v0.12 proves deterministic repeated-substructure discovery and a conservative structural cost model. It does **not** yet prove that a discovered macro improves downstream task quality or wall-clock inference. It also does not rewrite parent structures to realize all predicted savings, and it does not yet discover arbitrary graph motifs or unordered relational communities.

## Recommended next step — v0.13

**Macro Promotion + Parent Rewriting / Runtime Compression Plan.** The next step should take accepted discovery candidates, choose a mutually compatible non-overlapping set, rewrite/compile affected parent structures to reference them, and measure *realized* rather than potential reference/search reduction before promotion into a runtime BASE.

---

# Historical v0.11 documentation

# Equinox Forge v0.11 — Derived Artifact Store + Recursive Macro/Hierarchy Builder

Forge v0.11 adds the first real compiler family **above** provisional sense concepts. Derived outputs now live in a persistent Artifact Store with status and generation history, and the incremental scheduler can execute both `sense` and `macro` builders.

```text
Teacher/source
   ↓
Sense compiler
   ↓  stable/candidate/stale artifacts
Derived Artifact Store
   ↓
Macro builder
   ↓
higher Macro builder
   ↓
... recursive Equinox hierarchy
```

A source change can therefore propagate selectively through an actual derived hierarchy:

```text
teacher-bank@1
→ bank sense
→ macro-pair
→ macro-domain
```

while unrelated branches remain untouched. Intermediate derived nodes do **not** have to be forced into the canonical input tables; higher builders can read them directly from the Artifact Store.

The v0.10 dependency graph and v0.9 source-policy rebuild remain intact underneath this layer.

The v0.9 source-ablation and reweighting engine remains intact underneath this layer: raw evidence is preserved, source policies create an effective evidence view, and rebuilds remain deterministic/auditable.

## Central rule

Raw source evidence is never rewritten by an ablation or reweighting operation.

A source policy changes only what the compiler sees during a rebuild:

```text
main.evidence        = preserved source history
temp.evidence        = active + trust-weighted rebuild view
```

When the rebuild finishes, the temporary view is removed.

This means Forge can answer questions such as:

```text
What happens if Teacher C is removed?
What if Teacher B is trusted only at 0.4?
What if Qwen version 1 is replaced by version 2?
Which derived concepts remain stable?
Which concepts disappear or become contested?
```

without re-extracting every model.

## Persistent source policy

The Canonical DB adds `source_policies`:

```text
source_id
source_version
enabled
trust_weight
note
metadata
updated_at
```

A source without an explicit policy defaults to:

```text
enabled      = true
trust_weight = 1.0
```

Trust weight must be within `[0,1]`.

## Ablation

Disable one exact source version:

```bash
python -m equinox_forge.cli source-policy set \
  master.sqlite teacher-C 1 --disable \
  --note "ablation experiment"
```

The source remains in `main.evidence`, but its evidence is absent from the effective rebuild view.

Re-enable it:

```bash
python -m equinox_forge.cli source-policy set \
  master.sqlite teacher-C 1 --weight 1.0
```

## Reweighting

Reduce trust in a source:

```bash
python -m equinox_forge.cli source-policy set \
  master.sqlite teacher-B 1 --weight 0.4
```

The weight affects two things:

1. **relation aggregation** — effective evidence confidence is multiplied by source trust;
2. **cross-teacher consensus** — a source vote carries the configured source weight.

Independent-source count remains separate from trust weight. Therefore one source with weight `1.0` cannot impersonate two independent sources.

Example:

```text
Teacher A  weight 1.0  supports
Teacher B  weight 0.4  supports

support_sources = 2
support_weight  = 1.4
```

With the default `stable_min_support_weight = 1.5`, that hypothesis is not promoted to `stable` even though two source identities are present.

## Version replacement

A source version can be replaced atomically at policy level:

```bash
python -m equinox_forge.cli source-policy replace \
  master.sqlite qwen 1 2 --weight 0.8
```

This performs:

```text
qwen@1 → disabled
qwen@2 → enabled, weight 0.8
```

The old extracted evidence is retained for audit/replay.

## Inspecting policies

```bash
python -m equinox_forge.cli source-policy list master.sqlite
```

Only explicitly configured policies:

```bash
python -m equinox_forge.cli source-policy list master.sqlite --explicit-only
```

Clear an explicit policy and return to default behavior:

```bash
python -m equinox_forge.cli source-policy clear master.sqlite teacher-B 1
```

## Deterministic policy hash

Every rebuild receives a `source_policy_hash` derived only from behaviorally relevant fields:

```text
source_id
source_version
enabled
trust_weight
```

Notes, timestamps, metadata and whether a default policy was explicitly written do not change the semantic policy hash.

This allows reproducible rebuild comparison.

## Weighted cross-teacher consensus

v0.9 extends the v0.8 consensus report with:

```text
source_weight
support_weight
conflict_weight
decisive_weight
```

The consensus score is now:

```text
consensus = support_weight / (support_weight + conflict_weight)
```

while `support_sources` / `conflict_sources` continue to count independent source identities.

Default lifecycle controls now include:

```text
stable_min_sources          2
stable_min_runs             2
stable_consensus            0.75
stable_min_support_weight   1.5

quarantine_conflicts        2
quarantine_conflict_weight  1.5
```

So two low-trust conflicting sources do not automatically have the same quarantine force as two full-trust sources.

## Rebuild engine

Recompile a target surface using all currently configured source policies:

```bash
python -m equinox_forge.cli rebuild-senses \
  master.sqlite \
  bank_rebuilt.eqir.json \
  --surface Bank
```

The command:

```text
1. creates an effective evidence view
2. compiles provisional senses
3. performs weighted cross-source consensus
4. updates hypothesis lifecycle state
5. records a rebuild run
6. writes a rebuild report
7. removes the temporary view
```

Useful controls:

```text
--threshold
--min-channels
--min-contexts
--w-hidden
--w-semantic
--w-substitution
--w-transition
--w-prediction

--stable-min-sources
--stable-min-runs
--stable-consensus
--stable-min-support-weight
--quarantine-conflicts
--quarantine-conflict-weight
--quarantine-after-misses
```

`--no-track-stability` performs a policy-aware rebuild without adding a lifecycle run.

`--ingest-derived` explicitly writes the derived nodes/evidence back to the Canonical DB; it remains opt-in.

## Rebuild history

The Canonical DB adds `rebuild_runs`:

```text
rebuild_run_id
target_id
source_policy_hash
output_hash
raw_evidence_count
effective_evidence_count
created_at
metadata
```

This is separate from `hypothesis_runs` because a rebuild can be reproduced and compared even when lifecycle tracking is disabled.

## Example lifecycle under source policy changes

```text
Teacher A = 1.0
Teacher B = 1.0

Rebuild 1 → candidate
Rebuild 2 → stable

Teacher B reweighted to 0.4
Rebuild 3 → candidate
  support_sources = 2
  support_weight  = 1.4

Teacher A disabled
Rebuild 4 → current sense no longer clears the fusion threshold
  → hypothesis absent from rebuilt output
  → persisted lifecycle downgraded to contested
```

At no stage is the original A/B evidence deleted.

## Reproducible demo

Run:

```bash
python examples/build_rebuild_demo.py
```

The demo writes a small Canonical DB and a timeline showing promotion, reweighting and ablation.

## Regression suite

Run:

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V10_ALL_TESTS_OK
```

Coverage now includes:

```text
v0.1 canonical IR / database / relation aggregation
v0.2 Hugging-Face adapter contract
v0.3 static teacher embedding extraction
v0.4 controlled corpus evidence
v0.5 executed causal-teacher behaviour
v0.6 contextual hidden-state evidence
v0.7 evidence fusion / provisional sense compilation
v0.8 source-specific consensus + reversible lifecycle
v0.9 source ablation without raw-data deletion
v0.9 source trust reweighting
v0.9 weighted consensus
v0.9 deterministic policy hashing
v0.9 version replacement
v0.9 persisted rebuild history
```

## v0.10 dependency graph

The Canonical DB now stores generic `dependency_edges` with the form:

```text
dependent artifact  --depends on-->  dependency artifact
```

Artifact types are namespaced (`source`, `node`, `build_target`, `artifact`, ...), so the graph is not hard-coded to language senses. Automatic indexing currently records:

```text
node(parent)      → node(child)          composition_member
node(endpoint)    → source@version       evidence provenance
build_target      → target node          sense target
build_target      → context node         contextual-use dependency
build_target      → matching template    prediction dependency
derived sense     → build_target         compiler output
```

Manual/plugin dependencies can be registered without being erased when the automatic index is refreshed.

### Impact analysis

```bash
python -m equinox_forge.cli dependency-impact master.sqlite \
  --changed-source teacher-A@1
```

The command walks reverse dependencies transitively and reports affected nodes, registered build targets, and higher manual/plugin artifacts.

### Incremental rebuild

```bash
python -m equinox_forge.cli incremental-rebuild master.sqlite \
  --changed-source teacher-A@1 \
  --output-dir out/incremental
```

Dry run:

```bash
python -m equinox_forge.cli incremental-rebuild master.sqlite \
  --changed-source teacher-A@1 --dry-run
```

A successful v0.10 rebuild:

```text
1. refreshes the dependency index
2. starts from the changed source root(s)
3. computes the transitive invalidation closure
4. selects only affected registered build targets
5. automatically executes installed builders (currently: sense)
6. reports future/unknown builders as deferred
7. records an incremental_rebuild_run
8. leaves unrelated build targets untouched
```

### Persisted build recipes

`rebuild-senses` now registers its compiler policy in `build_targets`. That allows a later incremental rebuild to reproduce the target without the user re-specifying thresholds and fusion/consensus settings.

Existing pre-v0.10 databases are migrated non-destructively. A target created only by v0.9 must be rebuilt once with v0.10 to register its build recipe.

### Reproducible v0.10 demo

```bash
python examples/build_incremental_demo.py
```

The demo creates independent `bank` and `kran` targets. A change to `teacher-bank@1` rebuilds `bank` only, while dependency impact still propagates into higher synthetic artifacts. A registered future `macro` builder is reported as deferred rather than silently ignored.

## Regression suite

Run:

```bash
PYTHONPATH=. python tests/run_all.py
```

Expected final marker:

```text
FORGE_V10_ALL_TESTS_OK
```

New v0.10 coverage includes:

```text
transitive source → node → build-target invalidation
unrelated-target isolation
manual higher-artifact propagation
future-builder deferral
persisted build recipes
dry-run planning
incremental rebuild history
```

## What v0.10 does NOT prove

The dependency graph solves invalidation and selective recompilation; it does **not** yet provide executors for every future higher-level compiler. v0.10 automatically rebuilds registered `sense` targets. Unknown builders remain visible as `deferred`, preserving the transitive dependency chain instead of pretending they were rebuilt.

Source trust values also remain compiler policy and still require calibration against held-out benchmarks.

## Recommended next step — v0.11

**Derived Artifact Store + Macro/Hierarchy Builder.**

That would give the generic v0.10 scheduler a second real compiler family above provisional senses, so changes can propagate and rebuild not only sense nodes but higher Equinox macros/domains automatically.


## v0.11 derived Artifact Store

The Canonical DB now also owns a separate derived-output layer:

```text
derived_artifacts          current compiler outputs
derived_artifact_versions immutable output/status history
```

Every artifact records its build target, builder, canonical node ID, content hash, lifecycle status, generation, source-policy hash, and complete node payload. If an output disappears from a later rebuild it is not deleted; its current record becomes `stale` while its older generations remain auditable.

Sense compiler outputs are mirrored automatically. Their Artifact Store status follows the v0.8/v0.9 hypothesis lifecycle (`candidate`, `stable`, `contested`, `quarantined`).

Inspect current artifacts:

```bash
python -m equinox_forge.cli artifacts master.sqlite
python -m equinox_forge.cli artifacts master.sqlite --target-id bank --status stable
```

## v0.11 macro / hierarchy builder

A macro recipe may consume:

- explicit canonical/derived node IDs;
- current outputs of one or more build targets;
- only selected statuses such as `stable` or `active`.

Example:

```bash
python -m equinox_forge.cli build-macro master.sqlite macro.eqir.json \
  --target-id animal-domain \
  --input-target hund \
  --input-target katze \
  --allowed-status stable \
  --min-members 2 \
  --surface "macro:animal-domain"
```

The resulting level is structural only:

```text
level(macro) = 1 + max(level(member_i))
```

No importance or confidence bonus is assigned merely because a node is deeper. Membership is represented by `node_members` and explicit derived `composition` evidence.

Macro build targets register dependencies on upstream build targets/nodes. Therefore macros may themselves become inputs to higher macro targets. The existing v0.10 topological scheduler automatically executes them dependency-first.

## Artifact-only intermediate hierarchy

A core v0.11 rule is that an intermediate compiler output does not have to become canonical input state just to feed the next compiler. If a derived node is absent from `nodes`, the Macro Builder can resolve its current node payload from `derived_artifacts`. This keeps:

```text
source/canonical evidence
!=
derived compiler state
```

until an explicit ingest/runtime-pack stage decides what becomes part of the compiled BASE.

## Recursive invalidation test

The v0.11 regression fixture constructs:

```text
bank sense ─┐
            ├→ macro-pair ─┐
kran sense ─┘              ├→ macro-domain
hund sense ────────────────┘
```

Then `teacher-bank@1` is disabled. The expected rebuild order is:

```text
bank → macro-pair → macro-domain
```

`macro-pair` and `macro-domain` can no longer satisfy their minimum-member policy and become `stale`; `kran` and `hund` remain `stable`.

Run the reproducible demo:

```bash
PYTHONPATH=. python examples/build_macro_hierarchy_demo.py
```

## v0.11 regression suite

```bash
PYTHONPATH=. python tests/run_all.py
```

Expected final marker:

```text
FORGE_V11_ALL_TESTS_OK
```

## What v0.11 does NOT prove

The Macro Builder proves recursive representation, persistence, dependency tracking, and selective recompilation. It does not yet prove that Forge can automatically discover useful high-level macro boundaries at scale. v0.11 recipes explicitly state which upstream build targets/nodes may compose a macro; automatic hierarchy discovery is a separate compiler problem.

## Recommended next step — v0.12

**Automatic Macro Discovery + Structural Compression Metrics.**

Instead of manually declaring every higher macro recipe, v0.12 should scan stable relation/composition patterns, propose recurring higher structures, measure actual reuse/compression, and only promote structures that reduce repeated representation or search work.


---

# v0.14 — Runtime BASE Pack Compiler + Round-Trip Loader

v0.14 converts a persisted v0.13 runtime compression run into the first actual compact Equinox runtime binary rather than another JSON/SQLite planning structure.

```text
Canonical / Derived knowledge
        ↓
v0.13 runtime rewrite plan
        ↓
v0.14 BASE pack compiler
        ↓
*.eqbase
        ↓
round-trip loader + verifier
```

## Binary layout

The current `equinox-runtime-base-v1` format is deterministic and little-endian. It contains:

1. a fixed 112-byte header;
2. a deduplicated UTF-8 string table;
3. varint encoded node records;
4. varint node-member references;
5. relation records with float32 score/confidence;
6. a fixed 32-bit offset per node for direct numeric record seeking;
7. SHA-256 over the complete payload.

Node IDs remain stable canonical/derived IDs. Runtime parent member sequences are taken from the selected v0.13 compression run; the Canonical DB is not mutated.

## Integrity rules

The loader rejects:

- wrong magic / unsupported major format;
- inconsistent section offsets or file length;
- payload SHA-256 mismatch;
- malformed/truncated varints;
- node/member/relation references outside the pack;
- invalid node-offset index layout.

`verify-base` additionally checks unique node IDs and dangling member/relation endpoints.

## Compile

First persist a v0.13 compression run:

```bash
python -m equinox_forge.cli compress-runtime master.sqlite
```

Then compile the latest run:

```bash
python -m equinox_forge.cli compile-base master.sqlite master.eqbase \
  --pack-id equinox-master \
  --pack-version 1 \
  --report master.eqbase.report.json
```

For the smallest runtime-only form, omit compiler metadata strings:

```bash
python -m equinox_forge.cli compile-base master.sqlite master-mobile.eqbase \
  --pack-id equinox-master \
  --strip-metadata
```

Inspect / verify:

```bash
python -m equinox_forge.cli inspect-base master.eqbase
python -m equinox_forge.cli verify-base master.eqbase
```

## Round-trip contract

During compilation, v0.14 can immediately reload the file and compare it against the runtime view that produced it. Node identity, modality, kind, level, surface, member sequence, and optional metadata must match exactly. Relation weights intentionally use float32 in the runtime pack; the round-trip comparison therefore checks their exact float32 representation rather than pretending the original SQLite double precision was retained.

The same DB + compression run + pack metadata compiles byte-for-byte deterministically.

## Synthetic demo result

The included v0.13 demo currently compiles to:

```text
26 runtime nodes
0 relations
104 B node-offset index
1,623 B full pack with compiler metadata
635 B full pack with --strip-metadata
roundtrip_valid = true
```

These numbers are only a tiny deterministic format test, not a claim about large-model compression ratios.

Run it with:

```bash
PYTHONPATH=. python examples/build_runtime_compression_demo.py
PYTHONPATH=. python examples/build_runtime_base_demo.py
```

## Persistent audit

Each persisted build records a `runtime_base_pack_runs` row containing compression-run ID, pack ID/version, byte size, counts, payload/full-file SHA-256 and the full manifest. This links a runtime binary back to the exact physical rewrite plan that generated it.

## v0.14 regression suite

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V14_ALL_TESTS_OK
```

The runner now explicitly injects the project root into subprocess `PYTHONPATH`, so a clean extracted ZIP does not depend on an unrelated editable install.

---

# v0.15 — Runtime Indexes + Query / Traversal Benchmark Harness

v0.15 moves the test boundary from the Forge SQLite compiler into the compiled `.eqbase` runtime itself. All secondary indexes are built only from the loaded BASE pack; no canonical DB is consulted during query or benchmark execution.

## Runtime indexes

`RuntimeIndex` builds deterministic in-memory indexes for:

- `node_id -> RuntimeNode`;
- `surface -> node ids`;
- `child -> direct parents`;
- `node -> direct children`;
- outgoing relations;
- incoming relations;
- composite root nodes.

The binary v1 pack format itself is unchanged from v0.14. v0.15 therefore remains compatible with existing `equinox-runtime-base-v1` files.

## Queries

Examples:

```bash
python -m equinox_forge.cli query-base master.eqbase --node <NODE_ID>
python -m equinox_forge.cli query-base master.eqbase --surface Hund
python -m equinox_forge.cli query-base master.eqbase --parents <NODE_ID>
python -m equinox_forge.cli query-base master.eqbase --expand <NODE_ID>
python -m equinox_forge.cli query-base master.eqbase --relations-from <NODE_ID>
```

Each indexed query reports deterministic structural work units alongside optional host-Python microbench timings.

## Hierarchical routing benchmark

The benchmark compares two ways of finding roots that contain a known compiled macro:

1. **expanded baseline** — recursively expand each runtime root to terminal symbols and naively scan for the macro's terminal pattern;
2. **hierarchical route** — start at the macro node and follow the compiled parent index upward.

This is deliberately a structural comparison, not a claim about CPU instructions, Joules, Android performance, or a transformer baseline.

Run:

```bash
python -m equinox_forge.cli benchmark-base master.eqbase \
  --sample-nodes 128 \
  --sample-macros 16 \
  --timing-repeat 50 \
  --output benchmark.json
```

## Deterministic v0.15 demo

The included demo builds 80 independent roots containing the reusable sequence `[a,b,c]`, compiles the promoted macro into an `.eqbase`, loads that binary, and benchmarks the runtime graph.

Current fixture:

```text
244 runtime nodes
80 relations
80 composite roots
243 member edges
7,477 B .eqbase
```

Measured structural work on this fixture:

```text
node-id lookup:
  linear baseline   15,680 work units
  indexed              128
  reduction          99.18 %

surface lookup:
  linear baseline   31,232
  indexed              256
  reduction          99.18 %

parent lookup:
  linear baseline   31,104
  indexed              293
  reduction          99.06 %

relation adjacency:
  linear baseline    6,720
  indexed              205
  reduction          96.95 %

known-macro routing:
  expanded baseline    320 symbol comparisons
  hierarchy              81 work units
  reduction            74.69 %
  baseline roots found     80
  hierarchical roots       80
  coverage             100 %
```

The lookup reductions primarily demonstrate the expected benefit of indexing. The routing result is the more Equinox-specific test: a known higher structure can route directly through the compiled hierarchy instead of re-scanning the full expanded symbol stream.

Run the exact fixture:

```bash
PYTHONPATH=. python examples/build_runtime_query_benchmark_demo.py
```

The report is written to `examples/runtime_query_demo/benchmark.json`.

## Interpretation limits

- `work_units` are deterministic structural operations defined by the harness, not CPU instructions.
- host-Python nanosecond timings are diagnostic only and are not Android/runtime guarantees.
- macro-routing coverage may be below 100% in real packs when the same terminal pattern exists in roots that were intentionally not rewritten to the promoted macro because of overlap/conflict decisions.
- the benchmark does not yet measure answer quality, prediction quality, energy, or comparison against a transformer teacher.

## v0.15 regression suite

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V15_ALL_TESTS_OK
```

## Recommended next step — v0.16

**Runtime Recall + Prediction Engine.**

The runtime can now load, index and route through the compiled hierarchy. The next meaningful step is to consume the compiled relation channels themselves: activate a context, retrieve bounded candidates, score relation support / hierarchy relevance, and produce a next-state or next-token prediction directly from `.eqbase` without SQLite or a teacher model. That will let the benchmark move from pure graph traversal to actual retained behaviour.


---

# v0.16 — Runtime Recall + Prediction Engine

v0.16 turns the compiled `.eqbase` into a bounded, read-only cognitive runtime. The runtime never consults the Forge SQLite database and never learns or mutates the BASE pack.

```text
live text context
      ↓
context/surface resolution
      ↓
bounded structural + associative recall
      ↓
compiled directed prediction channels
      ↓
ranked next-surface candidates
```

## Hard separation: recall is not prediction

Recall may expand through parent routing and associative relations such as `semantic_similarity`, `substitution`, `is_a`, or contextual similarity. A node becomes a next-surface prediction **only** when a compiled `prediction` or `transition` relation supports it. Semantic similarity by itself is never converted into a next-token claim.

## Context resolution

The first text consumer remains tokenizer-independent. It resolves exact predictive contexts already present in the pack. If a longer prompt is not represented directly, it falls back to the longest known predictive suffix. Example: a BASE trained with a three-word context can answer `Der Hund ist ein` through the stored context `Hund ist ein`.

## Bounded recall

`RuntimeCognitionPolicy` caps:

- recalled nodes,
- recall depth,
- structural parents per node,
- associative relation neighbors,
- output prediction candidates,
- minimum activation and minimum prediction contribution.

This prevents an increasingly large BASE from automatically turning each request into an unbounded graph traversal.

## Candidate traces

Every returned prediction retains a contribution trace with:

- source context node,
- relation type,
- compiled relation score,
- compiled confidence,
- independent source count,
- context activation,
- runtime channel weight,
- final contribution.

The trace distinguishes direct context predictions, recalled-context predictions, and lexical transition predictions.

## Prediction benchmark harness

`benchmark-predictions` accepts JSONL or TSV pairs:

```json
{"context":"Der Hund ist ein","expected":"Tier"}
{"context":"Der Hund kann","expected":"bellen"}
```

It reports:

- Hit@1,
- Hit@K,
- mean reciprocal rank,
- unresolved contexts,
- expected surfaces missing from the pack,
- average recalled nodes,
- average relation checks.

These are runtime-retention diagnostics, not a claim that a small fixture reproduces a full teacher model.

## CLI

```bash
eqforge predict-base knowledge.eqbase --context "Der Hund ist ein"
eqforge benchmark-predictions knowledge.eqbase cases.jsonl --top-k 5
```

## v0.16 regression fixture

The deterministic language fixture compiles only corpus-derived directed relations into `.eqbase` and verifies:

```text
Der Hund ist ein -> Tier
Der Hund kann    -> bellen
Die Katze kann   -> miauen
```

All three expected surfaces are ranked first by the compiled runtime. The fixture also verifies that all candidate contributions originate exclusively from `prediction` or `transition` channels.

---

# v0.19 — Held-out Generalization + Context Coverage

v0.19 separates **captured-behaviour replay** from **held-out context transfer**. Only the train split is compiled into the Equinox BASE. The held-out split is probed against the same teacher only to obtain an evaluation reference and is never inserted into SQLite or the `.eqbase` pack.

```text
Teacher
  ├─ train prompts ─────→ Forge IR → Canonical DB → train.eqbase
  │                                           │
  │                                           └→ train replay baseline
  │
  └─ held-out prompts ─→ evaluation reference only
                                              │
                                              ↓
                                     Equinox held-out replay
```

## Strict split boundary

By default, normalized exact prompt overlap between train and held-out splits is a hard error. The output directory contains `split-manifest.json` with both normalized splits and SHA-256 hashes so the benchmark boundary is auditable.

The held-out teacher IR is stored under `evaluation_only/` and is never ingested into `train.sqlite`.

## Context coverage classes

Every held-out prompt is classified into one of four operational buckets:

- `proper_suffix_transfer` — the full prompt is unseen, but a shorter predictive context already compiled from the train split matches its suffix;
- `resolved_structural` — a predictive context is resolved structurally but is not a strict suffix;
- `lexical_only` — known lexical surfaces are present, but no predictive context is directly resolved;
- `unresolved` — neither predictive context nor useful lexical seed is present.

`exact_or_leaked` exists as a diagnostic bucket and should remain zero in strict mode.

v0.19 also reports:

- fraction of held-out contexts resolved at all;
- proper-suffix transfer rate;
- known-token coverage;
- held-out token novelty rate;
- teacher Top-1 target already present in the compiled pack;
- train-vs-held-out Top-1 and retained-mass gaps;
- metrics broken down by coverage bucket.

This distinction is important. A failure because the correct target surface does not exist in the BASE is different from a failure to route an otherwise-known target from a novel context.

## Two held-out runtime views

As in v0.17, v0.19 evaluates two runtime modes:

1. **Held-out Direct Replay** — associative recall depth is disabled. Longest-known-suffix context resolution remains enabled because it is itself the structural transfer mechanism being tested.
2. **Held-out Full Runtime** — normal bounded recall/routing is enabled.

This makes it possible to tell whether a held-out prediction came from deterministic structural reuse or from broader recalled context.

## Deterministic regression fixture

Compile split:

```text
Hund ist ein
Hund kann
Katze kann
```

Held-out split:

```text
Der Hund ist ein
Mein Hund kann
Die Katze kann
Vogel kann
```

The first three prompts do not exist as compiled context nodes. They are resolved through the known suffixes `Hund ist ein`, `Hund kann`, and `Katze kann`. `Vogel kann` has lexical overlap but no stored predictive suffix and its teacher Top-1 target `fliegen` is absent from the BASE.

Fixture result:

```text
Pack                         1,886 B
Runtime nodes                    36
Prediction relations              9

Train Top-1 replay            100 %
Held-out Top-1                75 %
Proper-suffix transfer        75 %
Lexical-only held-out         25 %
Held-out teacher Top-1 known  75 %
Exact held-out context nodes       0
```

This is intentionally not reported as broad language generalization. It demonstrates a narrower claim: **compiled Equinox structure can be reused on full contexts that were not present in the compile split when they contain a known predictive subcontext**.

## CLI

```bash
eqforge benchmark-generalization /path/to/local/model out/generalization \
  --train train-prompts.txt \
  --heldout heldout-prompts.txt \
  --source-id teacher-A \
  --teacher-top-k 8 \
  --runtime-top-k 8
```

Multiple `--train` and `--heldout` files may be supplied by repeating the flags.

Diagnostic-only exact overlap can be allowed with `--allow-exact-overlap`, but strict mode is the benchmark default.

## Output

```text
generalization-report.json
split-manifest.json
train.sqlite
train.eqbase
train-teacher-behaviour.eqir.json
train-teacher-probe-report.json
evaluation_only/
  heldout-teacher-reference.eqir.json
  heldout-teacher-probe-report.json
```

## Interpretation limit

v0.19 is a held-out **context-transfer** benchmark. It does not yet prove semantic compositionality, novel factual reasoning, or broad out-of-distribution language generalization. Those require progressively harder splits in which surface overlap, suffix overlap, entities, relation patterns, and finally task families are independently held out.

## Regression suite

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V19_ALL_TESTS_OK
```

## Recommended next step — v0.20

**Generalization Ladder + Leakage-Controlled Split Generator.**

Instead of one binary train/held-out split, v0.20 should create increasingly difficult evaluation levels:

```text
L0 exact replay
L1 unseen prefix / known suffix
L2 unseen surface recombination
L3 known entities + unseen relation composition
L4 held-out entities / substitution transfer
L5 held-out task or domain
```

That will show *which kind* of generalization Equinox actually performs, rather than compressing all novelty into one score.


---

# Step 0.20 — Generalization Ladder

v0.20 adds a stratified generalization benchmark instead of treating all unseen prompts as one bucket.
It compiles only the training split into `.eqbase`; evaluation teacher probes are stored under
`evaluation_only/` and are never inserted into the Canonical DB or runtime pack.

## Ladder

| Level | Name | Structural contract |
|---|---|---|
| L0 | exact replay control | exact normalized prompt exists in compile split |
| L1 | known suffix in new outer context | full prompt unseen; a proper suffix is a compiled predictive train prompt |
| L2 | novel recombination of known parts | all tokens known, no L1 suffix replay, at least one known local bigram |
| L3 | novel relation/order over known lexicon | all tokens known, no L1 suffix, no train bigram reused |
| L4 | novel entity in known relational frame | at least one novel token plus a previously observed local relational frame |
| L5 | held-out relation/task family | explicitly labeled family is absent from the entire compile split |

The level labels are evaluation metadata only. Forge validates the structural contract before running;
mislabelled cases fail by default instead of silently inflating a higher-level score.

## Outputs

`benchmark-generalization-ladder` writes:

- `train.sqlite`
- `train.eqbase`
- `train-teacher-behaviour.eqir.json`
- `evaluation_only/ladder-teacher-reference.eqir.json`
- `ladder-manifest.json` with SHA-256 hashes and the exact L0–L5 split
- `generalization-ladder-report.json` with per-level Direct Replay, Full Runtime, token/bigram coverage,
  context-resolution traces and structural-contract results

The report exposes both `highest_level_with_full_top1_success` and a stricter
`highest_contiguous_level_with_full_top1_success`. The contiguous frontier only advances when every
preceding populated level is also fully retained; an isolated success at a harder level therefore
cannot masquerade as a solved ladder.

## CLI

```bash
eqforge benchmark-generalization-ladder /path/to/local/model out/ladder \
  --train-jsonl train.jsonl \
  --eval-jsonl eval.jsonl \
  --source-id teacher-A \
  --teacher-top-k 8 \
  --runtime-top-k 8
```

Train JSONL:

```json
{"prompt":"Hund ist ein","family":"taxonomy"}
```

Evaluation JSONL:

```json
{"prompt":"Mein Hund kann","level":1,"family":"ability"}
```

The included deterministic demo currently reaches L0–L4 Top-1 in the small fixture and fails L5.
That is a pipeline/diagnostic result, not evidence of broad natural-language generalization.


---

# Step 0.21 — Mechanism Attribution / Ablation Suite

v0.21 asks a different question from the L0–L5 ladder: **why did the runtime succeed?**
Every ablation runs against the exact same immutable `.eqbase` pack and the same persisted
evaluation-only teacher reference. No teacher evidence is recompiled for an ablation.

## Runtime mechanism switches

`RuntimeCognitionPolicy` now exposes independent switches for:

- exact-context resolution
- known-suffix context resolution
- lexical seeding
- structural child→parent routing
- associative / semantic relation recall
- direct context prediction
- transition prediction
- prediction from recalled contexts

All switches default to `True`, so v0.16–v0.20 behavior is unchanged.

## Attribution design

The suite performs leave-one-mechanism-out tests plus targeted combination ablations. For every
mechanism and every populated L0–L5 level it reports:

- Top-1 retention delta
- NDCG delta
- retained teacher-probability-mass delta
- recall-node delta
- relation-check delta
- exact prompts that lose or gain Top-1

Single ablations are interpreted as **necessity under the current fixed BASE**, not as unique causal
credit. Redundant paths can hide one another, so v0.21 also contains combination probes such as
`no_suffix_and_parent_routing`.

## Deterministic fixture result

The included fixture retains 5/6 ladder cases at baseline (L0–L4; L5 remains unsupported).
The ablations identify:

```text
L0/L1 direct result path:
  direct context prediction is necessary

L1 redundancy:
  disable suffix only       -> survives
  disable parent only       -> survives
  disable suffix + parent   -> L1 fails

L2/L3/L4 transfer path:
  lexical seeds
      ↓
  parent routing
      ↓
  recalled-context prediction
```

Removing any one of those three mechanisms drops all L2–L4 Top-1 successes in the fixture.
`relation_recall` and `transition_prediction` are neutral there, which is expected because that
specific BASE contains teacher prediction edges but no supporting semantic-recall or corpus-transition
channel for those cases.

This is a controlled attribution result, not a claim that the same mechanisms dominate on larger or
natural corpora.

## CLI

```bash
eqforge benchmark-mechanisms /path/to/local/model out/attribution \
  --train-jsonl train.jsonl \
  --eval-jsonl eval.jsonl \
  --source-id teacher-A \
  --teacher-top-k 8 \
  --runtime-top-k 8
```

Outputs include the normal v0.20 ladder artifacts under `out/attribution/ladder/` plus
`mechanism-attribution-report.json` with per-case and per-level ablation traces.

# Step 0.29 — Exception Consensus, Stability & Reversal

v0.29 adds a persistent cross-source lifecycle for v0.28 automatic exception hypotheses. Exception
induction and runtime authorization are now separate: a newly discovered override starts as
`candidate`, becomes `stable` only after repeated independent support, falls to `contested` or
`quarantined` under contradictory sources, and can recover only after a fresh clean-support streak.

Runtime lifecycle gating keeps non-stable overrides in the `.eqbase` for auditability while preventing
them from changing predictions. Source trust weights are honored without allowing one source to count
as several independent sources. See `RELEASE_V0_29.md` for the lifecycle contract and fixture.
