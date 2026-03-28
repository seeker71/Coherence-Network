"""Concepts router — CRUD for the Living Codex ontology."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Optional

from app.services import concept_service

router = APIRouter()


class ConceptCreate(BaseModel):
    id: str
    name: str
    description: str
    typeId: Optional[str] = None
    level: Optional[int] = 2
    keywords: Optional[list[str]] = None
    axes: Optional[list[str]] = None
    userDefined: bool = True


class ConceptPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    typeId: Optional[str] = None
    level: Optional[int] = None
    keywords: Optional[list[str]] = None
    axes: Optional[list[str]] = None


class EdgeCreate(BaseModel):
    from_id: str
    to_id: str
    relationship_type: str
    created_by: str = "unknown"


@router.get("/concepts")
async def list_concepts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List concepts from the ontology."""
    return concept_service.list_concepts(limit=limit, offset=offset)


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
    """Create a new user-defined concept."""
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
    """Update a user-defined concept."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    if not concept.get("userDefined"):
        raise HTTPException(status_code=403, detail="Built-in ontology concepts cannot be modified")
    return concept_service.patch_concept(concept_id, body.model_dump(exclude_none=True))


@router.delete("/concepts/{concept_id}", status_code=204)
async def delete_concept(concept_id: str):
    """Delete a user-defined concept."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    if not concept.get("userDefined"):
        raise HTTPException(status_code=403, detail="Built-in ontology concepts cannot be deleted")
    concept_service.delete_concept(concept_id)


@router.get("/concepts/{concept_id}/edges")
async def get_concept_edges(concept_id: str):
    """Get edges for a concept."""
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


@router.get("/concepts/{concept_id}/related")
async def get_related(concept_id: str):
    """Get ideas and specs tagged with this concept."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_related_items(concept_id)
