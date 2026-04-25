"""Render attribution service.

Pure-logic piece of the asset-renderer-plugin spec (R4, R5). Given a
render event, split the CC pool across asset creator, renderer creator,
and host node according to a configurable split.

Override precedence per spec:
  1. Asset creator override (set per-asset by the content creator)
  2. Renderer default split (set at renderer registration)
  3. Platform default (80/15/5)

Pydantic validation on RenderCCSplit ensures the three shares sum to
1.0 before any attribution is computed, so cc_pool always reconciles
to the three returned amounts within decimal tolerance.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple, Optional

from app.models.renderer import (
    DEFAULT_ASSET_CREATOR_SHARE,
    DEFAULT_HOST_NODE_SHARE,
    DEFAULT_RENDERER_CREATOR_SHARE,
    RenderCCSplit,
)


class RenderAttribution(NamedTuple):
    """The three per-party amounts a render pool is split into."""

    cc_asset_creator: Decimal
    cc_renderer_creator: Decimal
    cc_host_node: Decimal


_PLATFORM_DEFAULT = RenderCCSplit(
    asset_creator=DEFAULT_ASSET_CREATOR_SHARE,
    renderer_creator=DEFAULT_RENDERER_CREATOR_SHARE,
    host_node=DEFAULT_HOST_NODE_SHARE,
)


def resolve_split(
    asset_override: Optional[RenderCCSplit] = None,
    renderer_default: Optional[RenderCCSplit] = None,
) -> RenderCCSplit:
    """Resolve which split applies per the override precedence.

    Asset override beats renderer default beats platform default.
    """
    if asset_override is not None:
        return asset_override
    if renderer_default is not None:
        return renderer_default
    return _PLATFORM_DEFAULT


def attribute_render_cc(
    cc_pool: Decimal,
    *,
    asset_override: Optional[RenderCCSplit] = None,
    renderer_default: Optional[RenderCCSplit] = None,
) -> RenderAttribution:
    """Split a render's CC pool into per-party attributions."""
    split = resolve_split(asset_override, renderer_default)
    return RenderAttribution(
        cc_asset_creator=cc_pool * split.asset_creator,
        cc_renderer_creator=cc_pool * split.renderer_creator,
        cc_host_node=cc_pool * split.host_node,
    )
