# Wave 2 Progress — Provenance (2026-04-21)

Autonomous-mode progress report for Wave 2 of the sec9 LinkML-centric redesign. Covers the two Wave 2 changes landed so far: `provenance-as-linkml-class` (declarations only) and `provenance-migration` (full storage + API rewrite).

## What landed

### `provenance-as-linkml-class` (commit 2809755, prior session)

Declaration-only scope per Decision 9.6.A. `hippo_ext` got `hippo_append_only` as a class-level annotation (version 0.1.0 → 0.2.0); `hippo_core` got `ProvenanceRecord` with `class_uri: prov:Activity`, `hippo_append_only: true`, and all sec9 §9.6 slots (version 0.2.0 → 0.3.0). `Operation` enum declared. Tests for the declaration (TestHippoCoreProvenanceRecord: 7 tests; TestHippoAppendOnlyAnnotation: 3 tests).

### `provenance-migration` (commits 3c01ead + 5bd0d47 + 3cb2636, this session)

Advisor-recommended decomposition — three commits inside the one OpenSpec change so the DDL-verification step lands additive before the invasive rewrite.

**Commit 1 (`3c01ead`) — DDL verification + inert write-guard helper.** Seven new tests in `TestHippoCoreProvenanceRecordDDL` assert that `DDLGenerator().generate(registry)` produces the expected `ProvenanceRecord` table shape from hippo_core. No generator changes needed — the LinkML-driven path already emits the right columns, NOT NULL constraints, indexes, and FKs. `SchemaRegistry.append_only_classes()` helper added (+ 4 tests in `TestAppendOnlyClassesHelper`). Purely additive; no behavioral change.

**Commit 2-prep (`5bd0d47`) — Decisions 9.6.B–E logged.** Per-site mapping table for the 11 legacy operation strings (flags "REPLACED" → `update`, not `supersede`; "EntitySuperseded" → `supersede` with `derived_from_id`). SQL triggers chosen over adapter-level Python checks per 9.6.C. DDL via LinkML pipeline per 9.6.D. Legacy `user_context` strings not back-populated per 9.6.E.

**Commit 2 (`3cb2636`) — The rewrite.** 14 files, ~750 insertions / ~684 deletions:

- **Storage:** `ProvenanceRecord` table replaces legacy `provenance` in both adapters. `entity_provenance_summary` view retargeted and updated to compute the sec9 §9.7 temporal fields including `schema_version` (from the latest record per entity).
- **API:** `ProvenanceStore.record()` accepts both sec9 kwargs and legacy kwargs; legacy strings map via `_LEGACY_OPERATION_MAP`. Six src call sites migrated to pass `Operation` values natively. `compute_state_hash`, `generate_operation_id`, `previous_state_hash`, `state_snapshot` dropped.
- **Enforcement:** `sqlite_triggers.py` retargeted — two triggers (`BEFORE UPDATE`, `BEFORE DELETE`) replacing the legacy five. Postgres mirror via PL/pgSQL.
- **Tests:** line-by-line audit per advisor guidance. `test_provenance.py` helper queries new table with aliased columns; `test_provenance_triggers.py` rewritten for the simpler two-trigger set; `test_supersede_entity.py` / `test_bulk_availability.py` / `test_replace.py` / `test_postgres_adapter.py` assertions updated to sec9 enum values.
- **850 tests pass** (all non-Postgres-integration tests). Postgres path statically audited.

**Commit 3 (`this`) — Docs cleanup.** Scope notes removed from `reference_hippo_core.md` (ProvenanceRecord section now marked Active) and `reference_hippo_ext.md` (hippo_append_only enforcement now documented as SQL-trigger-based). The "exclusions" table points at Decision 9.6.F for the two known transition gaps.

## Known transition gaps (Decision 9.6.F)

Two items intentionally not fixed in this commit, tracked explicitly so they don't ship silently:

1. **`actor_id = "unknown"` sentinel fallback** fires for new rows from callers that don't pass an actor. Sec9 §9.5 requires a UUID; requires threading per-request actor context through the service layer. Multi-day undertaking, out of scope for provenance-migration.

2. **`schema_version = ""` on every new row.** `SchemaRegistry` is not threaded through adapter construction. `ProvenanceStore.__init__` accepts the parameter but nothing populates it. Plumbing work, out of scope here.

Neither requires a data migration to fix later — both are additive-compatible.

## Things I'd particularly call out

1. **Three-commit decomposition under one OpenSpec change.** Advisor's guidance — verify DDL first (additive), then do the semantically-atomic rewrite, then docs cleanup. This let the DDL-verification commit land on a green tree without committing to the rewrite's shape; the rewrite went in with tests green on the first try for the newly-added work.

2. **Legacy-kwarg compatibility shim in `ProvenanceStore.record()`.** Accepting both the sec9 kwargs and the legacy kwargs (`operation_type`, `user_context`, `payload`) simplified the per-site migration — callers not yet updated still work. The shim is scoped to the transition and can be removed once all src callers pass Operation values natively.

3. **SQL triggers over adapter-level Python checks (Decision 9.6.C).** The proposal originally said "adapter write-guard." Implementing as adapter-level Python would have been a silent security downgrade — direct-SQL bypass (raw connections, sqlite3 CLI) would miss Python checks but not triggers. The trigger approach preserves the legacy status quo's security posture; Decision 9.6.C logs this rationale explicitly.

4. **Line-by-line test audit.** Per advisor guidance, not a mechanical rename. Tests asserting on dropped concepts (`previous_state_hash`, `state_snapshot` presence, separate `operation_id` field) were deleted outright (not adapted); tests exercising the concept they addressed kept (lineage → `derived_from_id`, state capture → `patch`).

## What's next in Wave 2

Per sec9 §9.12's dependency graph: `provenance-as-linkml-class` → `provenance-migration` → `computed-temporal-fields`.

The `computed-temporal-fields` change reads `ProvenanceRecord` directly (now present + queryable) and produces read-time `created_at` / `updated_at` / `schema_version` / `created_by` / `updated_by` on entity reads. Its proposal + tasks are already scaffolded under `openspec/changes/computed-temporal-fields/`.

Before starting `computed-temporal-fields`: the `schema_version = ""` transition gap from 9.6.F may become load-bearing — `computed-temporal-fields` is the primary consumer of the `schema_version` field. Recommend fixing the 9.6.F gap (plumbing `SchemaRegistry` through adapter construction) as a small preliminary before `computed-temporal-fields` rather than inside it.

## Pushing

3 new commits are queued locally on this branch. `git push origin main` from your terminal.
