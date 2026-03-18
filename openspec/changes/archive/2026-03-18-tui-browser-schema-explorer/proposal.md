# TUI: Entity Browser and Schema Explorer

## Why

Interacting with Hippo through the REST API or Python SDK requires technical knowledge and
is friction-heavy for researchers who want to explore their data without writing code. A
terminal user interface (TUI) provides an accessible, keyboard-driven way to browse entities,
inspect schemas, and traverse relationships — without requiring a running server or Python
fluency.

## What Changes

### New CLI subcommand: `hippo tui`

```bash
hippo tui                          # auto-detect local config.json / SQLite
hippo tui --backend sdk            # explicit SDK-direct mode (default)
hippo tui --backend rest           # REST API mode (requires server running)
hippo tui --url http://host:8000   # REST mode with explicit server URL
hippo tui --token mytoken          # Bearer token for REST mode
hippo tui --db ./path/to/hippo.db  # SDK mode with explicit db path
```

### Backend selection

Two backend modes, chosen via `--backend` flag:

- **`sdk` (default)** — instantiates `HippoClient` with `SQLiteAdapter` directly. No server
  needed. Reads `db_path` from `config.json` or `--db` flag.
- **`rest`** — thin REST client wrapping `httpx` (or `requests`). Connects to a running
  `hippo serve` instance. Requires `--url` (default: `http://127.0.0.1:8000`) and optionally
  `--token` (default: `dev-token`).

Both backends implement a common `TUIBackend` protocol so views are backend-agnostic.

### TUI layout

Built with [Textual](https://textual.textualize.io/). Requires `pip install hippo[tui]`
(Textual added as optional dependency group).

```
┌─ Hippo TUI ─────────────────────────────────────── q:quit ?:help ─┐
│ ┌─ Sidebar ──────────┐ ┌─ Main Panel ──────────────────────────┐  │
│ │ ENTITY TYPES        │ │                                       │  │
│ │ > Donor       (42)  │ │   [content of selected view]          │  │
│ │   Sample     (186)  │ │                                       │  │
│ │   DataFile   (891)  │ │                                       │  │
│ │                     │ │                                       │  │
│ │ SCHEMA              │ │                                       │  │
│ │   Schema Explorer   │ │                                       │  │
│ └─────────────────────┘ └───────────────────────────────────────┘  │
│ ┌─ Status bar ────────────────────────────── sdk │ hippo.db ──────┐ │
└────────────────────────────────────────────────────────────────────┘
```

**Sidebar** — always visible. Lists entity types with counts. Static "Schema Explorer" entry
at the bottom. Keyboard navigable (↑↓ arrows, Enter to select).

**Main panel** — context-sensitive content for the selected sidebar item:
- Entity type selected → Entity Browser view
- Schema Explorer selected → Schema Explorer view

**Status bar** — shows active backend (`sdk` or `rest`), connection target, entity count.

**Command palette** — activated with `/` or `Ctrl+P`. Fuzzy-search over:
- Entity type names
- Entity IDs and field values (recent/cached)
- Commands: "Go to schema", "Search", "Refresh", "Quit"

### View 1: Entity Browser

Activated when an entity type is selected in the sidebar.

```
┌─ Sample (186 entities) ─────────────────────────── /search ─────┐
│ ID              │ external_id      │ tissue_type │ created_at    │
│─────────────────┼──────────────────┼─────────────┼───────────────│
│ 3f2a...         │ SMPL-AD-001-HC   │ Brain       │ 2026-03-01    │
│ 8b1c...         │ SMPL-AD-002-FC   │ Brain       │ 2026-03-01    │
│ ...             │ ...              │ ...         │ ...           │
├──────────────────────────────────────────────────────────────────┤
│ Page 1 of 19  [←][→]          Filter: _                         │
└──────────────────────────────────────────────────────────────────┘
```

- **DataTable** showing paginated entities (20 per page)
- Columns: first 4 user-defined fields + `created_at` (configurable later)
- Inline filter bar (type to filter, uses FTS if available, falls back to field match)
- `Enter` on a row → Entity Detail panel (slide-in or replace main panel)
- `r` → refresh, `f` → focus filter, `←/→` → page navigation

**Entity Detail panel** (activated from browser row):
```
┌─ Sample: SMPL-AD-001-HC ─────────────────────────── [←back] ────┐
│ FIELDS                    │ RELATIONSHIPS                        │
│ id:           3f2a...     │ donated_by: Donor AD-001 →           │
│ external_id:  SMPL-AD-001 │ generated:  DataFile x3 →           │
│ tissue_type:  Brain       │                                      │
│ brain_region: Hippocampus │ PROVENANCE                           │
│ collection_d: 2026-03-01  │ ● CREATE  2026-03-01T10:30Z          │
│ rin_score:    8.4         │ ● UPDATE  2026-03-01T14:22Z          │
│ created_at:   2026-03-01  │   brain_region: Temporal → Hippo..  │
│ updated_at:   2026-03-01  │                                      │
└───────────────────────────┴──────────────────────────────────────┘
```

- Left: all entity fields
- Right top: relationships (click to navigate to related entity)
- Right bottom: provenance history (most recent 10 events)
- `Esc` or `←back` → return to entity browser

### View 2: Schema Explorer

Activated from "Schema Explorer" sidebar entry.

```
┌─ Schema Explorer ───────────────────────────────────────────────┐
│ ┌─ Entity Types ──────────┐ ┌─ Fields: Sample ────────────────┐ │
│ │ Donor           3 fields│ │ Field         Type    Req  Idx  │ │
│ │ > Sample        8 fields│ │ external_id   string  ✓    ✓   │ │
│ │   DataFile      7 fields│ │ donor         ref     ✓    ✓   │ │
│ │   WorkflowRun   5 fields│ │   → Donor                      │ │
│ └─────────────────────────┘ │ tissue_type   string  ✓    ✓   │ │
│                             │ brain_region  string  -    ✓   │ │
│ RELATIONSHIPS               │ collection_d  date    -    -   │ │
│ Donor ──donated──▶ Sample   │ rin_score     float   -    -   │ │
│ Sample ─generated▶ DataFile │ created_at    system  -    -   │ │
│                             └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

- Left panel: entity type list with field counts
- Right panel: field table for selected entity type — name, type, required, indexed
- Reference fields show the target entity type with `→` indicator (navigable)
- Bottom section: relationship declarations (from schema)
- Read-only; no editing

### Keyboard shortcuts (global)

| Key | Action |
|---|---|
| `q` / `Ctrl+C` | Quit |
| `?` | Help / keybindings overlay |
| `/` or `Ctrl+P` | Command palette |
| `Tab` | Move focus between panels |
| `↑↓` | Navigate lists |
| `Enter` | Select / drill in |
| `Esc` | Back / dismiss |
| `r` | Refresh current view |

## Capabilities

### New Capabilities
- `tui-browser` — entity browser view with pagination, filter, detail panel, provenance, relationships
- `tui-schema-explorer` — schema explorer view with field table and relationship graph
- `tui-backend` — TUIBackend protocol, SDK backend, REST backend, backend factory

### Modified Capabilities
- `hippo-cli` — new `hippo tui` subcommand; Textual added as optional `[tui]` dependency

## Open Questions

### OQ1: Relationship traversal depth in TUI
The Entity Detail panel shows immediate relationships. Should clicking a relationship
navigate to the related entity (replacing current view) or open a side panel? Deferred to
implementation.

### OQ2: Column selection in Entity Browser
Currently hardcoded to first 4 fields + `created_at`. A future `hippo tui --columns` flag
or per-entity-type config could allow customization. Deferred to v0.2 of TUI.

### OQ3: Write operations in TUI
Create / edit / delete entity forms are explicitly out of scope for this change. Deferred
to a follow-on `tui-write-operations` change.

## Impact

- New module: `src/hippo/tui/` (app, views, backends, widgets)
- New optional dependency: `textual>=0.50.0` in `[tui]` extras group in `pyproject.toml`
- New optional dependency: `httpx>=0.27.0` in `[tui]` extras group (REST backend)
- New CLI command: `hippo tui` in `src/hippo/cli/main.py`
- New tests: `tests/tui/` using Textual's `pilot` test harness
- No changes to core SDK, storage adapter, or REST API
