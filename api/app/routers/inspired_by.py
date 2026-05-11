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


class InspiredByManualRequest(BaseModel):
    """Direct link to an existing graph node — no web resolution.

    Used for private/local cells the open-web resolver cannot find
    (people whose practice is offline, communities that aren't on the
    public web, sanctuaries that hold a frequency but not a domain).
    The body's lineage prose may name them; this endpoint lets the
    graph hold the relation too.
    """

    source_contributor_id: str = Field(..., min_length=1, max_length=255)
    target_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Existing graph node id, e.g. 'contributor:ilena' or 'scene:vali-soul-sanctuary'",
    )
    weight: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Strength of the inspired-by relation; 0..1",
    )


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


@router.post(
    "/inspired-by/manual",
    status_code=201,
    summary="Link two existing nodes with an inspired-by edge (no resolver)",
)
async def create_inspired_by_manual(body: InspiredByManualRequest) -> dict[str, Any]:
    """Create (or refresh) an inspired-by edge between two existing
    graph nodes. The resolver-based POST /inspired-by handles open-web
    cells; this endpoint handles cells the body already knows
    locally — Ubud sanctuary teachers, private circles, communities
    whose substance the web has no page for.

    The source contributor and target node must both exist; this is a
    relation step, not a creation step. Returns the edge as stored.
    """
    edge = service.import_inspired_by_manual(
        source_contributor_id=body.source_contributor_id,
        target_id=body.target_id,
        weight=body.weight,
    )
    if edge is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Source contributor or target node not found in the graph. "
                "Use POST /api/inspired-by for cells that don't exist yet."
            ),
        )
    return edge


@router.get(
    "/inspired-by",
    summary="List what a contributor is inspired by",
)
async def list_inspired_by(
    contributor_id: str = Query(..., min_length=1, max_length=255),
    viewer_id: str | None = Query(
        None,
        min_length=1,
        max_length=255,
        description=(
            "Optional viewer contributor id. When provided, each item is "
            "annotated with ``shared_with_viewer`` — True when the viewer "
            "is also inspired-by that identity."
        ),
    ),
) -> dict[str, Any]:
    """Return every identity the contributor is inspired-by.

    When ``viewer_id`` is provided, each item carries a
    ``shared_with_viewer`` flag so a public profile can surface the
    kinship thread between the subject and whoever is looking.
    """
    items = service.list_inspired_by(contributor_id, viewer_contributor_id=viewer_id)
    shared = sum(1 for it in items if it.get("shared_with_viewer"))
    return {
        "items": items,
        "count": len(items),
        "shared_count": shared if viewer_id else None,
    }


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
