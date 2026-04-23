"""Render Events Router — log a render and attribute CC.

Endpoints:
  POST /api/render-events               - Log a render event, attribute CC
  GET  /api/render-events/{event_id}    - Fetch a single event

See specs/asset-renderer-plugin.md (R4). Closes the economic loop: a
render event comes in with (asset_id, renderer_id, reader_id,
duration_ms); the service computes the CC pool from engagement and
splits it per the renderer's cc_split (or the platform default if
none is registered).

Storage is an in-process list for this first slice, matching the
renderer registry. Graph-backed persistence is a follow-up.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.renderer import RenderCCSplit, RenderEvent
from app.routers.renderers import _REGISTRY as _RENDERER_REGISTRY
from app.services.render_attribution_service import attribute_render_cc

router = APIRouter(prefix="/render-events", tags=["render-events"])


# Base rate: 0.00001 CC per millisecond of engagement.
# 15 seconds of engagement → 0.15 CC pool (example from spec).
BASE_CC_RATE_PER_MS = Decimal("0.00001")


# In-process event log. Single-process only for this slice.
_EVENTS: Dict[UUID, RenderEvent] = {}


class RenderEventCreate(BaseModel):
    """Payload for POST /api/render-events."""

    asset_id: str
    renderer_id: str
    reader_id: str
    duration_ms: int = Field(ge=0)
    asset_cc_split_override: RenderCCSplit | None = None


@router.post(
    "",
    response_model=RenderEvent,
    status_code=201,
    summary="Log a render event and attribute CC",
)
async def log_render_event(body: RenderEventCreate) -> RenderEvent:
    """Log a render, compute the CC pool, split it per override precedence.

    - cc_pool = duration_ms * BASE_CC_RATE_PER_MS
    - Override precedence: asset override > renderer default > platform 80/15/5
    - Shares are validated to sum to 1.0 at the Pydantic layer.
    """
    renderer_default = None
    renderer = _RENDERER_REGISTRY.get(body.renderer_id)
    if renderer is not None:
        renderer_default = renderer.cc_split

    cc_pool = Decimal(body.duration_ms) * BASE_CC_RATE_PER_MS

    attribution = attribute_render_cc(
        cc_pool,
        asset_override=body.asset_cc_split_override,
        renderer_default=renderer_default,
    )

    event = RenderEvent(
        asset_id=body.asset_id,
        renderer_id=body.renderer_id,
        reader_id=body.reader_id,
        duration_ms=body.duration_ms,
        cc_pool=cc_pool,
        cc_asset_creator=attribution.cc_asset_creator,
        cc_renderer_creator=attribution.cc_renderer_creator,
        cc_host_node=attribution.cc_host_node,
    )
    _EVENTS[event.id] = event
    return event


@router.get(
    "/{event_id}",
    response_model=RenderEvent,
    summary="Get a single render event by id",
)
async def get_render_event(event_id: UUID) -> RenderEvent:
    if event_id not in _EVENTS:
        raise HTTPException(
            status_code=404,
            detail=f"render event '{event_id}' not found",
        )
    return _EVENTS[event_id]


def _reset_events_for_tests() -> None:
    """Testing hook. Not part of the public API."""
    _EVENTS.clear()
