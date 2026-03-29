"""Concepts router — CRUD for the Living Codex ontology (184 concepts, 46 rel types, 53 axes)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services import concept_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ConceptCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    type_id: str = "codex.ucore.user"
    level: int = 0
    keywords: list[str] = []
    parent_concepts: list[str] = []
    child_concepts: list[str] = []
    axes: list[str] = []


class ConceptPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    axes: list[str] | None = None


class EdgeCreate(BaseModel):
    from_id: str
    to_id: str
    relationship_type: str
    created_by: str = "unknown"


class ConceptTagBody(BaseModel):
    concept_ids: list[str]


class PlainConceptSuggest(BaseModel):
    """Plain-language concept submission for non-technical contributors."""
    plain_text: str = Field(..., min_length=2, max_length=500, description="Your idea in plain language")
    domains: list[str] = Field(default_factory=list, description="Domains you know (e.g. 'ecology', 'music')")
    contributor: str = Field(default="anonymous", description="Your name or handle")


class PlainConceptSubmit(BaseModel):
    """Submit a concept from the suggestion output (may be modified by contributor)."""
    id: str
    name: str
    description: str = ""
    type_id: str = "codex.ucore.user"
    level: int = 3
    keywords: list[str] = []
    domains: list[str] = []
    parent_concepts: list[str] = []
    child_concepts: list[str] = []
    axes: list[str] = []
    contributor: str = "anonymous"


# ---------------------------------------------------------------------------
# Core CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/concepts")
async def list_concepts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List concepts from the ontology (paged)."""
    return concept_service.list_concepts(limit=limit, offset=offset)


@router.post("/concepts", status_code=201)
async def create_concept(body: ConceptCreate):
    """Create a new user-defined concept (extends the ontology)."""
    if concept_service.get_concept(body.id):
        raise HTTPException(status_code=409, detail=f"Concept '{body.id}' already exists")
    return concept_service.create_concept(body.model_dump())


@router.get("/concepts/search")
async def search_concepts(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Full-text search concepts by name or description."""
    return concept_service.search_concepts(query=q, limit=limit)


@router.get("/concepts/stats")
async def concept_stats():
    """Get ontology statistics: concept count, relationship types, axes, user edges."""
    return concept_service.get_stats()


@router.get("/concepts/relationships")
async def list_relationships():
    """List all 46 relationship types from the Living Codex ontology."""
    return concept_service.list_relationship_types()


@router.get("/concepts/axes")
async def list_axes():
    """List all 53 ontology axes."""
    return concept_service.list_axes()


@router.get("/concepts/garden")
async def get_garden_view(
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Garden view — simplified cards layout for non-technical contributors.

    Returns concepts as cards grouped by domain, with only human-readable fields.
    This is what non-technical contributors see; technical peers see the graph.
    """
    return concept_service.get_garden_view(limit=limit)


@router.get("/concepts/domain/{domain}")
async def get_concepts_by_domain(
    domain: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get concepts tagged with a specific domain (e.g. 'ecology', 'music', 'systems')."""
    return concept_service.list_concepts_by_domain(domain=domain, limit=limit)


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Get a single concept by ID with full metadata."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept


@router.patch("/concepts/{concept_id}")
async def patch_concept(concept_id: str, body: ConceptPatch):
    """Patch mutable fields of a concept (name, description, keywords, axes)."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.patch_concept(concept_id, body.model_dump(exclude_none=True))


@router.delete("/concepts/{concept_id}", status_code=204)
async def delete_concept(concept_id: str):
    """Delete a user-created concept. Core ontology concepts cannot be deleted."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    result = concept_service.delete_concept(concept_id)
    if result.get("error"):
        raise HTTPException(status_code=403, detail=result["error"])


# ---------------------------------------------------------------------------
# Edge endpoints
# ---------------------------------------------------------------------------

@router.get("/concepts/{concept_id}/edges")
async def get_concept_edges(concept_id: str):
    """Get all user-defined edges for a concept (incoming and outgoing)."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_concept_edges(concept_id)


@router.post("/concepts/{concept_id}/edges", status_code=201)
async def create_edge(concept_id: str, body: EdgeCreate):
    """Create a typed relationship edge from this concept to another."""
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
# Tagging: attach concepts to ideas / specs
# ---------------------------------------------------------------------------

@router.get("/concepts/{concept_id}/related")
async def get_related_items(concept_id: str):
    """Get ideas and specs tagged with this concept."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_related_items(concept_id)


@router.post("/ideas/{idea_id}/concepts")
async def tag_idea_with_concepts(idea_id: str, body: ConceptTagBody):
    """Tag an idea with one or more concepts."""
    missing = [cid for cid in body.concept_ids if not concept_service.get_concept(cid)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Concepts not found: {missing}")
    return concept_service.tag_entity(entity_type="idea", entity_id=idea_id, concept_ids=body.concept_ids)


@router.get("/ideas/{idea_id}/concepts")
async def get_idea_concepts(idea_id: str):
    """Get concepts tagged on an idea."""
    return concept_service.get_entity_concepts(entity_type="idea", entity_id=idea_id)


@router.post("/specs/{spec_id}/concepts")
async def tag_spec_with_concepts(spec_id: str, body: ConceptTagBody):
    """Tag a spec with one or more concepts."""
    missing = [cid for cid in body.concept_ids if not concept_service.get_concept(cid)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Concepts not found: {missing}")
    return concept_service.tag_entity(entity_type="spec", entity_id=spec_id, concept_ids=body.concept_ids)


@router.get("/specs/{spec_id}/concepts")
async def get_spec_concepts(spec_id: str):
    """Get concepts tagged on a spec."""
    return concept_service.get_entity_concepts(entity_type="spec", entity_id=spec_id)


# ---------------------------------------------------------------------------
# Accessible ontology: plain-language contribution endpoints (POST only — GETs above)
# ---------------------------------------------------------------------------

@router.post("/concepts/suggest")
async def suggest_concept(body: PlainConceptSuggest):
    """
    Accessible ontology entry point for non-technical contributors.

    Submit an idea in plain language — the system finds where it fits in the
    ontology, suggests relationships, and returns a ready-to-submit concept body.
    No graph theory knowledge required.

    Example: {"plain_text": "the way rivers remember their paths through stone",
               "domains": ["ecology", "memory"], "contributor": "alice"}
    """
    return concept_service.suggest_concept_placement(
        plain_text=body.plain_text,
        domains=body.domains,
        contributor=body.contributor,
    )


@router.post("/concepts/submit", status_code=201)
async def submit_plain_concept(body: PlainConceptSubmit):
    """
    Commit a plain-language concept to the ontology.

    Accepts the output of /concepts/suggest (possibly refined by the contributor).
    Auto-creates relationship edges to related concepts.
    """
    if concept_service.get_concept(body.id):
        raise HTTPException(status_code=409, detail=f"Concept '{body.id}' already exists")
    return concept_service.create_concept_from_plain(body.model_dump())
