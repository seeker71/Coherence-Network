"""Discovery router — Serendipity Discovery feed endpoints.

Provides a unified discovery experience combining resonant ideas,
peers, cross-domain bridges, news, and ontology growth edges into
a single personalized feed per contributor.

Endpoints:
    GET /api/discover/{contributor_id}          — personalized discovery feed
    GET /api/discover/{contributor_id}/profile   — belief profile summary
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.models.discovery import DiscoveryFeed
from app.services import discovery_service, translator_service
from app.services.locale_projection import project, resolve_caller_lang

router = APIRouter()


@router.get(
    "/discover/{contributor_id}",
    response_model=DiscoveryFeed,
    summary="Personalized discovery feed",
    tags=["discovery"],
)
async def get_discovery_feed(
    request: Request,
    contributor_id: str,
    limit: int = Query(30, ge=1, le=100, description="Max items to return"),
    lang: str | None = Query(None, description="Target language. Item titles and summaries render in this locale."),
) -> DiscoveryFeed:
    """Return a personalized discovery feed for the given contributor.

    Combines five signal sources — resonant ideas, resonant peers,
    cross-domain bridges, resonant news, and ontology growth edges —
    into a single feed sorted by relevance score.

    If the contributor has no belief profile yet, the feed falls back
    to general popularity-based results.
    """
    feed = discovery_service.build_discovery_feed(contributor_id, limit=limit)
    target_lang = resolve_caller_lang(request, lang)
    if target_lang and target_lang != "en":
        for item in feed.items:
            # Entities we own (idea, concept, spec): substitute from entity_views.
            if item.entity_type in {"idea", "concept", "spec", "contribution", "asset"}:
                project(item, item.entity_type, item.entity_id, target_lang, title_field="title", body_field="summary")
            else:
                # Transient content (news, edges): on-demand snippet translation.
                t_title, t_summary = translator_service.translate_snippet(
                    item.title or "",
                    item.summary or "",
                    source_lang="en",
                    target_lang=target_lang,
                )
                item.title = t_title
                item.summary = t_summary
    return feed


@router.get(
    "/discover/{contributor_id}/profile",
    summary="Contributor belief profile summary",
    tags=["discovery"],
)
async def get_contributor_profile_summary(
    contributor_id: str,
) -> dict:
    """Return the contributor's belief profile summary.

    Includes worldview axes, top axes, concept count, and interest tags.
    Returns a note field when no profile exists.
    """
    return discovery_service.get_profile_summary(contributor_id)


@router.post(
    "/discover/notify-bridges",
    summary="Create activity events for new cross-domain resonance bridges",
    tags=["discovery"],
)
async def notify_bridges(
    workspace_id: str = "coherence-network",
    min_coherence: float = Query(0.35, ge=0.0, le=1.0, description="Minimum coherence for bridge notification"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict:
    """Scan for new cross-domain resonance bridges and create activity events.

    For each strong cross-domain pair not yet notified, creates an activity
    event of type "cross_domain_bridge". Requires a valid API key.
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(status_code=401, detail="API key required")

    count = discovery_service.notify_new_bridges(
        workspace_id=workspace_id,
        min_coherence=min_coherence,
    )
    return {"new_bridges_notified": count, "workspace_id": workspace_id}
