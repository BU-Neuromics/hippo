"""TUI backend protocol — data transfer objects and TUIBackend abstract interface."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class EntityTypeSummary:
    """Summary of an entity type shown in the sidebar."""

    name: str
    count: int


@dataclass
class PagedResult:
    """Paginated list of entity records."""

    items: list[dict[str, Any]]
    page: int
    total_pages: int
    total_items: int = 0


@dataclass
class RelatedEntityRef:
    """Reference to a related entity."""

    relationship_name: str
    target_type: str
    target_id: str


@dataclass
class EntityDetail:
    """Full detail view of a single entity."""

    id: str
    entity_type: str
    fields: dict[str, Any]
    relationships: list[RelatedEntityRef] = field(default_factory=list)


@dataclass
class FieldInfo:
    """Metadata about a single schema field."""

    name: str
    field_type: str
    required: bool = False
    indexed: bool = False
    ref_target: str | None = None  # set when field_type == "ref"


@dataclass
class RelationshipDeclaration:
    """A relationship declared in the schema."""

    source_type: str
    relationship_name: str
    target_type: str


@dataclass
class EntityTypeSchema:
    """Schema information for a single entity type."""

    name: str
    fields: list[FieldInfo] = field(default_factory=list)


@dataclass
class SchemaView:
    """Full schema view returned by get_schema()."""

    entity_types: list[EntityTypeSchema] = field(default_factory=list)
    relationships: list[RelationshipDeclaration] = field(default_factory=list)


@dataclass
class ProvenanceEvent:
    """A single provenance event for an entity."""

    event_type: str
    timestamp: str
    diff: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TUIBackend protocol
# ---------------------------------------------------------------------------


class TUIBackend(typing.Protocol):
    """Protocol that all TUI backends must satisfy.

    Both ``SDKBackend`` and ``RESTBackend`` implement this interface so that
    views are completely backend-agnostic.
    """

    async def list_entity_types(self) -> list[EntityTypeSummary]:
        """Return a summary of all entity types with their entity counts."""
        ...

    async def list_entities(
        self,
        entity_type: str,
        page: int = 1,
        filter_text: str = "",
    ) -> PagedResult:
        """Return a page of entities for the given type, optionally filtered."""
        ...

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityDetail:
        """Return full detail for a single entity."""
        ...

    async def get_schema(self) -> SchemaView:
        """Return the full schema view (entity types + relationships)."""
        ...

    async def get_provenance(
        self, entity_type: str, entity_id: str
    ) -> list[ProvenanceEvent]:
        """Return provenance history for an entity, newest first."""
        ...
