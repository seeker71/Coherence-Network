"""Creator economy router — public stats, proof cards, featured listings.

Endpoints:
  GET /api/creator-economy/stats       - Public cached summary (R1)
  GET /api/assets/{asset_id}/proof-card - Shareable proof card (R2)
  GET /api/creator-economy/featured    - Paginated featured list (R3)

See specs/creator-economy-promotion.md. The service layer stays pure
(takes AssetRow / AssetUsage inputs explicitly); this router is where
the in-process registries and the render-events store get wired.

Storage sources for this first slice:
  - AssetRow rows come from the in-process AssetRegistration store
    (the one already backing POST /api/assets/register) merged with
    the legacy in-memory asset lookup via graph_service.
  - AssetUsage is computed from the render-events in-process store.
  - arweave_url is left None for now; the Arweave publisher is still
    partner-gated.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.creator_economy import (
    CreatorStats,
    FeaturedAssetsList,
    ProofCard,
)
from app.routers.render_events import _EVENTS as _RENDER_EVENTS
from app.services import creator_economy_service
from app.services.creator_economy_service import AssetRow, AssetUsage

router = APIRouter(prefix="/creator-economy", tags=["creator-economy"])


# ---------- In-process asset registry (temporary glue) ----------

# Until graph_service exposes a MIME-aware read for creator-economy
# assets, this module keeps a small in-memory registry that
# POST /api/assets/register populates via a callback. For this first
# slice, the registry is initially empty and tests seed it directly.

_ASSETS: Dict[str, AssetRow] = {}
_STATS_CACHE: Dict[str, CreatorStats] = {}
_CACHE_TTL_SECONDS = 300


def register_creator_asset(row: AssetRow) -> None:
    """Hook used by POST /api/assets/register (future wiring) and by
    tests to seed the in-process creator-asset registry."""
    _ASSETS[row.id] = row


def _reset_for_tests() -> None:
    _ASSETS.clear()
    _STATS_CACHE.clear()


def _compute_usages() -> Dict[str, AssetUsage]:
    """Aggregate render events into per-asset (use_count, cc_earned)."""
    buckets: Dict[str, AssetUsage] = {}
    counts: Dict[str, int] = defaultdict(int)
    earned: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for e in _RENDER_EVENTS.values():
        counts[e.asset_id] += 1
        earned[e.asset_id] += e.cc_asset_creator
    for asset_id in set(counts) | set(earned):
        buckets[asset_id] = AssetUsage(
            asset_id=asset_id,
            use_count=counts.get(asset_id, 0),
            cc_earned=earned.get(asset_id, Decimal("0")),
        )
    return buckets


# ---------- Endpoints ----------


@router.get(
    "/stats",
    response_model=CreatorStats,
    summary="Public creator-economy stats (cached 5 min)",
)
async def get_creator_stats() -> CreatorStats:
    """R1: cached summary of total_creators, total_blueprints,
    total_cc_distributed, total_uses, verified_since.
    """
    now = datetime.now(timezone.utc)
    cached = _STATS_CACHE.get("default")
    if cached is not None:
        age = (now - cached.computed_at).total_seconds()
        if age < _CACHE_TTL_SECONDS:
            return cached

    stats = creator_economy_service.compute_creator_stats(
        assets=_ASSETS.values(),
        usages=_compute_usages(),
        now=now,
    )
    _STATS_CACHE["default"] = stats
    return stats


@router.get(
    "/featured",
    response_model=FeaturedAssetsList,
    summary="Featured creator-economy assets, ordered by use_count desc",
)
async def list_featured(
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0),
    asset_type: Optional[str] = Query(None, description="Filter by asset_type"),
    community_tag: Optional[str] = Query(None, description="Filter by community tag"),
) -> FeaturedAssetsList:
    return creator_economy_service.list_featured(
        assets=list(_ASSETS.values()),
        usages=_compute_usages(),
        limit=limit,
        offset=offset,
        asset_type=asset_type,
        community_tag=community_tag,
    )


# The proof-card endpoint lives at /api/assets/{id}/proof-card, which
# the spec's source map places in this router. Declare it with that
# path to match the contract rather than under /creator-economy/.
proof_router = APIRouter(tags=["creator-economy"])


@proof_router.get(
    "/assets/{asset_id:path}/proof-card",
    response_model=ProofCard,
    summary="Shareable proof card for any creator-economy asset",
)
async def get_asset_proof_card(asset_id: str) -> ProofCard:
    row = _ASSETS.get(asset_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"no proof card available for asset '{asset_id}'",
        )
    usage = _compute_usages().get(
        asset_id, AssetUsage(asset_id=asset_id, use_count=0, cc_earned=Decimal("0"))
    )
    return creator_economy_service.build_proof_card(row, usage)
