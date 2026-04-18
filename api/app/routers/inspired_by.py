"""Inspired-by router — post a name, a subgraph appears.

Naming someone you draw from is one gesture. POST /api/inspired-by
with any string — a name, a URL, a paste — and the resolver returns a
small subgraph: the identity node, the presences it maintains across
platforms, and the creations we could find. The ``inspired-by`` edge
from the source contributor carries a weight that emerges from what
was discovered.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import inspired_by_service as service

router = APIRouter()


class InspiredByCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=2000, description="Name, URL, or paste")
    source_contributor_id: str = Field(..., min_length=1, max_length=255)


@router.post(
    "/inspired-by",
    status_code=201,
    summary="Resolve a name into a subgraph and link as inspired-by",
)
async def create_inspired_by(body: InspiredByCreateRequest) -> dict[str, Any]:
    """Resolve the input into identity + presences + creations, persist
    the subgraph, and link the source contributor with an ``inspired-by``
    edge whose weight reflects discovery richness.
    """
    resolved = service.resolve(body.name)
    if resolved is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Couldn't resolve that. Try a more specific name or a direct URL "
                "(artist page, channel, festival site)."
            ),
        )
    return service.import_inspired_by(body.source_contributor_id, resolved)


@router.get(
    "/inspired-by",
    summary="List what a contributor is inspired by",
)
async def list_inspired_by(
    contributor_id: str = Query(..., min_length=1, max_length=255),
) -> dict[str, Any]:
    """Return every identity the contributor is inspired-by, each with
    its edge id and weight, newest first."""
    items = service.list_inspired_by(contributor_id)
    return {"items": items, "count": len(items)}


@router.delete(
    "/inspired-by/{edge_id}",
    summary="Drop an inspired-by link",
)
async def delete_inspired_by(edge_id: str) -> dict[str, Any]:
    """Remove the edge. The identity node and its creations stay in the
    graph — still claimable, still linked to each other."""
    if not service.remove_inspired_by_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return {"deleted": edge_id}
