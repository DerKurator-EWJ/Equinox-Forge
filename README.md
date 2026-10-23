# Equinox Forge v0.54 — Unified Numeric Relation Routing

v0.54 makes the new numeric relation space operational through one public query path. Scalar predicates, relation facets, relation-family IDs, and recursive relation-macro IDs are all addressed as opaque numeric relation IDs.

```text
subject ID + relation ID
          ↓
compiled numeric route
          ↓
scalar relation OR recursive relation macro
          ↓
object IDs
```

The runtime does not branch on semantic names such as `PROPERTY` or `ACTION`. The compiler discovers exact family-to-macro aliases structurally and serializes them as numeric routes.

Run the frozen v0.54 demo:

```bash
eqforge-unified-relation-runtime --out out/v0_54_unified_relation_runtime
```

See `RELEASE_V0_54.md` and `benchmarks/v0_54/` for the frozen contract and reference output. Historical release notes and regression tests remain included.
