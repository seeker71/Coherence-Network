"""Concepts router — CRUD for the Living Codex ontology."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any

from app.models.translation import ConceptTranslationResponse, TranslationLens
from app.services import concept_service, concept_translation_service

router = APIRouter()


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


@router.get("/concepts/{concept_id}/translate", response_model=ConceptTranslationResponse)
async def translate_concept_view(
    concept_id: str,
    from_lens: TranslationLens = Query(..., alias="from"),
    to_lens: TranslationLens = Query(..., alias="to"),
):
    """Reframe one ontology concept toward another lens (parent/keyword bridges)."""
    if from_lens == to_lens:
        raise HTTPException(status_code=400, detail="from and to must differ")
    result = concept_translation_service.translate_concept(
        concept_id, from_lens.value, to_lens.value
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return result


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Get a single concept by ID."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept


@router.get("/concepts/{concept_id}/edges")
async def get_concept_edges(concept_id: str):
    """Get edges for a concept."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_concept_edges(concept_id)


@router.post("/concepts/{concept_id}/edges")
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
