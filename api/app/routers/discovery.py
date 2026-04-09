"""Discovery router — Serendipity Discovery feed endpoints.

Provides a unified discovery experience combining resonant ideas,
peers, cross-domain bridges, news, and ontology growth edges into
a single personalized feed per contributor.

Endpoints:
    GET /api/discover/{contributor_id}          — personalized discovery feed
    GET /api/discover/{contributor_id}/profile   — belief profile summary
"""

from __future__ import annotations

from fastapi import APIRouter, Query

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
