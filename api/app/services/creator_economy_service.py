"""Creator economy service — computes public stats, proof cards,
and featured listings from existing assets + contributions.

Per specs/creator-economy-promotion.md (R1–R3, R6).

The service is pure-logic over explicit inputs — asset rows,
contribution rows, and render-event aggregates are all passed in.
That keeps it testable without graph state and leaves the caller
to choose between in-process sources and the real graph_service
read path. 5-minute caching happens at the router layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, List, Mapping, Optional, Sequence

from app.models.creator_economy import (
    CreatorStats,
    FeaturedAsset,
    FeaturedAssetsList,
    ProofCard,
)

# Asset types that count as "creator economy" contributions (R1 total_blueprints).
CREATOR_ECONOMY_TYPES = {"BLUEPRINT", "DESIGN", "RESEARCH"}


@dataclass(frozen=True)
class AssetRow:
    """Subset of asset fields this service reads. Callers build these
    from graph nodes, in-memory stores, or test fixtures."""

    id: str
    name: str
    asset_type: str
    creator_id: str
    creator_handle: str = ""
    community_tags: List[str] = None  # type: ignore[assignment]
    arweave_url: Optional[str] = None

    def __post_init__(self) -> None:  # type: ignore[override]
        if self.community_tags is None:
            object.__setattr__(self, "community_tags", [])


@dataclass(frozen=True)
class AssetUsage:
    """Per-asset usage totals aggregated from render events / contributions."""

    asset_id: str
    use_count: int
    cc_earned: Decimal


def _usage_for(usages: Mapping[str, AssetUsage], asset_id: str) -> AssetUsage:
    u = usages.get(asset_id)
    if u is None:
        return AssetUsage(asset_id=asset_id, use_count=0, cc_earned=Decimal("0"))
    return u


def compute_creator_stats(
    assets: Iterable[AssetRow],
    usages: Mapping[str, AssetUsage],
    *,
    verified_since: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> CreatorStats:
    """Aggregate public stats across creator-economy assets.

    - total_creators: distinct creator_id on creator-economy assets
    - total_blueprints: asset count in {BLUEPRINT, DESIGN, RESEARCH}
    - total_cc_distributed: sum of cc_earned across those assets
    - total_uses: sum of use_count across those assets
    """
    creators: set[str] = set()
    blueprint_count = 0
    total_cc = Decimal("0")
    total_uses = 0
    for row in assets:
        if row.asset_type not in CREATOR_ECONOMY_TYPES:
            continue
        creators.add(row.creator_id)
        blueprint_count += 1
        u = _usage_for(usages, row.id)
        total_cc += u.cc_earned
        total_uses += u.use_count

    return CreatorStats(
        total_creators=len(creators),
        total_blueprints=blueprint_count,
        total_cc_distributed=total_cc,
        total_uses=total_uses,
        verified_since=verified_since,
        computed_at=now or datetime.now(timezone.utc),
    )


def build_proof_card(
    asset: AssetRow,
    usage: AssetUsage,
    *,
    verification_base_url: str = "/api/verification/chain",
) -> ProofCard:
    """Compose a shareable proof card for a single asset (R2)."""
    verification_url = f"{verification_base_url}/{asset.id}"
    return ProofCard(
        asset_id=asset.id,
        name=asset.name,
        creator_handle=asset.creator_handle or asset.creator_id,
        asset_type=asset.asset_type,
        use_count=usage.use_count,
        cc_earned=usage.cc_earned,
        arweave_url=asset.arweave_url,
        verification_url=verification_url,
        community_tags=list(asset.community_tags or []),
    )


def list_featured(
    assets: Sequence[AssetRow],
    usages: Mapping[str, AssetUsage],
    *,
    limit: int = 12,
    offset: int = 0,
    asset_type: Optional[str] = None,
    community_tag: Optional[str] = None,
) -> FeaturedAssetsList:
    """Paginated featured list ordered by use_count desc (R3).

    Filters:
      - asset_type: exact match on asset.asset_type
      - community_tag: asset's community_tags must include this value
    """
    filtered: List[AssetRow] = []
    for row in assets:
        if row.asset_type not in CREATOR_ECONOMY_TYPES:
            continue
        if asset_type is not None and row.asset_type != asset_type:
            continue
        if community_tag is not None and community_tag not in (row.community_tags or []):
            continue
        filtered.append(row)

    def _sort_key(r: AssetRow) -> tuple[int, str]:
        return (-_usage_for(usages, r.id).use_count, r.id)

    filtered.sort(key=_sort_key)
    total = len(filtered)
    page = filtered[offset : offset + limit]
    items: List[FeaturedAsset] = []
    for row in page:
        u = _usage_for(usages, row.id)
        items.append(
            FeaturedAsset(
                asset_id=row.id,
                name=row.name,
                creator_handle=row.creator_handle or row.creator_id,
                asset_type=row.asset_type,
                use_count=u.use_count,
                cc_earned=u.cc_earned,
                community_tags=list(row.community_tags or []),
            )
        )
    return FeaturedAssetsList(items=items, total=total, limit=limit, offset=offset)
