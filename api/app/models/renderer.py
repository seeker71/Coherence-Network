"""Renderer and render-event models for the asset-renderer-plugin spec.

Part of the pluggable-renderer system where contributors can register
any MIME type as an asset and any renderer that displays those types
earns a share of the CC attributed on every render.

See specs/asset-renderer-plugin.md for the full contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


DEFAULT_ASSET_CREATOR_SHARE = Decimal("0.80")
DEFAULT_RENDERER_CREATOR_SHARE = Decimal("0.15")
DEFAULT_HOST_NODE_SHARE = Decimal("0.05")

# Sum-of-shares tolerance for decimal rounding.
_SHARE_TOLERANCE = Decimal("0.001")

MAX_RENDERER_BUNDLE_BYTES = 512_000  # 500KB hard cap per spec R9


class RenderCCSplit(BaseModel):
    """CC split for a render event.

    Three shares that must sum to 1.0 (100%) within rounding tolerance.
    Default is 80/15/5: the creator who made the content, the creator
    who made it viewable, the node that served it.
    """

    model_config = ConfigDict(frozen=True)

    asset_creator: Decimal = Field(default=DEFAULT_ASSET_CREATOR_SHARE, ge=0, le=1)
    renderer_creator: Decimal = Field(default=DEFAULT_RENDERER_CREATOR_SHARE, ge=0, le=1)
    host_node: Decimal = Field(default=DEFAULT_HOST_NODE_SHARE, ge=0, le=1)

    @model_validator(mode="after")
    def shares_sum_to_one(self) -> "RenderCCSplit":
        total = self.asset_creator + self.renderer_creator + self.host_node
        if abs(total - Decimal("1")) > _SHARE_TOLERANCE:
            raise ValueError(
                f"CC split shares must sum to 1.0, got {total} "
                f"(asset_creator={self.asset_creator}, "
                f"renderer_creator={self.renderer_creator}, "
                f"host_node={self.host_node})"
            )
        return self


class RendererCreate(BaseModel):
    """Payload for POST /api/renderers/register."""

    id: str
    name: str
    mime_types: List[str] = Field(min_length=1)
    creator_id: str
    component_url: str
    creation_cost_cc: Decimal
    version: str
    cc_split: Optional[RenderCCSplit] = None
    max_bundle_bytes: int = Field(default=MAX_RENDERER_BUNDLE_BYTES, le=MAX_RENDERER_BUNDLE_BYTES)


class Renderer(RendererCreate):
    """A registered renderer stored as a graph node."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RenderEvent(BaseModel):
    """Outcome of a single render: which asset, which renderer, which reader,
    how long, and how the CC pool was split across the three parties.
    """

    id: UUID = Field(default_factory=uuid4)
    asset_id: str
    renderer_id: str
    reader_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = Field(ge=0)
    cc_pool: Decimal
    cc_asset_creator: Decimal
    cc_renderer_creator: Decimal
    cc_host_node: Decimal
