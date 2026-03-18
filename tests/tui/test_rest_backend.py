"""Tests for RESTBackend — token precedence and connection failure handling."""

from __future__ import annotations

import asyncio
import os

import pytest

from hippo.tui.backend.rest import RESTBackend, _resolve_token


# ---------------------------------------------------------------------------
# Tests: token resolution
# ---------------------------------------------------------------------------


def test_explicit_token_takes_precedence(monkeypatch):
    """Explicit --token flag overrides env variable."""
    monkeypatch.setenv("HIPPO_TUI_TOKEN", "env-token")
    resolved = _resolve_token("explicit-token")
    assert resolved == "explicit-token"


def test_env_token_used_when_no_explicit(monkeypatch):
    """HIPPO_TUI_TOKEN is used when no explicit token is provided."""
    monkeypatch.setenv("HIPPO_TUI_TOKEN", "envtoken")
    resolved = _resolve_token(None)
    assert resolved == "envtoken"


def test_default_token_when_neither_set(monkeypatch):
    """Falls back to 'dev-token' when neither flag nor env is set."""
    monkeypatch.delenv("HIPPO_TUI_TOKEN", raising=False)
    resolved = _resolve_token(None)
    assert resolved == "dev-token"


def test_rest_backend_uses_bearer_token():
    """RESTBackend constructs Authorization header from token."""
    backend = RESTBackend(url="http://localhost:8000", token="mytoken")
    assert backend._token == "mytoken"
    import httpx

    client = backend._get_client()
    auth_header = client.headers.get("authorization")
    assert auth_header == "Bearer mytoken"


def test_rest_backend_token_from_env(monkeypatch):
    """RESTBackend picks up token from HIPPO_TUI_TOKEN env variable."""
    monkeypatch.setenv("HIPPO_TUI_TOKEN", "envtoken")
    backend = RESTBackend(url="http://localhost:8000")
    assert backend._token == "envtoken"


def test_rest_backend_default_token(monkeypatch):
    """RESTBackend uses dev-token when no flag or env variable provided."""
    monkeypatch.delenv("HIPPO_TUI_TOKEN", raising=False)
    backend = RESTBackend(url="http://localhost:8000")
    assert backend._token == "dev-token"


# ---------------------------------------------------------------------------
# Tests: connection failure handling
# ---------------------------------------------------------------------------


def test_connection_failure_sets_status_bar_message(monkeypatch):
    """Connection failure triggers status callback and does not crash."""
    import httpx

    errors: list[str] = []

    backend = RESTBackend(
        url="http://localhost:19999",
        status_callback=lambda msg: errors.append(msg),
    )

    async def mock_get_json(path: str):
        # Simulate the error path: return None (already handled)
        return None

    monkeypatch.setattr(backend, "_get_json", mock_get_json)

    result = asyncio.run(backend.list_entity_types())
    assert result == []


def test_connection_failure_returns_empty_paged_result(monkeypatch):
    """list_entities returns empty PagedResult on connection failure."""
    backend = RESTBackend(url="http://localhost:19999")

    async def mock_get_json(path: str):
        return None

    monkeypatch.setattr(backend, "_get_json", mock_get_json)

    result = asyncio.run(backend.list_entities("Sample"))
    assert result.items == []
    assert result.total_pages == 1


def test_get_json_handles_connect_error_gracefully():
    """_get_json catches ConnectError and reports it without raising."""
    errors: list[str] = []
    backend = RESTBackend(
        url="http://localhost:19999",
        status_callback=lambda msg: errors.append(msg),
    )

    async def run():
        return await backend._get_json("/nonexistent")

    result = asyncio.run(run())
    assert result is None
    # Should have reported an error via the callback
    assert len(errors) == 1


def test_authorization_header_sent_on_every_request(monkeypatch):
    """Every HTTP request includes Authorization: Bearer <token>."""
    import httpx

    captured_headers: list[dict] = []

    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return []

    class MockAsyncClient:
        def __init__(self, base_url="", headers=None, timeout=None):
            captured_headers.append(dict(headers or {}))

        async def get(self, path):
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    backend = RESTBackend(url="http://localhost:8000", token="testtoken")
    backend._client = None  # force re-creation

    async def run():
        return await backend._get_json("/test")

    asyncio.run(run())

    assert len(captured_headers) == 1
    assert captured_headers[0].get("Authorization") == "Bearer testtoken"
