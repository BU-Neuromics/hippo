"""TUI REST backend — thin httpx.AsyncClient wrapper for REST API mode."""

from __future__ import annotations

import math
import os
from typing import Any

from hippo.tui.backend.protocol import (
    EntityDetail,
    EntityTypeSummary,
    EntityTypeSchema,
    FieldInfo,
    PagedResult,
    ProvenanceEvent,
    RelatedEntityRef,
    RelationshipDeclaration,
    SchemaView,
)

_PAGE_SIZE = 20
_DEFAULT_URL = "http://127.0.0.1:8000"
_DEFAULT_TOKEN = "dev-token"


def _resolve_token(token: str | None) -> str:
    """Resolve the auth token.

    Priority: explicit *token* argument > ``HIPPO_TUI_TOKEN`` env variable > ``dev-token``.
    """
    if token is not None:
        return token
    env_token = os.environ.get("HIPPO_TUI_TOKEN")
    if env_token:
        return env_token
    return _DEFAULT_TOKEN


class RESTBackend:
    """TUIBackend implementation that calls a running ``hippo serve`` instance.

    Uses ``httpx.AsyncClient`` for non-blocking HTTP calls.

    Args:
        url: Base URL of the REST API server.
        token: Bearer token. Falls back to ``HIPPO_TUI_TOKEN`` env var, then ``dev-token``.
        status_callback: Optional callable(message: str) invoked on connection errors
            so the UI can display an error without crashing.
    """

    def __init__(
        self,
        url: str = _DEFAULT_URL,
        token: str | None = None,
        status_callback: Any = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._token = _resolve_token(token)
        self._status_callback = status_callback
        self._client: Any = None  # lazy httpx.AsyncClient

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Lazy-create and return an httpx.AsyncClient."""
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10.0,
            )
        return self._client

    def _report_error(self, message: str) -> None:
        """Report a connection error via callback (if set) without crashing."""
        if self._status_callback is not None:
            try:
                self._status_callback(message)
            except Exception:
                pass

    async def _get_json(self, path: str) -> Any:
        """GET *path* and return parsed JSON.

        Returns ``None`` on connection failure after reporting the error.
        """
        import httpx

        try:
            client = self._get_client()
            response = await client.get(path)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as exc:
            self._report_error(f"Connection failed: {self._url} — {exc}")
            return None
        except httpx.TimeoutException as exc:
            self._report_error(f"Request timed out: {self._url}{path} — {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            self._report_error(
                f"HTTP {exc.response.status_code} from {self._url}{path}"
            )
            return None
        except Exception as exc:
            self._report_error(f"Unexpected error: {exc}")
            return None

    # ------------------------------------------------------------------
    # TUIBackend protocol implementation
    # ------------------------------------------------------------------

    async def list_entity_types(self) -> list[EntityTypeSummary]:
        data = await self._get_json("/entity-types")
        if data is None:
            return []
        summaries = []
        for item in data if isinstance(data, list) else data.get("items", []):
            summaries.append(
                EntityTypeSummary(
                    name=item.get("name", ""),
                    count=item.get("count", 0),
                )
            )
        return summaries

    async def list_entities(
        self,
        entity_type: str,
        page: int = 1,
        filter_text: str = "",
    ) -> PagedResult:
        params = f"?page={page}&page_size={_PAGE_SIZE}"
        if filter_text:
            import urllib.parse

            params += f"&filter={urllib.parse.quote(filter_text)}"
        data = await self._get_json(f"/entities/{entity_type}{params}")
        if data is None:
            return PagedResult(items=[], page=page, total_pages=1, total_items=0)
        items = data.get("items", []) if isinstance(data, dict) else data
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
        total_pages = max(
            1,
            data.get("total_pages", math.ceil(total / _PAGE_SIZE))
            if isinstance(data, dict)
            else 1,
        )
        return PagedResult(
            items=items,
            page=page,
            total_pages=total_pages,
            total_items=total,
        )

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityDetail:
        data = await self._get_json(f"/entities/{entity_type}/{entity_id}")
        if data is None:
            return EntityDetail(
                id=entity_id,
                entity_type=entity_type,
                fields={},
                relationships=[],
            )

        fields = {
            "id": data.get("id", entity_id),
            "is_available": data.get("is_available", True),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }
        fields.update(data.get("data", {}))

        relationships = [
            RelatedEntityRef(
                relationship_name=rel.get("relationship_type", ""),
                target_type=rel.get("target_type", ""),
                target_id=rel.get("target_id", ""),
            )
            for rel in data.get("relationships", [])
        ]

        return EntityDetail(
            id=data.get("id", entity_id),
            entity_type=entity_type,
            fields=fields,
            relationships=relationships,
        )

    async def get_schema(self) -> SchemaView:
        data = await self._get_json("/schema")
        if data is None:
            return SchemaView()

        entity_types: list[EntityTypeSchema] = []
        for et in data.get("entity_types", []):
            fields = [
                FieldInfo(
                    name=f.get("name", ""),
                    field_type=f.get("type", "string"),
                    required=f.get("required", False),
                    indexed=f.get("indexed", False),
                    ref_target=f.get("ref_target"),
                )
                for f in et.get("fields", [])
            ]
            entity_types.append(
                EntityTypeSchema(name=et.get("name", ""), fields=fields)
            )

        relationships = [
            RelationshipDeclaration(
                source_type=r.get("source_type", ""),
                relationship_name=r.get("name", ""),
                target_type=r.get("target_type", ""),
            )
            for r in data.get("relationships", [])
        ]

        return SchemaView(entity_types=entity_types, relationships=relationships)

    async def get_provenance(
        self, entity_type: str, entity_id: str
    ) -> list[ProvenanceEvent]:
        data = await self._get_json(f"/entities/{entity_type}/{entity_id}/provenance")
        if data is None:
            return []

        events = data if isinstance(data, list) else data.get("events", [])
        return [
            ProvenanceEvent(
                event_type=ev.get("operation_type", ev.get("event_type", "UNKNOWN")),
                timestamp=ev.get("timestamp", ""),
                diff=ev.get("diff", ev.get("state_snapshot", {})) or {},
            )
            for ev in events[:10]
        ]
