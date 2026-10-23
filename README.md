# Equinox Forge v0.3 — First Text Teacher Extractor

Forge v0.3 is the first step that turns **actual Hugging Face Safetensors data** into Canonical Equinox IR.

It keeps the architectural boundary introduced in v0.2:

`teacher checkpoint -> adapter -> bounded extraction -> Canonical IR -> Canonical DB -> compile`

The teacher tensor is **never** treated as an Equinox runtime weight. It is only an evidence source.

## What v0.3 extracts

The first extraction channel is deliberately narrow:

1. inspect a local Hugging Face model;
2. resolve its `input_embeddings` tensor through the v0.2 adapter contract;
3. read a bounded subset of token embeddings from Safetensors;
4. decode token surfaces from local tokenizer JSON;
5. convert each accepted text surface into Equinox character-Q nodes plus a level-1 surface macro;
6. average duplicate token surfaces into one canonical surface vector;
7. compute sparse top-k cosine neighbours;
8. emit `semantic_similarity` evidence with full source/adapter/tensor provenance;
9. optionally ingest nodes, evidence, source model metadata and token aliases into the Canonical SQLite DB.

This is **not yet language understanding** and does not claim that cosine similarity equals meaning. It is the first measurable bridge from a real teacher representation into the Equinox evidence system.

## Why the Q layer is characters

For the text branch, the first Equinox representation uses:

`Q = Unicode character`

A teacher token such as `Hund` becomes a surface macro over:

`H -> u -> n -> d`

The teacher tokenizer remains source provenance only. Therefore two different models can map their own token IDs to the same canonical Equinox surface node.

Teacher token IDs are deliberately **not stored on canonical nodes**. They live in `source_aliases`, so importing another teacher cannot contaminate a shared canonical node with model-specific identity.

## Subwords are not silently called words

Hugging Face vocabularies often contain BPE / WordPiece / SentencePiece fragments. Forge v0.3 therefore labels imported level-1 nodes as generic text surfaces rather than pretending every teacher token is a whole word.

Common static decoding is supported for:

- GPT-2 / ByteLevel BPE reversible byte alphabet;
- `Ġ` word boundaries;
- SentencePiece `▁` boundaries;
- WordPiece `##` continuation markers;
- JSON BPE / WordPiece vocabularies;
- JSON Unigram vocabularies.

A checkpoint that only exposes a binary `tokenizer.model` / `spiece.model` without `tokenizer.json` or `vocab.json` is not parsed in v0.3.

## Sparse extraction

The extractor never creates every possible pair. For each canonical surface it keeps at most `top_k` embedding neighbours above `min_similarity`.

The implementation computes cosine similarities in row batches and uses partial top-k selection rather than fully sorting each vocabulary row.

For a bounded extraction of `N` surfaces with `k` neighbours, stored relation evidence is approximately `O(N*k)`, not `O(N²)`.

The similarity search is still `O(N²)` arithmetic in v0.3. ANN indexing is a later scaling step.

## Bounded Safetensors reads

Forge uses `safetensors.safe_open(...).get_slice()` and reads only the row interval needed by the selected token IDs rather than materializing the complete embedding matrix.

This matters for future large teachers where the full embedding matrix may be many gigabytes.

## Score and confidence are separate

For embedding-neighbour evidence:

- `score` = cosine similarity, clamped to the canonical `[0,1]` relation-score range after applying the configured minimum threshold;
- `confidence` = trust assigned to this extraction channel (`0.55` by default).

Confidence is intentionally **not** calculated from cosine magnitude. A very high cosine value does not prove that the relation has semantic truth.

Later channels can add independent evidence to the same canonical pair:

- controlled teacher predictions;
- hidden-state probes;
- corpus observations;
- structured knowledge graphs;
- other teacher models.

The compiler can then aggregate those independent sources.

## Idempotent ingestion

v0.3 adds an `evidence_fingerprint` to the Canonical DB. Re-running the exact same extraction does not duplicate the same evidence record.

Existing v0.1/v0.2 SQLite databases are migrated non-destructively when opened:

- `evidence_fingerprint` is added when absent;
- `source_aliases.metadata_json` is added when absent.

## Included adapters

- `adapters/deepseek_v3.json`
- `adapters/qwen2.json`
- `adapters/gpt2.json`

The actual local checkpoint is always inspected before extraction. Adapter tensor names are not blindly trusted.

## CLI

### Inspect and plan

```bash
python -m equinox_forge.cli inspect-hf /path/to/model
python -m equinox_forge.cli plan-hf /path/to/model adapters/gpt2.json --output out/plan.json
```

### Extract bounded text evidence

```bash
python -m equinox_forge.cli extract-text \
  /path/to/model \
  adapters/gpt2.json \
  out/teacher.eqir.json \
  --source-id my-teacher \
  --source-version v1 \
  --db out/master.sqlite \
  --max-tokens 10000 \
  --top-k 8 \
  --min-similarity 0.30
```

Useful bounds:

- `--start-token-id`
- `--max-tokens`
- `--top-k`
- `--min-similarity`
- `--batch-size`
- `--max-surface-chars`
- `--evidence-confidence`

### Compile current evidence

```bash
python -m equinox_forge.cli compile out/master.sqlite
```

## Offline Safetensors integration fixture

`examples/hf_teacher_synthetic/` is a complete Hugging-Face-like local directory containing:

- `config.json`;
- `tokenizer.json`;
- `tokenizer_config.json`;
- a real `model.safetensors` file.

Its vectors are deliberately hand-authored so the test can prove that expected clusters such as `Hund/Hunde`, `Auto/Wagen` and `laufen/rennen` are recovered. It is **not a trained language model** and is not used as evidence for model quality.

Example:

```bash
python -m equinox_forge.cli extract-text \
  examples/hf_teacher_synthetic \
  adapters/deepseek_v3.json \
  out/synthetic.eqir.json \
  --source-id synthetic/semantic \
  --source-version v1 \
  --db out/synthetic.sqlite \
  --max-tokens 32 \
  --top-k 2 \
  --min-similarity 0.60
```

Expected current fixture result:

```text
11 accepted teacher tokens
11 canonical text surfaces
24 unique character-Q nodes
14 sparse relation-evidence records
35 total nodes
```

## Tests

```bash
python tests/test_forge.py
python tests/test_hf_adapter.py
python tests/test_text_teacher.py
python tests/test_db_migration_v02.py
```

The tests cover:

- v0.1 canonical ID / relation aggregation behaviour;
- v0.2 adapter planning;
- real Safetensors row extraction;
- tokenizer surface conversion;
- expected nearest-neighbour relations;
- idempotent evidence ingestion;
- migration of an older v0.2-style database.

## Deliberate limits of v0.3

v0.3 does **not** yet:

- execute a Transformer;
- extract hidden states;
- extract contextual next-token behaviour;
- infer complete words/phrases from arbitrary subword streams;
- claim embedding similarity is equivalent to semantic knowledge;
- compile a final Android `BASE.eqx` language pack;
- use ANN search for million-node embedding spaces.

These limits are intentional. v0.3 proves the first teacher-data path without mixing model-specific runtime behaviour into the Canonical Equinox representation.

## Next Forge step

**v0.4 — Controlled Language Evidence**

The next useful step is to add a small probe-corpus pipeline that turns teacher/corpus context into structures above token surfaces:

`characters -> surfaces -> words/phrases -> contextual relations`

The key goal is to stop relying on static embedding geometry alone and start producing evidence for:

- directed transition / prediction;
- contextual co-activation;
- substitution classes;
- word-form composition;
- phrase macros.

That is the first step toward a language BASE that Equinox can actually query rather than merely a static similarity graph.
