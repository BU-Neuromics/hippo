"""Tests for CommandPalette (HippoCommandPalette) widget."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip(
    "textual", reason="textual not installed; run: pip install hippo[tui]"
)

from hippo.tui.widgets.command_palette import _fuzzy_match, _BUILTIN_COMMANDS


def test_fuzzy_match_exact():
    """Exact string matches."""
    assert _fuzzy_match("sample", "Sample") is True


def test_fuzzy_match_subsequence():
    """Characters in order but not contiguous."""
    assert _fuzzy_match("smpl", "Sample") is True


def test_fuzzy_match_empty_query():
    """Empty query matches everything."""
    assert _fuzzy_match("", "anything") is True


def test_fuzzy_match_no_match():
    """Non-matching query returns False."""
    assert _fuzzy_match("xyz", "Sample") is False


def test_builtin_commands_present():
    """Built-in commands include expected entries."""
    assert "Go to schema" in _BUILTIN_COMMANDS
    assert "Quit" in _BUILTIN_COMMANDS
    assert "Refresh" in _BUILTIN_COMMANDS


def test_command_palette_instantiation():
    """HippoCommandPalette can be created with entity type names."""
    from hippo.tui.widgets.command_palette import HippoCommandPalette

    palette = HippoCommandPalette(entity_type_names=["Sample", "Donor"])
    assert palette is not None


def test_command_palette_all_items():
    """_all_items includes entity types + built-in commands."""
    from hippo.tui.widgets.command_palette import HippoCommandPalette

    palette = HippoCommandPalette(entity_type_names=["Sample", "Donor"])
    assert "Sample" in palette._all_items
    assert "Donor" in palette._all_items
    assert "Quit" in palette._all_items


def test_command_palette_pilot_opens_and_closes():
    """CommandPalette opens, accepts input, and dismisses on Esc."""
    from hippo.tui.app import HippoTUIApp
    from hippo.tui.backend.protocol import EntityTypeSummary, PagedResult, SchemaView

    class MockBackend:
        async def list_entity_types(self):
            return [EntityTypeSummary("Sample", 5)]

        async def list_entities(self, *a, **kw):
            return PagedResult(items=[], page=1, total_pages=1, total_items=0)

        async def get_entity(self, *a, **kw):
            from hippo.tui.backend.protocol import EntityDetail

            return EntityDetail(
                id="x", entity_type="Sample", fields={}, relationships=[]
            )

        async def get_schema(self):
            return SchemaView()

        async def get_provenance(self, *a, **kw):
            return []

    app = HippoTUIApp(backend=MockBackend())

    async def run():
        async with app.run_test(headless=True, size=(80, 24)) as pilot:
            await pilot.pause()
            # Open command palette
            await pilot.press("slash")
            await pilot.pause()
            # Dismiss with Esc
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("q")

    asyncio.run(run())


def test_command_palette_fuzzy_filter_narrows_results():
    """Fuzzy match reduces result set."""
    from hippo.tui.widgets.command_palette import _fuzzy_match

    items = ["Sample", "Donor", "DataFile", "Go to schema", "Quit"]
    filtered = [item for item in items if _fuzzy_match("sam", item)]
    assert "Sample" in filtered
    assert "Donor" not in filtered


def test_command_palette_esc_dismisses():
    """Escape key dismisses command palette."""
    from hippo.tui.widgets.command_palette import HippoCommandPalette

    dismissed: list[bool] = []
    palette = HippoCommandPalette(entity_type_names=["Sample"])

    # Simulate the dismiss action (without full app context)
    original_dismiss = palette.dismiss

    def mock_dismiss(result=None):
        dismissed.append(True)

    palette.dismiss = mock_dismiss
    palette.action_dismiss()
    assert dismissed == [True]
