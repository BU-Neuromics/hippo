# sec9 Spike — Adopting `linkml-store` as Hippo's Storage Abstraction

**Status:** spike complete, awaiting design decision
**Date:** 2026-05-11
**Probes:** `hippo/spike/linkml-store/probe_*.py`
**Decision pending:** proceed with Option α (adopt linkml-store), Option β (delegate DDL only), or stay on hand-coded adapters

---

## Context

Hippo currently hand-codes its storage layer (`SQLiteAdapter`, `PostgresAdapter`, `DDLGenerator`, `schema_diff.py`) while `linkml-store>=0.3` and LinkML's own `SQLTableGenerator` sit unused in the dependency tree (`pyproject.toml:19–21`). Sec9 §9.1 already flags this duplication as known tech debt.

This spike validates whether `linkml-store` can serve as hippo's storage abstraction, supporting the "swap database backends seamlessly" design goal — and quantifies the gap. Three possible verdicts: Green (adopt), Yellow (adopt with upstream contributions), Red (fall back to Option β: delegate DDL only).

---

## Overall verdict: **Yellow**

`linkml-store` covers the *shape* of what hippo needs — per-class typed storage, uniform backend API, post-write hooks, transactions — but **skips most DB-level constraint enforcement** and **has no schema migration support**. Hippo can adopt it, but several hippo concerns (pre-write validation, append-only enforcement, schema evolution, FTS5, partial indexes) must live in a hippo layer *above* linkml-store, not delegated to it.

The upstream contributions required are small in count (5–7 PRs) but range from trivial (call `_pre_insert_hook` before writes) to substantial (add PK/FK/NOT NULL constraint emission). Total upstream work: estimated 1–2 engineer-weeks if upstream maintainers accept the PRs at hippo's pace.

The "swap backends" promise holds at the API level: DuckDB and MongoDB collections expose identical `insert`/`query`/`delete`/`upsert` signatures. But this only works because linkml-store treats *all* backends as document stores at the storage layer — DB-level constraints (PK, FK, NOT NULL) are uniformly absent. Hippo would shift all schema enforcement to the application layer via the existing `WriteValidator` chain.

---

## Per-probe results

### Tier 1 — load-bearing

| # | Probe | Verdict | Detail |
|---|---|---|---|
| 1 | Per-class typed storage | 🟡 Yellow | DuckDB emits one table per class (correct shape), but `_sqla_table` creates plain `Column(name, type)` with **no PK, no FK, no NOT NULL, no DEFAULT**. Boolean range becomes VARCHAR. Constraint violations (duplicate id, dangling FK, missing required field) all accepted silently. |
| 2 | `is_a: Entity` inheritance | 🟢 Green | `class_induced_slots` propagates `id`, `is_available` from `Entity` into derived class tables (`Sample`, `Donor`). Inheritance works correctly. |
| 3 | FTS5 / full-text search | 🟡 Yellow | No SQLite FTS5 or DuckDB FTS extension support. linkml-store has trigram `SimpleIndexer` (documented "not suitable for production") and embedding-based `LLMIndexer`, but no SQL-native FTS. Hippo's `hippo_search: fts5` must be a hippo-side layer atop linkml-store or contributed upstream. |
| 4 | Append-only enforcement | 🟡 Yellow | No native mechanism. `delete`, `delete_where`, `update`, `upsert`, `replace`, `apply_patches` (6 mutating methods) must all be overridden in a hippo subclass that checks `hippo_append_only`. Fragile — easy to miss a method as linkml-store evolves. |
| 5 | Backend parity (DuckDB / MongoDB) | 🟢 Green | API surface is uniform: same hooks, same `insert`/`query`/`delete`/`upsert` signatures. Different backends produce different storage shapes (SQL tables vs. document collections) but app code is backend-agnostic. **The trade-off**: all backends are uniformly weak on DB-level constraints. |
| 6 | Pre/post write hooks | 🟡 Yellow | **Critical finding**: `_post_insert_hook` works across all backends. **`_pre_insert_hook` is dead code — no concrete backend calls it before its write** (verified by grep across DuckDB, MongoDB, Dremio, Dremio-REST collection implementations). Provenance writes (post) are clean; pre-validation requires overriding `insert()` directly in every backend subclass hippo extends. |

### Tier 2 — workable, but verify

| # | Probe | Verdict | Detail |
|---|---|---|---|
| 7 | Partial indexes | 🟡 Yellow | DuckDB collection has no `index()` method. Hippo must fall through to `db.execute_sql("CREATE INDEX … WHERE is_available = 1")` for `hippo_index_partial` annotations. |
| 8 | Transactions | 🟢 Green | `conn.begin()` + `commit()` are used in DuckDB's `insert`. Transaction primitives present. |
| 9 | `ExternalID` as class | 🟢 Green | Once modeled as a LinkML class, it gets its own collection like any other entity. No special-casing needed. |
| 10 | Cross-class identity (UUID → class) | 🟡 Yellow | No built-in lookup. Hippo needs its own `_entity_registry(uuid, class_name)` shadow table, maintained by triggers or post-insert hooks. |
| 11 | Schema migration | 🔴 Red | Zero migration support. No `ALTER TABLE`, no `alter_table` anywhere in the codebase. `_create_table` is create-if-not-exists only. Hippo's existing `schema_diff.py` + `migration.py` remain entirely hippo-owned regardless of backend choice. |

---

## Implications for hippo's architecture

If hippo adopts `linkml-store`, the layering shifts as follows:

```
┌──────────────────────────────────────────────────────────────┐
│  hippo CLI / REST API / typed_client                          │
├──────────────────────────────────────────────────────────────┤
│  hippo.core.client.HippoClient                                │
├──────────────────────────────────────────────────────────────┤
│  hippo write/read path:                                       │
│    - WriteValidator chain (was already here)                  │
│    - ProvenanceManager (was already here)                     │
│    - NEW: hippo subclass of Collection that overrides         │
│      mutating methods to enforce hippo_append_only            │
│    - NEW: hippo subclass that runs WriteValidator + writes    │
│      ProvenanceRecord in a transaction                        │
│    - NEW: _entity_registry shadow table for cross-class UUID  │
│      lookup                                                    │
│    - NEW: FTS5 layer (separate from linkml-store's indexer)   │
│    - NEW: partial index emission via raw SQL                  │
│    - KEPT: schema_diff.py + migration.py (linkml-store has    │
│      no migration support)                                    │
├──────────────────────────────────────────────────────────────┤
│  linkml-store.Client → DuckDB/Postgres/MongoDB/Neo4j/…        │
│    - Per-class collections                                    │
│    - LinkML schema-driven                                     │
│    - Application-layer validation                             │
│    - No DB-level PK/FK/NOT NULL (gone vs. current hippo)      │
└──────────────────────────────────────────────────────────────┘
```

The **layers above linkml-store grow modestly** (hippo subclasses for hooks, append-only, FTS, partial indexes), while the **DDL/adapter machinery below shrinks substantially** (drop hand-coded `SQLiteAdapter` per-class table emission, drop hand-coded SQLAlchemy column generation, delegate to linkml-store + LinkML's `SQLTableGenerator`).

**Net code change estimate**: hippo's `core/storage/` directory shrinks by ~40–50%, but `core/validation/` and a new `core/storage/hippo_collection.py` (or similar) grow by ~20–30%. Overall: smaller codebase, but more of it is "glue between hippo invariants and linkml-store's looser primitives."

---

## Upstream contributions needed (Yellow → Green path)

To move from Yellow to Green, hippo would file (in approximate priority order):

1. **Backends should call `_pre_insert_hook(objs)` before DB write.** Trivial PR — one line in each of `duckdb_collection.py:24`, `mongodb_collection.py:36`, `dremio_collection.py:~250`. Unblocks pre-write validation across all backends. Low risk; should be a clear bug fix from upstream's perspective.

2. **Add `_pre_update_hook` and `_pre_delete_hook` to base Collection + call from backends.** Same pattern. Unblocks append-only enforcement without needing to override every mutating method.

3. **Emit PK + FK + NOT NULL + DEFAULT in SQL backend DDL.** Larger PR — modify `_sqla_table` in `duckdb_collection.py` to use LinkML's `SQLTableGenerator` underneath, or hand-roll the constraint emission. Restores DB-level enforcement for SQL backends; MongoDB/Neo4j unaffected. Moderate risk: changes existing DDL, may break downstream users.

4. **Add `alter_table` / schema migration scaffolding.** Substantial PR. May be out of scope for hippo's spike — hippo can keep `schema_diff.py` for now and revisit if linkml-store adds this later.

5. **Add SQLite FTS5 / DuckDB FTS indexer implementation.** Hippo-specific feature; might be too narrow for upstream. Likely lives in hippo as a custom indexer registered via `get_indexer("hippo_fts5")`.

6. **Add `partial_index` support to the indexer interface.** Hippo-specific need. Either upstream or hippo-side raw SQL.

7. **Expose a `migration_required(schema_view) -> Plan` API at the Database level.** Stretch goal; relates to #4.

PRs 1–2 are bug fixes; 3 is a clear improvement that benefits all linkml-store users; 4 is substantial new feature work. PRs 5–6 are arguably hippo-specific.

---

## Decision required

Three options:

**Option α (proceed):** Adopt linkml-store as the storage abstraction. Commit to filing upstream PRs 1–3 (and 4 eventually). Accept that hippo grows a `HippoCollection` subclass with overridden mutating methods. **Outcome**: real backend-swap capability (DuckDB → Postgres → MongoDB → Neo4j via config). Cost: ~6–8 weeks of focused work for the migration + 1–2 weeks for upstream PRs.

**Option α′ (proceed cautiously):** Adopt linkml-store but pin to a hippo-maintained fork until upstream PRs land. Same destination as α; reduces external dependency risk. Adds maintenance burden of a fork.

**Option β (delegate DDL only):** Don't adopt linkml-store. Delegate hippo's `DDLGenerator` to LinkML's `SQLTableGenerator` (one of the easy wins from this spike — the LinkML generator already produces ~80% of what hippo's emits, including PK/FK/NOT NULL which linkml-store skips). Keep hand-coded adapters. **Outcome**: smaller refactor (~2 weeks), no upstream dependencies, no backend-swap unless we write new adapters. Cost: doesn't deliver the multi-backend goal.

**Recommendation**: **Option α with the spike's PRs 1–3 in flight before the storage migration proper begins**. Reasoning:

- Backend-swap is the stated long-term design goal; β doesn't deliver it.
- Upstream PRs 1–3 are bug fixes / clear improvements that benefit all linkml-store users, not hippo-specific asks — likely to be accepted upstream.
- α′ (fork) adds maintenance pain; only worth it if upstream is unresponsive.
- The Red verdict on schema migration is acceptable: hippo already owns this, doesn't need to delegate.

If the upstream maintainers are unresponsive to PRs 1–3 within ~4 weeks, fall back to α′.

---

## What's still uncertain

- **Postgres backend parity**: not probed. linkml-store's `ibis` backend wraps Postgres but I didn't test it. Could be a follow-up spike if/when Postgres becomes a near-term need.
- **Neo4j parity**: not probed. Hippo's relational semantics may not map cleanly onto Neo4j's graph model; this requires its own design pass before Neo4j is a real option.
- **Performance**: this spike didn't measure throughput. Adding a hippo-layer subclass over linkml-store adds Python overhead on every write. Worth benchmarking before committing.
- **`linkml-store`'s API stability**: the package is at 0.3.0. Coupling hippo's storage layer to a pre-1.0 dependency is a real risk. Worth checking the upstream roadmap and release cadence before committing.

---

## Artifacts

- `hippo/spike/linkml-store/probe_01_typed_storage.py` — per-class DDL + constraint probe
- `hippo/spike/linkml-store/probe_06_write_hooks.py` — pre/post hook probe (also demonstrates the dead `_pre_insert_hook`)
- This document — `hippo/design/sec9_spike_linkml_store.md`
