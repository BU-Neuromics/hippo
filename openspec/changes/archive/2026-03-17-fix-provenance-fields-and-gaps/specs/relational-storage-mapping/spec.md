## MODIFIED Requirements

### Requirement: Computed field derivation is documented
The relational storage section SHALL specify how `created_at`, `updated_at`, and `schema_version` are derived from the provenance log at read time in a relational context (e.g., JOIN or subquery patterns). The section SHALL further specify that the `entity_provenance_summary` VIEW is required (not optional) for correct operation of `client.query()` with provenance-derived fields, and SHALL define the view's expected columns and derivation logic.

#### Scenario: Computed field implementation guidance
- **WHEN** a coding agent implements entity reads for the relational adapter
- **THEN** it finds guidance on how to derive temporal and version fields from the provenance log

#### Scenario: entity_provenance_summary view is documented as required
- **WHEN** a coding agent reads the relational storage section on computed field derivation
- **THEN** the section states that `entity_provenance_summary` is a required view (not a recommendation) for `client.query()` to return provenance-derived `created_at`/`updated_at`
- **AND** the view's expected columns (`entity_id`, `created_at`, `updated_at`, `schema_version`) and derivation logic (first CREATE timestamp, latest non-DELETE timestamp) are defined

#### Scenario: hippo migrate creates entity_provenance_summary view if absent
- **WHEN** `hippo migrate` is run on a database that does not have the `entity_provenance_summary` view
- **THEN** the view is created before any entity table migrations are applied

## ADDED Requirements

### Requirement: entities table gains superseded_by column via hippo migrate
`hippo migrate` SHALL add a nullable `superseded_by TEXT` column to every entity type table when the column does not already exist. This column stores the ID of the superseding entity and serves as a fast-read cache of the `superseded_by` relationship edge.

#### Scenario: Migration adds superseded_by column to entity tables
- **WHEN** `hippo migrate` is run against a schema with existing entity types that do not have a `superseded_by` column
- **THEN** each entity type table gains `ADD COLUMN superseded_by TEXT` (nullable, no default)

#### Scenario: Existing rows unaffected by superseded_by migration
- **WHEN** `hippo migrate` adds the `superseded_by` column
- **THEN** all pre-existing entity rows have `superseded_by = NULL`, correctly representing "not superseded"

#### Scenario: superseded_by column is a system column applied generically
- **WHEN** a coding agent reads the migration section for system columns
- **THEN** `superseded_by` is listed alongside `is_available` as a system column applied to all entity types, not declared per-schema
