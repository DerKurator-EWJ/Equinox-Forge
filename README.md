# Equinox Forge v0.16 — Runtime Recall + Prediction Engine

**Current milestone:** v0.16 executes bounded recall and ranked prediction directly on the compiled `.eqbase` runtime, preserving a hard distinction between recall links and directed prediction channels. It adds contribution traces plus a context→expected benchmark harness for measuring how much compiled behaviour survives into the runtime. Historical sections below document the earlier Forge milestones.

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
