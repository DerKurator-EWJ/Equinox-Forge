# Equinox Forge v0.4 — Controlled Language Evidence

Forge v0.4 adds the first **directed language evidence** above the static embedding geometry introduced in v0.3.

The architecture is now:

`teacher embeddings + controlled corpus -> canonical text nodes -> typed evidence channels -> Canonical DB -> compiler`

The important rule remains: **evidence source is not runtime representation**. Corpus statistics, teacher embeddings and later teacher behaviour can all support the same canonical Equinox nodes without being collapsed into one opaque source weight.

## What v0.4 adds

A UTF-8 controlled-corpus extractor now creates:

1. Unicode text surfaces over character-Q nodes;
2. sentence-local ordered token streams;
3. directed `transition` evidence using empirical `P(next | current)`;
4. canonical context-template nodes;
5. directed `prediction` evidence using empirical `P(target | context)` for bounded n-gram contexts;
6. repeated phrase composite nodes;
7. symmetric `substitution` evidence when different words occur in overlapping immediate `(left,right)` slots;
8. full source/version/extraction provenance for every evidence record.

No language relation is inferred from its tier name. Tiers remain **composition depth only**.

## Canonical text structure

The current text branch uses:

`Q = Unicode character`

A surface such as `Hund` is a level-1 macro over:

`H -> u -> n -> d`

Phrase and context structures are ordered composites of these canonical surfaces. Word boundaries therefore exist structurally between members and do not require a teacher-specific token ID.

Example:

`Der Hund -> [Der, Hund]`

The predictive context role and an observed repeated phrase are intentionally represented as different node kinds even when their visible label is identical. This keeps **"observed composition"** separate from **"context used to predict"**.

## Evidence channels

### Transition

For every sentence-local adjacent pair:

`w_t -> w_(t+1)`

Forge stores:

`score = count(w_t,w_(t+1)) / count(w_t,*)`

The metadata preserves the raw count and context total.

### Prediction

For context widths `1..max_context`, Forge creates ordered context templates and stores:

`context -> next surface`

with:

`score = count(context,target) / count(context,*)`

This is the first directed context evidence in Forge. It is corpus MLE evidence, not yet a Transformer forward-pass probability.

### Repeated phrase macros

Contiguous token sequences of length `2..max_phrase_words` are counted. Phrases reaching `min_phrase_count` are materialized as canonical composite observations.

A four-word phrase is not automatically placed four tiers deeper. Its tier follows the actual composition graph. This preserves the Equinox rule that tier means **recursive composition depth**, not linguistic importance or length.

### Substitution

For every word, Forge records immediate `(left,right)` context slots. Two words become substitution candidates when those slot distributions overlap.

v0.4 uses weighted Jaccard:

`sum(min(count_a(slot), count_b(slot))) / sum(max(count_a(slot), count_b(slot)))`

This is stored as symmetric `substitution` evidence. It means **contextual replaceability evidence**, not identity or synonymy.

## Why channels stay separate

A relation such as `Hund <-> Tier` can later receive evidence from several independent sources:

- static teacher embedding neighbourhood;
- corpus transition/prediction;
- hidden-state probes;
- teacher output probabilities;
- structured knowledge graphs;
- another teacher model.

Forge stores these as separate evidence records with separate relation types and provenance. Only the compiler decides how compatible evidence is aggregated.

The same canonical `Hund` node can therefore participate in, for example:

- `semantic_similarity`
- `transition`
- `prediction`
- `substitution`
- later `is_a`

without pretending those scores mean the same thing.

## CLI

### Extract a controlled corpus

```bash
python -m equinox_forge.cli extract-corpus \
  examples/corpus/german_mini.txt \
  out/german.eqir.json \
  --source-id corpus/german-mini \
  --source-version v1 \
  --db out/master.sqlite \
  --max-context 2 \
  --min-phrase-count 2
```

Multiple UTF-8 files can be supplied before the output path.

Useful controls:

- `--lowercase`
- `--include-punctuation`
- `--max-context`
- `--min-transition-count`
- `--min-prediction-count`
- `--min-phrase-count`
- `--max-phrase-words`
- `--max-substitutions-per-word`
- `--min-substitution-score`
- `--evidence-confidence`

### Combine with a teacher extraction

The same Canonical DB can receive v0.3 embedding evidence:

```bash
python -m equinox_forge.cli extract-text \
  examples/hf_teacher_synthetic \
  adapters/deepseek_v3.json \
  out/teacher.eqir.json \
  --source-id synthetic/semantic \
  --source-version v1 \
  --db out/master.sqlite \
  --max-tokens 32 \
  --top-k 2 \
  --min-similarity 0.60
```

Both paths resolve canonical surfaces independently. `Hund` from the corpus and `Hund` decoded from the teacher therefore receive the same deterministic Equinox node ID.

## Current deterministic fixture result

For `examples/corpus/german_mini.txt` with `max_context=2` and `min_phrase_count=2`:

```text
8 sentences
30 lexical tokens
11 unique surfaces
18 character-Q nodes
10 repeated phrase nodes
12 transition evidence records
22 prediction evidence records
6 substitution evidence records
54 total canonical nodes
40 total evidence records
```

The merged demonstration with the v0.3 synthetic embedding teacher currently yields:

```text
72 canonical nodes
54 evidence records
2 independent evidence sources
```

The canonical `Hund` surface is shared between both extraction paths and currently participates in `prediction`, `transition` and `semantic_similarity` evidence channels.

## Tests

```bash
python tests/test_forge.py
python tests/test_hf_adapter.py
python tests/test_text_teacher.py
python tests/test_db_migration_v02.py
python tests/test_language_evidence.py
```

Current expected markers:

```text
FORGE_V01_OK
FORGE_V02_OK
FORGE_V03_OK
FORGE_V03_DB_MIGRATION_OK
FORGE_V04_OK
```

The v0.4 test verifies:

- sentence-local tokenization;
- directed transition probabilities;
- context-template prediction;
- contextual substitution evidence;
- repeated phrase materialization;
- Canonical DB idempotence;
- successful compilation of the new relation channels.

## Deliberate limits of v0.4

v0.4 still does **not**:

- execute a Transformer forward pass;
- use teacher next-token probabilities;
- induce semantic facts such as `Hund IS_A Tier` from arbitrary prose;
- perform syntactic parsing;
- solve coreference or long-range discourse identity;
- recursively promote phrase macros into deeper language hierarchy automatically;
- build a final Android language `BASE.eqx`;
- claim contextual substitution equals synonymy.

Those are intentionally separate problems.

## Next Forge step

**v0.5 — Teacher Behaviour Probes**

The next step should run a small supported causal language model on controlled prompts and record actual teacher behaviour:

`controlled context -> teacher next-token distribution -> canonical surface evidence`

That would add a new source of `prediction` evidence distinct from corpus frequency and embedding geometry. The same canonical nodes could then be supported by three independent channels:

`embedding geometry + observed corpus behaviour + teacher predictive behaviour`

This is the first serious step toward testing how much of a teacher's behaviour can be compiled into Equinox without carrying the teacher runtime onto the target device.
