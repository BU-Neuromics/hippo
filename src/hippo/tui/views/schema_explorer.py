"""SchemaExplorerView — read-only view of entity types, fields, and relationships."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, ListItem, ListView

from hippo.tui.backend.protocol import EntityTypeSchema, SchemaView

if TYPE_CHECKING:
    pass


class SchemaExplorerView(Widget):
    """Read-only schema explorer with entity type list and field table.

    Args:
        schema: Cached ``SchemaView`` from ``HippoTUIApp``.
        app_ref: Reference to the parent ``HippoTUIApp`` for cache invalidation.
    """

    BINDINGS = [
        Binding("r", "refresh_schema", "Refresh", show=True),
    ]

    def __init__(self, schema: SchemaView, app_ref: Any = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._schema = schema
        self._app_ref = app_ref
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="schema-main"):
            # Left panel: entity type list
            with Vertical(id="schema-left"):
                yield Label("Entity Types", id="schema-left-header")
                yield ListView(id="entity-type-list")

            # Right panel: field table
            with Vertical(id="schema-right"):
                yield Label("Fields", id="schema-right-header")
                yield DataTable(id="field-table")
                yield Label("Relationships", id="rel-section-header")
                yield ListView(id="rel-list")

    async def on_mount(self) -> None:
        """Populate the entity type list on mount."""
        await self._populate_entity_list()
        if self._schema.entity_types:
            await self._show_entity_type(self._schema.entity_types[0])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _populate_entity_list(self) -> None:
        lv = self.query_one("#entity-type-list", ListView)
        await lv.clear()
        for et in self._schema.entity_types:
            field_count = len(et.fields)
            label_text = f"{et.name}   {field_count} fields"
            await lv.append(
                ListItem(
                    Label(label_text),
                    id=f"et-{et.name}",
                )
            )

    async def _show_entity_type(self, entity_schema: EntityTypeSchema) -> None:
        """Populate the right panel with fields for *entity_schema*."""
        # Update header
        try:
            header = self.query_one("#schema-right-header", Label)
            header.update(f"Fields: {entity_schema.name}")
        except Exception:
            pass

        # Rebuild field table
        table = self.query_one("#field-table", DataTable)
        table.clear(columns=True)
        table.add_column("Field", key="field", width=20)
        table.add_column("Type", key="type", width=10)
        table.add_column("Req", key="req", width=5)
        table.add_column("Idx", key="idx", width=5)

        for field in entity_schema.fields:
            field_type = field.field_type
            if field.ref_target:
                field_type = f"ref → {field.ref_target}"
            table.add_row(
                field.name,
                field_type,
                "✓" if field.required else "-",
                "✓" if field.indexed else "-",
            )

        # Update relationship list
        await self._populate_relationships()

    async def _populate_relationships(self) -> None:
        lv = self.query_one("#rel-list", ListView)
        await lv.clear()

        if not self._schema.relationships:
            await lv.append(ListItem(Label("(no relationships defined)")))
            return

        for rel in self._schema.relationships:
            text = f"{rel.source_type} ──{rel.relationship_name}──▶ {rel.target_type}"
            await lv.append(ListItem(Label(text)))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Update field table when user selects a different entity type."""
        if event.list_view.id != "entity-type-list":
            return
        item = event.item
        et_name = item.id.removeprefix("et-") if item.id else None
        if et_name:
            for et in self._schema.entity_types:
                if et.name == et_name:
                    await self._show_entity_type(et)
                    break

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_refresh_schema(self) -> None:
        """Invalidate schema cache, re-fetch, and re-render."""
        if self._app_ref is not None:
            self._schema = await self._app_ref.invalidate_schema_cache()
        await self._populate_entity_list()
        if self._schema.entity_types:
            await self._show_entity_type(self._schema.entity_types[0])
