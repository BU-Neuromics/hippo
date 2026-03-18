"""HippoTUIApp — Textual application root for the Hippo TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from hippo.tui.backend.protocol import SchemaView, TUIBackend
from hippo.tui.widgets.sidebar import EntityTypeSidebar
from hippo.tui.widgets.status_bar import StatusBar
from hippo.tui.widgets.command_palette import HippoCommandPalette
from hippo.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    pass


class HippoTUIApp(App):
    """Hippo Terminal User Interface.

    Provides a keyboard-driven browser for entities, schemas, and provenance.

    Args:
        backend: The TUIBackend implementation (SDK or REST).
    """

    CSS = """
    #sidebar {
        width: 24;
        min-width: 18;
    }
    #main-panel {
        width: 1fr;
    }
    #status-bar {
        height: 1;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("question_mark", "help_overlay", "Help", show=True, key_display="?"),
        Binding("slash", "command_palette", "Palette", show=True, key_display="/"),
        Binding("ctrl+p", "command_palette", "Palette", show=False),
        Binding("tab", "focus_next", "Focus next", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "escape", "Back", show=False),
    ]

    def __init__(self, backend: TUIBackend, **kwargs) -> None:
        super().__init__(**kwargs)
        self._backend = backend
        self._schema_cache: SchemaView | None = None

    # ------------------------------------------------------------------
    # Schema cache
    # ------------------------------------------------------------------

    @property
    def backend(self) -> TUIBackend:
        return self._backend

    @property
    def schema_cache(self) -> SchemaView | None:
        return self._schema_cache

    @schema_cache.setter
    def schema_cache(self, value: SchemaView | None) -> None:
        self._schema_cache = value

    async def get_or_fetch_schema(self) -> SchemaView:
        """Return cached schema or fetch from backend and cache the result."""
        if self._schema_cache is None:
            self._schema_cache = await self._backend.get_schema()
        return self._schema_cache

    async def invalidate_schema_cache(self) -> SchemaView:
        """Invalidate the schema cache and re-fetch from backend."""
        self._schema_cache = None
        return await self.get_or_fetch_schema()

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            yield EntityTypeSidebar(id="sidebar")
            with Vertical(id="main-panel"):
                pass
        yield StatusBar(id="status-bar")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_mount(self) -> None:
        """Fetch schema and populate sidebar on startup."""
        await self.get_or_fetch_schema()
        sidebar = self.query_one(EntityTypeSidebar)
        await sidebar.load_entity_types(self._backend)

        # Initialise status bar
        status_bar = self.query_one(StatusBar)
        if hasattr(self._backend, "_db_path"):
            status_bar.set_backend("sdk", str(self._backend._db_path))
        elif hasattr(self._backend, "_url"):
            status_bar.set_backend("rest", self._backend._url)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_help_overlay(self) -> None:
        """Show the help/keybindings overlay."""
        await self.push_screen(HelpOverlay())

    async def action_command_palette(self) -> None:
        """Open the command palette."""
        schema = await self.get_or_fetch_schema()
        entity_type_names = [et.name for et in schema.entity_types]
        await self.push_screen(HippoCommandPalette(entity_type_names=entity_type_names))

    async def action_refresh(self) -> None:
        """Invalidate schema cache and refresh the current view."""
        await self.invalidate_schema_cache()
        sidebar = self.query_one(EntityTypeSidebar)
        await sidebar.load_entity_types(self._backend)
        # Notify the active view if it supports refresh
        from textual.screen import Screen

        active = self.screen
        if hasattr(active, "action_refresh"):
            await active.action_refresh()

    async def action_escape(self) -> None:
        """Go back / dismiss overlays."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def on_entity_type_sidebar_entity_type_selected(
        self, message: "EntityTypeSidebar.EntityTypeSelected"
    ) -> None:
        """Swap the main panel to an EntityBrowserView for the selected type."""
        from hippo.tui.views.entity_browser import EntityBrowserView

        main_panel = self.query_one("#main-panel")
        await main_panel.remove_children()
        view = EntityBrowserView(
            entity_type=message.entity_type,
            backend=self._backend,
        )
        await main_panel.mount(view)

        # Update status bar entity count
        status_bar = self.query_one(StatusBar)
        status_bar.entity_count = message.entity_count

    async def on_entity_type_sidebar_schema_explorer_selected(
        self, message: "EntityTypeSidebar.SchemaExplorerSelected"
    ) -> None:
        """Swap the main panel to SchemaExplorerView."""
        from hippo.tui.views.schema_explorer import SchemaExplorerView

        schema = await self.get_or_fetch_schema()
        main_panel = self.query_one("#main-panel")
        await main_panel.remove_children()
        view = SchemaExplorerView(schema=schema, app_ref=self)
        await main_panel.mount(view)
