"""Influences router — turn a paste into a node, list, and remove.

Naming an influence is one gesture. POST /api/influences with any
string — a URL or a bare name — and the system resolves it, creates
a claimable node, and links the source contributor to it with an
``inspired-by`` edge. Re-pasting the same URL is a no-op (idempotent
on canonical_url).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import influence_resolver_service as resolver

router = APIRouter()


class InfluenceCreateRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=2000, description="URL or free-text name")
    source_contributor_id: str = Field(..., min_length=1, max_length=255)


@router.post("/influences", status_code=201, summary="Resolve and create an influence")
async def create_influence(body: InfluenceCreateRequest) -> dict[str, Any]:
    """Resolve a paste (URL or name) into a graph node and link it.

    Returns the resolved metadata, the node (created or existing), and
    the new edge id (or a flag if the edge already existed).
    """
    resolved = resolver.resolve(body.input)
    if resolved is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not resolve that input. Try a direct URL "
                "(artist page, channel, festival site) or a more specific name."
            ),
        )
    return resolver.import_influence(body.source_contributor_id, resolved)


@router.get("/influences", summary="List a contributor's influences")
async def list_influences(
    contributor_id: str = Query(..., min_length=1, max_length=255),
) -> dict[str, Any]:
    """Return everything a contributor is inspired-by, newest first."""
    items = resolver.list_influences(contributor_id)
    return {"items": items, "count": len(items)}


@router.delete("/influences/{edge_id}", summary="Remove an influence link")
async def delete_influence(edge_id: str) -> dict[str, Any]:
    """Delete the inspired-by edge. The node stays — it's still
    claimable by the real person or collective it points to."""
    if not resolver.remove_influence_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return {"deleted": edge_id}
