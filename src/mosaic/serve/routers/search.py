"""Search router for Mosaic API.

Provides endpoints for full-text search of entities.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from mosaic.core.client import MosaicClient

router = APIRouter(prefix="/search", tags=["search"])


async def get_client(request: Request) -> MosaicClient:
    """Get the MosaicClient from request state."""
    if hasattr(request.app.state, "hippo_client"):
        return request.app.state.hippo_client
    return MosaicClient()


@router.get("")
async def search_entities(
    request: Request,
    entity_type: str = Query(..., description="Entity type to search"),
    q: str = Query(..., description="Search query"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    filter_mode: str = Query("and", description="Filter composition: 'and' or 'or'"),
) -> list[dict[str, Any]]:
    """Search entities using full-text search.

    Args:
        request: FastAPI request object.
        entity_type: The entity type to search.
        q: The search query string.
        limit: Maximum number of results.
        offset: Number of results to skip.

    Returns:
        List of matching entities.
    """
    client = await get_client(request)

    results = client.search(
        entity_type=entity_type,
        query=q,
        limit=limit,
    )

    return results[offset : offset + limit]
