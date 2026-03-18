## ADDED Requirements

### Requirement: Entity Browser displays a paginated table of entities
The system SHALL render an `EntityBrowserView` in the main panel when an entity type is
selected in the sidebar. The view SHALL display a `DataTable` with 20 entities per page.
Columns SHALL consist of the first 4 user-defined fields for the entity type plus `created_at`.
The view SHALL show the current page number and total pages. Navigation between pages SHALL
use the left/right arrow keys.

#### Scenario: Browser shows first page on selection
- **WHEN** the user selects an entity type in the sidebar
- **THEN** the Entity Browser renders page 1 of the entity list with up to 20 rows

#### Scenario: Right arrow advances to next page
- **WHEN** the user presses `→` on a page that is not the last
- **THEN** the DataTable refreshes to show the next 20 entities and the page indicator increments

#### Scenario: Left arrow returns to previous page
- **WHEN** the user presses `←` on any page after the first
- **THEN** the DataTable refreshes to show the previous 20 entities and the page indicator decrements

#### Scenario: Arrow navigation is disabled at page boundaries
- **WHEN** the user presses `→` on the last page
- **THEN** no navigation occurs and the page indicator does not change

#### Scenario: `r` key refreshes the current page
- **WHEN** the user presses `r` while in the Entity Browser
- **THEN** the DataTable fetches fresh data for the current page from the backend

---

### Requirement: Entity Browser supports inline text filtering
The system SHALL provide a filter bar at the bottom of the Entity Browser. Pressing `f`
SHALL focus the filter input. As the user types, the entity list SHALL update to show only
matching entities. If the backend supports full-text search (FTS), the filter SHALL use FTS;
otherwise it SHALL fall back to a case-insensitive substring match on visible field values.
Clearing the filter SHALL restore the full paginated list.

#### Scenario: Typing in filter narrows the list
- **WHEN** the user presses `f` and types a search term
- **THEN** the DataTable updates to show only entities whose fields contain the search term

#### Scenario: Clearing filter restores full list
- **WHEN** the user clears the filter input
- **THEN** the DataTable returns to the unfiltered paginated view

#### Scenario: Filter resets page to 1
- **WHEN** the user applies a filter while on page 3
- **THEN** the view returns to page 1 of the filtered results

---

### Requirement: Entity Detail panel shows all fields, relationships, and provenance
The system SHALL display an Entity Detail panel when the user presses `Enter` on a DataTable
row. The panel SHALL replace the main panel content and show:
- All entity fields in a left column
- Immediate relationships with clickable navigation in a right top section
- The most recent 10 provenance events in a right bottom section

Pressing `Esc` or activating the `[←back]` control SHALL return to the Entity Browser.

#### Scenario: Enter on a row opens Entity Detail
- **WHEN** the user presses `Enter` on an entity row
- **THEN** the Entity Detail panel is displayed showing that entity's fields, relationships, and provenance

#### Scenario: Entity Detail shows all user-defined and system fields
- **WHEN** the Entity Detail panel is open
- **THEN** every field defined for that entity type, including system fields `id` and `is_available`, is visible

#### Scenario: Relationships show target entity type and navigable indicator
- **WHEN** the Entity Detail panel displays a reference field
- **THEN** the relationship row shows the target entity type name and a `→` navigation affordance

#### Scenario: Provenance section shows up to 10 most recent events
- **WHEN** the Entity Detail panel is open for an entity with more than 10 provenance events
- **THEN** only the 10 most recent events are shown, in reverse chronological order

#### Scenario: Esc returns to Entity Browser
- **WHEN** the user presses `Esc` in the Entity Detail panel
- **THEN** the Entity Browser is restored with the same page and filter state

---

### Requirement: Global keyboard shortcuts are active in all views
The system SHALL support the following global keyboard shortcuts regardless of which view is
active: `q` / `Ctrl+C` to quit, `?` to open a help/keybindings overlay, `/` or `Ctrl+P` to
activate the command palette, `Tab` to cycle focus between panels, `↑`/`↓` to navigate
lists, `Enter` to select, and `Esc` to go back or dismiss.

#### Scenario: q quits the TUI
- **WHEN** the user presses `q`
- **THEN** the TUI exits and the terminal is restored

#### Scenario: ? opens help overlay
- **WHEN** the user presses `?`
- **THEN** a modal overlay listing all keyboard shortcuts is displayed

#### Scenario: Esc dismisses help overlay
- **WHEN** the help overlay is displayed and the user presses `Esc`
- **THEN** the overlay is dismissed and the previous view is restored

---

### Requirement: Command palette supports fuzzy navigation
The system SHALL display a command palette modal when the user presses `/` or `Ctrl+P`. The
palette SHALL support fuzzy-search over: entity type names, recent entity IDs and field
values (cached from current session), and commands including "Go to schema", "Search",
"Refresh", and "Quit". Selecting an item SHALL navigate to the corresponding view or execute
the command.

#### Scenario: Command palette opens on / key
- **WHEN** the user presses `/`
- **THEN** the command palette modal is displayed with an empty search input

#### Scenario: Fuzzy typing narrows palette results
- **WHEN** the user types partial text in the command palette
- **THEN** matching entity types and commands are shown filtered by fuzzy match score

#### Scenario: Selecting an entity type navigates to its browser
- **WHEN** the user selects an entity type name in the command palette
- **THEN** the Entity Browser for that entity type is shown

#### Scenario: Esc dismisses command palette
- **WHEN** the command palette is open and the user presses `Esc`
- **THEN** the palette is dismissed without navigation

---

### Requirement: Status bar reflects current backend and connection target
The system SHALL display a status bar at the bottom of the TUI showing the active backend
mode (`sdk` or `rest`), the connection target (SQLite file path for SDK mode, base URL for
REST mode), and the total entity count for the currently selected entity type.

#### Scenario: Status bar shows sdk mode and db path
- **WHEN** the TUI is launched with `--backend sdk --db hippo.db`
- **THEN** the status bar displays `sdk | hippo.db`

#### Scenario: Status bar shows rest mode and URL
- **WHEN** the TUI is launched with `--backend rest --url http://host:8000`
- **THEN** the status bar displays `rest | http://host:8000`
