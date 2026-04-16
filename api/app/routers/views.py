"""Views router — per-contributor view tracking, analytics, discovery rewards."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from app.services import read_tracking_service
from app.services import discovery_reward_service

log = logging.getLogger(__name__)

router = APIRouter()


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
