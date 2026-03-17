## Context

Hippo's spec (sec3, sec3b, sec6) mandates that temporal fields (`created_at`, `updated_at`, `schema_version`) are derived from the provenance log at read time — never stored as independent entity table columns. In practice the v0.1 implementation diverged from this in at least three ways:

1. `created_at`/`updated_at` are written as independent entity table columns and are not kept in sync with provenance events.
2. `PaginatedResult` is defined and exported but `client.query()` returns a bare `list[dict]`, leaving callers with no way to get total count or continuation cursor.
3. `client.supersede()` only handles external ID supersession. Entity-level supersession — marking an entity unavailable and pointing to its replacement — has no dedicated method, despite being defined in sec3 §3.3 and sec6 §6.3 (`EntitySuperseded` event type).

All three gaps were identified during a v0.1 documentation audit. They are independent in implementation but are batched here because they collectively represent the delta between the written spec and the shipped SDK.

---

## Goals / Non-Goals

**Goals:**
- Align `client.get()` / `client.query()` / `client.put()` response dicts with sec3 §3.2: `created_at` and `updated_at` are derived from provenance, not from stale entity table columns.
- Maintain entity table `created_at`/`updated_at` columns as a write-through cache (no schema migration required), kept in sync on every write to preserve query performance.
- Change `client.query()` to return `PaginatedResult` with `items`, `total`, `limit`, and `offset`.
- Add `client.supersede_entity()` implementing the `EntitySuperseded` provenance event and `superseded_by` edge as specified in sec3 §3.3 and sec6 §6.3.

**Non-Goals:**
- Removing `created_at`/`updated_at` physical columns from entity tables — they remain as a cache.
- Implementing cursor-based pagination (offset/limit is sufficient for v0.1).
- Implementing `state_at()` or history filtering (those are separate sec6 §6.7 concerns).
- Any changes to the REST transport layer signature (transport calls SDK; SDK return type changes flow through).
- Auth or actor resolution — `actor` remains caller-supplied.

---

## Decisions

### Decision 1: Entity table columns as a write-through cache

**Choice:** Keep `created_at`/`updated_at` as physical columns on entity tables, but treat them as a denormalized cache that must be populated/updated on every write operation. Reads derive authoritative values from the provenance log.

**Rationale:** The provenance log is the authoritative source per spec. However, eliminating the columns entirely would require a schema migration and risk breaking any direct SQL consumers. Keeping them as a cache allows read-time derivation (provenance → entity response) without a performance penalty on individual `get()` calls: the entity table fast path remains available when provenance data is unavailable (e.g. during bootstrapping).

**Alternative considered:** Remove columns entirely and always join to `entity_provenance_summary` view. Rejected because it requires a column-drop migration (which Hippo's migration planner explicitly rejects per sec3 §3.8) and adds a mandatory JOIN to every single-entity read.

**Alternative considered:** Store only provenance-derived values, no cache. Rejected for the same reasons — and because high-volume `client.query()` calls benefit from the `entity_provenance_summary` VIEW join rather than N provenance subqueries.

---

### Decision 2: PaginatedResult is additive — callers iterate `.items`

**Choice:** `client.query()` return type changes from `list[dict]` to `PaginatedResult`. `PaginatedResult` already exists in `core/types.py` with `items: list[dict]`, `total: int`, `limit: int`, `offset: int`. Existing callers that iterate the result (e.g. `for e in client.query(...)`) will break without code changes.

**Rationale:** The existing type definition signals intent. Callers that need total count for pagination UI currently have no way to get it. The `PaginatedResult` wrapper is the minimal interface that satisfies pagination without adding a separate `count()` call.

**Trade-off:** This is a breaking change for callers that iterate the return value directly rather than via `.items`. The risk is contained since Hippo has no external callers in v0.1 — all current callers are internal tests and the REST transport, which can be updated atomically.

---

### Decision 3: `supersede_entity()` is atomic and writes to both entities

**Choice:** `client.supersede_entity(entity_id, replacement_id, reason=None, actor=...)` is an atomic operation that:
1. Marks `entity_id` as unavailable (`is_available = false`).
2. Writes an `EntitySuperseded` provenance event on `entity_id` with `superseded_by_id = replacement_id`.
3. Writes a `superseded_by` relationship edge from `entity_id` to `replacement_id` in `entity_relationships`.
4. Writes an `EntityUpdated` provenance event on `replacement_id` noting the supersession (it is now an active replacement).
5. Sets `superseded_by` on the `entities` column (new nullable column, see Gap 3 migration below).

All five writes are wrapped in a single storage adapter transaction. If any step fails the entire operation rolls back.

**Rationale:** Sec3 §3.3 states: "Setting `superseded_by` automatically marks the source entity as unavailable. Supersession is an atomic SDK operation." Atomicity is non-negotiable — a partial supersession (entity unavailable but no edge) would create an orphaned unavailable entity with no audit trail.

**Alternative considered:** Implement supersession as sequential SDK operations (availability change + relationship write + provenance). Rejected because the spec is explicit about atomicity and the storage adapter already supports transactional writes.

---

### Decision 4: `superseded_by` as a column on entity tables (not just a relationship edge)

**Choice:** Add a nullable `superseded_by TEXT` column to entity tables (via `hippo migrate`) to allow `client.get()` to return `superseded_by` without a relationship table JOIN.

**Rationale:** `client.get()` returning a superseded entity should surface `superseded_by` without requiring callers to follow the edge graph. The column is a denormalization of the `superseded_by` relationship edge — it is set atomically with the edge write. The relationship edge remains the authoritative record (and is audited by provenance); the column is a fast-path cache.

**Migration:** `ALTER TABLE {entity_type}s ADD COLUMN superseded_by TEXT` (nullable, no default). This is a safe additive migration that Hippo's migration planner supports per sec3 §3.8.

**Scope:** `superseded_by` is a system field present on all entity types. The column is added by `hippo migrate` generically, not per-schema-declaration. This mirrors how `is_available` is treated.

---

## Risks / Trade-offs

**`client.query()` return type is a breaking change** → Mitigation: Update all existing callers in the same PR. The REST transport is the only non-test consumer and can be updated atomically. Document the change clearly in the CHANGELOG.

**Write-through cache can drift if writes bypass the SDK** → Mitigation: The SQLite adapter enforces provenance immutability via triggers; entity table writes that bypass `HippoClient` are unsupported and undocumented. Direct DB access is out of scope for v0.1.

**`superseded_by` column requires a schema migration per entity type** → Mitigation: `hippo migrate` handles this as a standard additive `ALTER TABLE`. The column is nullable so existing rows are unaffected. The migration runs once at upgrade time.

**`EntityUpdated` event on `replacement_id` during supersession is implicit** → The replacement entity may not have changed in content, but recording provenance on it makes the audit trail bidirectional: both the old and new entity have a provenance record documenting the supersession event. This is intentional and consistent with sec6 §6.3 ("A companion `EntityCreated` (or `EntityUpdated`) event is fired on the new entity in the same transaction.").

---

## Migration Plan

**Gap 1 (provenance-derived fields):** No DDL required. Entity table `created_at`/`updated_at` columns already exist. SDK change only: derive values from provenance at read time; continue to write them on every mutation as cache. Update `entity_provenance_summary` view if not already present (see sec6 §6.6).

**Gap 2 (PaginatedResult):** No DDL required. SDK return type change. Update REST transport to unwrap `.items` when constructing API response, and surface `total`/`limit`/`offset` in the response envelope.

**Gap 3 (entity supersession):** Requires `hippo migrate`:
```sql
ALTER TABLE {entity_type}s ADD COLUMN superseded_by TEXT;
```
This migration is applied per entity type in the deployed schema. No data backfill required (existing entities have `NULL`, which correctly means "not superseded").

**Rollback:** All three gaps are purely additive — new method, return type wrapper, nullable column. Rollback is a code revert; the nullable column can be left in place with no effect if the SDK is rolled back (it will never be written to).

---

## Open Questions

1. **`entity_provenance_summary` view creation:** Is this view guaranteed to exist in all v0.1 deployments, or must the migration add it if absent? The spec (sec6 §6.6) documents it as a recommendation; the implementation should treat it as required for correct `query()` behaviour with provenance-derived fields.

2. **`supersede_entity()` on already-superseded entities:** Should calling `supersede_entity()` on an entity that is already superseded be idempotent, fail fast, or raise a distinct error? Current spec is silent. Proposal: raise `EntityAlreadySupersededError`.

3. **`client.supersede()` naming collision:** The existing `client.supersede()` method handles external ID supersession. The new `client.supersede_entity()` method handles entity supersession. Should these be unified under a single `client.supersede()` with a dispatch on argument type, or remain distinct? Distinct names are explicit and avoid magic dispatch — current plan keeps them separate.
