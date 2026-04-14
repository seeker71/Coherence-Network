"""Concepts router — CRUD for the ontology. All data lives in graph DB."""

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Any

from app.services import concept_auto_tagger, concept_service, translate_service
from app.services.translate_service import TranslateLens

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

@router.get("/concepts", summary="List concepts from the ontology (paged)")
async def list_concepts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List concepts from the ontology (paged)."""
    return concept_service.list_concepts(limit=limit, offset=offset)


@router.post("/concepts", status_code=201, summary="Create a new user-defined concept (extends the ontology)")
async def create_concept(body: ConceptCreate):
    """Create a new user-defined concept (extends the ontology)."""
    if concept_service.get_concept(body.id):
        raise HTTPException(status_code=409, detail=f"Concept '{body.id}' already exists")
    return concept_service.create_concept(body.model_dump())


@router.get("/concepts/search", summary="Full-text search concepts by name or description")
async def search_concepts(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Full-text search concepts by name or description."""
    return concept_service.search_concepts(query=q, limit=limit)


@router.get("/concepts/stats", summary="Get ontology statistics: concept count, relationship types, axes, user edges")
async def concept_stats():
    """Get ontology statistics: concept count, relationship types, axes, user edges."""
    return concept_service.get_stats()


@router.post("/concepts/auto-tag-all", summary="Run concept auto-tagging on every non-internal idea in the portfolio")
async def auto_tag_all_ideas() -> dict[str, Any]:
    """Run concept auto-tagging on every non-internal idea in the portfolio.

    Matches each idea's name + description against the Living Codex concepts
    via keyword overlap scoring and tags each idea with its top matches.
    """
    return concept_auto_tagger.tag_all_ideas()


@router.get("/concepts/domain/{domain}", summary="List concepts belonging to a specific domain")
async def list_concepts_by_domain(
    domain: str,
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    """Return concepts filtered by domain (e.g. 'living-collective').

    Each concept carries a `domains` array; this endpoint returns those
    whose domains include the requested value. Results include the
    concept hierarchy (level 0-3) and all metadata.
    """
    result = concept_service.list_concepts_by_domain(domain, limit=limit)
    return result


@router.get("/concepts/communities", summary="List all aligned communities")
async def list_communities(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Return community nodes from the graph DB."""
    from app.services import graph_service
    return graph_service.list_nodes(type="community", limit=limit)


@router.get("/concepts/communities/{community_id}", summary="Get a single community by ID")
async def get_community(community_id: str) -> dict:
    """Return a single community node with all properties."""
    from app.services import graph_service
    node = graph_service.get_node(community_id)
    if not node:
        raise HTTPException(status_code=404, detail="Community not found")
    return node


@router.get("/concepts/scenes", summary="List all life scenes")
async def list_scenes(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Return scene nodes — the visual moments of daily community life."""
    from app.services import graph_service
    return graph_service.list_nodes(type="scene", limit=limit)


@router.get("/concepts/stories", summary="List all living stories")
async def list_stories(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Return story nodes — immersive narratives of specific people and moments."""
    from app.services import graph_service
    return graph_service.list_nodes(type="story", limit=limit)


@router.get("/concepts/practices", summary="List aligned practices and traditions")
async def list_practices(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Return practice nodes — traditions that carry pieces of the vision."""
    from app.services import graph_service
    return graph_service.list_nodes(type="practice", limit=limit)


@router.get("/concepts/networks", summary="List aligned networks")
async def list_networks(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Return network-org nodes — organizations connecting communities."""
    from app.services import graph_service
    return graph_service.list_nodes(type="network-org", limit=limit)


@router.get("/concepts/domain/{domain}/vision-data", summary="Assembled data for the vision hub page")
async def get_vision_data(domain: str) -> dict:
    """Return a pre-assembled payload for the vision hub page.

    Includes root concepts (level 0-1 with visual_path), emerging visions
    (level 2 with lc-v- prefix), and gallery configuration.
    """
    all_lc = concept_service.list_concepts_by_domain(domain, limit=200)
    items = all_lc.get("items", [])

    sections = [c for c in items if c.get("level") in (0, 1) and c.get("visual_path")]
    visions = [c for c in items if c.get("id", "").startswith("lc-v-")]

    return {
        "sections": sections,
        "visions": visions,
        "total_concepts": all_lc.get("total", 0),
    }


@router.get("/concepts/relationships", summary="List ontology relationship types")
async def list_relationships():
    """List all relationship types from the graph DB."""
    return concept_service.list_relationship_types()


@router.get("/concepts/axes", summary="List ontology axes")
async def list_axes():
    """List all ontology axes from the graph DB."""
    return concept_service.list_axes()


@router.get("/concepts/{concept_id}/translate", summary="Translate a concept from one worldview lens framing to another")
async def translate_concept_view(
    concept_id: str,
    from_lens: TranslateLens = Query(..., alias="from", description="Source worldview lens"),
    to_lens: TranslateLens = Query(..., alias="to", description="Target worldview lens"),
) -> dict:
    """Translate a concept from one worldview lens framing to another.

    Not language translation — conceptual framework translation using the ontology graph.
    """
    if from_lens == to_lens:
        raise HTTPException(status_code=400, detail="'from' and 'to' lenses must be different")

    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")

    return translate_service.translate_concept(
        concept_id=concept_id,
        concept_name=concept.get("name", concept_id),
        concept_description=concept.get("description", ""),
        from_lens=from_lens.value,
        to_lens=to_lens.value,
    )


@router.get("/concepts/{concept_id}", summary="Get a single concept by ID with full metadata")
async def get_concept(concept_id: str):
    """Get a single concept by ID with full metadata."""
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept


@router.patch("/concepts/{concept_id}", summary="Patch mutable fields of a concept (name, description, keywords, axes)")
async def patch_concept(concept_id: str, body: ConceptPatch):
    """Patch mutable fields of a concept (name, description, keywords, axes)."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.patch_concept(concept_id, body.model_dump(exclude_none=True))


@router.delete("/concepts/{concept_id}", status_code=204, summary="Delete a user-created concept. Core ontology concepts cannot be deleted")
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

@router.get("/concepts/{concept_id}/edges", summary="Get all user-defined edges for a concept (incoming and outgoing)")
async def get_concept_edges(concept_id: str):
    """Get all user-defined edges for a concept (incoming and outgoing)."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_concept_edges(concept_id)


@router.post("/concepts/{concept_id}/edges", status_code=200, summary="Create a typed relationship edge from this concept to another")
async def create_edge(concept_id: str, body: EdgeCreate, response: Response):
    """Create a typed relationship edge from this concept to another."""
    source = concept_service.get_concept(concept_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    target = concept_service.get_concept(body.to_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Target concept '{body.to_id}' not found")
    if bool(source.get("userDefined")) and bool(target.get("userDefined")):
        response.status_code = 201
    return concept_service.create_edge(
        from_id=concept_id,
        to_id=body.to_id,
        rel_type=body.relationship_type,
        created_by=body.created_by,
    )


# ---------------------------------------------------------------------------
# Tagging: attach concepts to ideas / specs
# ---------------------------------------------------------------------------

@router.get("/concepts/{concept_id}/related", summary="Get ideas and specs tagged with this concept")
async def get_related_items(concept_id: str):
    """Get ideas and specs tagged with this concept."""
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.get_related_items(concept_id)


@router.post("/ideas/{idea_id}/concepts", summary="Tag an idea with one or more concepts")
async def tag_idea_with_concepts(idea_id: str, body: ConceptTagBody):
    """Tag an idea with one or more concepts."""
    missing = [cid for cid in body.concept_ids if not concept_service.get_concept(cid)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Concepts not found: {missing}")
    return concept_service.tag_entity(entity_type="idea", entity_id=idea_id, concept_ids=body.concept_ids)


@router.get("/ideas/{idea_id}/concepts", summary="Get concepts tagged on an idea")
async def get_idea_concepts(idea_id: str):
    """Get concepts tagged on an idea."""
    return concept_service.get_entity_concepts(entity_type="idea", entity_id=idea_id)


@router.post("/specs/{spec_id}/concepts", summary="Tag a spec with one or more concepts")
async def tag_spec_with_concepts(spec_id: str, body: ConceptTagBody):
    """Tag a spec with one or more concepts."""
    missing = [cid for cid in body.concept_ids if not concept_service.get_concept(cid)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Concepts not found: {missing}")
    return concept_service.tag_entity(entity_type="spec", entity_id=spec_id, concept_ids=body.concept_ids)


@router.get("/specs/{spec_id}/concepts", summary="Get concepts tagged on a spec")
async def get_spec_concepts(spec_id: str):
    """Get concepts tagged on a spec."""
    return concept_service.get_entity_concepts(entity_type="spec", entity_id=spec_id)


# ---------------------------------------------------------------------------
# Accessible ontology: plain-language contribution endpoints (POST only — GETs above)
# ---------------------------------------------------------------------------

@router.post("/concepts/suggest", summary="Accessible ontology entry point for non-technical contributors")
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


@router.post("/concepts/submit", status_code=201, summary="Commit a plain-language concept to the ontology")
async def submit_plain_concept(body: PlainConceptSubmit):
    """
    Commit a plain-language concept to the ontology.

    Accepts the output of /concepts/suggest (possibly refined by the contributor).
    Auto-creates relationship edges to related concepts.
    """
    if concept_service.get_concept(body.id):
        raise HTTPException(status_code=409, detail=f"Concept '{body.id}' already exists")
    return concept_service.create_concept_from_plain(body.model_dump())
