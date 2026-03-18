## 1. Project Setup

- [x] 1.1 Add `textual>=0.50.0,<1.0` and `httpx>=0.27.0` to the `[tui]` optional extras group in `pyproject.toml`
- [x] 1.2 Create the `src/hippo/tui/` subpackage directory with `__init__.py`
- [x] 1.3 Create `src/hippo/tui/backend/` subdirectory with `__init__.py`
- [x] 1.4 Create `src/hippo/tui/views/` subdirectory with `__init__.py`
- [x] 1.5 Create `src/hippo/tui/widgets/` subdirectory with `__init__.py`
- [x] 1.6 Create `tests/tui/` test directory with `__init__.py`

## 2. Backend Protocol and Data Types

- [x] 2.1 Define `EntityTypeSummary`, `PagedResult`, `EntityDetail`, `SchemaView`, and `ProvenanceEvent` dataclasses in `src/hippo/tui/backend/protocol.py`
- [x] 2.2 Define the `TUIBackend` `typing.Protocol` with async methods: `list_entity_types()`, `list_entities()`, `get_entity()`, `get_schema()`, `get_provenance()` in `protocol.py`
- [x] 2.3 Write unit tests in `tests/tui/test_protocol.py` verifying a `MockBackend` satisfies the protocol and data types carry expected fields

## 3. SDKBackend

- [x] 3.1 Implement `SDKBackend` in `src/hippo/tui/backend/sdk.py` instantiating `HippoClient` with `SQLiteAdapter`
- [x] 3.2 Implement `db_path` resolution: explicit argument takes precedence over `config.json`
- [x] 3.3 Wrap all synchronous `HippoClient` calls with `asyncio.to_thread()` in each `TUIBackend` method
- [x] 3.4 Write tests in `tests/tui/test_sdk_backend.py` verifying `db_path` resolution and that calls use `asyncio.to_thread()`

## 4. RESTBackend

- [x] 4.1 Implement `RESTBackend` in `src/hippo/tui/backend/rest.py` using `httpx.AsyncClient`
- [x] 4.2 Implement token resolution: `--token` flag > `HIPPO_TUI_TOKEN` env variable > `dev-token` default
- [x] 4.3 Add `Authorization: Bearer <token>` header to every request
- [x] 4.4 Implement graceful error handling: connection failures set a status bar error message without crashing
- [x] 4.5 Write tests in `tests/tui/test_rest_backend.py` verifying token precedence and connection failure handling

## 5. Backend Factory

- [x] 5.1 Implement `create_backend(mode, **kwargs) -> TUIBackend` factory in `src/hippo/tui/backend/__init__.py`
- [x] 5.2 Factory returns `SDKBackend` for `"sdk"`, `RESTBackend` for `"rest"`, raises `ValueError` for unknown modes
- [x] 5.3 Write tests in `tests/tui/test_backend_factory.py` covering all three cases

## 6. CLI Entry Point

- [x] 6.1 Add the `tui` Click command group to `src/hippo/cli/main.py` with `--backend`, `--url`, `--token`, and `--db` options
- [x] 6.2 Guard the `from hippo.tui.app import HippoTUIApp` import behind `try/except ImportError`; raise `click.ClickException("TUI requires 'pip install hippo[tui]'")` if Textual is not installed
- [x] 6.3 Wire the factory call: `create_backend(mode, ...)` → `HippoTUIApp(backend).run()`
- [x] 6.4 Write tests in `tests/tui/test_cli.py` verifying help text without Textual, install error message, and flag-to-backend wiring

## 7. Core TUI Application

- [x] 7.1 Create `HippoTUIApp` (Textual `App` subclass) in `src/hippo/tui/app.py` accepting a `TUIBackend` and holding a schema cache
- [x] 7.2 Define global keyboard bindings: `q`/`Ctrl+C` quit, `?` help overlay, `/`/`Ctrl+P` command palette, `Tab` cycle focus, `Esc` back/dismiss
- [x] 7.3 Implement schema cache: call `get_schema()` once on startup; invalidate and re-fetch on `r`
- [x] 7.4 Write a smoke test in `tests/tui/test_app.py` using Textual's `pilot` harness with a `MockBackend`

## 8. EntityTypeSidebar Widget

- [x] 8.1 Implement `EntityTypeSidebar` in `src/hippo/tui/widgets/sidebar.py` as a `ListView` populated from `list_entity_types()`
- [x] 8.2 Append a static "Schema Explorer" entry as the last item, always visible
- [x] 8.3 Emit a message on selection so `HippoTUIApp` can swap the main panel view
- [x] 8.4 Write tests verifying "Schema Explorer" is last and selection messages fire correctly

## 9. StatusBar Widget

- [x] 9.1 Implement `StatusBar` in `src/hippo/tui/widgets/status_bar.py` showing backend mode and connection target
- [x] 9.2 Add reactive property for current entity count, updated whenever a new entity type is selected
- [x] 9.3 Add an error display mode for REST backend connection failures
- [x] 9.4 Write tests verifying SDK path display and REST URL display formats

## 10. EntityBrowserView

- [x] 10.1 Implement `EntityBrowserView` in `src/hippo/tui/views/entity_browser.py` with a `DataTable` (20 rows per page)
- [x] 10.2 Display the first 4 user-defined fields + `created_at` as DataTable columns
- [x] 10.3 Implement page navigation: `→` next page, `←` previous page; disable at boundaries; show page indicator
- [x] 10.4 Implement filter bar: press `f` to focus, live-update DataTable as user types, reset to page 1 on filter change, restore full list on clear
- [x] 10.5 Implement `r` refresh: re-fetch current page from backend
- [x] 10.6 Write tests using Textual `pilot` verifying pagination, filter, and refresh behaviors

## 11. EntityDetailPanel

- [x] 11.1 Implement `EntityDetailPanel` in `src/hippo/tui/views/entity_browser.py` (or a separate file) showing fields (left), relationships (right top), provenance (right bottom)
- [x] 11.2 Open panel on `Enter` keypress on a DataTable row; replace main panel content
- [x] 11.3 Show all user-defined and system fields (`id`, `is_available`)
- [x] 11.4 Show relationships with `→ TargetType` navigation affordance
- [x] 11.5 Show up to 10 most recent provenance events in reverse chronological order
- [x] 11.6 Return to Entity Browser (restoring page and filter state) on `Esc` or `[←back]`
- [x] 11.7 Write tests verifying field display, relationship rows, provenance truncation, and back-navigation

## 12. SchemaExplorerView

- [x] 12.1 Implement `SchemaExplorerView` in `src/hippo/tui/views/schema_explorer.py` with a left panel (entity type list) and right panel (field table)
- [x] 12.2 Left panel: list entity type name + user-defined field count; keyboard-navigable with `↑`/`↓`
- [x] 12.3 Right panel: field table rows showing field name, type, required (✓/-), indexed (✓/-); reference fields show `→ TargetType`; make table scrollable
- [x] 12.4 Add a relationships section showing `SourceType ──<rel-name>──▶ TargetType` for each relationship in `SchemaView`; render empty section when none exist
- [x] 12.5 Use cached schema data from `HippoTUIApp`; do not call `get_schema()` again on entity type navigation
- [x] 12.6 Invalidate cache and re-render on `r` keypress
- [x] 12.7 Write tests verifying field table content, relationship rendering, and cache behavior

## 13. CommandPalette Widget

- [x] 13.1 Implement `CommandPalette` modal in `src/hippo/tui/widgets/command_palette.py` activated by `/` or `Ctrl+P`
- [x] 13.2 Populate with entity type names (from cached schema) and built-in commands: "Go to schema", "Search", "Refresh", "Quit"
- [x] 13.3 Implement fuzzy-match filtering as user types; update results list in real time
- [x] 13.4 Navigate to Entity Browser for selected entity type; execute command for built-in commands
- [x] 13.5 Dismiss without action on `Esc`
- [x] 13.6 Write tests verifying palette opens, fuzzy filtering narrows results, entity type navigation, and Esc dismissal

## 14. Help Overlay Widget

- [x] 14.1 Implement help/keybindings modal overlay in `src/hippo/tui/widgets/` (or inline in `app.py`)
- [x] 14.2 List all global keyboard shortcuts and their descriptions
- [x] 14.3 Dismiss on `Esc`
- [x] 14.4 Write a test verifying the overlay opens on `?` and closes on `Esc`

## 15. Integration and Final Verification

- [x] 15.1 Run the full test suite (`pytest tests/tui/`) and fix any failures
- [x] 15.2 Verify `pip install hippo` does not install `textual` or `httpx`
- [x] 15.3 Verify `pip install hippo[tui]` installs both at compatible versions
- [ ] 15.4 Manually smoke-test `hippo tui` in SDK mode against a local SQLite database
- [ ] 15.5 Manually smoke-test `hippo tui --backend rest` against a running `hippo serve` instance
- [x] 15.6 Confirm `hippo tui --help` works without Textual installed and shows the install error when Textual is absent
