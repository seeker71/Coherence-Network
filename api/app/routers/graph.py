"""Graph router — generic CRUD for nodes and edges.

This is the universal API. Entity-specific routers (/api/ideas, /api/specs)
are thin adapters that call graph_service with type filters.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services import concept_service, graph_service

router = APIRouter()


# ── Request models ───────────────────────────────────────────────────


class NodeCreate(BaseModel):
    id: str | None = None
    type: str
    name: str
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    phase: str = "water"


class NodeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    phase: str | None = None
    properties: dict[str, Any] | None = None


class EdgeCreate(BaseModel):
    from_id: str
    to_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    strength: float = 1.0
    created_by: str = "system"


# ── Node endpoints ──────────────────────────────────────────────────


@router.get("/graph/nodes")
async def list_nodes(
    type: str | None = None,
    phase: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List nodes with optional type, phase, and search filters."""
    return graph_service.list_nodes(
        type=type, phase=phase, search=search, limit=limit, offset=offset,
    )


@router.post("/graph/nodes")
async def create_node(body: NodeCreate):
    """Create a new node."""
    return graph_service.create_node(
        id=body.id, type=body.type, name=body.name,
        description=body.description, properties=body.properties,
        phase=body.phase,
    )


@router.get("/graph/nodes/count")
async def count_nodes(type: str | None = None):
    """Count nodes, optionally filtered by type."""
    return graph_service.count_nodes(type=type)


@router.get("/graph/stats")
async def graph_stats():
    """Get graph-wide statistics."""
    return graph_service.get_stats()


@router.get("/graph/nodes/{node_id}")
async def get_node(node_id: str):
    """Get a single node."""
    node = graph_service.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return node


@router.patch("/graph/nodes/{node_id}")
async def update_node(node_id: str, body: NodeUpdate):
    """Update a node."""
    result = graph_service.update_node(node_id, **body.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return result


@router.delete("/graph/nodes/{node_id}")
async def delete_node(node_id: str):
    """Delete a node and all its edges."""
    if not graph_service.delete_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return {"deleted": node_id}


# ── Edge endpoints ──────────────────────────────────────────────────


@router.get("/graph/nodes/{node_id}/edges")
async def get_edges(
    node_id: str,
    direction: str = Query(default="both", regex="^(both|outgoing|incoming)$"),
    type: str | None = None,
):
    """Get edges for a node."""
    return graph_service.get_edges(node_id, direction=direction, edge_type=type)


# ── Unified edge surface (aliases for graph navigation UIs / CLI docs) ─


@router.get("/edges/types")
async def list_edge_types():
    """Living Codex ontology: all typed relationship kinds (e.g. resonates-with, emerges-from)."""
    return concept_service.list_relationship_types()


@router.get("/edges")
async def list_edges(
    type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List edges in the universal graph (paginated). Filter by relationship type when given."""
    return graph_service.list_edges(edge_type=type, limit=limit, offset=offset)


@router.get("/entities/{entity_id}/edges")
async def get_entity_edges(
    entity_id: str,
    direction: str = Query(default="both", regex="^(both|outgoing|incoming)$"),
    type: str | None = None,
):
    """Same as ``GET /api/graph/nodes/{id}/edges`` — entities are graph nodes."""
    return graph_service.get_edges(entity_id, direction=direction, edge_type=type)


@router.post("/graph/edges")
async def create_edge(body: EdgeCreate):
    """Create an edge between two nodes."""
    return graph_service.create_edge(
        from_id=body.from_id, to_id=body.to_id, type=body.type,
        properties=body.properties, strength=body.strength,
        created_by=body.created_by,
    )


@router.post("/edges")
async def create_edge_unified(body: EdgeCreate):
    """Alias of ``POST /api/graph/edges`` for clients that target ``/api/edges``."""
    return graph_service.create_edge(
        from_id=body.from_id, to_id=body.to_id, type=body.type,
        properties=body.properties, strength=body.strength,
        created_by=body.created_by,
    )


@router.delete("/graph/edges/{edge_id}")
async def delete_edge(edge_id: str):
    """Delete an edge."""
    if not graph_service.delete_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return {"deleted": edge_id}


# ── Graph query endpoints ───────────────────────────────────────────


@router.get("/graph/nodes/{node_id}/neighbors")
async def get_neighbors(
    node_id: str,
    edge_type: str | None = None,
    node_type: str | None = None,
):
    """Get neighboring nodes (1 hop)."""
    return graph_service.get_neighbors(
        node_id, edge_type=edge_type, node_type=node_type,
    )


@router.get("/graph/nodes/{node_id}/subgraph")
async def get_subgraph(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=5),
    edge_types: str | None = None,
):
    """Get a subgraph centered on a node."""
    types = edge_types.split(",") if edge_types else None
    return graph_service.get_subgraph(node_id, depth=depth, edge_types=types)


@router.get("/graph/path")
async def find_path(
    from_id: str = Query(...),
    to_id: str = Query(...),
    max_depth: int = Query(default=5, ge=1, le=10),
):
    """Find shortest path between two nodes."""
    path = graph_service.get_path(from_id, to_id, max_depth=max_depth)
    if path is None:
        return {"path": None, "message": f"No path found within {max_depth} hops"}
    return {"path": path, "length": len(path)}


# ── DIF Feedback endpoints ───────────────────────────────────────────

@router.get("/dif/feedback/stats")
async def dif_feedback_stats():
    """Get DIF feedback statistics — true/false positive rates, accuracy."""
    from app.services import dif_feedback_service
    return dif_feedback_service.get_stats()


@router.get("/dif/feedback/recent")
async def dif_feedback_recent(limit: int = Query(default=20, ge=1, le=100)):
    """Get recent DIF feedback entries."""
    from app.services import dif_feedback_service
    return dif_feedback_service.get_recent(limit=limit)


@router.post("/dif/feedback")
async def record_dif_feedback(body: dict):
    """Record a DIF verification result for accuracy tracking."""
    from app.services import dif_feedback_service
    return dif_feedback_service.record_verification(
        task_id=body.get("task_id", ""),
        task_type=body.get("task_type", ""),
        file_path=body.get("file_path", ""),
        language=body.get("language", ""),
        dif_result=body.get("dif_result", {}),
        agent_action=body.get("agent_action", "pending"),
        idea_id=body.get("idea_id", ""),
        provider=body.get("provider", ""),
    )
