## 7. Non-Functional Requirements

**Document status:** Draft v0.1
**Depends on:** sec2_architecture.md, sec4_api_layer.md
**Feeds into:** (implementation)

---

### 7.1 Performance

#### Targets (v0.1, SQLite adapter, single-host deployment)

| Operation | Target | Notes |
|---|---|---|
| Single entity `get()` | < 5 ms | With provenance derivation |
| Filter query, 100 results | < 50 ms | On indexed fields, available records only |
| Filter query, 1000 results | < 200 ms | Same |
| `put()` single entity | < 20 ms | Includes schema validation + provenance write |
| `upsert()` single entity | < 25 ms | Includes ExternalID lookup + conditional write |
| Batch ingest, 500 records | < 5 s | One committed batch |
| Fuzzy search (FTS), top 10 | < 100 ms | SQLite FTS5 |
| `events_since()`, 1000 events | < 100 ms | Via `idx_provenance_timestamp` |

These targets assume a warm SQLite connection, indexed fields, and a dataset of up to ~1M
entities. Performance degrades gracefully beyond this scale — the PostgreSQL adapter is the
recommended upgrade path for larger deployments.

#### Performance constraints

- **No unbounded queries.** All list operations are paginated (max `page_size` 1000). The SDK
  and REST API refuse requests without pagination parameters.
- **Partial indexes on `is_available`.** All indexed fields use partial indexes scoped to
  `is_available = true` (sec3b §3b.2). Query performance is independent of how many
  unavailable entities have accumulated.
- **Provenance queries use dedicated indexes.** The `idx_provenance_entity` and
  `idx_provenance_timestamp` indexes (sec6 §6.4) ensure provenance operations do not scan
  the full events table.
- **Write validators are bounded.** Config-driven validator expand paths have a
  `max_expand_list_size` cap (default 200, hard cap 1000). Plugin validators should complete
  within 100 ms; a configurable per-validator timeout will be added in a future release.

---

### 7.2 Scalability

Hippo scales via adapter selection and deployment tier — no code changes required.

| Scale | Adapter | Transport | Notes |
|---|---|---|---|
| Single researcher | SQLite | SDK direct (no server) | In-process, no network overhead |
| Small team (< 20 concurrent) | SQLite or PostgreSQL | REST (`hippo serve`, 4 workers) | WAL mode handles concurrent reads |
| Mid-size lab (20–100 concurrent) | PostgreSQL | REST (multiple workers or replicas) | Connection pooling via `psycopg2` |
| Enterprise / cloud | PostgreSQL (RDS) or DynamoDB | REST behind ALB | Managed scaling, multi-AZ |

The SQLite adapter is suitable for deployments ingesting up to ~10M entities and ~100M
provenance events. Beyond this, PostgreSQL is strongly recommended.

---

### 7.3 Reliability

#### Data integrity

- **All writes are atomic.** A write either commits fully (entity + provenance event) or not
  at all. There are no partial writes.
- **No hard deletes.** Entities and provenance records are retained indefinitely.
  `is_available` is the only lifecycle operation that reduces visibility.
- **Schema migrations are reversible** for additive changes. Destructive changes (field type
  changes, entity type removal) are rejected by the migration planner.

#### SQLite durability

- WAL mode is enabled by default (`PRAGMA journal_mode=WAL`).
- Synchronous mode is set to `NORMAL` (`PRAGMA synchronous=NORMAL`) — this provides
  durability against application crashes while accepting a small risk of data loss on OS
  crash. Set to `FULL` for stricter durability at a write-performance cost.
- Regular `VACUUM` is recommended for deployments with high write volume (many unavailability
  transitions accumulate dead rows).

#### Error handling

All storage adapter errors are wrapped in `AdapterError` before surfacing to callers.
Internal implementation details (SQLite error codes, PostgreSQL exceptions) never leak
through the SDK boundary. See sec2 §2.11 for the full error hierarchy.

---

### 7.4 Security

#### v0.1 posture

Authentication and authorisation are **explicitly out of scope for v0.1**. The REST layer
includes a no-op auth stub. Hippo v0.1 is designed for trusted-network or single-user
deployments where network-level access control is sufficient.

**Consequence:** Any client with network access to the REST API can read, write, or modify
any entity. Do not expose the v0.1 REST API to untrusted networks.

#### Planned auth model (post-v0.1)

- JWT bearer tokens validated at the REST transport layer before the SDK is called
- RBAC roles: `reader` (GET only), `writer` (GET + POST/PATCH), `admin` (all + migrate)
- The SDK is intentionally auth-unaware — auth is a transport concern
- The `actor` field is populated by the transport layer from the authenticated identity

#### Data protection

- **No PII by default.** Hippo is a metadata registry. Raw data files are never ingested.
  Deployments that store PII-adjacent metadata (subject demographics, clinical data) must
  ensure network-level and filesystem-level controls are in place.
- **Audit trail is immutable.** The provenance log cannot be modified or redacted via the
  SDK. Physical database access is required to alter provenance records.

#### Input validation

- All user-supplied field values are validated against schema config before storage
- `ref` field values are validated against entity existence and availability
- JSON fields are parsed and re-serialised to prevent injection via raw JSON strings
- URI fields are validated against the declared allowed schemes

---

### 7.5 Observability

#### Structured logging

Hippo emits structured JSON logs at INFO and DEBUG levels. Log entries include:
- Operation type (read/write/search/migrate)
- Entity type and ID (where applicable)
- Duration in milliseconds
- Actor
- Error type and message (on failure)

Log output goes to stdout by default; configurable via `logging.output` in `hippo.yaml`.

#### Health endpoint (REST only)

```
GET /health
→ {"status": "ok", "adapter": "sqlite", "schema_version": "1.0", "uptime_s": 3600}
```

Returns HTTP 200 when the server is healthy and can reach the storage backend.
Returns HTTP 503 if the storage backend is unreachable.

#### Metrics (future)

Prometheus-compatible metrics endpoint (`/metrics`) is deferred to post-v0.1. The health
endpoint is sufficient for v0.1 deployment monitoring.

---

### 7.6 Testability

- **All business logic in the Core SDK.** The transport layer (REST) and infrastructure
  layer (storage adapters) are thin wrappers. Unit tests operate on the SDK directly.
- **`InMemoryEntityStore`** — a test-only in-memory storage adapter is provided for unit
  tests that don't need a real database. It implements the full `EntityStore` ABC.
- **Config injection.** All components receive configuration via constructor injection.
  Tests can supply minimal `HippoConfig` objects without config files.
- **Write validators** are plain Python classes testable in isolation by constructing
  `WriteOperation` objects directly.
- **Reference loaders** can be tested against locally cached ontology files without network
  access by passing `source="local"` to `loader.load()`.

---

### 7.7 Compatibility

- **Python:** ≥ 3.10 required (uses `match` statements, `X | Y` union types)
- **SQLite:** ≥ 3.35 required (FTS5, WAL mode, partial indexes, `ALTER TABLE ADD COLUMN`)
- **PostgreSQL:** ≥ 13 required (future adapter; uses `JSONB`, partial indexes, `ON CONFLICT`)
- **API stability:** Pre-v1.0, minor version bumps may include breaking changes to ABCs and
  REST endpoints with deprecation notices. v1.0 marks stable API commitment.

---
