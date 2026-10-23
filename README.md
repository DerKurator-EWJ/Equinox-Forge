# Equinox Forge v0.55 — Unified Numeric Execution Kernel

v0.55 consolidates the numeric runtime work from v0.48-v0.54 into one flat DB-free runtime pack and one execution engine:

```text
facts + surfaces + concept shortcuts + relation routes
                       ↓
          UnifiedNumericExecutionKernel
                       ↓
          resolve(subject_id, relation_id)
```

The deployed kernel no longer nests the historical numeric, concept-macro, facet, relation-macro, and unified-relation runtime packs. Those layers remain in Forge for compatibility, audit, and regression comparison.

Frozen v0.55 reference results:

- 240/240 compiled subject/relation query pairs semantically identical to v0.54,
- 0 parity failures,
- flat pack ≈ 67.23% of the nested v0.54 JSON size on the reference fixture,
- runtime-only import requires none of the historical v0.48-v0.54 runtime modules.

Run:

```bash
eqforge-unified-numeric-kernel --out out/v0_55_unified_numeric_kernel
```

See `RELEASE_V0_55.md` and `benchmarks/v0_55/` for the frozen contract. Historical release notes and regression tests remain included.
