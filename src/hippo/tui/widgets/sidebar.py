"""EntityTypeSidebar widget — lists entity types and a Schema Explorer entry."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import ListItem, ListView, Label

from hippo.tui.backend.protocol import TUIBackend

_SCHEMA_EXPLORER_LABEL = "Schema Explorer"


class EntityTypeSidebar(ListView):
    """A ``ListView`` sidebar that shows entity types and a Schema Explorer entry.

    Emits:
        EntityTypeSelected — when the user selects an entity type.
        SchemaExplorerSelected — when the user selects the Schema Explorer entry.
    """

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    class EntityTypeSelected(Message):
        """Fired when an entity type is selected."""

        def __init__(self, entity_type: str, entity_count: int = 0) -> None:
            super().__init__()
            self.entity_type = entity_type
            self.entity_count = entity_count

    class SchemaExplorerSelected(Message):
        """Fired when the Schema Explorer entry is selected."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        # Items are populated dynamically via load_entity_types()
        yield ListItem(Label(_SCHEMA_EXPLORER_LABEL), id="schema-explorer-item")

    async def load_entity_types(self, backend: TUIBackend) -> None:
        """Fetch entity types from *backend* and populate the list.

        The "Schema Explorer" entry is always appended last.
        """
        summaries = await backend.list_entity_types()

        # Remove all existing items except the Schema Explorer entry
        for item in list(self.query(ListItem)):
            if item.id != "schema-explorer-item":
                await item.remove()

        # Insert entity type items before the Schema Explorer entry
        schema_item = self.query_one("#schema-explorer-item")

        for summary in summaries:
            label_text = f"{summary.name}  ({summary.count})"
            new_item = ListItem(
                Label(label_text),
                id=f"entity-type-{summary.name}",
            )
            # Store count as an attribute for later use
            new_item._entity_type = summary.name  # type: ignore[attr-defined]
            new_item._entity_count = summary.count  # type: ignore[attr-defined]
            await self.mount(new_item, before=schema_item)

        # Move schema explorer to end (it's already there from compose but
        # we need to ensure it stays at the bottom after dynamic inserts)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection — determine which item was selected and emit message."""
        item = event.item
        if item.id == "schema-explorer-item":
            self.post_message(self.SchemaExplorerSelected())
        elif item.id and item.id.startswith("entity-type-"):
            entity_type = getattr(
                item, "_entity_type", item.id.removeprefix("entity-type-")
            )
            entity_count = getattr(item, "_entity_count", 0)
            self.post_message(self.EntityTypeSelected(entity_type, entity_count))
