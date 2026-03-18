"""TUI SDK backend — wraps HippoClient + SQLiteAdapter for SDK-direct mode."""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
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


def _resolve_db_path(db_path: str | Path | None) -> Path:
    """Resolve the SQLite database path.

    Priority: explicit *db_path* argument > ``config.json`` in cwd.

    Args:
        db_path: Explicit path override, or ``None`` to read from ``config.json``.

    Returns:
        Resolved ``Path`` to the SQLite database file.
    """
    if db_path is not None:
        return Path(db_path)

    config_file = Path("config.json")
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            candidate = cfg.get("db_path") or cfg.get("database_url")
            if candidate:
                return Path(candidate)
        except (json.JSONDecodeError, OSError):
            pass

    return Path("hippo.db")


class SDKBackend:
    """TUIBackend implementation that uses HippoClient with SQLiteAdapter directly.

    All synchronous SDK calls are dispatched via ``asyncio.to_thread()`` so that
    Textual's async event loop is never blocked.

    Args:
        db_path: Path to the SQLite database file. If omitted, falls back to
            ``config.json`` in the current working directory, then ``hippo.db``.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = _resolve_db_path(db_path)
        self._client: Any = None  # lazy-initialized on first use

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Lazy-create and return the HippoClient + SQLiteAdapter."""
        if self._client is None:
            from hippo.core.client import HippoClient
            from hippo.core.storage.adapters.sqlite_adapter import SQLiteAdapter

            storage = SQLiteAdapter(str(self._db_path))
            self._client = HippoClient(storage=storage)
        return self._client

    def _list_entity_types_sync(self) -> list[EntityTypeSummary]:
        """Synchronous helper — lists entity types from the SQLite schema."""
        client = self._get_client()
        storage = client.storage
        if storage is None:
            return []

        with storage._transaction() as conn:
            cursor = conn.cursor()
            # Pull table names from sqlite_master that look like entity tables
            cursor.execute(
                """SELECT name FROM sqlite_master
                   WHERE type='table'
                     AND name NOT LIKE 'sqlite_%'
                     AND name NOT IN (
                         'entities', 'provenance_log', 'external_ids',
                         'entity_relationships', 'schema_migrations',
                         'entity_provenance_summary'
                     )
                     AND name NOT LIKE '%_fts%'
                     AND name NOT LIKE 'migration_%'
                   ORDER BY name"""
            )
            table_rows = cursor.fetchall()

        summaries: list[EntityTypeSummary] = []
        for row in table_rows:
            table_name = row["name"] if hasattr(row, "keys") else row[0]
            # Count rows in each entity table
            with storage._transaction() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')  # noqa: S608
                    count = cursor.fetchone()[0]
                except Exception:
                    count = 0
            summaries.append(EntityTypeSummary(name=table_name, count=count))

        return summaries

    def _list_entities_sync(
        self, entity_type: str, page: int, filter_text: str
    ) -> PagedResult:
        """Synchronous helper — paginated entity listing."""
        client = self._get_client()

        from hippo.core.storage import Query

        filters = []
        if filter_text:
            # Simple substring match on the data JSON field
            # We'll do post-query filtering for simplicity
            pass

        result = client.query(entity_type=entity_type)
        all_items = result.items

        if filter_text:
            lowered = filter_text.lower()
            all_items = [
                item
                for item in all_items
                if lowered in json.dumps(item.get("data", {})).lower()
            ]

        total = len(all_items)
        total_pages = max(1, math.ceil(total / _PAGE_SIZE))
        page = max(1, min(page, total_pages))
        offset = (page - 1) * _PAGE_SIZE
        page_items = all_items[offset : offset + _PAGE_SIZE]

        return PagedResult(
            items=page_items,
            page=page,
            total_pages=total_pages,
            total_items=total,
        )

    def _get_entity_sync(self, entity_type: str, entity_id: str) -> EntityDetail:
        """Synchronous helper — full entity detail."""
        client = self._get_client()
        entity = client.get(entity_type=entity_type, entity_id=entity_id)

        data = entity.get("data", {})
        fields: dict[str, Any] = {
            "id": entity.get("id"),
            "is_available": entity.get("is_available", True),
            "created_at": entity.get("created_at"),
            "updated_at": entity.get("updated_at"),
        }
        fields.update(data)

        # Fetch relationships
        relationships: list[RelatedEntityRef] = []
        storage = client.storage
        if storage is not None:
            try:
                with storage._transaction() as conn:
                    rel_store = storage._get_relationship_store(conn)
                    rels = list(rel_store.list_for_entity(entity_id))
                for rel in rels:
                    # Determine target entity type from entities table
                    target_type = rel.relationship_type
                    try:
                        with storage._transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "SELECT entity_type FROM entities WHERE id = ?",
                                (rel.target_id,),
                            )
                            row = cursor.fetchone()
                            if row:
                                target_type = (
                                    row["entity_type"]
                                    if hasattr(row, "keys")
                                    else row[0]
                                )
                    except Exception:
                        pass
                    relationships.append(
                        RelatedEntityRef(
                            relationship_name=rel.relationship_type,
                            target_type=target_type,
                            target_id=rel.target_id,
                        )
                    )
            except Exception:
                pass

        return EntityDetail(
            id=entity_id,
            entity_type=entity_type,
            fields=fields,
            relationships=relationships,
        )

    def _get_schema_sync(self) -> SchemaView:
        """Synchronous helper — build SchemaView from SQLite tables."""
        client = self._get_client()
        storage = client.storage
        if storage is None:
            return SchemaView()

        entity_types: list[EntityTypeSchema] = []
        with storage._transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT name FROM sqlite_master
                   WHERE type='table'
                     AND name NOT LIKE 'sqlite_%'
                     AND name NOT IN (
                         'entities', 'provenance_log', 'external_ids',
                         'entity_relationships', 'schema_migrations',
                         'entity_provenance_summary'
                     )
                     AND name NOT LIKE '%_fts%'
                     AND name NOT LIKE 'migration_%'
                   ORDER BY name"""
            )
            table_names = [
                (row["name"] if hasattr(row, "keys") else row[0])
                for row in cursor.fetchall()
            ]

        for table_name in table_names:
            fields: list[FieldInfo] = []
            with storage._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(f'PRAGMA table_info("{table_name}")')  # noqa: S608
                for col in cursor.fetchall():
                    col_name = col["name"] if hasattr(col, "keys") else col[1]
                    col_type = col["type"] if hasattr(col, "keys") else col[2]
                    not_null = col["notnull"] if hasattr(col, "keys") else col[3]
                    # Skip system columns
                    if col_name in ("id", "is_available", "created_at", "updated_at"):
                        continue
                    fields.append(
                        FieldInfo(
                            name=col_name,
                            field_type=col_type.lower() if col_type else "string",
                            required=bool(not_null),
                            indexed=False,
                        )
                    )
            entity_types.append(EntityTypeSchema(name=table_name, fields=fields))

        return SchemaView(entity_types=entity_types, relationships=[])

    def _get_provenance_sync(
        self, entity_type: str, entity_id: str
    ) -> list[ProvenanceEvent]:
        """Synchronous helper — get provenance history, newest first."""
        client = self._get_client()
        storage = client.storage
        if storage is None:
            return []

        try:
            history = client.history(entity_id)
        except Exception:
            return []

        events: list[ProvenanceEvent] = []
        for record in reversed(history):  # newest first
            events.append(
                ProvenanceEvent(
                    event_type=record.get("operation_type", "UNKNOWN"),
                    timestamp=record.get("timestamp", ""),
                    diff=record.get("state_snapshot") or {},
                )
            )
        return events[:10]

    # ------------------------------------------------------------------
    # TUIBackend protocol implementation
    # ------------------------------------------------------------------

    async def list_entity_types(self) -> list[EntityTypeSummary]:
        return await asyncio.to_thread(self._list_entity_types_sync)

    async def list_entities(
        self,
        entity_type: str,
        page: int = 1,
        filter_text: str = "",
    ) -> PagedResult:
        return await asyncio.to_thread(
            self._list_entities_sync, entity_type, page, filter_text
        )

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityDetail:
        return await asyncio.to_thread(self._get_entity_sync, entity_type, entity_id)

    async def get_schema(self) -> SchemaView:
        return await asyncio.to_thread(self._get_schema_sync)

    async def get_provenance(
        self, entity_type: str, entity_id: str
    ) -> list[ProvenanceEvent]:
        return await asyncio.to_thread(
            self._get_provenance_sync, entity_type, entity_id
        )
