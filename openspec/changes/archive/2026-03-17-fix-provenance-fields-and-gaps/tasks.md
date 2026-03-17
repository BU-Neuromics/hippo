## 1. Schema Migration — superseded_by column

- [x] 1.1 Update `hippo migrate` to add `superseded_by TEXT` (nullable, no default) to every entity type table when the column is absent
- [x] 1.2 Ensure `hippo migrate` applies the `superseded_by` column addition before entity-level migrations, mirroring how `is_available` is handled
- [x] 1.3 Verify that pre-existing rows receive `NULL` for `superseded_by` with no data backfill required
- [x] 1.4 Add `superseded_by` to the internal list of system columns (alongside `is_available`) so it is applied generically, not per-schema-declaration

## 2. entity_provenance_summary View

- [x] 2.1 Confirm whether `entity_provenance_summary` view exists in all v0.1 deployments; if not guaranteed, add creation to `hippo migrate`
- [x] 2.2 Define (or verify) view columns: `entity_id`, `created_at` (timestamp of first `CREATE` event), `updated_at` (timestamp of most recent non-DELETE event), `schema_version`
- [x] 2.3 Ensure `hippo migrate` creates the view before entity table migrations so the view is available for all subsequent `query()` calls
- [x] 2.4 Update the relational storage spec section (sec3b or equivalent) to classify `entity_provenance_summary` as required, not optional, with full column definitions and derivation logic

## 3. Gap 1 — Provenance-Derived Temporal Fields

- [x] 3.1 Update `QueryEngine` (or the storage adapter read path) so that `created_at` and `updated_at` in entity dicts returned by `client.get()` and `client.query()` are derived from the provenance log via `entity_provenance_summary`
- [x] 3.2 Update every write path in `IngestionPipeline` (create, update, availability toggle) to keep the entity table `created_at`/`updated_at` cache in sync with provenance values on each mutation
- [x] 3.3 Write unit tests: `get()` returns provenance-derived `created_at`; after multiple updates `updated_at` matches the most recent write event timestamp
- [x] 3.4 Write unit test: entity table cache columns are updated on each write operation

## 4. Gap 2 — PaginatedResult Return Type

- [x] 4.1 Verify `PaginatedResult` in `core/types.py` has the required fields: `items: list[dict]`, `total: int`, `limit: int`, `offset: int`; add any missing fields
- [x] 4.2 Update `client.query()` to return `PaginatedResult` instead of `list[dict]`; populate `total` from a count query (not `len(items)`)
- [x] 4.3 Update the REST transport layer to unwrap `.items` when constructing the API response body and surface `total`, `limit`, `offset` in the response envelope
- [x] 4.4 Update all existing internal callers of `client.query()` (tests, transport) to iterate via `.items`
- [x] 4.5 Write unit tests: non-empty query returns correct `PaginatedResult`; empty query returns `items=[]` and `total=0`; `total` reflects count ignoring limit/offset

## 5. Gap 3 — client.supersede_entity()

- [x] 5.1 Add `EntityAlreadySupersededError` to `core/exceptions.py` (or equivalent errors module)
- [x] 5.2 Implement `client.supersede_entity(entity_id, replacement_id, reason=None, actor=...)` on `HippoClient`:
  - Mark `entity_id` as `is_available = false` in the entity table
  - Write `superseded_by = replacement_id` to the entity table column
  - Write an `EntitySuperseded` provenance event on `entity_id` with `superseded_by_id` and optional `reason`
  - Write a `superseded_by` relationship edge from `entity_id` to `replacement_id` in `entity_relationships`
  - Write an `EntityUpdated` provenance event on `replacement_id` noting it is the active replacement
  - Wrap all five writes in a single storage adapter transaction
- [x] 5.3 Add guard: raise `EntityAlreadySupersededError` if `entity_id` is already superseded before any writes
- [x] 5.4 Add guard: raise a suitable error if either `entity_id` or `replacement_id` does not exist
- [x] 5.5 Update `client.get()` read path to include `superseded_by` in the returned entity dict (from the entity table column); return `None` when not superseded
- [x] 5.6 Write unit tests:
  - Happy path: source entity is unavailable, `superseded_by` is set, both provenance events exist, relationship edge exists
  - Already-superseded raises `EntityAlreadySupersededError` with no state change
  - Non-existent entity raises error with no state change
  - Mid-transaction failure rolls back all five writes (mock storage failure)
  - `client.get()` on superseded entity returns `superseded_by` field; on non-superseded entity returns `None`

## 6. Documentation Updates

- [x] 6.1 Update sec3 data model section to document `superseded_by` as a system field on all entity tables (alongside `is_available`)
- [x] 6.2 Update sec6 provenance section to confirm `EntitySuperseded` is a supported `operation_type` and document the bidirectional event pattern
- [x] 6.3 Update sec3b / relational storage section to mark `entity_provenance_summary` as required and document view columns + derivation logic
- [x] 6.4 Add a CHANGELOG entry documenting the breaking change to `client.query()` return type and the new `client.supersede_entity()` method
