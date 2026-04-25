"""Creator economy models — public stats, proof cards, featured listings.

Per specs/creator-economy-promotion.md. These are the read shapes the
web surfaces consume; they're computed from existing assets and
contribution data, not stored as separate rows.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CreatorStats(BaseModel):
    """Cached public summary for the creators landing page (R1)."""

    total_creators: int = Field(ge=0)
    total_blueprints: int = Field(ge=0)
    total_cc_distributed: Decimal = Decimal("0")
    total_uses: int = Field(ge=0)
    verified_since: Optional[datetime] = None
    computed_at: datetime


class ProofCard(BaseModel):
    """Shareable proof card for a single asset (R2)."""

    asset_id: str
    name: str
    creator_handle: str
    asset_type: str
    use_count: int = Field(ge=0)
    cc_earned: Decimal = Decimal("0")
    arweave_url: Optional[str] = None
    verification_url: str
    community_tags: List[str] = Field(default_factory=list)


class FeaturedAsset(BaseModel):
    """One entry in the featured-assets list (R3)."""

    asset_id: str
    name: str
    creator_handle: str
    asset_type: str
    use_count: int = Field(ge=0)
    cc_earned: Decimal = Decimal("0")
    community_tags: List[str] = Field(default_factory=list)


class FeaturedAssetsList(BaseModel):
    items: List[FeaturedAsset] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int
    offset: int
