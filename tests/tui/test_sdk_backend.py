"""Tests for SDKBackend — db_path resolution and asyncio.to_thread usage."""

from __future__ import annotations

import asyncio
import json
import os
import unittest.mock
from pathlib import Path

import pytest

from hippo.tui.backend.sdk import SDKBackend, _resolve_db_path


# ---------------------------------------------------------------------------
# Tests: db_path resolution
# ---------------------------------------------------------------------------


def test_explicit_db_path_takes_precedence(tmp_path):
    """Explicit db_path argument overrides config.json."""
    explicit = tmp_path / "explicit.db"
    resolved = _resolve_db_path(explicit)
    assert resolved == explicit


def test_config_json_db_path_used_when_no_explicit(tmp_path, monkeypatch):
    """Falls back to config.json in cwd when no explicit path given."""
    config = {"db_path": str(tmp_path / "from_config.db")}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_db_path(None)
    assert resolved == Path(str(tmp_path / "from_config.db"))


def test_default_hippo_db_when_no_config(tmp_path, monkeypatch):
    """Falls back to hippo.db when config.json is absent."""
    monkeypatch.chdir(tmp_path)
    resolved = _resolve_db_path(None)
    assert resolved == Path("hippo.db")


def test_explicit_string_path_is_resolved():
    """String paths are converted to Path objects."""
    resolved = _resolve_db_path("/tmp/my.db")
    assert resolved == Path("/tmp/my.db")


# ---------------------------------------------------------------------------
# Tests: asyncio.to_thread wrapping
# ---------------------------------------------------------------------------


def test_list_entity_types_uses_to_thread(monkeypatch):
    """list_entity_types dispatches via asyncio.to_thread."""
    backend = SDKBackend(db_path=":memory:")

    calls: list[str] = []

    original_to_thread = asyncio.to_thread

    async def mock_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)

    async def run():
        try:
            await backend.list_entity_types()
        except Exception:
            pass

    asyncio.run(run())
    assert "_list_entity_types_sync" in calls


def test_list_entities_uses_to_thread(monkeypatch):
    """list_entities dispatches via asyncio.to_thread."""
    backend = SDKBackend(db_path=":memory:")

    calls: list[str] = []
    original_to_thread = asyncio.to_thread

    async def mock_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)

    async def run():
        try:
            await backend.list_entities("Sample")
        except Exception:
            pass

    asyncio.run(run())
    assert "_list_entities_sync" in calls


def test_get_schema_uses_to_thread(monkeypatch):
    """get_schema dispatches via asyncio.to_thread."""
    backend = SDKBackend(db_path=":memory:")

    calls: list[str] = []
    original_to_thread = asyncio.to_thread

    async def mock_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", mock_to_thread)

    async def run():
        try:
            await backend.get_schema()
        except Exception:
            pass

    asyncio.run(run())
    assert "_get_schema_sync" in calls
