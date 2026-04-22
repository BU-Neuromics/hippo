# Tasks — `provenance-migration`

## 1. DDL migration

- [x] 1.1 Removed the hand-coded `CREATE TABLE IF NOT EXISTS provenance (...)` and `CREATE INDEX` blocks from both `SQLiteAdapter._init_database` and `PostgresAdapter._init_database`. Legacy `provenance` table is dropped on startup if present.
- [x] 1.2 The `ProvenanceRecord` table shape is stamped inline to match what the LinkML DDL generator produces from `hippo_core.ProvenanceRecord` (verified by `tests/core/test_ddl_generator.py::TestHippoCoreProvenanceRecordDDL`). All sec9 §9.6 columns, NOT NULL on required slots, indexes on annotated slots, FK from `process_id` to `Process`.
- [x] 1.3 No data migration — dev-only deployments per Decision 9.6.D. Legacy table dropped-and-recreated via a simple `DROP TABLE IF EXISTS` in `_run_migrations` / `_init_database`.

## 2. ProvenanceStore rewrite

- [x] 2.1 `ProvenanceStore.record(...)` signature updated to accept sec9 §9.6 parameters: `entity_id`, `entity_type`, `operation`, `actor_id`, `patch`, `context`, `derived_from_id`, `process_id`, `schema_version`.
- [x] 2.2 Insert into `ProvenanceRecord` with the new column names.
- [x] 2.3 `find_by_entity(entity_id, operation=None)`, `get_history(entity_id)` query the new table. `get_history` returns legacy-shape dicts (with `previous_state_hash: None`) for back-compat; `find_by_entity` yields the new Pydantic shape.
- [x] 2.4 Compatibility shim: `_LEGACY_OPERATION_MAP` in `sqlite_adapter.py` maps legacy strings to sec9 Operation values. Covers all 11 strings surfaced by the audit, not just the five in the original task list. Shim will be removed once all callers pass enum values natively.
- [x] 2.5 `compute_state_hash` helper dropped.
- [x] 2.6 `state_snapshot` parameter accepted (and discarded) for back-compat; internal persistence uses `patch`.
- [ ] 2.7 `schema_version` captured from the SchemaRegistry at write time. **Deferred — Decision 9.6.F tracks the gap.** `__init__` accepts the parameter; adapters don't plumb a registry yet. Always `""` on new rows currently.

## 3. `Operation` enum migration

- [x] 3.1 Six src call sites (ingestion_service, provenance_service, relationship, sqlite_adapter, postgres_adapter) pass lowercase sec9 Operation values natively.
- [x] 3.2 `"SOFT_DELETE"` and `"AVAILABILITY_CHANGE"` map to `availability_change`; the Status driver is carried in `patch` (`{"status": "deleted", ...}` for delete paths).
- [x] 3.3 Transition-period note: the legacy-string shim is still present by design (Decision 9.6.B) to absorb calls from code paths not yet migrated. Full removal of the shim is a follow-up.

## 4. `hippo_append_only` enforcement via SQL triggers (Decision 9.6.C)

- [x] 4.1 `SchemaRegistry.append_only_classes()` (landed in commit 1). Available for future DDL-generator-driven trigger emission and for non-SQL adapters (Neo4j etc.); not consumed by SQL adapters in this commit.
- [x] 4.2 `sqlite_triggers.py` retargeted at `ProvenanceRecord`. Five column-specific triggers replaced by one `BEFORE UPDATE` (any column) + one `BEFORE DELETE`. Error message: "Cannot {update,delete} ProvenanceRecord: hippo_append_only class".
- [x] 4.3 `SQLiteAdapter._init_database` installs triggers after creating `ProvenanceRecord` (same code path as before).
- [x] 4.4 PostgresAdapter: PL/pgSQL `RAISE EXCEPTION` equivalents.
- [x] 4.5 `tests/core/test_provenance_triggers.py` rewritten — six focused tests covering UPDATE on each of four columns, DELETE, and transaction rollback. All assertions check for `"hippo_append_only"` in the error message.

## 5. Test suite updates

- [x] 5.1 `tests/core/test_provenance.py` — helper queries ProvenanceRecord with alias columns to keep existing assertions working; dropped `test_provenance_new_columns_exist`, `test_provenance_operation_id_generation`, `test_provenance_state_hash_computation`, `test_provenance_state_snapshot` (concepts no longer exist per sec9 §9.6). `test_provenance_table_schema` updated to assert the sec9 column inventory.
- [x] 5.2 `tests/core/test_supersede_entity.py` assertions updated — `EntitySuperseded` → `supersede`, `EntityUpdated` → `update`.
- [x] 5.3 `tests/core/test_bulk_availability.py` — `AvailabilityChanged` → `availability_change`.
- [x] 5.4 `tests/integration/test_postgres_adapter.py` — `CREATE` → `create`, `SOFT_DELETE` → `availability_change`; `track_deletion` now returns `availability_change` per Decision 9.6.B.
- [ ] 5.5 Dedicated tests for `derived_from_id` / `process_id` / `schema_version`-from-registry. **Partial** — `derived_from_id` is exercised via the supersede path; `process_id` and `schema_version`-from-registry land with `computed-temporal-fields` (the primary consumer).

## 6. Decision log

- [x] 6.1 Decisions 9.6.B–F added to `design/sec9_decisions.md`:
  - 9.6.B legacy operation-string mapping (per-site table)
  - 9.6.C SQL triggers over adapter Python checks
  - 9.6.D DDL via LinkML pipeline
  - 9.6.E legacy `user_context` strings not back-populated (Option A)
  - 9.6.F transition-period fallbacks flagged explicitly (`actor_id="unknown"`, `schema_version=""`)

## 7. Documentation

- [x] 7.1 `design/reference_hippo_core.md` — ProvenanceRecord section's scope note replaced with a "Status: Active" note pointing at Decision 9.6.F for the known transition gaps. Exclusions table updated.
- [x] 7.2 `design/reference_hippo_ext.md` — `hippo_append_only` section documents SQL-trigger enforcement, points at Decision 9.6.C.
- [ ] 7.3 Sec6 (Provenance spec) revision per sec9's revision plan. **Deferred** — sec6's current prose predates sec9 and is slated for broader revision. Light-touch pointer at sec9 §9.6 as authoritative can land whenever sec6 is next touched.

## 8. Acceptance

- [x] 8.1 `ProvenanceRecord` table present; legacy `provenance` table dropped on init.
- [x] 8.2 UPDATE / DELETE against `ProvenanceRecord` rejected by SQLite triggers (verified by `test_provenance_triggers.py`). Postgres trigger parity pending integration-env verification.
- [x] 8.3 No residual legacy operation strings in src/ outside the intentional `_LEGACY_OPERATION_MAP` shim.
- [x] 8.4 `ProvenanceStore` API aligned with sec9 §9.6. `schema_version` pending Decision 9.6.F follow-up.
- [x] 8.5 Full non-Postgres-integration test suite green (850 passed, 7 skipped).
