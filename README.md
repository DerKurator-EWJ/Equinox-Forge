# Equinox Forge v0.7 — Evidence Fusion + Provisional Sense Compiler

Forge v0.7 is the first release that turns the evidence collected in v0.3–v0.6 into a **new Equinox-native higher-order hypothesis**.

Until v0.6 Forge only collected evidence:

```text
static teacher embedding geometry
+ controlled corpus observations
+ executed next-token behaviour
+ contextual hidden-state geometry
        ↓
Canonical DB
```

v0.7 adds:

```text
Canonical DB
   ↓
source-aware relation aggregation
   ↓
multi-channel context fusion
   ↓
complete-link contextual clustering
   ↓
provisional Equinox sense/concept nodes
```

The central rule is still:

> A compiled sense is an Equinox hypothesis supported by evidence. It is not a copied teacher label, activation, token ID or ontology entry.

## Why this step matters

A surface such as `Bank` should remain one canonical text surface. Different uses can later support different higher structures:

```text
                 ┌─ provisional sense A
canonical Bank ──┤
                 └─ provisional sense B
```

Forge must discover those higher structures from evidence rather than pre-programming `Bank(finance)` and `Bank(seat)`.

## Inputs used by the fusion compiler

For each pair of contextual uses of one canonical surface, v0.7 can combine six channels:

1. `contextual_similarity`
   - hidden-state similarity from v0.6;
2. lexical overlap
   - exact overlap of canonical context members;
3. `semantic_similarity`
   - static teacher embedding evidence from v0.3;
4. `substitution`
   - corpus slot evidence from v0.4;
5. `transition`
   - directed corpus transition evidence from v0.4;
6. prediction-signature similarity
   - similarity of compiled next-token distributions from v0.4/v0.5 canonical prediction contexts.

The default weights are:

```text
hidden_similarity     0.55
lexical_overlap       0.05
semantic_similarity   0.15
substitution          0.10
transition            0.05
prediction_signature  0.10
```

They are policy, not ontology. They can be changed and recomputed without re-extracting the raw teacher/corpus evidence.

## No opaque universal weight

Every pair in the compiler report preserves:

- each channel score separately;
- the weights actually used;
- the fused score;
- the number of positively supporting channels.

Missing channels are not silently treated as positive evidence. Available zero-valued channels may penalize the weighted score, while `min_channels` counts only channels with positive support.

## Relation aggregation remains source-aware

Raw evidence remains in the Canonical DB. Before fusion, evidence for an identical canonical relation is aggregated using the existing v0.1 compiler logic:

```text
raw evidence A ─┐
raw evidence B ─┼→ compiled relation score/confidence
raw evidence C ─┘
```

The compiled relation retains evidence/source counts. The sense compiler consumes that derived view; it does not destroy or overwrite raw evidence.

## Complete-link clustering

v0.7 deliberately does **not** use simple connected components.

With connected components:

```text
A ~ B
B ~ C
```

could merge `A,B,C` even if `A` and `C` are incompatible.

Instead the compiler uses deterministic complete-link merging. Two clusters merge only when **every cross-cluster pair**:

```text
fused_score >= threshold
AND
supporting_channels >= min_channels
```

This makes provisional senses harder to create and reduces bridge-collapse.

## Provisional sense identity

A sense node is a canonical `concept` node whose members are:

```text
[target surface, context 1, context 2, ...]
```

Its ID is deterministic from that canonical composition. Therefore the same DB + policy + cluster membership yields the same sense ID.

The node metadata explicitly marks:

```json
{
  "provisional": true,
  "compiler": "equinox-forge-sense-compiler-v1",
  "compiler_version": "0.7"
}
```

A provisional sense is not claimed to be a permanent truth. Later compiler passes may strengthen, split, merge, quarantine or discard it.

## Benchmark-label isolation

The existing `Bank` probe dataset contains labels only for evaluation. The sense compiler receives only the Canonical DB.

The v0.7 regression test verifies that:

- the compiler forms two three-context clusters;
- the external benchmark labels correspond to the two clusters;
- the strings `finance` and `seat` never appear in the derived Equinox IR;
- repeated compilation yields identical concept IDs.

This prevents evaluation truth from leaking into the knowledge graph.

## CLI

After ingesting contextual and other evidence into one Canonical DB:

```bash
python -m equinox_forge.cli compile-senses \
  out/master.sqlite \
  out/bank_senses.eqir.json \
  --surface Bank
```

Important controls:

```text
--threshold 0.62
--min-channels 2
--min-contexts 2
--include-singletons
--w-hidden
--w-lexical
--w-semantic
--w-substitution
--w-transition
--w-prediction
```

By default this is a dry derived compile: it writes IR + report but does not mutate the Canonical DB.

To persist the provisional nodes/evidence:

```bash
python -m equinox_forge.cli compile-senses \
  out/master.sqlite \
  out/bank_senses.eqir.json \
  --surface Bank \
  --ingest-derived
```

This explicit switch is intentional because derived hypotheses should not silently contaminate the evidence store.

## Output report

The report contains:

```text
target surface/id
contexts found
all context-pair channel scores
fused pair scores
accepted-pair count
cluster membership
mean/min internal cluster score
evidence channels supporting each cluster
unresolved contexts
fusion policy
```

No raw hidden vectors are required.

## Current Bank fixture

The deterministic integration fixture has six uses of `Bank`:

```text
3 financial uses
3 bench/seating uses
```

The compiler does not see those labels. With scripted hidden evidence plus independent semantic evidence, it produces:

```text
6 contexts
2 provisional concepts
3 contexts per concept
0 unresolved contexts
```

The labels are then used only to verify the result externally.

## Regression suite

Run:

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V07_ALL_TESTS_OK
```

The suite covers:

```text
v0.1 canonical IR / DB / aggregation
v0.2 Hugging-Face adapter contract
v0.3 static embedding extraction
v0.4 controlled corpus language evidence
v0.5 executed causal teacher behaviour
v0.5 real tiny causal neural runtime
v0.6 contextual hidden-state evidence
v0.6 real tiny contextual neural runtime
v0.7 multi-channel evidence fusion
v0.7 deterministic provisional sense compilation
v0.7 benchmark-label non-leakage
v0.7 idempotent derived ingest
```

## What v0.7 does NOT claim

v0.7 does not prove that its provisional concepts correspond to human meanings in general.

It proves that Forge now has a deterministic mechanism for:

```text
independent evidence
→ source-aware aggregation
→ multi-channel support
→ conservative clustering
→ higher Equinox-native structure
```

Real semantic quality must be measured on larger labelled and unlabelled datasets and across multiple teachers.

## Recommended next step — v0.8

**Conflict, Stability & Cross-Teacher Consensus Compiler**.

The next compiler should test whether a provisional structure survives when:

```text
Teacher A agrees
Teacher B disagrees
Corpus evidence is weak/strong
new contexts arrive
sources are removed/reweighted
```

That requires explicit support/conflict accounting, stability across recompilations, source ablation and promotion rules from `provisional` to a stronger derived state.
