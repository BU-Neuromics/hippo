## ADDED Requirements

### Requirement: client.query() returns PaginatedResult
`client.query()` SHALL return a `PaginatedResult` object (defined in `core/types.py`) instead of a bare `list[dict]`. `PaginatedResult` SHALL expose `items: list[dict]`, `total: int`, `limit: int`, and `offset: int`.

#### Scenario: Query returns PaginatedResult with items
- **WHEN** a caller invokes `client.query(entity_type, filters, limit=10, offset=0)`
- **THEN** the return value is a `PaginatedResult` instance
- **AND** `result.items` contains the matching entity dicts
- **AND** `result.total` is the total count of matching entities (ignoring limit/offset)
- **AND** `result.limit` equals the requested limit
- **AND** `result.offset` equals the requested offset

#### Scenario: PaginatedResult supports iteration via .items
- **WHEN** a caller iterates over `result.items` from `client.query()`
- **THEN** iteration yields the same dicts that a bare `list[dict]` return would have yielded

#### Scenario: Query with no results returns PaginatedResult with empty items
- **WHEN** `client.query()` matches no entities
- **THEN** `result.items` is an empty list and `result.total` is 0

### Requirement: client.supersede_entity() marks entity unavailable and records replacement
`client.supersede_entity(entity_id, replacement_id, reason=None, actor=...)` SHALL be a public method on `HippoClient`. It SHALL atomically mark `entity_id` as unavailable, record `replacement_id` as the superseding entity, and write provenance events on both entities. The operation SHALL be wrapped in a single storage adapter transaction.

#### Scenario: Supersede entity marks source as unavailable
- **WHEN** `client.supersede_entity("e1", "e2")` is called and both entities exist
- **THEN** `client.get("e1")` returns the entity with `is_available = false`
- **AND** the entity dict includes `superseded_by = "e2"`

#### Scenario: Supersede entity writes provenance on both entities
- **WHEN** `client.supersede_entity("e1", "e2", reason="new version")` is called
- **THEN** `client.history("e1")` includes an `EntitySuperseded` provenance event referencing `"e2"`
- **AND** `client.history("e2")` includes an `EntityUpdated` provenance event noting it is now an active replacement

#### Scenario: Supersede entity is atomic — partial failure rolls back
- **WHEN** `client.supersede_entity("e1", "e2")` is called and the storage layer fails mid-transaction
- **THEN** no partial state is written (entity availability, superseded_by column, provenance, and relationship edge are all reverted)

#### Scenario: Supersede entity on already-superseded entity raises error
- **WHEN** `client.supersede_entity("e1", "e2")` is called and `e1` is already superseded
- **THEN** an `EntityAlreadySupersededError` is raised and no state is modified

#### Scenario: Supersede entity on non-existent entity raises error
- **WHEN** `client.supersede_entity("e1", "e2")` is called and either entity does not exist
- **THEN** a suitable error is raised and no state is modified

### Requirement: client.get() on superseded entity includes superseded_by field
`client.get(entity_id)` SHALL return the entity dict including a `superseded_by` field when the entity has been superseded. The field SHALL be `None` (or absent) when the entity is not superseded.

#### Scenario: Get superseded entity returns superseded_by
- **WHEN** entity `e1` has been superseded by `e2` via `client.supersede_entity()`
- **THEN** `client.get("e1")` returns a dict with `superseded_by = "e2"`

#### Scenario: Get non-superseded entity does not include superseded_by
- **WHEN** an entity has not been superseded
- **THEN** `client.get(entity_id)` returns a dict where `superseded_by` is absent or `None`
