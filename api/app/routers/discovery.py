"""Discovery router — Serendipity Discovery feed endpoints.

Provides a unified discovery experience combining resonant ideas,
peers, cross-domain bridges, news, and ontology growth edges into
a single personalized feed per contributor.

Endpoints:
    GET /api/discover/{contributor_id}          — personalized discovery feed
    GET /api/discover/{contributor_id}/profile   — belief profile summary
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from app.models.discovery import DiscoveryFeed
from app.services import discovery_service

router = APIRouter()


@router.get(
    "/discover/{contributor_id}",
    response_model=DiscoveryFeed,
    summary="Personalized discovery feed",
    tags=["discovery"],
)
async def get_discovery_feed(
    contributor_id: str,
    limit: int = Query(30, ge=1, le=100, description="Max items to return"),
) -> DiscoveryFeed:
    """Return a personalized discovery feed for the given contributor.

    Combines five signal sources — resonant ideas, resonant peers,
    cross-domain bridges, resonant news, and ontology growth edges —
    into a single feed sorted by relevance score.

    If the contributor has no belief profile yet, the feed falls back
    to general popularity-based results.
    """
    return discovery_service.build_discovery_feed(contributor_id, limit=limit)


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
