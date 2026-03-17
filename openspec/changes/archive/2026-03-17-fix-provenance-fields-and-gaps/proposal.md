# Fix Provenance Fields and v0.1 Gaps

## Why

Three gaps were identified during the v0.1 documentation audit:

1. **`created_at`/`updated_at` stored directly** — the design spec requires these to be derived from the provenance log at read time (spec: `relational-storage-mapping`, "Computed field derivation is documented"). Currently they are written as independent columns and never updated from provenance.

2. **`PaginatedResult` unused** — the type is defined in `core/types.py` and exported from `__init__.py` but `client.query()` returns a plain `list[dict]` instead. Callers have no way to get total count or cursor for pagination.

3. **Entity-level supersession not implemented** — `client.supersede()` only handles external ID supersession. The design spec (sec3) defines entity supersession as marking an entity unavailable and pointing to its replacement. There is no `supersede_entity()` method.

## What Changes

### Gap 1: Provenance-derived temporal fields
- `client.get()` / `client.query()` / `client.put()` return dicts should include `created_at` and `updated_at` derived from the provenance log (first CREATE record timestamp, last non-DELETE record timestamp)
- The `entities` table columns `created_at`/`updated_at` remain as a fast-read cache (no schema migration needed) but must be kept in sync with provenance on every write
- `client.history()` already returns provenance records — no change needed there

### Gap 2: PaginatedResult from client.query()
- `client.query()` signature changes to return `PaginatedResult` (already defined in `core/types.py`)
- `PaginatedResult` wraps `items: list[dict]`, `total: int`, `limit: int`, `offset: int`
- Backwards-compatible: callers can still iterate `.items`

### Gap 3: Entity supersession
- Add `client.supersede_entity(entity_id, replacement_id, reason=None)` method
- Marks `entity_id` as unavailable (`is_available=0`), stores `replacement_id` reference
- Records a `SUPERSEDE` provenance event on both entities
- `client.get()` on a superseded entity returns the entity with `superseded_by` field populated
- Does not hard-delete anything (immutability preserved)

## Capabilities

### Modified Capabilities
- `hippo-data-model` — PaginatedResult usage, entity supersession semantics
- `provenance-tracking` — SUPERSEDE operation type, provenance-derived fields
- `relational-storage-mapping` — computed field sync on write

## Impact

- `client.query()` return type change (PaginatedResult wrapping list — additive)
- New `client.supersede_entity()` method
- `client.get()` return dict gains optional `superseded_by` field
- Entities table gains `superseded_by` column (nullable, migration required)
- All existing tests should continue to pass; new tests added for each gap
