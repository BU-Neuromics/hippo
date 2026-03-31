## 4. API Layer

**Document status:** Draft v0.1
**Depends on:** sec2_architecture.md, sec3_data_model.md, sec6_provenance.md
**Feeds into:** sec5_ingestion.md, sec7_nfr.md

---

### 4.1 Design Philosophy

The API layer is SDK-first. All business logic lives in the Core SDK (`HippoClient`). The
REST API is a thin transport adapter that calls the SDK — it contains no logic of its own.
This means the SDK and REST API are always in sync, and the REST API is never "ahead" of the
SDK in capability.

The public surface of the API layer is:
1. **`HippoClient`** — the Python SDK public interface (primary)
2. **REST API** — JSON over HTTP, auto-documented via OpenAPI (secondary; for non-Python callers)

GraphQL is reserved for a future version.

---

### 4.2 HippoClient Public Interface

`HippoClient` is the single entry point to all Hippo functionality. It is instantiated once
with a `HippoConfig` and used throughout the application lifetime.

```python
from hippo import HippoClient, HippoConfig

client = HippoClient(HippoConfig.from_file("hippo.yaml"))
```

#### Entity operations

```python
# Create or update an entity (upsert semantics — see sec5 §5.4)
entity = client.put(
    entity_type="Sample",
    data={"tissue_type": "brain", "external_ids": [{"system": "starlims", "id": "SL-123"}]},
    actor="pipeline-run-42",
    provenance_context={"workflow_run_id": "wf-abc"}  # optional
)
# Returns the written entity dict including system fields

# Fetch by Hippo UUID
sample = client.get("Sample", "uuid-here")

# Fetch by ExternalID
sample = client.get_by_external_id("Sample", system="starlims", external_id="SL-123")

# Fetch multiple by UUID (batch)
samples = client.get_many("Sample", ids=["uuid-1", "uuid-2", "uuid-3"])
```

#### Query operations

```python
# Filter query
results = client.query(
    "Sample",
    tissue_type="brain",
    is_available=True,           # default; pass False to include unavailable
    exact_type=False,            # default; pass True to exclude subtypes
    limit=100,
    offset=0,
    order_by="created_at",
    order_dir="desc"
)
# Returns PaginatedResult (see §4.4)

# Fuzzy search on indexed fields
matches = client.search(
    entity_type="AnatomyTerm",
    field="preferred_label",
    query="prefrontal cortex",
    limit=5,
    min_score=0.5
)
# Returns list[ScoredMatch]

# Graph traversal: follow a named relationship
subjects = client.traverse(
    start_type="Sample", start_id="sample-uuid",
    relationship="donated",
    direction="inbound",   # "outbound" | "inbound" | "both"
    target_type="Subject"  # optional filter
)

# Fetch updated since a timestamp (used by Cappella hippo_poll trigger)
recent = client.query_updated_since(
    entity_type="Sample",
    since="2024-01-01T00:00:00Z",
    limit=500
)
```

#### Availability and lifecycle operations

```python
# Mark unavailable
client.set_availability(
    entity_type="Sample", entity_id="uuid",
    available=False,
    reason="Sample quality insufficient",
    actor="data-team"
)

# Supersede one entity with another
client.supersede(
    entity_type="Sample",
    old_id="old-uuid", new_id="new-uuid",
    actor="pipeline-run-42",
    reason="Corrected tissue region annotation"
)
```

#### Relationship operations

```python
# Create a relationship
client.relate(
    relationship="donated",
    from_type="Subject", from_id="subj-uuid",
    to_type="Sample",   to_id="sample-uuid",
    actor="data-team",
    properties={"method": "surgical biopsy"}
)

# Remove a relationship (soft delete)
client.unrelate(
    relationship_id="edge-uuid",
    actor="data-team",
    reason="Incorrectly linked"
)

# Query relationships
edges = client.relationships(
    entity_type="Subject", entity_id="subj-uuid",
    relationship="donated",
    direction="outbound"
)
```

#### ExternalID operations

```python
# Register an ExternalID
client.register_external_id(
    entity_type="Sample", entity_id="uuid",
    system="starlims", external_id="SL-123",
    actor="data-team"
)

# Correct an ExternalID (supersession)
client.correct_external_id(
    entity_type="Sample", entity_id="uuid",
    system="starlims",
    old_value="SL-123", new_value="SL-124",
    reason="Transcription error",
    actor="data-team"
)
```

#### Provenance operations

```python
# Full history for an entity
events = client.history("Sample", "uuid")
# Returns list[ProvenanceRecord] in chronological order

# Filtered history
events = client.history("Sample", "uuid",
    event_types=["EntityUpdated", "AvailabilityChanged"],
    since="2024-01-01T00:00:00Z"
)

# State reconstruction at a point in time
state = client.state_at("Sample", "uuid", timestamp="2024-06-01T00:00:00Z")
```

#### Schema introspection

```python
# List all entity types
entity_types = client.schema.entity_types()

# Describe an entity type (fields, validators, relationships)
descriptor = client.schema.describe("Sample")

# List installed reference loaders
loaders = client.schema.reference_loaders()

# Check deprecated fields
deprecated = client.schema.deprecated_fields("Sample")

# Check subtype hierarchy
subtypes = client.schema.subtypes("Sample")   # ["BrainSample", "CellLine"]
ancestors = client.schema.ancestors("BrainSample")  # ["Sample"]
```

---

### 4.3 REST API

The REST API is a FastAPI application. All endpoints call `HippoClient` directly — no
separate REST-layer business logic.

Base path: `/api/v1`

Auto-generated docs available at `/docs` (Swagger UI) and `/redoc`. OpenAPI JSON at
`/openapi.json`.

#### Entity endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/entities/{entity_type}` | Query entities (supports filter params, pagination) |
| `POST` | `/entities/{entity_type}` | Create or update an entity (upsert) |
| `PUT` | `/entities/{entity_type}/{entity_id}` | Update an existing entity (returns 404 if not found) |
| `GET` | `/entities/{entity_type}/{entity_id}` | Fetch entity by UUID |
| `GET` | `/entities/{entity_type}/{entity_id}/history` | Full provenance history |
| `POST` | `/entities/{entity_type}/{entity_id}/availability` | Set availability (single entity) |
| `POST` | `/entities/{entity_type}/bulk-availability` | Set availability for multiple entities |
| `POST` | `/entities/{entity_type}/{entity_id}/supersede` | Supersede with another entity |
| `GET` | `/entities/{entity_type}/{entity_id}/relationships` | List relationships |

#### Search endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/search/{entity_type}` | Fuzzy search on a field (`?field=&q=&limit=&min_score=`) |

#### Relationship endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/relationships` | Create a relationship |
| `DELETE` | `/relationships/{relationship_id}` | Remove a relationship (soft delete) |

#### ExternalID endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/external-ids/{system}/{external_id}` | Lookup entity by ExternalID |
| `POST` | `/entities/{entity_type}/{entity_id}/external-ids` | Register ExternalID |
| `PUT` | `/entities/{entity_type}/{entity_id}/external-ids/{system}` | Correct ExternalID |

#### Ingestion endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest/{entity_type}` | Batch ingest (JSON array body) |

#### Schema introspection endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/schema/entity-types` | List all entity types |
| `GET` | `/schema/entity-types/{entity_type}` | Describe an entity type |
| `GET` | `/schema/reference-loaders` | List installed reference loaders and versions |

#### System endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — returns `{"status": "ok"}` |
| `GET` | `/status` | Adapter type, schema version, entity counts, plugin summary |

#### `PUT /entities/{entity_type}/{entity_id}` — Explicit Update

Unlike `POST /entities/{entity_type}` (upsert), this endpoint returns `404 Not Found` if the
entity does not exist. Use it when the caller requires the entity to already exist — for
example, when updating a sample record that was ingested by a separate pipeline.

**Request body:**
```json
{
  "data": { "tissue_type": "liver" }
}
```

Partial update semantics: only the fields present in `data` are updated. Fields absent from
the request body are left unchanged.

**Response:** The updated entity (same shape as `POST`).

**SDK equivalent:**
```python
entity = client.update(
    entity_type="Sample",
    entity_id="uuid-here",
    data={"tissue_type": "liver"},
    actor="pipeline-run-99",
    provenance_context={"workflow_run_id": "wf-xyz"}
)
# Raises EntityNotFoundError if entity_id does not exist
```

---

#### `POST /entities/{entity_type}/bulk-availability` — Bulk Availability Change

Sets availability on a list of entities in a single call. All records are processed
individually (per-record error isolation); the call does not abort on partial failure.

**Request body:**
```json
{
  "entity_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "available": false,
  "reason": "Dataset archived — Q1 2026 cohort",
  "actor": "data-team"
}
```

**Response:**
```json
{
  "data": {
    "updated": 2,
    "errors": [
      { "entity_id": "uuid-3", "error": "EntityNotFoundError", "message": "uuid-3 not found" }
    ]
  },
  "error": null,
  "meta": { "schema_version": "1.1", "request_id": "uuid" }
}
```

HTTP status codes:
- `200 OK` — all entities updated successfully
- `207 Multi-Status` — partial success (some entities updated, some errored)
- `404 Not Found` — entity type not in schema

**SDK equivalent:**
```python
result = client.set_availability_bulk(
    entity_type="Sample",
    entity_ids=["uuid-1", "uuid-2", "uuid-3"],
    available=False,
    reason="Dataset archived",
    actor="data-team"
)
# result.updated: int
# result.errors: list[BulkOperationError]
```

---

#### Query Filtering — OR Composition

By default, all query parameters are AND-combined. Phase 1 adds two mechanisms for OR
composition:

**Multi-value parameters (same-field OR):** Repeat a query parameter to match any of the
given values (logical OR within the field, AND across fields).

```
GET /entities/Sample?tissue_type=brain&tissue_type=liver&is_available=true
# Returns samples where tissue_type IN ('brain', 'liver') AND is_available = true
```

**`filter` parameter (cross-field CEL expression):** For more complex predicates, pass a
URL-encoded CEL expression as the `filter` parameter. The expression is evaluated against
each entity's `data` fields.

```
GET /entities/Sample?filter=data.age_at_collection%20%3E%2018%20%26%26%20data.tissue_type%20!%3D%20%22control%22
# Returns samples where age_at_collection > 18 AND tissue_type != "control"
```

The `filter` CEL context has access to: `data` (the entity's data fields), `id` (UUID),
`is_available` (bool), `created_at`, `updated_at` (ISO8601 strings).

**SDK equivalent:**
```python
# Multi-value: pass a list
results = client.query("Sample", tissue_type=["brain", "liver"], is_available=True)

# CEL filter
results = client.query("Sample", filter='data.age_at_collection > 18')
```

**Opinionated decision:** CEL evaluation for `filter` is done in the storage adapter. The
SQLite adapter translates common patterns to SQL predicates; others fall back to in-memory
evaluation. Complex `filter` expressions on large datasets should use
`query_updated_since` + client-side filtering where possible.

---

#### Standard request/response conventions

**Request headers:**
- `X-Hippo-Actor: <identity>` — actor for write operations (required on all writes; defaults
  to `"anonymous"` if absent in v0.1)
- `X-Hippo-Context: <JSON>` — provenance context JSON (optional)

**Response envelope (all responses):**
```json
{
  "data": { ... },        // null on error
  "error": null,          // null on success; see error format below
  "meta": {               // always present
    "schema_version": "1.1",
    "request_id": "uuid"
  }
}
```

**Error format:**
```json
{
  "data": null,
  "error": {
    "type": "ValidationError",
    "message": "Sample 'abc-123' failed validation",
    "detail": {
      "validator": "active_subject_check",
      "errors": ["Subject xyz is withdrawn"]
    }
  },
  "meta": { "schema_version": "1.1", "request_id": "uuid" }
}
```

HTTP status codes:
- `200 OK` — successful read
- `201 Created` — entity created
- `200 OK` — entity updated (not 204, always returns the entity)
- `404 Not Found` — `EntityNotFoundError`
- `422 Unprocessable Entity` — `ValidationError` (schema or rule)
- `409 Conflict` — `ConfigError` (e.g. adapter conflict)
- `500 Internal Server Error` — `AdapterError` (storage failure)

---

### 4.4 Pagination

Hippo supports two pagination modes: **offset-based** (v0.1, always available) and
**cursor-based** (Phase 1, for stable iteration over large result sets).

**Opinionated decision (v0.1):** Offset pagination is the default and is always available.
Cursor-based pagination is additive — callers opt in by passing `cursor` instead of
`offset`. Both modes are supported concurrently. Do not mix `cursor` and `offset` in the
same request; `cursor` takes precedence if both are present.

#### SDK pagination

```python
# Automatic pagination: iterates all pages and yields individual entities
for sample in client.iter_query("Sample", tissue_type="brain"):
    process(sample)

# Manual pagination: caller controls page fetch
page = client.query("Sample", tissue_type="brain", limit=100, offset=0)
# page.items: list[dict]
# page.total: int (total matching entities, not just this page)
# page.limit: int
# page.offset: int
# page.has_more: bool
```

#### REST pagination

Query parameters: `?limit=<n>&offset=<n>` (default limit: 100, max: 1000)

Response includes pagination metadata in `meta`:

```json
{
  "data": [ ...entities... ],
  "error": null,
  "meta": {
    "schema_version": "1.1",
    "request_id": "uuid",
    "pagination": {
      "total": 4821,
      "limit": 100,
      "offset": 200,
      "has_more": true
    }
  }
}
```

#### Cursor-based pagination (Phase 1)

Cursor pagination guarantees stable iteration: new records inserted during pagination do
not shift subsequent pages. Use it when iterating large result sets where page drift is
unacceptable — for example, background export jobs or incremental sync pipelines.

**Request:** Pass `?cursor=<opaque-token>&limit=<n>` instead of `?offset=<n>`.

```
GET /entities/Sample?cursor=eyJpZCI6ImFiYyIsInRzIjoiMjAyNi0wMS0wMVQwMCJ9&limit=100
```

**Response:** `next_cursor` is included in `meta.pagination` when more pages exist. When
the last page is reached, `next_cursor` is `null`.

```json
{
  "data": [ ...entities... ],
  "error": null,
  "meta": {
    "schema_version": "1.1",
    "request_id": "uuid",
    "pagination": {
      "limit": 100,
      "has_more": true,
      "next_cursor": "eyJpZCI6Inl6eiIsInRzIjoiMjAyNi0wMS0wMVQwMCJ9"
    }
  }
}
```

**Cursor encoding:** Cursors are opaque base64-encoded tokens. Callers must not parse or
construct cursors manually — always use `next_cursor` from the previous response. Cursors
encode the sort position of the last returned record and are tied to the query's `order_by`
and `order_dir` parameters; changing these parameters invalidates a cursor.

**Cursor lifetime:** Cursors are stateless (encoded position, not server-side session).
They do not expire, but they may return fewer results than expected if records are deleted
between pages.

**Offset fallback:** Callers receiving a cursor response can convert to offset-mode by
omitting `cursor` and computing `offset = page_number * limit`. Both modes return results
in the same order for the same `order_by` / `order_dir`.

**SDK equivalent:**
```python
# Manual cursor pagination
page = client.query("Sample", tissue_type="brain", limit=100)
while page.has_more:
    page = client.query("Sample", tissue_type="brain", limit=100, cursor=page.next_cursor)
    process(page.items)

# Automatic cursor pagination (preferred)
for sample in client.iter_query("Sample", tissue_type="brain", pagination="cursor"):
    process(sample)
```

---

### 4.5 `query_updated_since` — Polling Support

This method is designed for Cappella's `hippo_poll` trigger source and any other caller that
needs efficient change detection.

```python
recent = client.query_updated_since(
    entity_type="Sample",
    since="2024-01-01T00:00:00Z",
    limit=500,
    offset=0
)
```

**Implementation:** Uses the `entity_provenance_summary` view (see sec6 §6.6) to find
entities with `updated_at > since`, ordered by `updated_at` ascending (oldest first, so
callers can process in order and advance their watermark incrementally).

**REST endpoint:**

```
GET /entities/{entity_type}?updated_since=<ISO8601 timestamp>&limit=500
```

**Opinionated decision:** The `since` timestamp is based on Hippo's provenance `updated_at`
(server-side UTC), not any caller-supplied timestamp. This avoids clock skew issues between
Cappella and Hippo. Callers should persist the `updated_at` value of the last entity they
processed as their watermark for the next poll.

---

### 4.6 Open Questions

| Question | Priority | Notes |
|---|---|---|
| Cursor-based pagination | Medium | **Specced in §4.4 (Phase 1 / v0.5).** Implement when `iter_query` callers report page drift issues. |
| OR filter composition | Medium | **Specced in §4.3 (Phase 1 / v0.5).** Multi-value params + `?filter=` CEL. SQLite adapter translates common patterns; complex expressions fall back to in-memory evaluation. |
| `PUT /entities/{type}/{id}` explicit update | Medium | **Specced in §4.3 (Phase 1 / v0.5).** Returns 404 on missing. Partial update semantics. |
| Bulk availability change | Medium | **Specced in §4.3 (Phase 1 / v0.5).** Per-record error isolation; 207 on partial success. |
| GraphQL transport | Low | Reserved in `hippo/graphql/`. Defer to post-v0.1. |
| Bulk relationship query | Medium | `client.relationships_bulk(entity_ids=[...])` — fetch relationships for many entities in one query. Useful for Cappella expand path engine. Omitted from v0.1 for simplicity; add when needed. |
| Rate limiting | Low | Out of scope for v0.1 (no auth layer). Add with auth in a future version. |
| `filter` CEL performance | Medium | Storage-adapter-dependent. Document adapter capability declaration at startup (similar to fuzzy search capability flag). Add a `capabilities.cel_filter` flag to the `/status` endpoint. |

---
