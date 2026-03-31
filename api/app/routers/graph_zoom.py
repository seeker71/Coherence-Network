"""Fractal zoom navigation router (Spec 182).

GET /api/graph/pillars         — root-level pillar nodes (public)
GET /api/graph/zoom/{node_id}  — subtree rooted at node_id up to depth N (public)
"""

from fastapi import APIRouter, HTTPException, Query

from app.models.graph_zoom import PillarListResponse, ZoomResponse
from app.services import zoom_service

router = APIRouter()


@router.get("/graph/pillars", response_model=PillarListResponse, tags=["graph"])
async def get_pillars():
    """Return all root-level pillar nodes: traceability, trust, freedom, uniqueness, collaboration."""
    return zoom_service.get_pillars()


@router.get("/graph/zoom/{node_id}", response_model=ZoomResponse, tags=["graph"])
async def zoom_node(
    node_id: str,
    depth: int = Query(default=1, ge=0),
):
    """Return a fractal subtree rooted at node_id.

    - depth=0: node only, no children
    - depth=1..3: subtree up to N levels
    - depth>3: HTTP 422
    """
    if depth > 3:
        raise HTTPException(
            status_code=422,
            detail=f"depth must be between 0 and 3, got {depth}",
        )
    try:
        return zoom_service.get_zoom(node_id, depth)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found",
        )
