"""EntityBrowserView and EntityDetailPanel — entity table and detail drill-down."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Label, ListItem, ListView, Static

from hippo.tui.backend.protocol import EntityDetail, PagedResult, TUIBackend

_PAGE_SIZE = 20
_MAX_COLS = 4  # first 4 user-defined fields


# ---------------------------------------------------------------------------
# EntityBrowserView
# ---------------------------------------------------------------------------


class EntityBrowserView(Widget):
    """Paginated entity browser with inline filter.

    Args:
        entity_type: The entity type to browse.
        backend: The TUIBackend to fetch data from.
    """

    BINDINGS = [
        Binding("right", "next_page", "Next page", show=True),
        Binding("left", "prev_page", "Prev page", show=True),
        Binding("f", "focus_filter", "Filter", show=True),
        Binding("r", "refresh_view", "Refresh", show=True),
        Binding("enter", "open_detail", "Detail", show=True),
    ]

    _current_page: reactive[int] = reactive(1)
    _total_pages: reactive[int] = reactive(1)
    _filter_text: reactive[str] = reactive("")

    def __init__(self, entity_type: str, backend: TUIBackend, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entity_type = entity_type
        self._backend = backend
        self._columns: list[str] = []
        self._rows: list[dict[str, Any]] = []
        self._saved_page: int = 1
        self._saved_filter: str = ""

    def compose(self) -> ComposeResult:
        yield Label(f"{self._entity_type}", id="browser-title")
        yield DataTable(id="entity-table")
        with Horizontal(id="browser-footer"):
            yield Label("Page 1 of 1", id="page-indicator")
            yield Input(placeholder="Filter… (press f)", id="filter-input")

    async def on_mount(self) -> None:
        await self._load_page()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_page(self) -> None:
        """Fetch the current page from the backend and refresh the DataTable."""
        result: PagedResult = await self._backend.list_entities(
            entity_type=self._entity_type,
            page=self._current_page,
            filter_text=self._filter_text,
        )

        self._rows = result.items
        self._total_pages = max(1, result.total_pages)
        # Clamp page
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages

        await self._refresh_table(result)
        self._update_page_indicator()

    async def _refresh_table(self, result: PagedResult) -> None:
        """Rebuild DataTable columns and rows from *result*."""
        table = self.query_one(DataTable)
        table.clear(columns=True)

        if not result.items:
            table.add_column("(no entities)")
            return

        # Determine columns: first 4 user-defined fields + created_at
        sample = result.items[0]
        data = sample.get("data", {})
        user_fields = list(data.keys())[:_MAX_COLS]
        cols = ["id"] + user_fields + ["created_at"]
        self._columns = cols

        for col in cols:
            table.add_column(col, key=col)

        for item in result.items:
            data = item.get("data", {})
            row = []
            for col in cols:
                if col == "id":
                    row.append(str(item.get("id", ""))[:12] + "…")
                elif col == "created_at":
                    val = item.get("created_at", "")
                    row.append(str(val)[:10] if val else "")
                else:
                    row.append(str(data.get(col, "")))
            table.add_row(*row, key=item.get("id", ""))

    def _update_page_indicator(self) -> None:
        try:
            label = self.query_one("#page-indicator", Label)
            label.update(f"Page {self._current_page} of {self._total_pages}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_next_page(self) -> None:
        if self._current_page < self._total_pages:
            self._current_page += 1
            await self._load_page()

    async def action_prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            await self._load_page()

    def action_focus_filter(self) -> None:
        try:
            self.query_one("#filter-input", Input).focus()
        except Exception:
            pass

    async def action_refresh_view(self) -> None:
        await self._load_page()

    async def action_open_detail(self) -> None:
        """Open Entity Detail panel for the highlighted row."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        try:
            row_key = table.get_row_at(table.cursor_row)
        except Exception:
            return
        # Find entity_id from rows
        if table.cursor_row < len(self._rows):
            entity_id = self._rows[table.cursor_row].get("id", "")
            if entity_id:
                await self._open_entity_detail(entity_id)

    async def _open_entity_detail(self, entity_id: str) -> None:
        """Replace self with EntityDetailPanel."""
        entity = await self._backend.get_entity(self._entity_type, entity_id)
        provenance = await self._backend.get_provenance(self._entity_type, entity_id)

        # Stash state for back-navigation
        self._saved_page = self._current_page
        self._saved_filter = self._filter_text

        parent = self.parent
        if parent is None:
            return

        panel = EntityDetailPanel(
            entity=entity,
            provenance=provenance,
            on_back=self._on_back_from_detail,
        )
        await self.remove()
        await parent.mount(panel)

    async def _on_back_from_detail(self, panel: "EntityDetailPanel") -> None:
        """Restore browser when user presses Esc/back from detail panel."""
        parent = panel.parent
        if parent is None:
            return

        # Restore page/filter state
        self._current_page = self._saved_page
        self._filter_text = self._saved_filter
        await panel.remove()
        await parent.mount(self)
        await self._load_page()

    # ------------------------------------------------------------------
    # Input events
    # ------------------------------------------------------------------

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Live-update table as filter text changes."""
        if event.input.id == "filter-input":
            self._filter_text = event.value
            self._current_page = 1  # Reset to page 1 on filter change
            await self._load_page()


# ---------------------------------------------------------------------------
# EntityDetailPanel
# ---------------------------------------------------------------------------


class EntityDetailPanel(Widget):
    """Detail view for a single entity — fields, relationships, provenance.

    Args:
        entity: The ``EntityDetail`` to display.
        provenance: Provenance events (up to 10, newest first).
        on_back: Async callback invoked when the user navigates back.
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
    ]

    def __init__(
        self,
        entity: EntityDetail,
        provenance: list,
        on_back=None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._entity = entity
        self._provenance = provenance[:10]
        self._on_back = on_back

    def compose(self) -> ComposeResult:
        title = f"{self._entity.entity_type}: {self._entity.id}"
        yield Label(f"[←back]  {title}", id="detail-title")

        with Horizontal(id="detail-columns"):
            # Left: fields
            with Vertical(id="fields-panel"):
                yield Label("FIELDS", id="fields-header")
                for name, value in self._entity.fields.items():
                    yield Label(f"{name}: {value}", classes="field-row")

            # Right: relationships + provenance
            with Vertical(id="right-panel"):
                yield Label("RELATIONSHIPS", id="rel-header")
                if self._entity.relationships:
                    for rel in self._entity.relationships:
                        yield Label(
                            f"{rel.relationship_name}: {rel.target_type} {rel.target_id[:8]}… →",
                            classes="rel-row",
                        )
                else:
                    yield Label("(none)", classes="rel-row")

                yield Label("PROVENANCE", id="prov-header")
                if self._provenance:
                    for ev in self._provenance:
                        ts = ev.timestamp[:19] if ev.timestamp else ""
                        yield Label(
                            f"● {ev.event_type}  {ts}",
                            classes="prov-row",
                        )
                else:
                    yield Label("(no provenance)", classes="prov-row")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_go_back(self) -> None:
        """Return to Entity Browser."""
        if self._on_back:
            await self._on_back(self)

    async def on_label_clicked(self, event) -> None:
        """Handle click on the [←back] label."""
        label = event.widget
        if label.id == "detail-title":
            await self.action_go_back()
