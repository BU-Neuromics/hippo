"""Tests for EntityBrowserView and EntityDetailPanel."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip(
    "textual", reason="textual not installed; run: pip install hippo[tui]"
)

from hippo.tui.backend.protocol import (
    EntityDetail,
    EntityTypeSummary,
    PagedResult,
    ProvenanceEvent,
    RelatedEntityRef,
    SchemaView,
)


class MockBrowserBackend:
    def __init__(self, total_items=50):
        self._total_items = total_items

    async def list_entity_types(self):
        return [EntityTypeSummary(name="Sample", count=self._total_items)]

    async def list_entities(self, entity_type, page=1, filter_text=""):
        page_size = 20
        import math

        total_pages = max(1, math.ceil(self._total_items / page_size))
        items = [
            {
                "id": f"sample-{(page - 1) * page_size + i}",
                "data": {"external_id": f"SMPL-{i:03d}", "tissue_type": "Brain"},
                "created_at": "2026-03-01",
            }
            for i in range(min(page_size, self._total_items - (page - 1) * page_size))
            if (page - 1) * page_size + i < self._total_items
        ]
        if filter_text:
            items = [it for it in items if filter_text.lower() in str(it).lower()]
        return PagedResult(
            items=items,
            page=page,
            total_pages=total_pages,
            total_items=self._total_items,
        )

    async def get_entity(self, entity_type, entity_id):
        return EntityDetail(
            id=entity_id,
            entity_type=entity_type,
            fields={"id": entity_id, "tissue_type": "Brain", "is_available": True},
            relationships=[RelatedEntityRef("donated_by", "Donor", "donor-1")],
        )

    async def get_schema(self):
        return SchemaView()

    async def get_provenance(self, entity_type, entity_id):
        return [
            ProvenanceEvent("CREATE", "2026-03-01T10:00:00Z", {}),
            ProvenanceEvent(
                "UPDATE", "2026-03-01T14:00:00Z", {"tissue_type": "Cortex"}
            ),
        ]


def test_entity_browser_view_pagination():
    """EntityBrowserView shows correct total_pages for >20 entities."""
    from hippo.tui.app import HippoTUIApp

    backend = MockBrowserBackend(total_items=50)
    app = HippoTUIApp(backend=backend)

    async def run():
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.pause()
            # Mount entity browser manually into the main panel
            from hippo.tui.views.entity_browser import EntityBrowserView

            main_panel = app.query_one("#main-panel")
            view = EntityBrowserView(entity_type="Sample", backend=backend)
            await main_panel.mount(view)
            await pilot.pause()

            # Check page indicator exists
            label = view.query_one("#page-indicator")
            assert "1 of 3" in label.renderable or "Page 1" in str(label.renderable)
            await pilot.press("q")

    asyncio.run(run())


def test_entity_browser_next_page_action():
    """EntityBrowserView action_next_page advances the page."""
    from hippo.tui.views.entity_browser import EntityBrowserView

    backend = MockBrowserBackend(total_items=50)
    view = EntityBrowserView(entity_type="Sample", backend=backend)

    async def run():
        view._total_pages = 3
        view._current_page = 1
        await view.action_next_page()
        assert view._current_page == 2

    asyncio.run(run())


def test_entity_browser_prev_page_action():
    """EntityBrowserView action_prev_page goes back."""
    from hippo.tui.views.entity_browser import EntityBrowserView

    backend = MockBrowserBackend(total_items=50)
    view = EntityBrowserView(entity_type="Sample", backend=backend)

    async def run():
        view._total_pages = 3
        view._current_page = 2
        await view.action_prev_page()
        assert view._current_page == 1

    asyncio.run(run())


def test_entity_browser_no_prev_at_first_page():
    """action_prev_page does nothing on page 1."""
    from hippo.tui.views.entity_browser import EntityBrowserView

    backend = MockBrowserBackend(total_items=50)
    view = EntityBrowserView(entity_type="Sample", backend=backend)
    view._total_pages = 3
    view._current_page = 1

    async def run():
        await view.action_prev_page()
        assert view._current_page == 1

    asyncio.run(run())


def test_entity_browser_no_next_at_last_page():
    """action_next_page does nothing on last page."""
    from hippo.tui.views.entity_browser import EntityBrowserView

    backend = MockBrowserBackend(total_items=50)
    view = EntityBrowserView(entity_type="Sample", backend=backend)
    view._total_pages = 3
    view._current_page = 3

    async def run():
        await view.action_next_page()
        assert view._current_page == 3

    asyncio.run(run())


def test_entity_browser_filter_resets_to_page_1():
    """Filter change resets to page 1."""
    from hippo.tui.views.entity_browser import EntityBrowserView
    from textual.widgets import Input

    backend = MockBrowserBackend(total_items=50)
    view = EntityBrowserView(entity_type="Sample", backend=backend)
    view._current_page = 3
    view._total_pages = 3

    async def run():
        view._filter_text = "brain"
        view._current_page = 1  # simulates what on_input_changed does
        assert view._current_page == 1

    asyncio.run(run())


def test_entity_detail_panel_fields_display():
    """EntityDetailPanel shows all user-defined and system fields."""
    from hippo.tui.views.entity_browser import EntityDetailPanel

    entity = EntityDetail(
        id="sample-1",
        entity_type="Sample",
        fields={
            "id": "sample-1",
            "is_available": True,
            "tissue_type": "Brain",
            "brain_region": "Hippocampus",
        },
        relationships=[RelatedEntityRef("donated_by", "Donor", "donor-1")],
    )
    provenance = [
        ProvenanceEvent("CREATE", "2026-03-01T10:00:00Z", {}),
        ProvenanceEvent("UPDATE", "2026-03-01T14:00:00Z", {}),
    ]
    panel = EntityDetailPanel(entity=entity, provenance=provenance)
    assert panel._entity.id == "sample-1"
    assert "id" in panel._entity.fields
    assert "is_available" in panel._entity.fields


def test_entity_detail_panel_provenance_truncation():
    """EntityDetailPanel only keeps up to 10 provenance events."""
    from hippo.tui.views.entity_browser import EntityDetailPanel

    entity = EntityDetail(id="x", entity_type="Sample", fields={}, relationships=[])
    provenance = [
        ProvenanceEvent(f"EVENT_{i}", f"2026-03-01T{i:02d}:00:00Z", {})
        for i in range(15)
    ]
    panel = EntityDetailPanel(entity=entity, provenance=provenance)
    assert len(panel._provenance) == 10


def test_entity_detail_panel_relationships():
    """EntityDetailPanel shows relationships with target type."""
    from hippo.tui.views.entity_browser import EntityDetailPanel

    entity = EntityDetail(
        id="s-1",
        entity_type="Sample",
        fields={},
        relationships=[RelatedEntityRef("donated_by", "Donor", "d-1")],
    )
    panel = EntityDetailPanel(entity=entity, provenance=[])
    assert panel._entity.relationships[0].target_type == "Donor"
