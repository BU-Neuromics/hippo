# TUI — Terminal User Interface

`hippo tui` launches an interactive, keyboard-driven terminal browser for a
Hippo instance. It can talk to a **local SQLite database directly through the
Python SDK**, or to a **remote `hippo serve` instance over the REST API** —
the interface is identical in both modes.

```bash
pip install 'hippo[tui]'
hippo tui
```

## Launching

### SDK mode (local database, default)

```bash
# Use config.json / data/hippo.db / hippo.db from the current directory
hippo tui

# Point at an explicit database and schema
hippo tui --db data/hippo.db --schema schemas/
```

| Option | Default | Description |
|--------|---------|-------------|
| `--backend`, `-b` | `sdk` | Backend mode: `sdk` or `rest` |
| `--db` | resolved | SQLite database path. Falls back to `config.json` in the cwd, then `data/hippo.db`, then `hippo.db` |
| `--schema` | resolved | LinkML schema file or directory. Falls back to `schemas/` in the cwd, then the bundled `hippo_core` schema |

### REST mode (remote `hippo serve`)

```bash
hippo serve &                       # on the host
hippo tui -b rest --url http://localhost:8000 --token $TOKEN
```

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | `http://127.0.0.1:8000` | Base URL of the `hippo serve` instance |
| `--token` | env / `dev-token` | Bearer token. Falls back to the `HIPPO_TUI_TOKEN` environment variable, then `dev-token` |

The status bar at the bottom always shows the backend mode, the connection
target, and a live connection indicator (green `●` when the backend is
reachable). Connection failures surface as error toasts and in the status bar.

## Screens

### Sidebar

Lists every entity type in the schema with live entity counts, plus entries
for the **Schema** explorer and the **Query** screen. `Enter` opens the
selection in the main panel.

### Entity browser

The main listing for one entity type:

- **Filter** (`f`): incremental text filter over the visible columns.
- **Pagination** (`←` / `→`): 20 entities per page.
- **`Enter`**: open the entity detail screen.
- **`n`** new entity, **`e`** edit, **`a`** availability, **`p`** provenance.

### Entity detail

Shows every field of one entity — system fields (`id`, `is_available`,
`version`) and computed temporal fields (`created_at`, `updated_at`,
`schema_version`, derived from the provenance log at read time) are rendered
dimmed above the user slots. The right panel lists outbound relationships
(`Enter` follows a link and chains detail screens; `Esc` unwinds) and a
preview of the most recent provenance events.

### Create / edit forms

`n` (create) and `e` (edit) open a modal form generated from the entity
type's LinkML schema:

- Enums and booleans render as dropdowns; everything else as typed inputs.
- Values are coerced to the slot's range (`integer`, `float`, `boolean`,
  comma-separated lists for multivalued slots) with inline error messages.
- Required slots are marked `*` and block saving when empty.
- Server-side validation failures are shown inline with the backend's detail
  message.
- `Ctrl+S` saves, `Esc` cancels.

### Availability transitions

Hippo has **no hard deletes**. `a` opens the availability dialog, which maps
the entity lifecycle statuses onto the `is_available` flag:

| Status | `is_available` |
|--------|----------------|
| `active` | `true` |
| `archived`, `superseded`, `deleted`, `distributed`, `removed` | `false` |

The chosen status (plus an optional free-text note) is recorded as the reason
in the provenance log.

### Provenance history

`p` opens the full append-only history for an entity, newest first, with a
payload inspector showing the diff recorded for the highlighted event.

### Schema explorer

Browses the LinkML schema: entity types, slot ranges, required/multivalued
flags, enum values, and relationships. `Enter` on a relationship jumps to the
target type.

### Query screen

`Ctrl+Q` opens the query screen:

- **Field filters** — `field=value, field2=value2` with AND/OR composition,
  backed by the SDK `QueryEngine`. Shown only when the backend supports
  structured filters (SDK mode); the REST API points you at full-text search
  instead.
- **Full-text search** — backed by the FTS index in both modes.

Results land in a table; `Enter` opens the detail screen.

## Keyboard shortcuts

Press `?` inside the TUI for this list.

| Key | Action |
|-----|--------|
| `q` / `Ctrl+C` | Quit |
| `?` | Help overlay |
| `/` or `Ctrl+P` | Command palette (jump to any entity type or command) |
| `Ctrl+Q` | Query screen |
| `Ctrl+T` | Toggle dark/light theme |
| `Tab` | Cycle focus between panels |
| `↑` / `↓` | Navigate lists |
| `Enter` | Select / drill in |
| `Esc` | Go back / dismiss |
| `r` | Refresh current view (also invalidates the schema cache) |
| `f` | Focus filter bar (entity browser) |
| `←` / `→` | Previous / next page |
| `n` | New entity |
| `e` | Edit entity |
| `a` | Availability transition |
| `p` | Provenance history |

## Architecture notes

The TUI is a pure consumer of the SDK ([design principles](design-principles.md)):
all views talk to a small `TUIBackend` protocol with two implementations —
`SDKBackend` (wraps `HippoClient`, dispatching sync calls off the event loop)
and `RESTBackend` (an `httpx` async client for `hippo serve`). Backends
declare capabilities (structured filters, FTS) and the UI gates features
accordingly, so both modes stay first-class. All data loading runs in
Textual workers; the UI never blocks.
