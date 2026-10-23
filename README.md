# Equinox Forge v0.8 — Cross-Teacher Consensus & Hypothesis Stability

Forge v0.8 adds a persistent **quality-control layer for derived Equinox knowledge**.

The previous pipeline can already create provisional higher-order concepts from multiple evidence channels:

```text
embeddings
+ corpus observations
+ teacher next-token behaviour
+ contextual hidden-state evidence
        ↓
Evidence Fusion
        ↓
Provisional Sense / Concept
```

v0.8 asks the next necessary question:

> Does that derived concept remain supported when independent sources and later rebuilds are taken into account?

The new pipeline is:

```text
raw source evidence
        ↓
provisional sense compiler
        ↓
source-specific re-evaluation
        ↓
support / conflict / abstain votes
        ↓
cross-source consensus
        ↓
persistent rebuild history
        ↓
candidate / stable / contested / quarantined
```

## Central rule

A high fused score is **not sufficient** to make a derived concept stable.

A hypothesis becomes `stable` only when it receives enough independent support and survives repeated compiler runs under the same policy.

Stability is reversible:

```text
candidate
   ↓ repeated independent confirmation
stable
   ↓ later conflicting evidence
contested
   ↓ stronger/multiple conflict
quarantined
```

A hypothesis that disappears on later rebuilds is also downgraded and may eventually be quarantined.

## Source-specific voting

v0.8 reconstructs evidence per independent `source_id@source_version` instead of using only the already aggregated relation graph.

For each provisional cluster, a source is evaluated against:

- internal affinity between contexts that belong to the cluster;
- competing affinity from those contexts to contexts outside the cluster;
- the source-specific evidence channels that were actually observed.

A source can vote:

```text
support
conflict
abstain
```

Structural lexical overlap is deliberately **not** counted as an independent source vote, because it does not originate from an external teacher/corpus source.

Current source-specific channels can include:

```text
contextual_similarity
semantic_similarity
substitution
transition
prediction_signature
```

Missing channels remain missing; they are not silently converted into positive support.

## Consensus score

For decisive source votes:

```text
consensus = support_sources / (support_sources + conflict_sources)
```

Abstaining sources do not artificially penalize consensus.

The default lifecycle policy is:

```text
source_vote_threshold      0.58
source_vote_margin         0.08
stable_min_sources         2
stable_min_runs            2
stable_consensus           0.75
quarantine_conflicts       2
quarantine_after_misses    2
```

These values are compiler policy, not Equinox ontology. They can be changed and the derived state rebuilt.

## Persistent hypothesis history

The Canonical DB now contains two new tables:

### `hypothesis_runs`

One record per tracked derived compile:

```text
run_id
compiler
target_id
policy_hash
output_hash
created_at
metadata
```

### `hypothesis_states`

Persistent state for every derived hypothesis under a specific policy:

```text
hypothesis_id
target_id
policy_hash
membership_hash
status
first_seen_run
last_seen_run
seen_runs
consecutive_seen
missed_runs
consensus_score
support_sources
conflict_sources
metadata
```

The raw evidence store remains untouched. Lifecycle state is derived metadata and can be rebuilt.

## Reversible status rules

### `candidate`

The concept exists, but has not yet accumulated enough independent and temporal confirmation.

### `stable`

Requires all of the configured conditions, including:

```text
support_sources >= stable_min_sources
consecutive_seen >= stable_min_runs
consensus_score >= stable_consensus
```

### `contested`

Used when later source conflict weakens a previously accepted hypothesis or when a hypothesis disappears from a rebuild but has not yet crossed the quarantine threshold.

### `quarantined`

Used conservatively when:

```text
conflict_sources >= quarantine_conflicts
```

or when a previously known hypothesis repeatedly disappears from rebuilds.

Quarantine means "do not trust this derived structure as normal BASE knowledge". It does not delete raw evidence.

## CLI

The existing sense compiler can now track stability:

```bash
python -m equinox_forge.cli compile-senses \
  master.sqlite \
  bank_senses.eqir.json \
  --surface Bank \
  --track-stability
```

Useful controls:

```text
--source-vote-threshold 0.58
--source-vote-margin 0.08
--min-observed-pairs 1
--stable-min-sources 2
--stable-min-runs 2
--stable-consensus 0.75
--quarantine-conflicts 2
--quarantine-after-misses 2
--consensus-report path.json
```

The resulting derived IR concept nodes are annotated with fields such as:

```json
{
  "lifecycle_status": "stable",
  "consensus_score": 1.0,
  "support_sources": 2,
  "conflict_sources": 0,
  "seen_runs": 2,
  "consecutive_seen": 2
}
```

The persistent DB state is authoritative even if an older copy of a derived node already exists in the Canonical DB.

## Inspecting hypothesis state

```bash
python -m equinox_forge.cli hypotheses master.sqlite
```

Optionally filter by target ID:

```bash
python -m equinox_forge.cli hypotheses master.sqlite --target-id <canonical-id>
```

`stats` now also reports:

```text
hypothesis_runs
hypotheses
```

## Reproducible v0.8 demo

Run:

```bash
python examples/build_consensus_demo.py
```

The demo creates two `Bank` sense hypotheses and applies four rebuild stages:

```text
Run 1:
Teacher A supports
Teacher B supports
→ candidate

Run 2:
same independent support again
→ stable

Run 3:
Teacher C prefers competing cross-sense coupling
→ contested

Run 4:
Teacher D independently adds the same conflict
→ quarantined
```

The demo writes:

```text
out/consensus_demo.sqlite
out/consensus_demo.eqir.json
out/consensus_demo.states.json
out/consensus_demo.timeline.json
```

The benchmark labels used to verify the fixture are never imported as Equinox knowledge.

## Why this matters before large-scale import

Without this layer, a Master Compiler could promote a mistake simply because one teacher was very confident.

v0.8 changes the model to:

```text
one source says X
        ↓
possible evidence

several independent sources say X
        ↓
stronger candidate

same structure survives rebuilds
        ↓
stable derived knowledge

later sources contradict X
        ↓
downgrade / quarantine
```

This is especially important once Forge begins combining many Hugging-Face models, datasets and future vision/audio teachers.

## Regression suite

Run:

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V08_ALL_TESTS_OK
```

The suite currently covers:

```text
v0.1 canonical IR / database / relation aggregation
v0.2 Hugging-Face adapter contract
v0.3 static teacher embedding extraction
v0.4 controlled corpus evidence
v0.5 executed causal-teacher behaviour
v0.5 real tiny causal neural runtime
v0.6 contextual hidden-state evidence
v0.6 real tiny contextual neural runtime
v0.7 evidence fusion / provisional sense compilation
v0.7 benchmark-label non-leakage
v0.8 source-specific consensus voting
v0.8 candidate → stable promotion
v0.8 stable → contested downgrade
v0.8 multi-source quarantine
v0.8 persistent run/state history
```

## What v0.8 does NOT prove

v0.8 does not prove that the compiled concepts are semantically correct in general.

It establishes the infrastructure required to distinguish:

```text
high score
```

from:

```text
independently supported + temporally stable derived knowledge
```

Real quality still has to be tested on larger datasets and real independent teacher models.

## Recommended next step — v0.9

**Source Ablation, Reweighting & Rebuild Engine**.

The next step should make provenance operational:

```text
remove Teacher C
change trust weight of Teacher B
upgrade one source version
rebuild derived knowledge
compare which hypotheses survive/change
```

That will allow Forge to repair the Master DB without re-extracting every source and will be a prerequisite for safely merging many large external models.
