# Equinox Forge v0.9 — Source Ablation, Reweighting & Rebuild Engine

Forge v0.9 makes provenance **operational**.

Until v0.8, Forge could preserve source provenance, fuse evidence, create provisional sense concepts, and track cross-teacher stability. v0.9 adds the ability to change the trust policy for a source **after extraction** and rebuild derived Equinox knowledge without running the original teacher again.

```text
raw extracted evidence (immutable history)
        ↓
source policy
  enabled / disabled
  trust weight 0..1
  version replacement
        ↓
temporary effective-evidence view
        ↓
existing v0.1–v0.8 compiler
        ↓
recompiled senses + weighted consensus
        ↓
new rebuild report / lifecycle state
```

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
FORGE_V09_ALL_TESTS_OK
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

## What v0.9 does NOT prove

v0.9 does not determine the objectively correct trust value for a teacher. Trust weights are compiler policy and must eventually be calibrated against held-out benchmarks.

It also does not yet rebuild the **entire Master DB transitively** after a source change. The current engine rebuilds a specified derived target/sense family and records the result.

That makes the next logical step:

## Recommended next step — v0.10

**Dependency Graph + Incremental Transitive Rebuild.**

Instead of manually rebuilding `Bank`, `Hund`, etc., Forge should know which derived structures depend on which evidence or lower-level hypotheses:

```text
source changed
    ↓
find directly affected derived nodes
    ↓
walk dependency graph upward
    ↓
rebuild only affected subgraph
    ↓
leave unrelated Master DB untouched
```

That is the step needed before scaling from experiments to a genuinely large continuously maintainable Master Archive.
