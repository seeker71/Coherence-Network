"""Views router — per-contributor view tracking, analytics, discovery rewards."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from app.services import read_tracking_service
from app.services import discovery_reward_service

log = logging.getLogger(__name__)

router = APIRouter()


class PingBody(BaseModel):
    asset_id: str = Field(..., description="Concept or asset id being read, e.g. lc-sensing")
    concept_id: str | None = Field(None, description="Concept id when asset_id refers to a concept surface")
    source_page: str | None = Field(None, description="The page route the read happened on, e.g. /vision/lc-sensing")


@router.post(
    "/views/ping",
    summary="Record that a contributor met a concept or asset",
    description=(
        "Lightweight read-ping the web client fires from the browser when a "
        "visitor opens a concept page. Carries X-Contributor-Id so the read "
        "can be attributed back to the person. Anonymous reads (no header) "
        "are still recorded by session_fingerprint."
    ),
)
async def views_ping(
    body: PingBody,
    x_contributor_id: str | None = Header(default=None, alias="X-Contributor-Id"),
    x_session_fingerprint: str | None = Header(default=None, alias="X-Session-Fingerprint"),
    x_referrer_contributor_id: str | None = Header(default=None, alias="X-Referrer-Contributor-Id"),
) -> dict[str, Any]:
    event_id = read_tracking_service.record_view(
        asset_id=body.asset_id,
        concept_id=body.concept_id or (body.asset_id if body.asset_id.startswith("lc-") else None),
        contributor_id=x_contributor_id or None,
        session_fingerprint=x_session_fingerprint or None,
        source_page=body.source_page,
        referrer_contributor_id=x_referrer_contributor_id or None,
    )
    read_tracking_service.record_read(
        asset_id=body.asset_id,
        concept_id=body.concept_id or (body.asset_id if body.asset_id.startswith("lc-") else None),
        contributor_id=x_contributor_id or None,
    )
    return {"ok": True, "event_id": event_id}


@router.get(
    "/views/trail/{contributor_id:path}",
    summary="The concepts a contributor has sat with",
    description=(
        "Aggregates a contributor's read history by concept. Each entry is a "
        "concept they've opened, how many times, and when they last met it. "
        "This is what a person sees reflected back on /me — their own field-trail."
    ),
)
async def contributor_trail(
    contributor_id: str,
    limit: int = Query(10, ge=1, le=50, description="Concepts to return"),
    days: int = Query(90, ge=1, le=365, description="Lookback window in days"),
) -> dict[str, Any]:
    return read_tracking_service.get_contributor_trail(contributor_id, limit=limit, days=days)


# ---------------------------------------------------------------------------
# GET /api/views/stats/{asset_id}
# ---------------------------------------------------------------------------

@router.get(
    "/views/stats/{asset_id}",
    summary="Asset view stats",
    description="Total views, unique contributors, daily breakdown, top referrers.",
)
async def asset_view_stats(
    asset_id: str,
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> dict[str, Any]:
    return read_tracking_service.get_asset_view_stats(asset_id, days=days)


# ---------------------------------------------------------------------------
# GET /api/views/trending
# ---------------------------------------------------------------------------

@router.get(
    "/views/trending",
    summary="Trending assets",
    description="Assets ranked by view velocity over a time window.",
)
async def trending_assets(
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(7, ge=1, le=90),
) -> list[dict[str, Any]]:
    return read_tracking_service.get_trending(limit=limit, days=days)


# ---------------------------------------------------------------------------
# GET /api/views/contributor/{contributor_id}
# ---------------------------------------------------------------------------

@router.get(
    "/views/contributor/{contributor_id}",
    summary="Contributor view history",
    description="What this contributor has viewed, most recent first.",
)
async def contributor_view_history(
    contributor_id: str,
    limit: int = Query(50, ge=1, le=500),
) -> list[dict[str, Any]]:
    return read_tracking_service.get_contributor_view_history(
        contributor_id, limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /api/views/discovery/{asset_id}
# ---------------------------------------------------------------------------

@router.get(
    "/views/discovery/{asset_id}",
    summary="Discovery chain",
    description="Referrer chain — who brought whom to this asset.",
)
async def discovery_chain(asset_id: str) -> list[dict[str, Any]]:
    return read_tracking_service.get_discovery_chain(asset_id)


# ---------------------------------------------------------------------------
# GET /api/views/summary
# ---------------------------------------------------------------------------

@router.get(
    "/views/summary",
    summary="Aggregate view stats",
    description="Dashboard-level aggregate view statistics.",
)
async def view_summary(
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """Aggregate stats: total events, unique assets, unique contributors."""
    trending = read_tracking_service.get_trending(limit=100, days=days)
    total_views = sum(t["view_count"] for t in trending)
    unique_assets = len(trending)
    unique_contributors = sum(t.get("unique_viewers", 0) for t in trending)

    return {
        "days": days,
        "total_views": total_views,
        "unique_contributors": unique_contributors,
        "assets_viewed": unique_assets,
        "top_trending": trending[:5],
    }


# ---------------------------------------------------------------------------
# GET /api/views/earnings/{contributor_id}
# ---------------------------------------------------------------------------

@router.get(
    "/views/earnings/{contributor_id}",
    summary="Discovery earnings",
    description="How much CC a contributor has earned through organic discovery.",
)
async def discovery_earnings(
    contributor_id: str,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    return discovery_reward_service.get_referrer_earnings(contributor_id, days=days)
