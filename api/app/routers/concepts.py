"""Concepts router — CRUD for the Living Codex ontology (184 concepts, 46 rel types, 53 axes)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Optional

from app.services import concept_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ConceptCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    typeId: str = "codex.ucore.custom"
    level: int = 1
    keywords: list[str] = []
    parentConcepts: list[str] = []
    childConcepts: list[str] = []
    axes: list[str] = []


class ConceptPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    axes: Optional[list[str]] = None
    parentConcepts: Optional[list[str]] = None
    childConcepts: Optional[list[str]] = None


class EdgeCreate(BaseModel):
    to_id: str
    relationship_type: str
    created_by: str = "unknown"


class TagRequest(BaseModel):
    entity_type: str  # idea, news, spec, task
    entity_id: str
    tagged_by: str = "unknown"


# ---------------------------------------------------------------------------
# Concept CRUD
# ---------------------------------------------------------------------------

@router.get("/concepts")
async def list_concepts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    axis: Optional[str] = Query(default=None),
):
    """List concepts from the ontology, optionally filtered by axis."""
    return concept_service.list_concepts(limit=limit, offset=offset, axis=axis)


@router.get("/concepts/search")
async def search_concepts(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Search concepts by name or description."""
    return concept_service.search_concepts(query=q, limit=limit)


@router.get("/concepts/stats")
async def concept_stats():
    """Get ontology statistics."""
    return concept_service.get_stats()


@router.get("/concepts/relationships")
async def list_relationships():
    """List all 46 relationship types."""
    return concept_service.list_relationship_types()


@router.get("/concepts/axes")
async def list_axes():
    """List all 53 ontology axes."""
    return concept_service.list_axes()


@router.post("/concepts", status_code=201)
async def create_concept(body: ConceptCreate):
    """Create a new custom concept."""
    if concept_service.get_concept(body.id):
        raise HTTPException(status_code=409, detail=f"Concept '{body.id}' already exists")
    return concept_service.create_concept(body.model_dump())


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Get a single concept by ID."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept


@router.patch("/concepts/{concept_id}")
async def patch_concept(concept_id: str, body: ConceptPatch):
    """Update mutable fields on a concept."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.patch_concept(concept_id, body.model_dump(exclude_none=True))


@router.delete("/concepts/{concept_id}", status_code=204)
async def delete_concept(concept_id: str):
    """Delete a custom concept (ontology seed concepts are protected)."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    if concept.get("typeId", "").startswith("codex.ucore.base"):
        raise HTTPException(status_code=403, detail="Cannot delete seed ontology concepts")
    concept_service.delete_concept(concept_id)


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

@router.get("/concepts/{concept_id}/edges")
async def get_concept_edges(concept_id: str):
    """Get edges for a concept (both seed ontology hierarchy and user edges)."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_concept_edges(concept_id)


@router.post("/concepts/{concept_id}/edges", status_code=201)
async def create_edge(concept_id: str, body: EdgeCreate):
    """Create a new edge from this concept to another."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    if not concept_service.get_concept(body.to_id):
        raise HTTPException(status_code=404, detail=f"Target concept '{body.to_id}' not found")
    return concept_service.create_edge(
        from_id=concept_id,
        to_id=body.to_id,
        rel_type=body.relationship_type,
        created_by=body.created_by,
    )


# ---------------------------------------------------------------------------
# Related entities (ideas/news/specs tagged with concept)
# ---------------------------------------------------------------------------

@router.get("/concepts/{concept_id}/related")
async def get_related(concept_id: str):
    """Get all entities (ideas, news, specs, tasks) tagged with this concept."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_related_entities(concept_id)


@router.post("/concepts/{concept_id}/tags", status_code=201)
async def tag_entity(concept_id: str, body: TagRequest):
    """Tag an entity (idea/news/spec/task) with this concept."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.tag_entity(
        concept_id=concept_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        tagged_by=body.tagged_by,
    )


@router.delete("/concepts/{concept_id}/tags/{entity_type}/{entity_id}", status_code=204)
async def untag_entity(concept_id: str, entity_type: str, entity_id: str):
    """Remove a concept tag from an entity."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    removed = concept_service.untag_entity(concept_id, entity_type, entity_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Tag not found")
