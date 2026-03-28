"""Edge navigation — browse the universal graph by typed relationships.

Canonical graph CRUD remains under `/api/graph/*`. These routes expose the
same data with Living Codex–aligned paths for clients and CLI.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.edge_navigation import EdgeListEnvelope, RelationshipTypesEnvelope
from app.services import concept_service, graph_service

router = APIRouter()


@router.get("/edges", response_model=EdgeListEnvelope)
async def list_edges(
    rel_type: str | None = Query(
        None,
        alias="type",
        description="Filter by relationship type id (e.g. resonates-with)",
    ),
    from_id: str | None = Query(None, description="Filter by source node id"),
    to_id: str | None = Query(None, description="Filter by target node id"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List edges in the graph store (paginated)."""
    return graph_service.list_edges(
        edge_type=rel_type,
        from_id=from_id,
        to_id=to_id,
        limit=limit,
        offset=offset,
    )


@router.get("/edges/types", response_model=RelationshipTypesEnvelope)
async def list_relationship_types():
    """Return the 46 Living Codex relationship types from the ontology."""
    items = concept_service.list_relationship_types()
    return {"total": len(items), "items": items}


@router.get("/entities/{entity_id}/edges")
async def get_entity_edges(
    entity_id: str,
    direction: str = Query(default="both", pattern="^(both|outgoing|incoming)$"),
    rel_type: str | None = Query(
        None,
        alias="type",
        description="Filter by relationship type (e.g. resonates-with)",
    ),
):
    """Edges for any graph node (idea, concept, contributor, spec, task, …) with peer summaries."""
    node = graph_service.get_node(entity_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return graph_service.get_edges_for_entity_nav(
        entity_id,
        direction=direction,
        edge_type=rel_type,
    )
