## ADDED Requirements

### Requirement: EntitySuperseded provenance event type is supported
The provenance system SHALL support an `EntitySuperseded` operation type. An `EntitySuperseded` event SHALL be recorded on the source entity when `client.supersede_entity()` is called, capturing the replacement entity ID and optional reason.

#### Scenario: EntitySuperseded event is recorded on source entity
- **WHEN** `client.supersede_entity("e1", "e2", reason="upgraded")` is called
- **THEN** a provenance record with `operation_type = "EntitySuperseded"` is written for entity `e1`
- **AND** the record includes `superseded_by_id = "e2"`
- **AND** the record includes `reason = "upgraded"` if provided

#### Scenario: EntityUpdated event is recorded on replacement entity during supersession
- **WHEN** `client.supersede_entity("e1", "e2")` is called
- **THEN** a provenance record with `operation_type = "EntityUpdated"` is written for entity `e2`
- **AND** the record notes that `e2` has become the active replacement for `e1`

#### Scenario: Both provenance events are written in the same transaction
- **WHEN** `client.supersede_entity("e1", "e2")` is called
- **THEN** the `EntitySuperseded` event on `e1` and the `EntityUpdated` event on `e2` are written atomically in a single transaction

### Requirement: Temporal fields created_at and updated_at are derived from provenance at read time
At read time, `created_at` and `updated_at` returned in entity dicts SHALL be derived from the provenance log: `created_at` is the timestamp of the first `CREATE` event for the entity; `updated_at` is the timestamp of the most recent non-DELETE event.

#### Scenario: created_at reflects first CREATE provenance record
- **WHEN** `client.get(entity_id)` or `client.query()` returns an entity dict
- **THEN** the `created_at` value equals the timestamp of the first `CREATE` provenance record for that entity

#### Scenario: updated_at reflects most recent write provenance record
- **WHEN** an entity has been updated multiple times and `client.get(entity_id)` is called
- **THEN** the `updated_at` value equals the timestamp of the most recent non-DELETE provenance record for that entity

#### Scenario: Temporal fields from entity table are kept in sync as a cache
- **WHEN** any write operation (create, update, supersede) is performed on an entity
- **THEN** the entity table `created_at` and `updated_at` columns are updated to match the provenance-derived values
- **AND** subsequent `client.get()` calls return the provenance-authoritative values
