from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


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


class ConceptTag(BaseModel):
    """A weighted link from an asset to a Living Collective concept."""

    concept_id: str
    weight: float = Field(ge=0.0, le=1.0)


class AssetRegistrationCreate(BaseModel):
    """Payload for POST /api/assets/register — MIME-aware asset registration
    that extends the legacy AssetCreate taxonomy (CODE/MODEL/CONTENT/DATA)
    with free-form MIME types, content provenance, and concept tags.

    See specs/asset-renderer-plugin.md (R1).
    """

    type: str = Field(description="MIME type or custom type identifier")
    name: str
    description: str
    content_hash: str = Field(description="SHA-256 of raw content")
    arweave_tx: Optional[str] = None
    ipfs_cid: Optional[str] = None
    concept_tags: List[ConceptTag] = Field(default_factory=list)
    creator_id: str
    creation_cost_cc: Decimal
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssetRegistration(AssetRegistrationCreate):
    """Registered asset with server-assigned id and timestamp."""

    id: str = Field(description="asset:<uuid> identifier")
    created_at: datetime
