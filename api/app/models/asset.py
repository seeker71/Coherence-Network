from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AssetType(str, Enum):
    """Pipeline-tracked asset categories. New code contributions
    must pick one of these seven. The resolver + KB seed produce
    nodes with richer asset_type strings (BLUEPRINT, VIDEO, AUDIO,
    album, track, book, etc.); those are read-only on the listing
    side and flow through Asset.type as free strings."""
    CODE = "CODE"
    MODEL = "MODEL"
    CONTENT = "CONTENT"
    DATA = "DATA"
    BLUEPRINT = "BLUEPRINT"
    DESIGN = "DESIGN"
    RESEARCH = "RESEARCH"


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
    lens that doesn't reject non-pipeline values.

    ``image_url`` (absolute URL on remote nodes from inspired-by
    resolvers) and ``file_path`` (local path under /visuals/... for
    KB-generated visuals) are exposed on the listing so cards can
    render real thumbnails for IMAGE-typed assets without a second
    round-trip per card.

    Optional rich fields are passed through from the underlying graph
    node so detail pages can surface a title (``name``), an external
    source link (``canonical_url``), the originating cell
    (``creator_id``), and the structured-data context that makes a
    surface trustworthy (``mime_type``, ``content_hash``, ``ipfs_cid``,
    ``arweave_tx``, ``slug``, ``era``, ``company``, ``location``,
    ``substrate``, ``creation_kind``, etc.). The thin contract still
    works for old callers; new callers can read everything they need
    in one round-trip."""
    id: UUID = Field(default_factory=uuid4)
    type: str
    description: str
    total_cost: Decimal = Decimal("0.00")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_url: Optional[str] = None
    file_path: Optional[str] = None

    # Rich graph-node fields, optional so the legacy listing contract
    # is preserved when the underlying node is sparse.
    node_id: Optional[str] = None
    name: Optional[str] = None
    canonical_url: Optional[str] = None
    slug: Optional[str] = None
    creator_id: Optional[str] = None
    creation_kind: Optional[str] = None
    asset_type: Optional[str] = None
    mime_type: Optional[str] = None
    content_hash: Optional[str] = None
    ipfs_cid: Optional[str] = None
    arweave_tx: Optional[str] = None
    asin: Optional[str] = None
    isbn: Optional[str] = None
    runtime_length_min: Optional[int] = None
    era: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    substrate: Optional[str] = None
    when: Optional[str] = None
    language: Optional[str] = None

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
