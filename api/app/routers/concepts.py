"""Concepts router — CRUD for the ontology. All data lives in graph DB."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from typing import Any

from app.services import (
    concept_auto_tagger,
    concept_service,
    concept_voice_service,
    translate_service,
    translation_cache_service as translation_cache,
    translator_service,
)
from app.services.localized_errors import caller_lang, localize
from app.services.translate_service import TranslateLens

router = APIRouter()


# ---------------------------------------------------------------------------
# Living-Collective concept-name glossary (inline).
# LibreTranslate sometimes returns single-word titles unchanged (treats them
# as proper nouns). This seed map gives names that translate beautifully in
# the community's own vocabulary. Consulted as a post-process after the
# snippet-translate call in the single-concept endpoint below.
# ---------------------------------------------------------------------------
_CONCEPT_NAME_GLOSSARY: dict[str, dict[str, str]] = {
    "de": {
        "Nourishing": "Nährend",
        "Community": "Gemeinschaft",
        "Ritual": "Ritual",
        "Stillness": "Stille",
        "Longing": "Sehnen",
        "Belonging": "Zugehörigkeit",
        "Holding": "Halten",
        "Listening": "Lauschen",
        "Remembering": "Erinnern",
        "Tending": "Hüten",
        "Ripening": "Reifen",
        "Wholeness": "Ganzheit",
        "Space": "Raum",
        "Energy": "Energie",
        "Presence": "Gegenwart",
        "Attunement": "Einstimmung",
        "Resonance": "Resonanz",
        "Emergence": "Entfalten",
        "Weaving": "Weben",
    },
    "es": {
        "Nourishing": "Nutritivo",
        "Community": "Comunidad",
        "Ritual": "Ritual",
        "Stillness": "Quietud",
        "Belonging": "Pertenencia",
        "Listening": "Escucha",
        "Tending": "Cuidar",
        "Wholeness": "Plenitud",
        "Energy": "Energía",
        "Presence": "Presencia",
        "Resonance": "Resonancia",
        "Weaving": "Tejer",
    },
    "id": {
        "Nourishing": "Menyuburkan",
        "Community": "Komunitas",
        "Belonging": "Kepemilikan",
        "Listening": "Mendengarkan",
        "Wholeness": "Keutuhan",
        "Presence": "Kehadiran",
        "Resonance": "Resonansi",
    },
}


def _glossary_title(title: str, lang: str) -> str | None:
    """Look up a concept title in the LC glossary. Returns the translated
    term when found, else None (caller keeps the backend's output)."""
    if not title or not lang:
        return None
    table = _CONCEPT_NAME_GLOSSARY.get(lang) or {}
    return table.get(title.strip())


def _write_anchor_view_from_concept(concept_id: str, concept: dict[str, Any]):
    return translation_cache.write_view(
        entity_type="concept",
        entity_id=concept_id,
        lang=translator_service.DEFAULT_LOCALE,
        content_title=str(concept.get("name") or concept_id),
        content_description=str(concept.get("description") or ""),
        content_markdown=str(concept.get("story_content") or concept.get("details") or ""),
        author_type=translation_cache.AUTHOR_TYPE_ORIGINAL_HUMAN,
        notes="Auto-created from legacy concept fields so on-demand i18n has an anchor.",
    )


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


class StoryPatch(BaseModel):
    """Update a concept's living story content."""
    story_content: str | None = None
    visuals: list[dict[str, str]] | None = None  # [{prompt, caption}]


class ViewUpsert(BaseModel):
    """Upsert a language view of a concept. Used by the KB sync pass and by
    community contributors editing or translating.

    author_type:
      - original_human: this view was authored directly in ``lang`` (no source)
      - translation_human: this view was attuned from ``translated_from_lang``
        by a human
      - translation_machine: this view was attuned by a machine backend

    ``translated_from_lang`` and ``translated_from_hash`` are required for the
    two translation types so the anchor logic can detect staleness when the
    origin view moves.
    """
    lang: str
    content_title: str = ""
    content_description: str = ""
    content_markdown: str = ""
    author_type: str = "translation_human"
    author_id: str | None = None
    translator_model: str | None = None
    translated_from_lang: str | None = None
    translated_from_hash: str | None = None
    notes: str | None = None


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


def _format_profile(entity_id: str, views: dict) -> dict:
    import math as _m
    from app.services import frequency_profile_service
    return {
        "entity_id": entity_id,
        "dimensions": sum(len(v) for v in views.values()),
        "magnitude": round(frequency_profile_service.magnitude(views), 4),
        "hash": frequency_profile_service.profile_hash(entity_id),
        "top": frequency_profile_service.top_dimensions(views, n=15),
        "views": {
            name: {
                "dimensions": len(view),
                "magnitude": round(_m.sqrt(sum(v * v for v in view.values())), 4) if view else 0.0,
            }
            for name, view in views.items()
        },
    }


class FrequencyScoreRequest(BaseModel):
    """Request body for frequency scoring."""
    text: str = Field(..., min_length=1, description="Text to score for living vs institutional frequency")


# ---------------------------------------------------------------------------
# Frequency scoring endpoint
# ---------------------------------------------------------------------------

@router.post("/concepts/frequency-score", summary="Score text for living vs institutional frequency")
async def frequency_score(body: FrequencyScoreRequest):
    """Score how 'alive' vs 'institutional' a piece of text reads.

    Returns 0.0 (pure institutional) to 1.0 (pure living frequency),
    with per-sentence breakdown and marker identification.
    """
    from app.services import frequency_scoring
    return frequency_scoring.score_frequency(body.text)


@router.get("/concepts/{concept_id}/frequency-profile", summary="Get the frequency profile vector for a concept")
async def get_concept_frequency_profile(concept_id: str):
    """Returns the multi-dimensional frequency profile for a concept.

    Not a single score — a vector across all concept dimensions.
    Used for resonance matching. See also GET /api/profile/{entity_id}
    for the universal version that works with any entity type.
    """
    from app.services import frequency_profile_service
    views = frequency_profile_service.get_profile(concept_id)
    if not any(views.values()):
        raise HTTPException(status_code=404, detail=f"No profile for '{concept_id}'")
    return _format_profile(concept_id, views)


@router.post("/concepts/frequency-field", summary="Token-level frequency field analysis")
async def frequency_field(body: FrequencyScoreRequest):
    """Analyze every token's frequency relative to its context.

    Returns dissonances — specific words that don't match the frequency
    of their surrounding sentence. Each dissonance includes the word,
    its signal, the context average, and the deviation.
    """
    from app.services import frequency_field
    return frequency_field.analyze_token_field(body.text)


@router.get("/concepts/{concept_id}/frequency-field", summary="Full frequency field analysis for a concept")
async def concept_frequency_field(concept_id: str):
    """Analyze a concept's complete frequency field.

    Returns token map, dissonances, top living/institutional tokens,
    and edit suggestions.
    """
    from app.services import frequency_field
    result = frequency_field.analyze_concept(concept_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/concepts/frequency-edit", summary="Find and fix institutional-frequency phrases")
async def frequency_edit(body: FrequencyScoreRequest):
    """Find institutional-frequency phrases and suggest living replacements.

    Returns before/after scores, list of changes, and the improved text.
    """
    from app.services import frequency_editor
    return frequency_editor.edit_and_score(body.text)


# ---------------------------------------------------------------------------
# Core CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/concepts", summary="List concepts from the ontology (paged)")
async def list_concepts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    lang: str | None = Query(None, description="Target language for concept name/description."),
):
    """List concepts from the ontology (paged)."""
    from app.services.locale_projection import resolve_caller_lang
    target_lang = resolve_caller_lang(request, lang)
    result = concept_service.list_concepts(limit=limit, offset=offset)
    if target_lang and translator_service.is_supported(target_lang) and target_lang != translator_service.DEFAULT_LOCALE:
        items = result.get("items") or result.get("concepts") or []
        for c in items:
            cid = c.get("id") if isinstance(c, dict) else None
            if not cid:
                continue
            rec = translation_cache.canonical_view("concept", cid, target_lang)
            if rec:
                if rec.content_title:
                    c["name"] = rec.content_title
                if rec.content_description:
                    c["description"] = rec.content_description
                continue
            # Fall back to live snippet translation (cached) when no
            # canonical view exists yet.
            src_title = c.get("name", "")
            src_desc = c.get("description", "")
            if src_title or src_desc:
                t_title, t_desc = translator_service.translate_snippet(
                    src_title, src_desc, source_lang="en", target_lang=target_lang,
                )
                if t_title:
                    c["name"] = t_title
                if t_desc:
                    c["description"] = t_desc
    return result


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
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    lang: str | None = Query(None, description="Target language view. When set and a canonical view exists, each concept's name/description come from that view."),
) -> dict:
    """Return concepts filtered by domain (e.g. 'living-collective').

    When ``lang`` is supplied (or Accept-Language resolves to a supported
    locale), each concept's name and description are replaced with the
    canonical view for that language where one exists. Concepts without a
    view in the target language keep their anchor content.
    """
    from app.services.locale_projection import resolve_caller_lang
    target_lang = resolve_caller_lang(request, lang)
    result = concept_service.list_concepts_by_domain(domain, limit=limit)
    if target_lang and translator_service.is_supported(target_lang) and target_lang != translator_service.DEFAULT_LOCALE:
        items = result.get("items") or result.get("concepts") or []
        for c in items:
            cid = c.get("id") if isinstance(c, dict) else None
            if not cid:
                continue
            rec = translation_cache.canonical_view("concept", cid, target_lang)
            if rec:
                if rec.content_title:
                    c["name"] = rec.content_title
                if rec.content_description:
                    c["description"] = rec.content_description
                continue
            # No canonical view for this concept yet — fall back to a live
            # snippet translation so the listing reads in the viewer's tongue.
            # Cached in-process so repeat requests are cheap.
            src_title = c.get("name", "")
            src_desc = c.get("description", "")
            if src_title or src_desc:
                t_title, t_desc = translator_service.translate_snippet(
                    src_title, src_desc, source_lang="en", target_lang=target_lang,
                )
                if t_title:
                    c["name"] = t_title
                if t_desc:
                    c["description"] = t_desc
    return result


@router.get("/concepts/garden", summary="Concept garden — all concepts grouped by domain")
async def concept_garden(limit: int = Query(500, ge=1, le=1000)) -> dict:
    """Group concepts by domain for the concept garden visualization."""
    return concept_service.get_garden_view(limit=limit)


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


@router.patch("/concepts/{concept_id}/story", summary="Update a concept's living story content and visuals")
async def update_story(concept_id: str, body: StoryPatch):
    """Update a concept's living story content.

    If visuals are not explicitly provided, they are auto-extracted from
    inline ``![caption](visuals:prompt)`` entries in story_content.

    Note: this endpoint writes to the graph-node's unlocalized story_content
    for backward compatibility. To author or update a specific language view
    (including English as a view), use ``POST /api/concepts/{id}/views``.
    """
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.update_story(
        concept_id,
        story_content=body.story_content,
        visuals=body.visuals,
    )


@router.post("/concepts/{concept_id}/views", summary="Upsert a language view of a concept")
async def upsert_concept_view(concept_id: str, body: ViewUpsert, request: Request):
    """Upsert a language view for a concept. Every language is equal — this
    endpoint accepts the view ``en``, ``de``, ``es``, ``id`` on the same
    footing. The anchor (freshest human-touched view) is discovered at read
    time, not hardcoded.

    Called by the KB sync pass (reading ``docs/vision-kb/concepts/{id}.{lang}.md``)
    and by community contributors authoring or attuning directly. The new row
    becomes canonical immediately; any prior canonical row for the same
    (concept, lang) is preserved as superseded so the history is visible.
    """
    err_lang = caller_lang(request, body.lang if translator_service.is_supported(body.lang) else None)
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=localize("concept_not_found", err_lang, id=concept_id))
    if not translator_service.is_supported(body.lang):
        raise HTTPException(status_code=400, detail=localize("unsupported_locale", err_lang, code=body.lang))
    if body.author_type not in {
        translation_cache.AUTHOR_TYPE_ORIGINAL_HUMAN,
        translation_cache.AUTHOR_TYPE_TRANSLATION_HUMAN,
        translation_cache.AUTHOR_TYPE_TRANSLATION_MACHINE,
    }:
        raise HTTPException(status_code=400, detail=localize("invalid_author_type", err_lang, type=body.author_type))

    if body.author_type != translation_cache.AUTHOR_TYPE_ORIGINAL_HUMAN:
        if not body.translated_from_lang or not body.translated_from_hash:
            raise HTTPException(
                status_code=400,
                detail=localize("translated_from_required", err_lang),
            )

    rec = translation_cache.write_view(
        entity_type="concept",
        entity_id=concept_id,
        lang=body.lang,
        content_title=body.content_title,
        content_description=body.content_description,
        content_markdown=body.content_markdown,
        author_type=body.author_type,
        author_id=body.author_id,
        translator_model=body.translator_model,
        translated_from_lang=body.translated_from_lang,
        translated_from_hash=body.translated_from_hash,
        notes=body.notes,
    )
    return {
        "id": rec.id,
        "concept_id": concept_id,
        "lang": rec.lang,
        "content_hash": rec.content_hash,
        "author_type": rec.author_type,
        "translated_from_lang": rec.translated_from_lang,
        "translated_from_hash": rec.translated_from_hash,
        "status": rec.status,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


@router.get("/concepts/{concept_id}/views", summary="List all language views for a concept (with anchor + staleness)")
async def list_concept_views(concept_id: str):
    """Every canonical view for a concept, plus which one is the anchor and
    which are stale. The edit UI uses this to show the full language map.
    """
    if not concept_service.get_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")

    views = translation_cache.all_canonical_views("concept", concept_id)
    anchor = translation_cache.find_anchor(views)
    return {
        "concept_id": concept_id,
        "anchor_lang": anchor.lang if anchor else None,
        "views": [
            {
                "lang": v.lang,
                "author_type": v.author_type,
                "content_hash": v.content_hash,
                "translated_from_lang": v.translated_from_lang,
                "translated_from_hash": v.translated_from_hash,
                "is_anchor": anchor is not None and v.id == anchor.id,
                "stale": translation_cache.is_stale(v, anchor),
                "updated_at": v.updated_at.isoformat() if v.updated_at else None,
            }
            for v in views
        ],
    }


@router.get("/concepts/{concept_id}/views/{lang}/history", summary="History of a single language view (canonical + superseded)")
async def list_view_history(concept_id: str, lang: str):
    if not translator_service.is_supported(lang):
        raise HTTPException(status_code=400, detail=f"Unsupported locale '{lang}'")
    rows = translation_cache.list_history("concept", concept_id, lang)
    return {
        "concept_id": concept_id,
        "lang": lang,
        "views": [
            {
                "id": r.id,
                "status": r.status,
                "author_type": r.author_type,
                "author_id": r.author_id,
                "content_hash": r.content_hash,
                "translated_from_lang": r.translated_from_lang,
                "translated_from_hash": r.translated_from_hash,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "notes": r.notes,
            }
            for r in rows
        ],
    }


@router.post("/concepts/{concept_id}/visuals/regenerate", summary="Regenerate story and gallery images for a concept")
async def regenerate_visuals(concept_id: str, force: bool = Query(False, description="Re-download even if file exists")):
    """Trigger image generation for a single concept.

    Downloads images from Pollinations using deterministic seeds.
    Returns the list of generated/skipped files.
    """
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return concept_service.regenerate_visuals(concept_id, concept, force=force)


@router.get("/concepts/{concept_id}", summary="Get a single concept by ID with full metadata")
async def get_concept(
    concept_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    lang: str | None = Query(
        default=None,
        description="Optional language view (en, de, es, id). When set, the concept is "
                    "rendered in that language view if one exists. A language_meta block "
                    "declares which view is the anchor (freshest human-touched expression) "
                    "and whether the returned view is stale relative to it. "
                    "If no view exists yet and an LLM backend is registered, a background "
                    "attunement is enqueued and the next request will be served from cache.",
    ),
):
    """Get a single concept by ID.

    When ``lang`` is supplied and a canonical view exists for that language,
    the concept's ``name``, ``description``, and ``story_content`` come from
    that view. ``language_meta`` exposes:

    - ``lang``: what was returned
    - ``is_anchor``: true if this view is the most recently human-touched
    - ``stale``: true if this view was translated from an earlier state of
      the anchor and needs re-attunement
    - ``anchor``: the anchor view's lang + updated_at, so UI can offer
      "read the anchor in German" if a stale English view is served
    - ``available_langs``: every language that has a canonical view
    """
    err_lang = caller_lang(request, lang)
    concept = concept_service.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=localize("concept_not_found", err_lang, id=concept_id))

    views = translation_cache.all_canonical_views("concept", concept_id)
    anchor = translation_cache.find_anchor(views)

    # When no views exist yet, fall back to the base concept (legacy unlocalized data)
    if not views:
        if lang and lang != translator_service.DEFAULT_LOCALE:
            if not translator_service.is_supported(lang):
                raise HTTPException(status_code=400, detail=localize("unsupported_locale", err_lang, code=lang))
            if translator_service.has_backend():
                try:
                    anchor = _write_anchor_view_from_concept(concept_id, concept)
                    translated = translator_service.attune_from_anchor(
                        entity_type="concept",
                        entity_id=concept_id,
                        target_lang=lang,
                    )
                    if translated is not None:
                        concept["name"] = translated.content_title or concept.get("name")
                        concept["description"] = translated.content_description or concept.get("description")
                        concept["story_content"] = translated.content_markdown or concept.get("story_content")
                        concept["language_meta"] = {
                            "lang": lang,
                            "is_anchor": False,
                            "stale": False,
                            "available_langs": sorted([translator_service.DEFAULT_LOCALE, lang]),
                            "pending": False,
                            "anchor": {
                                "lang": anchor.lang,
                                "author_type": anchor.author_type,
                                "updated_at": anchor.updated_at.isoformat() if anchor.updated_at else None,
                                "content_hash": anchor.content_hash,
                            },
                        }
                        return concept
                except Exception:
                    pass
            # Snippet-fallback: even before the background attunement lands,
            # translate the name + description synchronously so a first-time
            # visitor in this language doesn't see English content. The
            # translator backend memoizes, so repeated calls are cheap.
            # Single-word concept names get a glossary override because the
            # backend (LibreTranslate) often returns them unchanged.
            src_title = concept.get("name", "")
            src_desc = concept.get("description", "")
            if src_title or src_desc:
                try:
                    t_title, t_desc = translator_service.translate_snippet(
                        src_title, src_desc,
                        source_lang=translator_service.DEFAULT_LOCALE,
                        target_lang=lang,
                    )
                    # Glossary wins for known LC concept names — the community
                    # vocabulary is the ground truth, not the backend.
                    gloss = _glossary_title(src_title, lang)
                    if gloss:
                        concept["name"] = gloss
                    elif t_title:
                        concept["name"] = t_title
                    if t_desc:
                        concept["description"] = t_desc
                except Exception:
                    pass
            concept["language_meta"] = {
                "lang": lang,
                "is_anchor": False,
                "stale": False,
                "available_langs": [],
                "pending": True,
                "anchor": None,
            }
        return concept

    # Decide which view to return
    target_lang = lang or (anchor.lang if anchor else translator_service.DEFAULT_LOCALE)
    if lang and not translator_service.is_supported(lang):
        raise HTTPException(status_code=400, detail=localize("unsupported_locale", err_lang, code=lang))

    chosen = next((v for v in views if v.lang == target_lang), None)
    pending = chosen is None

    # On-demand attunement: if the view is missing or stale and a backend is
    # configured, enqueue a translation. The current request still serves the
    # anchor (no latency penalty); the next request reads from the cache.
    if (
        (pending or (chosen and translation_cache.is_stale(chosen, anchor)))
        and target_lang != translator_service.DEFAULT_LOCALE
        and translator_service.has_backend()
    ):
        background_tasks.add_task(
            translator_service.attune_from_anchor,
            entity_type="concept",
            entity_id=concept_id,
            target_lang=target_lang,
        )

    if chosen is not None:
        concept["name"] = chosen.content_title or concept.get("name")
        concept["description"] = chosen.content_description or concept.get("description")
        concept["story_content"] = chosen.content_markdown or concept.get("story_content")
    elif target_lang != translator_service.DEFAULT_LOCALE:
        # No canonical view in the target lang yet — synchronously translate
        # name + description so the visitor meets the concept in her language
        # before the background attunement finishes. Cached by the translator.
        # Single-word concept names get a glossary override because the
        # backend (LibreTranslate) often returns them unchanged.
        src_title = concept.get("name", "")
        src_desc = concept.get("description", "")
        if src_title or src_desc:
            try:
                t_title, t_desc = translator_service.translate_snippet(
                    src_title, src_desc,
                    source_lang=translator_service.DEFAULT_LOCALE,
                    target_lang=target_lang,
                )
                gloss = _glossary_title(src_title, target_lang)
                if gloss:
                    concept["name"] = gloss
                elif t_title:
                    concept["name"] = t_title
                if t_desc:
                    concept["description"] = t_desc
            except Exception:
                pass

    concept["language_meta"] = {
        "lang": target_lang,
        "is_anchor": chosen is not None and anchor is not None and chosen.id == anchor.id,
        "stale": chosen is not None and translation_cache.is_stale(chosen, anchor),
        "pending": pending,
        "available_langs": sorted([v.lang for v in views]),
        "anchor": (
            {
                "lang": anchor.lang,
                "author_type": anchor.author_type,
                "updated_at": anchor.updated_at.isoformat() if anchor.updated_at else None,
                "content_hash": anchor.content_hash,
            }
            if anchor
            else None
        ),
    }
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


# ---------------------------------------------------------------------------
# Community voices — readers offering their lived experience
# ---------------------------------------------------------------------------


class ConceptVoiceIn(BaseModel):
    author_name: str
    body: str
    locale: str = "en"
    location: str | None = None
    author_id: str | None = None
    # Short opaque client-supplied token so two visitors sharing a
    # display name get distinct contributor_ids during auto-graduation.
    device_fingerprint: str | None = None
    # Chain lineage: the contributor_id of whoever invited this
    # person here. Recorded on the new contributor node at
    # auto-graduation so the invite chain is queryable in the graph.
    invited_by: str | None = None


@router.post(
    "/concepts/{concept_id}/voices",
    status_code=201,
    summary="Offer a lived-experience voice on this concept",
)
async def add_concept_voice(concept_id: str, body: ConceptVoiceIn, request: Request) -> dict:
    """Open write-back surface on any concept. Trust by default — no moderation
    queue. A voice is a short testimony: "this is how we live it here".

    Soft-identity auto-graduation: if ``author_id`` is omitted, the service
    creates a contributor node keyed by ``author_name`` + ``device_fingerprint``
    and returns ``author_id`` in the response. The web client writes it back
    to ``cc-contributor-id`` so the visitor is now a real contributor in
    every subsequent surface — no signup screen involved.

    When ``invited_by`` is present, the chain lineage is recorded on the
    new contributor node so the invite graph is preserved server-side.
    """
    if not concept_service.get_concept(concept_id):
        raise HTTPException(
            status_code=404,
            detail=localize("concept_not_found", caller_lang(request), id=concept_id),
        )
    try:
        return concept_voice_service.add_voice(
            concept_id=concept_id,
            author_name=body.author_name,
            body=body.body,
            locale=body.locale,
            author_id=body.author_id,
            location=body.location,
            device_fingerprint=body.device_fingerprint,
            invited_by=body.invited_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/concepts/{concept_id}/voices",
    summary="List lived-experience voices for a concept",
)
async def list_concept_voices(concept_id: str, limit: int = Query(50, ge=1, le=200)) -> dict:
    voices = concept_voice_service.list_voices(concept_id, limit=limit)
    return {"concept_id": concept_id, "voices": voices, "total": len(voices)}


@router.get(
    "/concepts/voices/recent",
    summary="Recent voices across all concepts — the community pulse of lived experience",
)
async def recent_concept_voices(limit: int = Query(20, ge=1, le=100)) -> dict:
    voices = concept_voice_service.recent_voices(limit=limit)
    return {"voices": voices, "total": len(voices)}


class VoiceRipenIn(BaseModel):
    title: str | None = Field(
        None,
        description="Optional override — default derives from the voice's first sentence",
    )
    body: str | None = Field(
        None,
        description="Optional override — default uses the voice body verbatim",
    )
    author_id: str | None = None


@router.post(
    "/concepts/voices/{voice_id}/propose",
    status_code=201,
    summary="Ripen a voice into a proposal the collective can vote on",
    description=(
        "Any reader can lift a voice they find worth offering to the "
        "collective. The proposal carries the voice's text forward and "
        "links back to the concept where it was spoken. Idempotent."
    ),
)
async def ripen_voice(voice_id: str, payload: VoiceRipenIn | None = None) -> dict:
    payload = payload or VoiceRipenIn()
    try:
        return concept_voice_service.ripen_into_proposal(
            voice_id,
            title=payload.title,
            body=payload.body,
            author_id=payload.author_id,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
