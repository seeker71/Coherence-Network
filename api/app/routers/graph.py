"""Graph router — generic CRUD for nodes and edges.

This is the universal API. Entity-specific routers (/api/ideas, /api/specs)
are thin adapters that call graph_service with type filters.

Spec 169 additions:
  GET /api/graph/node-types  — canonical 10-type registry
  GET /api/graph/edge-types  — canonical 7-type registry
  GET /api/graph/proof       — aggregate proof the graph is the fractal data layer
  GET /api/graph/nodes/{id}/neighbors — extended with lifecycle_state, rel_type, direction
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services import graph_service
from app.models.graph import CANONICAL_EDGE_TYPE_SET, CANONICAL_NODE_TYPE_SET

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
    """Create a new node. Validates node_type and lifecycle_state for canonical types (Spec 169)."""
    # Validate canonical node types via service layer
    if body.type in CANONICAL_NODE_TYPE_SET:
        try:
            graph_service.validate_node_type(body.type)
            lc = body.properties.get("lifecycle_state")
            if lc is not None:
                graph_service.validate_lifecycle_state(lc)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    try:
        return graph_service.create_node(
            id=body.id, type=body.type, name=body.name,
            description=body.description, properties=body.properties,
            phase=body.phase if body.phase != "water" else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


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


@router.post("/graph/edges")
async def create_edge(body: EdgeCreate):
    """Create an edge between two nodes. Validates edge_type and prevents self-loops (Spec 169)."""
    # Canonical edge type validation
    if body.type not in CANONICAL_EDGE_TYPE_SET:
        raise HTTPException(
            status_code=422,
            detail=(
                f"edge_type '{body.type}' is not a recognized edge type. "
                "Valid types: inspires, depends-on, implements, contradicts, extends, "
                "analogous-to, parent-of."
            ),
        )
    # Self-loop prevention
    if body.from_id == body.to_id:
        raise HTTPException(
            status_code=422,
            detail="Self-loop edges are not allowed: from_node_id and to_node_id must be different.",
        )
    try:
        return graph_service.create_edge(
            from_id=body.from_id, to_id=body.to_id, type=body.type,
            properties=body.properties, strength=body.strength,
            created_by=body.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


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
    rel_type: str | None = None,
    node_type: str | None = None,
    lifecycle_state: str | None = None,
    direction: str = Query(default="both", regex="^(both|outgoing|incoming)$"),
    depth: int = Query(default=1, ge=1, le=2),
):
    """Get neighboring nodes (1–2 hops).

    Spec 169 extensions:
    - lifecycle_state: filter neighbors by gas/ice/water
    - rel_type: alias for edge_type (canonical name)
    - direction: outgoing/incoming/both
    - depth: 1 or 2
    """
    if lifecycle_state is not None and lifecycle_state not in ("gas", "ice", "water"):
        raise HTTPException(
            status_code=422,
            detail=f"lifecycle_state '{lifecycle_state}' is not valid. Must be one of: gas, ice, water.",
        )
    effective_edge_type = rel_type or edge_type
    return graph_service.get_neighbors(
        node_id,
        edge_type=effective_edge_type,
        node_type=node_type,
        direction=direction,
        lifecycle_state=lifecycle_state,
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


# ── Spec 169: Registry + Proof endpoints ────────────────────────────


@router.get("/graph/node-types")
async def get_node_types():
    """Return the canonical 10-type node registry (Spec 169).

    Lists all valid node_type values, their descriptions, default lifecycle states,
    and payload schemas.
    """
    return graph_service.get_node_type_registry()


@router.get("/graph/edge-types")
async def get_edge_types():
    """Return the canonical 7-type edge registry (Spec 169).

    Lists all valid edge_type values, their semantics, symmetry, and examples.
    """
    return graph_service.get_edge_type_registry()


@router.get("/graph/proof")
async def get_graph_proof():
    """Return aggregate proof that the graph is the fractal data layer (Spec 169).

    Returns node/edge counts by type, lifecycle distribution, graph density,
    coverage metrics, and last-edge timestamp. Returns 200 even on empty graph.
    """
    return graph_service.get_proof()


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
