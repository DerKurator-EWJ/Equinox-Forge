# Equinox Forge v0.6 — Contextual Hidden-State Evidence

Forge v0.6 adds a fourth independent language-evidence channel: **context-dependent internal teacher representations**.

The current pipeline can now combine:

```text
static embedding geometry
+ controlled corpus observations
+ executed next-token behaviour
+ contextual hidden-state geometry
        ↓
canonical Equinox text nodes
        ↓
typed raw evidence with provenance
        ↓
Canonical DB
        ↓
future compiler / Runtime BASE
```

The central rule remains:

> **The source representation is not the Equinox runtime representation.**

Transformer token IDs, hidden dimensions and raw activation vectors do not become Equinox identities.

## Why v0.6 exists

A static token embedding cannot distinguish meanings that depend on context. For example, the same surface form:

```text
Bank
```

can occur in:

```text
Die Bank genehmigte den Kredit.
Wir sitzen im Park auf der Bank.
```

Both uses resolve to the **same canonical Equinox surface node** `Bank`. Forge then asks the teacher for the target token's contextual hidden representation and records sparse evidence between the two **context nodes**.

No second character-Q alphabet and no teacher-specific word ID is created.

## Canonical representation

For each probe Forge creates or reuses:

```text
character Qs
   ↓
canonical surface: Bank
   ↓ contextual_use
canonical marked context
```

A marked context is deterministic, e.g.:

```text
Die ⟦Bank⟧ genehmigte den Kredit.
```

The target marker is part of the context identity so multiple occurrences in one sentence can remain distinguishable.

## Hidden vectors are transient extraction data

Raw hidden vectors are deliberately **not written into Canonical IR or the Canonical DB**.

Forge normalizes them during extraction and derives bounded sparse evidence:

```text
context A ← contextual_similarity → context B
```

The raw cosine is preserved in evidence metadata. The canonical relation score stays inside `[0,1]`.

This means a future compiler can combine hidden evidence from models with completely different hidden sizes without making Equinox depend on any one teacher architecture.

## Probe dataset format

Input is JSONL. A header is optional:

```json
{"format":"equinox-forge-probe-dataset-v1"}
{"id":"bank-fin-1","text":"Die Bank genehmigte den Kredit.","target":"Bank","label":"finance"}
{"id":"bank-seat-1","text":"Wir sitzen im Park auf der Bank.","target":"Bank","label":"seat"}
```

Fields:

- `id`: stable evaluation probe ID;
- `text`: teacher input;
- `target`: exact surface whose contextual state is extracted;
- `occurrence`: optional 1-based occurrence when the target appears multiple times;
- `label`: optional benchmark label;
- `metadata`: optional evaluation metadata.

### Labels cannot leak into knowledge

`label` is used **only in the separate evaluation report** to compute metrics such as same-sense vs different-sense cosine and nearest-neighbour label accuracy.

Labels are not stored in:

- canonical node IDs;
- node metadata;
- relation metadata;
- Canonical DB evidence.

The regression suite verifies that removing all labels leaves the canonical IR/evidence graph unchanged.

## Evidence channels added in v0.6

### `contextual_use`

```text
canonical surface -> canonical context
```

Records that a particular target surface was probed in a particular context/layer.

### `contextual_similarity`

```text
context A -> context B
```

A sparse top-k graph derived from teacher hidden-state cosine similarity. By default comparisons are restricted to uses of the **same canonical surface**. Cross-surface hidden similarity is opt-in so it cannot silently replace the separate `semantic_similarity` channel from v0.3.

## Evaluation metrics

When labels are provided, the report can calculate:

- mean cosine for same-label pairs;
- mean cosine for different-label pairs;
- nearest-neighbour label accuracy.

These are diagnostics only. They do not become Equinox relation weights.

## Optional Hugging Face backend

`TransformersHiddenStateBackend` uses:

- `AutoTokenizer` with a fast tokenizer and offset mappings;
- `AutoModel` with `output_hidden_states=True`;
- exact character-span → teacher-subword alignment;
- selectable hidden layers;
- `mean`, `first` or `last` pooling over target subwords.

It never uses teacher tokenization as canonical Equinox tokenization.

Install the optional extraction runtime on the machine doing teacher work:

```bash
pip install -e '.[hf-runtime]'
```

The backend uses **local model files only** and does not implicitly download a checkpoint.

## CLI

Example:

```bash
python -m equinox_forge.cli probe-hidden \
  /path/to/local/hf/model \
  examples/probes/bank_senses.jsonl \
  out/bank_hidden.eqir.json \
  --source-id teacher/my-model \
  --source-version v1 \
  --adapter adapters/qwen2.json \
  --db out/master.sqlite \
  --layers -1 \
  --pooling mean \
  --top-k 6 \
  --min-cosine 0.25
```

Useful controls:

- `--layers -1 -5 ...`
- `--pooling mean|first|last`
- `--top-k`
- `--min-cosine`
- `--evidence-confidence`
- `--max-context-words`
- `--include-cross-surface`
- `--keep-vectors-in-report` — diagnostic report only, never Canonical IR;
- `--device cpu|cuda`
- `--dtype auto|float32|float16|bfloat16`
- `--trust-remote-code` — off by default.

## Included benchmark fixture

`examples/probes/bank_senses.jsonl` contains six German uses of `Bank`:

- three financial contexts;
- three seating/bench contexts.

The labels are present only to validate whether a teacher's contextual space separates these uses.

## Real neural integration test

`test_tiny_contextual_runtime.py` trains a small bidirectional PyTorch GRU and extracts the actual neural hidden state at the `bank` token through the same generic Forge backend boundary.

This is a plumbing/integration test, **not evidence that a toy GRU solves semantic disambiguation generally**.

The test verifies that Forge consumes a computed neural state rather than only scripted vectors.

## Regression suite

Run:

```bash
python tests/run_all.py
```

Expected final marker:

```text
FORGE_V06_ALL_TESTS_OK
```

Current suite covers:

```text
v0.1 canonical IR / DB / aggregation
v0.2 Hugging-Face adapter contract
v0.3 static embedding extraction
v0.4 controlled corpus language evidence
v0.5 executed causal teacher behaviour
v0.6 contextual hidden-state evidence
v0.6 real tiny neural hidden-state runtime
```

## What v0.6 does NOT claim

This release does not yet create permanent Equinox "sense" nodes such as `Bank(finance)` or `Bank(seat)`.

That is intentional. v0.6 collects the evidence needed to justify such structures first.

A later compiler can create a sense/concept macro only when multiple independent observations and/or teacher sources support a stable contextual cluster.

This avoids turning one model's hidden geometry directly into Equinox ontology.

## Recommended next step — v0.7

**Evidence Fusion + Provisional Sense Compiler**:

```text
embedding evidence
+ corpus substitution/prediction
+ teacher behaviour
+ contextual hidden evidence
        ↓
source-aware evidence fusion
        ↓
stable contextual clusters
        ↓
provisional sense/concept nodes
        ↓
confidence / conflict / provenance
```

The important constraint for v0.7 should be that a sense node is a compiled hypothesis supported by evidence, not a direct copy of a teacher activation.
