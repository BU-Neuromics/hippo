## Context

Hippo has a Python SDK (`HippoClient`), a REST API (`hippo serve`), and a CLI — but no interactive
interface for exploring data. Researchers need to browse entities, inspect schemas, and trace
provenance without writing code or making raw API calls.

The TUI will be a new optional module (`hippo[tui]`) layered on top of the existing SDK and REST
API. It must not change the Core SDK, storage adapters, or REST API — it is purely an additional
presentation layer.

Current constraints:
- Core SDK is the authority on business logic; the TUI must not duplicate it.
- SQLite is the only supported storage backend for v0.1; REST mode assumes a running `hippo serve`.
- The `SchemaConfig` and `HippoClient` APIs are already defined and stable for v0.1 purposes.
- Textual (the TUI framework) has its own async event loop which must coexist with sync SDK calls.

## Goals / Non-Goals

**Goals:**
- Provide a keyboard-driven terminal UI launched via `hippo tui`
- Support two backends: SDK-direct (default) and REST, switchable via `--backend` flag
- Abstract both backends behind a `TUIBackend` protocol so views are backend-agnostic
- Entity Browser view: paginated table, inline filter, entity detail with provenance and relationships
- Schema Explorer view: field table per entity type, relationship declarations
- Command palette (`/` or `Ctrl+P`) for fuzzy navigation across entity types and commands
- Global keyboard shortcuts (quit, help overlay, refresh, navigation)

**Non-Goals:**
- Write operations (create / edit / delete entities) — deferred to `tui-write-operations`
- Column configuration (`--columns` flag or per-entity-type config) — deferred to TUI v0.2
- Relationship traversal depth beyond immediate neighbors — deferred to implementation follow-on
- GraphQL backend support
- Changes to Core SDK, REST API, or storage adapters

## Decisions

### D1: Textual as the TUI framework

**Decision:** Use [Textual](https://textual.textualize.io/) (`>=0.50.0`) as the sole TUI library.

**Rationale:** Textual provides composable widgets (DataTable, ListView, Input), a reactive data
model, CSS-like styling, and a built-in `pilot` test harness for automation. Alternatives:

| Option | Reason rejected |
|---|---|
| `urwid` | Low-level; no composable widget system; requires significant boilerplate |
| `blessed` / `curses` | Even lower level; no layout engine; testing is painful |
| `rich` alone | Not interactive; no event loop or widget composition |
| `prompt_toolkit` | Good for line-based TUIs; not suited to panel/layout UIs |

Textual is the only library that satisfies layout, interactivity, and testability in a single
dependency.

**Trade-off:** Textual adds ~2 MB to the optional `[tui]` extras group and pulls in `rich`. This
is acceptable because it is strictly opt-in.

---

### D2: `TUIBackend` protocol instead of direct SDK calls in views

**Decision:** Define a `TUIBackend` protocol (Python structural subtyping via `typing.Protocol`)
that both `SDKBackend` and `RESTBackend` implement. Views call only `TUIBackend` methods.

```
TUIBackend (Protocol)
├── list_entity_types() → list[EntityTypeSummary]
├── list_entities(type, page, filter) → PagedResult
├── get_entity(type, id) → EntityDetail
├── get_schema() → SchemaView
└── get_provenance(type, id) → list[ProvenanceEvent]
```

**Rationale:** Decouples view logic from backend specifics. Any future backend (GraphQL, mock for
tests) can be added without touching views. Views are independently testable with a `MockBackend`.

**Alternatives considered:**
- Injecting `HippoClient` directly into views: simple but couples views to SDK; REST views would
  need a parallel code path.
- Separate view classes per backend: maximum coupling; duplicates all view logic.

---

### D3: SDK backend runs synchronous SDK calls in a thread pool

**Decision:** The `SDKBackend` wraps synchronous `HippoClient` calls using
`asyncio.to_thread()` (Python 3.9+) so they don't block Textual's async event loop.

**Rationale:** `HippoClient` methods are synchronous (SQLite I/O via SQLAlchemy). Textual runs on
`asyncio`. Blocking the event loop would freeze the UI during data fetches. `asyncio.to_thread()`
is the standard pattern for this; no additional thread pool management needed.

**Alternatives considered:**
- Making SDK methods async: requires invasive changes to core SDK; out of scope.
- `concurrent.futures.ThreadPoolExecutor` directly: more boilerplate than `asyncio.to_thread()`;
  no meaningful benefit.

---

### D4: REST backend uses `httpx` (async) with a `Bearer` token

**Decision:** The `RESTBackend` uses `httpx.AsyncClient` for non-blocking HTTP calls. Default URL
is `http://127.0.0.1:8000`; default token is `dev-token`. Both are overridable via CLI flags.

**Rationale:** `httpx` has a first-class async API that integrates naturally with Textual's event
loop. `requests` is sync-only and would require the same thread-wrapping as the SDK backend.

**Alternatives considered:**
- `aiohttp`: Heavier dependency; `httpx` is already the de-facto async HTTP client for modern
  Python and may already be present in the project.

---

### D5: Module structure under `src/hippo/tui/`

**Decision:** New `tui` subpackage with this layout:

```
src/hippo/tui/
├── __init__.py
├── app.py          # HippoTUIApp (Textual Application subclass)
├── backend/
│   ├── __init__.py
│   ├── protocol.py  # TUIBackend Protocol + data types
│   ├── sdk.py       # SDKBackend
│   └── rest.py      # RESTBackend
├── views/
│   ├── __init__.py
│   ├── entity_browser.py   # EntityBrowserView + EntityDetailPanel
│   └── schema_explorer.py  # SchemaExplorerView
└── widgets/
    ├── __init__.py
    ├── sidebar.py           # EntityTypeSidebar
    ├── status_bar.py        # StatusBar
    └── command_palette.py   # CommandPalette
```

**Rationale:** Separates concerns cleanly: app wiring, backend abstraction, views, and reusable
widgets. Mirrors Textual's own recommended project layout. Tests in `tests/tui/` can import each
layer independently.

---

### D6: `hippo tui` CLI entry point in existing `main.py`

**Decision:** Add `tui` as a Click command group in `src/hippo/cli/main.py`. Import of
`src/hippo/tui` is guarded behind a try/except that raises a clear error if Textual is not
installed.

```python
try:
    from hippo.tui.app import HippoTUIApp
except ImportError:
    raise click.ClickException("TUI requires 'pip install hippo[tui]'")
```

**Rationale:** Keeps the CLI entry point unified. Users see `hippo tui --help` without installing
the optional dependency; they only get the install error if they actually run it.

## Risks / Trade-offs

**[Risk] Textual API stability** → Textual has been evolving rapidly. Pin to `>=0.50.0,<1.0` and
add a `CHANGELOG` note to test on Textual upgrades. The `pilot` harness API is stable as of 0.50.

**[Risk] Blocking SQLite calls cause UI stuttering under large datasets** → Mitigated by D3
(thread pool). Additionally, entity browser pages are limited to 20 rows; schema reads are cached
after first load (schema rarely changes during a session).

**[Risk] REST backend auth token in shell history** → `--token` value is passed as a CLI flag and
will appear in `ps` output and shell history. Documented limitation for v0.1; a `HIPPO_TUI_TOKEN`
environment variable fallback will be added alongside the flag.

**[Risk] Textual's async loop vs. `asyncio.run()` conflicts if `HippoTUIApp` is embedded** →
TUI is designed to run as a top-level process via `hippo tui`; embedding is not supported.
Documented as a non-use-case.

**[Risk] Test environment lacks a terminal** → Textual's `pilot` harness runs headless, so CI
tests do not require a TTY. Integration with a real SQLite DB is handled via a temp-file fixture.

## Open Questions

**OQ1 (from proposal): Relationship navigation — replace view or side panel?**
Navigation decision deferred to implementation. Recommendation: replace main panel (simpler state
model); a `[←back]` breadcrumb allows return. Side panel adds layout complexity without clear
benefit for v0.1.

**OQ2 (from proposal): Column selection in Entity Browser**
Deferred to TUI v0.2. `SchemaConfig` already exposes field ordering; a future `--columns`
flag can read from there without architecture changes.

**OQ3: Schema caching strategy**
Schema data (`get_schema()`) should be cached for the lifetime of a TUI session since schemas do
not change at runtime. Cache invalidation on `r` (refresh) is sufficient. No persistent cache
needed.
