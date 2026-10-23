# Equinox Forge v0.1 — Canonical IR

Forge is the offline knowledge-compilation branch of Equinox. It deliberately separates **where knowledge comes from** from **how Equinox stores and runs it**.

## Principle

`Teacher / dataset / model -> adapter -> Canonical IR -> canonical DB -> evidence aggregation -> hierarchy/runtime compilation`

This version is **model-independent**. There is no DeepSeek/Qwen/Llama-specific code yet.

## Canonical hierarchy

- `level 0 / Q`: elementary modality symbol. For the first text experiment this is a Unicode character.
- `level 1 / F`: a directly composed surface form, e.g. `Hund = H + u + n + d`.
- `level 2 / E`: composition of F structures, e.g. a phrase/sentence pattern.
- deeper levels continue recursively: `D C B A S SS SSS Ω Ω+n`.

Tier is composition depth only. It is **not** importance, confidence, frequency, or source quality.

`Hund`, `Hunde`, and `Hunden` remain separate surface macros. A later relation/template layer may learn that they are strongly related. Homographs likewise keep one surface form while context/sense structures live above it.

## Evidence, not weight copying

Forge stores raw source evidence separately from compiled runtime relations. Two teacher models can both support the same canonical relation without creating duplicate nodes:

`teacher A -> Hund IS_A Tier 0.91`

`teacher B -> Hund IS_A Tier 0.87`

The canonical DB keeps both pieces of evidence. `compile` aggregates them deterministically. The aggregation policy is intentionally replaceable, so future weighting research does not require re-extracting the teacher models.

## SQLite canonical DB

Tables:

- `nodes`
- `node_members`
- `evidence`
- `source_aliases`

The canonical IDs are content-derived SHA-256 prefixes, not teacher-specific IDs. Therefore the same exact structure imported from two different adapters deduplicates automatically.

## Commands

From the project root:

```bash
python examples/build_demo.py
python -m equinox_forge.cli validate examples/german_demo.eqir.json
python -m equinox_forge.cli ingest out/master.sqlite examples/german_demo.eqir.json
python -m equinox_forge.cli stats out/master.sqlite
python -m equinox_forge.cli compile out/master.sqlite
python -m equinox_forge.cli export out/master.sqlite out/base_preview.json --pack-id german-demo --version 1
python tests/test_forge.py
```

## Important boundary with Android Step 46

Android Step 46 currently imports `equinox-external-knowledge-v1` where level-1 nodes must reference **already existing Equinox sensor-token IDs**. Forge v0.1 intentionally introduces `TEXT Q = Unicode character`, which the Android runtime does not yet have as a native modality.

Therefore v0.1 exports a **Forge runtime preview**, not a fake Step-46 BASE. The correct future bridge is:

1. add a native TEXT-Q namespace/input adapter to Equinox Runtime;
2. define deterministic text-Q integer IDs shared by Forge and Runtime;
3. add a strict Forge -> EQKI exporter;
4. then compile the first 1k/10k-word BASE for the phone.

This avoids pretending that text characters are existing camera/audio quant IDs.

## Next Forge steps

- v0.2: Hugging Face adapter contract + model config files.
- v0.3: first text teacher extractor (small open model first).
- v0.4: canonical duplicate/evidence merge at 1k–10k word scale.
- v0.5: Android TEXT-Q bridge and real `BASE.eqx` export.
