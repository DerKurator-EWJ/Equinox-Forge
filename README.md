# Equinox Forge v0.2 — Hugging Face Adapter Contract

Forge v0.2 freezes the boundary between **teacher/model-specific extraction** and the **model-independent Equinox compiler**.

The goal is deliberately not to write a new compiler for every Hugging Face model. A new teacher family should normally require only an adapter JSON that declares where useful teacher signals live and which extraction channels are allowed.

## Pipeline

`Hugging Face model -> adapter contract -> extraction plan -> extractor -> Canonical IR -> canonical DB -> Equinox compilation`

The v0.1 Canonical IR, content-derived IDs, evidence aggregation and SQLite database remain intact.

## Adapter format

`equinox-forge-hf-adapter-v1` separates four things:

- model identity: family, `model_type`, architecture names;
- Equinox target semantics: modality and Q strategy (`unicode_character` for the first language branch);
- tensor **roles**, not hard-coded compiler assumptions;
- extraction channels and their prerequisites.

Example roles:

- `input_embeddings`
- `output_head`
- `transformer_layers`

Example channels:

- `token_embedding_neighbors`: static sparse neighbour evidence;
- `output_prediction_priors`: directed prediction evidence;
- `runtime_hidden_states`: behaviour extraction that requires executing the teacher.

A teacher tensor is never declared to be an Equinox weight. It is only a source from which an extractor may generate canonical evidence.

## Local Hugging Face inspection

Forge can inspect a downloaded model directory without loading the model into RAM. It reads:

- `config.json`;
- common tokenizer file presence;
- `*.safetensors.index.json` weight maps;
- or, for unsharded Safetensors, only the small JSON header.

Tensor payloads are not loaded by `inspect-hf` or `plan-hf`.

## Extraction plans

Before extraction, Forge resolves every adapter role against the actual local model and emits a deterministic extraction plan containing:

- adapter hash;
- resolved tensor names;
- enabled/unavailable channels;
- model-type/architecture warnings;
- validity status.

This is the reproducibility boundary: later evidence can record exactly which adapter version/hash was used.

## Included adapter templates

- `adapters/deepseek_v3.json`
- `adapters/qwen2.json`

These are configuration templates. They are still checked against the actual local model before any extraction is allowed. A model update therefore cannot silently move a tensor and keep using a stale assumption.

## Canonical DB addition

v0.2 adds `source_models`, recording:

- source/model version;
- adapter ID;
- adapter SHA-256;
- model type;
- inspected source manifest.

Raw relation evidence remains separate, as in v0.1.

## CLI

```bash
python -m equinox_forge.cli validate-adapter adapters/deepseek_v3.json
python -m equinox_forge.cli inspect-hf /path/to/hf/model
python -m equinox_forge.cli plan-hf /path/to/hf/model adapters/deepseek_v3.json --output out/plan.json
python -m equinox_forge.cli detect-adapter /path/to/hf/model --adapters adapters
python -m equinox_forge.cli auto-adapter /path/to/hf/model out/my_model_adapter.json --adapter-id my-model-v1
```

The existing v0.1 commands (`validate`, `ingest`, `stats`, `compile`, `export`) remain available.

## Synthetic offline test

`examples/hf_synthetic/` contains a tiny Hugging-Face-like directory with only config/tokenizer metadata and a Safetensors index. No model weights are required to test adapter resolution.

```bash
python tests/test_forge.py
python tests/test_hf_adapter.py
```

## Important boundaries

v0.2 does **not** yet extract millions of vectors and does not execute a Transformer. That is intentional. It first makes the interface stable so the next extractor cannot leak model-specific assumptions into the canonical compiler.

The first real extractor should start with a small open causal language model and produce bounded evidence for a small vocabulary before scaling toward DeepSeek-class models.

## Next Forge step

**v0.3 — First Text Teacher Extractor**

Planned proof:

1. load a small Hugging Face causal LM;
2. decode a bounded vocabulary into surface strings;
3. map those strings to Equinox character-Q / surface macros;
4. extract sparse top-k embedding-neighbour evidence;
5. optionally add controlled next-token prediction evidence;
6. ingest the resulting IR into the canonical DB;
7. verify deduplication and measure source/IR/runtime sizes.
