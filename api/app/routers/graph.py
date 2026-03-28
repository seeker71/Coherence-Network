"""Graph router — generic CRUD for nodes and edges.

This is the universal API. Entity-specific routers (/api/ideas, /api/specs)
are thin adapters that call graph_service with type filters.

Spec-169 additions:
  GET  /graph/node-types            — canonical node type vocabulary
  POST /graph/nodes/{id}/transition — Ice/Water/Gas lifecycle transitions
  POST /graph/nodes/{id}/sub-nodes  — create fractal sub-node
  GET  /graph/nodes/{id}/sub-nodes  — list direct sub-nodes
  POST /graph/validate-edge         — advisory type constraint check
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services import graph_service
from app.services import fractal_primitives_service

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


@router.post("/graph/edges")
async def create_edge(body: EdgeCreate):
    """Create an edge between two nodes."""
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


# ── Spec-169: Node type vocabulary ─────────────────────────────────────


@router.get("/graph/node-types")
async def get_node_types(family: str | None = None):
    """Return the canonical node type vocabulary (spec-169).

    Lists all node types grouped by family, with lifecycle metadata
    (allowed phases, fractal flag, description).
    """
    result = fractal_primitives_service.get_node_type_registry()
    if family:
        result["families"] = [
            f for f in result["families"]
            if f["slug"] == family or f["name"] == family
        ]
        result["total"] = sum(len(f["types"]) for f in result["families"])
    return result


# ── Spec-169: Lifecycle phase transitions ──────────────────────────────


class PhaseTransitionRequest(BaseModel):
    to_phase: str
    reason: str = ""
    actor: str = "system"


@router.post("/graph/nodes/{node_id}/transition")
async def transition_node_phase(node_id: str, body: PhaseTransitionRequest):
    """Transition a node's lifecycle phase (gas ↔ water ↔ ice).

    Valid transitions:
      gas   → water | ice
      water → ice   | gas
      ice   → water | gas

    Returns 404 if node not found, 400 if transition is invalid.
    """
    result = fractal_primitives_service.transition_node_phase(
        node_id=node_id,
        to_phase=body.to_phase,
        reason=body.reason,
        actor=body.actor,
    )
    error = result.get("error")
    if error == "not_found":
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    if error in ("invalid_phase", "invalid_transition", "phase_not_allowed_for_type"):
        raise HTTPException(status_code=400, detail=result.get("detail", error))
    if error == "no_op":
        return result  # 200 with no_op is fine
    return result


# ── Spec-169: Fractal sub-nodes ─────────────────────────────────────


class SubNodeCreate(BaseModel):
    type: str
    name: str
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    phase: str | None = None
    created_by: str = "system"


@router.post("/graph/nodes/{node_id}/sub-nodes", status_code=201)
async def create_sub_node(node_id: str, body: SubNodeCreate):
    """Create a fractal sub-node of node_id (spec-169).

    Creates the child node and a parent-of edge from parent → child.
    Returns 404 if parent not found, 400 if parent type is not fractal.
    """
    result = fractal_primitives_service.create_sub_node(
        parent_id=node_id,
        type=body.type,
        name=body.name,
        description=body.description,
        properties=body.properties,
        phase=body.phase,
        created_by=body.created_by,
    )
    error = result.get("error")
    if error == "parent_not_found":
        raise HTTPException(status_code=404, detail=f"Parent node '{node_id}' not found")
    if error == "not_fractal":
        raise HTTPException(status_code=400, detail=result.get("detail", "not_fractal"))
    return result


@router.get("/graph/nodes/{node_id}/sub-nodes")
async def get_sub_nodes(
    node_id: str,
    type: str | None = None,
    phase: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """List direct sub-nodes of node_id (spec-169).

    Only returns nodes connected via parent-of edges.
    Optionally filters by node type and/or phase.
    """
    result = fractal_primitives_service.get_sub_nodes(
        parent_id=node_id,
        node_type=type,
        phase=phase,
        limit=limit,
    )
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return result


# ── Spec-169: Edge constraint validation ───────────────────────────────


class EdgeValidateRequest(BaseModel):
    from_type: str
    to_type: str
    edge_type: str


@router.post("/graph/validate-edge")
async def validate_edge_types(body: EdgeValidateRequest):
    """Advisory check: is this edge type semantically valid between two node types?

    Does not write anything. Returns warnings if the combination is unusual.
    Always returns 200 — use the 'valid' field to check the result.
    """
    return fractal_primitives_service.validate_edge_for_types(
        from_type=body.from_type,
        to_type=body.to_type,
        edge_type=body.edge_type,
    )


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
