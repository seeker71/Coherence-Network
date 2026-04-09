"""Constellation view routes — network graph data for visualization.

GET /constellation — returns nodes, edges, and stats for force-directed layout
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import constellation_service

router = APIRouter()


@router.get("/constellation")
async def get_constellation(
    workspace_id: str = Query("coherence-network", description="Workspace to visualize"),
    max_nodes: int = Query(100, ge=10, le=500, description="Maximum number of nodes to return"),
) -> dict:
    """Return network graph data optimized for constellation/force-directed visualization."""
    return constellation_service.build_constellation(
        workspace_id=workspace_id,
        max_nodes=max_nodes,
    )
