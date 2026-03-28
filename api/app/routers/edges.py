"""Dedicated edges router — /api/edges and /api/entities/{id}/edges.

Implements the canonical 46-type edge navigation layer from spec task_fbceb79ee5d481d5.
The /api/graph/edges and /api/graph/nodes/{id}/edges routes remain in graph.py as aliases.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.config.edge_types import EDGE_TYPE_FAMILIES, CANONICAL_EDGE_TYPES
from app.services import graph_service

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────


class EdgeCreateRequest(BaseModel):
    from_id: str
    to_id: str
    type: str
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"


# ── Type Registry ─────────────────────────────────────────────────────


@router.get("/edges/types")
async def get_edge_types(family: str | None = None):
    """Return all 46 canonical edge types grouped by family.

    Stable and cacheable — no DB query needed.
    Returns 200 with empty families array if family filter matches nothing.
    """
    families = EDGE_TYPE_FAMILIES
    if family:
        families = [f for f in families if f["slug"] == family or f["name"] == family]

    total = sum(len(f["types"]) for f in families)
    return {
        "total": total,
        "families": families,
    }


# ── Edge CRUD ─────────────────────────────────────────────────────────


@router.get("/edges")
async def list_edges(
    type: str | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List edges with optional filters. Responses include from_node and to_node stubs."""
    return graph_service.list_edges(
        edge_type=type, from_id=from_id, to_id=to_id, limit=limit, offset=offset
    )


@router.get("/edges/{edge_id}")
async def get_edge(edge_id: str):
    """Get a single edge by ID with node stubs."""
    edge = graph_service.get_edge_by_id(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return edge


@router.post("/edges", status_code=201)
async def create_edge(body: EdgeCreateRequest, strict: bool = False):
    """Create a typed edge between two entities.

    - Returns 409 if the (from_id, to_id, type) triplet already exists.
    - Returns 404 if either endpoint node does not exist.
    - Returns 400 with strict=true if type is not in the 46 canonical list.
    - Non-canonical types are allowed by default (canonical: false in response).
    """
    # Validate canonical type in strict mode
    is_canonical = body.type in CANONICAL_EDGE_TYPES
    if strict and not is_canonical:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown edge type '{body.type}'. Use GET /api/edges/types for valid types.",
        )

    # Validate that both endpoint nodes exist
    from_node = graph_service.get_node(body.from_id)
    if not from_node:
        raise HTTPException(status_code=404, detail=f"Node '{body.from_id}' not found")
    to_node = graph_service.get_node(body.to_id)
    if not to_node:
        raise HTTPException(status_code=404, detail=f"Node '{body.to_id}' not found")

    result = graph_service.create_edge_strict(
        from_id=body.from_id,
        to_id=body.to_id,
        type=body.type,
        properties=body.properties,
        strength=body.strength,
        created_by=body.created_by,
    )

    if result.get("error") == "edge_exists":
        raise HTTPException(
            status_code=409,
            detail=f"Edge already exists: {body.from_id} --[{body.type}]--> {body.to_id}",
        )

    result["canonical"] = is_canonical
    result["from_node"] = {"id": from_node["id"], "type": from_node["type"], "name": from_node["name"]}
    result["to_node"] = {"id": to_node["id"], "type": to_node["type"], "name": to_node["name"]}
    return result


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str):
    """Delete an edge by ID."""
    if not graph_service.delete_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return {"deleted": edge_id}


# ── Entity-scoped edge endpoints ───────────────────────────────────────


@router.get("/entities/{entity_id}/edges")
async def get_entity_edges(
    entity_id: str,
    type: str | None = None,
    direction: str = Query(default="both", pattern="^(both|outgoing|incoming)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List all edges for any entity regardless of node type.

    Returns 404 if the entity does not exist.
    Enriches each edge with from_node and to_node stubs.
    """
    entity = graph_service.get_node(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return graph_service.list_edges_for_entity(
        entity_id=entity_id,
        edge_type=type,
        direction=direction,
        limit=limit,
        offset=offset,
    )


@router.get("/entities/{entity_id}/neighbors")
async def get_entity_neighbors(
    entity_id: str,
    type: str | None = None,
    node_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Return neighboring node objects reachable via 1 hop from entity_id.

    Returns 404 if entity does not exist.
    """
    entity = graph_service.get_node(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return graph_service.get_neighbors_enriched(
        node_id=entity_id, edge_type=type, node_type=node_type, limit=limit
    )
