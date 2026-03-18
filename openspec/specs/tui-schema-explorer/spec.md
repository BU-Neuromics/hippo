# tui-schema-explorer Specification

## Purpose
TBD - created by archiving change tui-browser-schema-explorer. Update Purpose after archive.
## Requirements
### Requirement: Schema Explorer view is accessible from the sidebar
The system SHALL display a static "Schema Explorer" entry at the bottom of the sidebar,
below all entity type entries. Selecting it SHALL activate the `SchemaExplorerView` in the
main panel. The Schema Explorer SHALL be read-only; no editing of schema definitions is
permitted through the TUI.

#### Scenario: Schema Explorer entry is always visible in sidebar
- **WHEN** the TUI is launched
- **THEN** "Schema Explorer" appears as the last item in the sidebar regardless of how many entity types are loaded

#### Scenario: Selecting Schema Explorer opens the view
- **WHEN** the user selects "Schema Explorer" in the sidebar
- **THEN** the `SchemaExplorerView` is rendered in the main panel

---

### Requirement: Schema Explorer displays entity types with field counts
The system SHALL render a left panel in `SchemaExplorerView` listing all entity types defined
in the active schema. Each entry SHALL show the entity type name and the number of
user-defined fields it declares. The list SHALL be keyboard-navigable with `↑`/`↓` arrows.

#### Scenario: Entity type list shows name and field count
- **WHEN** the Schema Explorer is open
- **THEN** each entity type is shown as "TypeName   N fields" where N is the count of user-defined fields

#### Scenario: Navigating the list updates the field table
- **WHEN** the user moves the selection to a different entity type
- **THEN** the right panel updates immediately to show that entity type's field table

---

### Requirement: Schema Explorer displays a field table for the selected entity type
The system SHALL render a right panel in `SchemaExplorerView` showing a table of fields for
the currently selected entity type. Each row SHALL show: field name, field type, whether the
field is required (✓ or -), and whether the field is indexed (✓ or -). Reference fields
SHALL display the target entity type name with a `→` indicator. The field table SHALL be
scrollable if the number of fields exceeds the panel height.

#### Scenario: Field table shows all user-defined fields
- **WHEN** an entity type with 8 user-defined fields is selected
- **THEN** 8 rows are shown in the field table, one per field

#### Scenario: Reference field shows target entity type
- **WHEN** a field of type `ref` targeting `Donor` is displayed
- **THEN** the row shows type `ref` and an additional `→ Donor` indicator

#### Scenario: Required and indexed flags render correctly
- **WHEN** a required, indexed field is displayed
- **THEN** the Required column shows ✓ and the Indexed column shows ✓

#### Scenario: Optional, non-indexed field renders dashes
- **WHEN** an optional, non-indexed field is displayed
- **THEN** the Required column shows - and the Indexed column shows -

---

### Requirement: Schema Explorer displays relationship declarations
The system SHALL render a relationships section below or adjacent to the entity type list in
`SchemaExplorerView`. Each relationship SHALL be shown as:
`SourceType ──<rel-name>──▶ TargetType`.
The list SHALL be derived from the `SchemaView.relationships` returned by the backend.

#### Scenario: Relationship declarations are listed for all defined relationships
- **WHEN** the schema defines a `donated_by` relationship from `Sample` to `Donor`
- **THEN** the relationships section shows `Sample ──donated_by──▶ Donor`

#### Scenario: Empty relationships section when no relationships are defined
- **WHEN** the schema defines entity types but no explicit relationships
- **THEN** the relationships section is present but empty (no rows)

---

### Requirement: Schema data is cached for the TUI session lifetime
The system SHALL cache the result of `backend.get_schema()` after the first call. Subsequent
view renderings SHALL use the cached `SchemaView` and SHALL NOT call `get_schema()` again
unless the user explicitly triggers a refresh with `r`. On refresh, the cache SHALL be
invalidated and `get_schema()` SHALL be called again.

#### Scenario: Switching entity types does not re-fetch schema
- **WHEN** the user navigates between entity types in the Schema Explorer
- **THEN** `backend.get_schema()` is called exactly once per session (until refresh)

#### Scenario: r key invalidates schema cache and re-fetches
- **WHEN** the user presses `r` while in the Schema Explorer
- **THEN** `backend.get_schema()` is called again and the view updates with fresh schema data

