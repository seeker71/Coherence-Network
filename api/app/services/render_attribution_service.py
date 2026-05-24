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

Also carries the small bridge ``log_render_event`` that lets the
read-tracking service materialize a render event from each content
read. Settlement reads from the same ``_EVENTS`` dict the render-events
router writes to, so the bridge closes the read → settlement loop
without changing settlement's contract (story-protocol-integration
R5+R8 — see PR #1963 e2e gap #3).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Mapping, NamedTuple, Optional

from app.models.renderer import (
    DEFAULT_ASSET_CREATOR_SHARE,
    DEFAULT_HOST_NODE_SHARE,
    DEFAULT_RENDERER_CREATOR_SHARE,
    RenderCCSplit,
    RenderEvent,
)

log = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Bridge — content reads materialize render events
# ---------------------------------------------------------------------------

# "renderer_id" for events synthesized from direct content-delivery reads
# (i.e. GET /api/assets/{id}/content). Distinct from registered renderer
# plugins so analytics can tell the two apart; settlement aggregates both.
CONTENT_DIRECT_RENDERER_ID = "content-direct"


def log_render_event(
    *,
    asset_id: str,
    renderer_id: str = CONTENT_DIRECT_RENDERER_ID,
    reader_id: Optional[str] = None,
    cc_amount: Any = 0,
    concept_resonance: Optional[Mapping[str, float]] = None,
    read_type: str = "free",
    duration_ms: int = 0,
    asset_override: Optional[RenderCCSplit] = None,
    renderer_default: Optional[RenderCCSplit] = None,
) -> RenderEvent:
    """Materialize a render event from a read so settlement sees the read.

    Inserts the event into ``app.routers.render_events._EVENTS`` — the
    same dict ``app.routers.settlement`` scans when computing a daily
    batch. The CC pool is the read's ``cc_amount`` (paid reads carry
    positive CC; free reads carry 0 and contribute to ``read_count``
    only). Splits default to the platform 80/15/5; an asset override
    or renderer default may be supplied by the caller.

    ``concept_resonance`` and ``read_type`` are accepted so the bridge
    is symmetric with ``read_tracking_service.record_read``; the
    current ``RenderEvent`` shape doesn't carry them, but the bridge
    surface keeps the door open for a richer event without forcing a
    caller change later.
    """
    pool = cc_amount if isinstance(cc_amount, Decimal) else Decimal(str(cc_amount or 0))
    attribution = attribute_render_cc(
        pool,
        asset_override=asset_override,
        renderer_default=renderer_default,
    )
    event = RenderEvent(
        asset_id=asset_id,
        renderer_id=renderer_id,
        reader_id=reader_id or "anonymous",
        duration_ms=int(duration_ms or 0),
        cc_pool=pool,
        cc_asset_creator=attribution.cc_asset_creator,
        cc_renderer_creator=attribution.cc_renderer_creator,
        cc_host_node=attribution.cc_host_node,
    )
    # Late import to avoid a hard cycle (router imports this service).
    from app.routers.render_events import _EVENTS

    _EVENTS[event.id] = event
    return event
