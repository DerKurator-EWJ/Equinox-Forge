# Equinox Forge v0.5 — Teacher Behaviour Probes

Forge v0.5 adds the first **executed teacher behaviour** channel.

The knowledge pipeline is now:

`teacher embeddings + controlled corpus + teacher forward behaviour -> canonical text nodes -> typed evidence -> Canonical DB -> compiler`

The central rule remains unchanged:

**The source of knowledge is not the Equinox runtime representation.**

A Transformer may produce the evidence, but its tokenizer IDs, tensors and runtime do not become Equinox's canonical identity system.

## What v0.5 adds

A new causal-teacher probe layer can execute controlled prompts and record the model's actual next-token distribution:

`controlled context -> causal teacher -> top-k next-token probabilities -> canonical Equinox context/target nodes -> prediction evidence`

Each prediction record preserves:

- teacher token ID;
- raw tokenizer token;
- decoded token surface;
- canonical surface;
- top-k rank;
- raw logit when available;
- teacher probability;
- temperature;
- source/model version;
- extraction method;
- backend identity.

The **score stored in raw evidence is the teacher probability**. It is not silently reinterpreted as an Equinox relation weight. The compiler remains responsible for later source weighting and aggregation.

## Three independent language evidence channels now exist

### 1. Static embedding geometry — v0.3

`surface A <-> surface B`

Evidence type:

`semantic_similarity`

This says that two teacher embedding vectors are nearby. It does not say that one predicts the other or that they are synonyms.

### 2. Observed corpus behaviour — v0.4

`context -> observed next surface`

Evidence type:

`prediction`

Score is an empirical corpus estimate such as `P(target | context)`.

### 3. Teacher predictive behaviour — v0.5

`context -> teacher next-token surface`

Evidence type:

`prediction`

Score is the probability produced by an executed causal teacher forward pass.

Corpus and teacher prediction share the same relation semantics, but remain separate evidence records with different extraction provenance.

## Canonical context identity

Teacher-specific tokenization does not define the context node.

For example:

`Der Hund ist ein`

is represented as canonical text surfaces over character-Q nodes and an ordered context/template node:

`[Der, Hund, ist, ein]`

If the controlled corpus extractor observes the same context, both extraction paths resolve to the **same deterministic Equinox context ID**.

Therefore these two observations:

`corpus: P(Tier | Der Hund ist ein) = 1.0`

and

`teacher: P(Tier | Der Hund ist ein) = 0.72`

support the same canonical edge while preserving two independent evidence records.

## Optional Hugging Face runtime backend

The Forge compiler itself still has only lightweight dependencies.

Actual Hugging Face model execution is isolated behind the `CausalTeacherBackend` contract. The included backend is:

`TransformersCausalLMBackend`

It uses:

- `AutoTokenizer`;
- `AutoModelForCausalLM`;
- local model files only (`local_files_only=True`);
- deterministic top-k probability extraction;
- optional CPU/CUDA execution.

Install the optional runtime on the machine that performs teacher extraction:

```bash
pip install -e '.[hf-runtime]'
```

The Forge target/device runtime does **not** need Transformers.

## CLI: probe a local causal teacher

Put one controlled prompt per line into a UTF-8 file, for example:

```text
Der Hund ist ein
Die Katze ist ein
Ein Hund kann
Ein Tier kann
```

Then run:

```bash
python -m equinox_forge.cli probe-teacher \
  /path/to/local/hf/model \
  examples/probes/german_prompts.txt \
  out/teacher_behaviour.eqir.json \
  --source-id teacher/my-model \
  --source-version v1 \
  --adapter adapters/qwen2.json \
  --db out/master.sqlite \
  --top-k 8 \
  --temperature 1.0 \
  --min-probability 0.001
```

The command never downloads a model implicitly. The model must already exist locally.

Useful controls:

- `--top-k`
- `--temperature`
- `--min-probability`
- `--max-prompt-words`
- `--evidence-confidence`
- `--device cpu|cuda`
- `--dtype auto|float32|float16|bfloat16`
- `--trust-remote-code` (off by default)

## Backend contract

A future runtime does not have to be Hugging Face Transformers. Any backend can feed Forge if it implements:

```python
backend_id: str
next_token(prompt, top_k, temperature) -> list[TeacherCandidate]
manifest() -> dict
```

That allows later adapters for:

- llama.cpp / GGUF;
- vLLM;
- ONNX Runtime;
- remote teacher APIs where permitted;
- custom research models;
- multimodal autoregressive teachers.

The canonical compiler remains unchanged.

## Real causal integration test

The v0.5 test suite contains two behaviour tests.

### Deterministic probe test

A scripted teacher verifies:

- top-k filtering;
- probability thresholds;
- context canonicalization;
- exact evidence provenance;
- idempotent database ingestion;
- canonical sharing between corpus prediction and teacher prediction.

### Tiny learned causal model test

`test_tiny_causal_runtime.py` trains a small local PyTorch GRU language model on a miniature German corpus and then performs real forward inference through the same Forge behaviour boundary.

The learned teacher currently resolves:

```text
Der Hund ist ein -> Tier
Die Katze kann   -> miauen
```

at rank 1 in the deterministic integration fixture.

This test exists so the v0.5 pipeline is not validated only with hand-authored probability fixtures.

## Tests

Run:

```bash
python tests/run_all.py
```

Expected markers:

```text
FORGE_V01_OK
FORGE_V02_OK
FORGE_V03_OK
FORGE_V03_DB_MIGRATION_OK
FORGE_V04_OK
FORGE_V05_BEHAVIOUR_OK
FORGE_V05_TINY_CAUSAL_OK
FORGE_V05_ALL_TESTS_OK
```

If PyTorch is unavailable, only the tiny learned causal-model integration test is skipped. Core Forge remains independent of PyTorch.

## Deliberate limits of v0.5

v0.5 does **not** claim that top-k next-token distributions reproduce an LLM's full capability.

It does not yet extract:

- hidden-state geometry conditioned on context;
- attention patterns;
- multi-step generation trajectories;
- instruction-following behaviour;
- chain-of-thought or private reasoning;
- tool use;
- long-horizon planning;
- factual truth merely because a teacher predicts a token;
- a final Android language BASE.

The system stores **observable teacher behaviour**, not an assertion that every teacher output is correct.

## Why v0.5 matters

Forge can now place three independent measurements onto the same canonical knowledge structure:

`embedding geometry + corpus statistics + executed teacher predictions`

This is the first point where Equinox can experimentally ask:

> How much useful behaviour of a teacher can be compiled into a sparse canonical relation system while leaving the teacher itself off the target device?

## Next Forge step

**v0.6 — Contextual Hidden-State Evidence + Probe Dataset Runner**

The next useful step is to move beyond only the output head:

1. run a reproducible probe dataset through a supported teacher;
2. capture selected hidden-state representations for controlled contexts;
3. compare context-conditioned semantic neighbourhoods with static embeddings;
4. store these as a separate evidence channel;
5. add checkpoint/resume and batch execution so a large extraction job can be run safely over many prompts.

That would distinguish:

`static meaning geometry`

from

`contextual representation geometry`

and

`observable output behaviour`.
