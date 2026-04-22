from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class AssetType(str, Enum):
    """Pipeline-tracked asset categories. New code contributions
    must pick one of these four. The resolver + KB seed produce
    nodes with richer asset_type strings (BLUEPRINT, VIDEO, AUDIO,
    album, track, book, etc.); those are read-only on the listing
    side and flow through Asset.type as free strings."""
    CODE = "CODE"
    MODEL = "MODEL"
    CONTENT = "CONTENT"
    DATA = "DATA"


class AssetBase(BaseModel):
    type: AssetType
    description: str


class AssetCreate(AssetBase):
    """POST contract — keeps the enum tight so pipeline contributions
    stay in the four-value taxonomy."""
    pass


class Asset(BaseModel):
    """Listing + detail read model — accepts any asset_type string the
    graph carries. Resolver-minted nodes (albums, tracks, videos,
    blueprints, audio recordings) all live under type=asset in the
    graph but with their own type taxonomy; rendering them requires a
    lens that doesn't reject non-pipeline values."""
    id: UUID = Field(default_factory=uuid4)
    type: str
    description: str
    total_cost: Decimal = Decimal("0.00")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
