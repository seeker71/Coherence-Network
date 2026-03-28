"""Graph router — generic CRUD for nodes and edges.

This is the universal API. Entity-specific routers (/api/ideas, /api/specs)
are thin adapters that call graph_service with type filters.

Spec-168 additions (fractal-node-edge-primitives):
  GET  /graph/node-types            — canonical node type vocabulary (10 types)
  GET  /graph/edge-types            — canonical edge type vocabulary (7 types)
  GET  /graph/proof                 — live graph health / coverage metrics
  Validation on POST /graph/nodes   — node_type constrained to 10 canonical values
  Validation on POST /graph/edges   — edge_type constrained to 7 canonical values, no self-loops
  Lifecycle filter on GET /graph/nodes/{id}/neighbors

Spec-169 additions:
  POST /graph/nodes/{id}/transition — Ice/Water/Gas lifecycle transitions
  POST /graph/nodes/{id}/sub-nodes  — create fractal sub-node
  GET  /graph/nodes/{id}/sub-nodes  — list direct sub-nodes
  POST /graph/validate-edge         — advisory type constraint check
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import graph_service
from app.services import fractal_primitives_service

router = APIRouter()

# ── Spec 168: Canonical type vocabularies ────────────────────────────

_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"


def _load_node_type_registry() -> list[dict]:
    """Load node type registry from JSON config."""
    path = _CONFIG_DIR / "node_type_registry.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _load_edge_type_registry() -> list[dict]:
    """Load edge type registry from JSON config."""
    path = _CONFIG_DIR / "edge_type_registry.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


# Cached at module load — these are static configurations
_NODE_TYPE_REGISTRY: list[dict] = _load_node_type_registry()
_EDGE_TYPE_REGISTRY: list[dict] = _load_edge_type_registry()

# Sets for O(1) validation
VALID_NODE_TYPES: set[str] = {entry["type"] for entry in _NODE_TYPE_REGISTRY}
VALID_EDGE_TYPES: set[str] = {entry["type"] for entry in _EDGE_TYPE_REGISTRY}
VALID_LIFECYCLE_STATES: set[str] = {"gas", "ice", "water"}

# Lifecycle defaults by node_type
_LIFECYCLE_DEFAULTS: dict[str, str] = {
    entry["type"]: entry["lifecycle_default"]
    for entry in _NODE_TYPE_REGISTRY
}


# ── Request models ───────────────────────────────────────────────────


class NodeCreate(BaseModel):
    # Spec 168 fields (new)
    node_type: str | None = None
    external_id: str | None = None
    payload: dict[str, Any] | None = None
    # Legacy fields (spec 166 / spec 169)
    id: str | None = None
    type: str | None = None
    name: str | None = None
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    phase: str = "water"


class NodeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    phase: str | None = None
    properties: dict[str, Any] | None = None


class EdgeCreate(BaseModel):
    # Spec 168 fields (new)
    edge_type: str | None = None
    from_node_id: str | None = None
    to_node_id: str | None = None
    weight: float | None = None
    # Legacy fields (spec 166 / spec 169)
    from_id: str | None = None
    to_id: str | None = None
    type: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    strength: float = 1.0
    created_by: str = "system"


# ── Node endpoints ──────────────────────────────────────────────────


@router.get("/graph/nodes")
async def list_nodes(
    type: str | None = None,
    node_type: str | None = None,
    phase: str | None = None,
    lifecycle_state: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List nodes with optional type, phase/lifecycle_state, and search filters."""
    effective_type = node_type or type
    effective_phase = lifecycle_state or phase
    return graph_service.list_nodes(
        type=effective_type, phase=effective_phase, search=search,
        limit=limit, offset=offset,
    )


@router.post("/graph/nodes")
async def create_node(body: NodeCreate):
    """Create a new node.

    Accepts both spec-168 format (node_type, external_id, payload) and
    legacy format (type, name, properties, phase).

    Spec-168 validation:
      - node_type must be one of the 10 canonical values
      - lifecycle_state in payload defaults to node_type default when absent
    """
    # Spec 168 path: node_type provided
    if body.node_type is not None:
        if body.node_type not in VALID_NODE_TYPES:
            valid_list = ", ".join(sorted(VALID_NODE_TYPES))
            raise HTTPException(
                status_code=422,
                detail=(
                    f"node_type '{body.node_type}' is not a recognized node type. "
                    f"Valid types: {valid_list}. "
                    f"See /api/graph/node-types for details."
                ),
            )
        # Apply lifecycle default
        payload = dict(body.payload or {})
        if "lifecycle_state" not in payload:
            payload["lifecycle_state"] = _LIFECYCLE_DEFAULTS.get(body.node_type, "water")

        lifecycle = payload["lifecycle_state"]
        node_id = body.external_id or body.id

        return graph_service.create_node(
            id=node_id,
            type=body.node_type,
            name=payload.get("title") or payload.get("name") or (body.external_id or ""),
            description=body.description,
            properties=payload,
            phase=lifecycle,
        )

    # Legacy path: type provided (or missing → error)
    node_type_val = body.type
    if not node_type_val:
        raise HTTPException(status_code=422, detail="Either 'node_type' or 'type' must be provided.")

    return graph_service.create_node(
        id=body.id, type=node_type_val, name=body.name or "",
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
    """Create an edge between two nodes.

    Accepts both spec-168 format (edge_type, from_node_id, to_node_id, weight) and
    legacy format (type, from_id, to_id, strength).

    Spec-168 validation:
      - edge_type must be one of the 7 canonical values
      - self-loops (from_node_id == to_node_id) are rejected
    """
    # Resolve to canonical field names
    effective_edge_type = body.edge_type or body.type
    effective_from = body.from_node_id or body.from_id
    effective_to = body.to_node_id or body.to_id
    effective_strength = body.weight if body.weight is not None else body.strength

    if not effective_edge_type:
        raise HTTPException(status_code=422, detail="Either 'edge_type' or 'type' must be provided.")
    if not effective_from:
        raise HTTPException(status_code=422, detail="Either 'from_node_id' or 'from_id' must be provided.")
    if not effective_to:
        raise HTTPException(status_code=422, detail="Either 'to_node_id' or 'to_id' must be provided.")

    # Spec 168: validate edge_type when using new field name
    if body.edge_type is not None:
        if body.edge_type not in VALID_EDGE_TYPES:
            valid_list = ", ".join(sorted(VALID_EDGE_TYPES))
            raise HTTPException(
                status_code=422,
                detail=(
                    f"edge_type '{body.edge_type}' is not a recognized edge type. "
                    f"Valid types: {valid_list}."
                ),
            )

    # Spec 168: reject self-loops
    if effective_from == effective_to:
        raise HTTPException(
            status_code=422,
            detail="Self-loop edges are not allowed: from_node_id and to_node_id must be different.",
        )

    return graph_service.create_edge(
        from_id=effective_from,
        to_id=effective_to,
        type=effective_edge_type,
        properties=body.properties,
        strength=effective_strength,
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
    rel_type: str | None = None,
    node_type: str | None = None,
    lifecycle_state: str | None = None,
    direction: str = Query(default="both", regex="^(both|outgoing|incoming)$"),
    depth: int = Query(default=1, ge=1, le=2),
):
    """Get neighboring nodes (1-2 hops).

    Spec-168 extensions:
      - lifecycle_state=gas|ice|water  — filter neighbors by lifecycle state
      - rel_type=<edge_type>           — alias for edge_type filter
      - direction=incoming|outgoing|both
      - depth=1|2

    Returns 422 for unknown lifecycle_state values.
    """
    if lifecycle_state is not None and lifecycle_state not in VALID_LIFECYCLE_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"lifecycle_state '{lifecycle_state}' is invalid. Valid values: gas, ice, water.",
        )

    effective_edge_type = rel_type or edge_type
    return graph_service.get_neighbors_with_lifecycle(
        node_id=node_id,
        edge_type=effective_edge_type,
        node_type=node_type,
        lifecycle_state=lifecycle_state,
        direction=direction,
        depth=depth,
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


# ── Spec-168: Node type registry ────────────────────────────────────


@router.get("/graph/node-types")
async def get_node_types():
    """Return the canonical node type vocabulary (spec-168).

    Returns exactly 10 node types with type, description, and lifecycle_default.
    """
    return {"node_types": _NODE_TYPE_REGISTRY}


# ── Spec-168: Edge type registry ────────────────────────────────────


@router.get("/graph/edge-types")
async def get_edge_types():
    """Return the canonical edge type vocabulary (spec-168).

    Returns exactly 7 edge types with type, description, and is_symmetric.
    """
    return {"edge_types": _EDGE_TYPE_REGISTRY}


# ── Spec-168: Graph proof / health endpoint ─────────────────────────


@router.get("/graph/proof")
async def get_graph_proof():
    """Return aggregate evidence that the graph is being used as the fractal data layer.

    Always returns 200 — even with an empty graph.
    Returns total_nodes, total_edges, nodes_by_type, edges_by_type,
    lifecycle_distribution, coverage_pct.
    """
    return graph_service.get_graph_proof()


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
