"""Settlement router — daily CC distribution batch per story-protocol-integration R8.

Endpoints:
  POST /api/settlement/run            - Compute a settlement batch for a date
  GET  /api/settlement/{date}         - Retrieve a computed batch
  GET  /api/settlement                - List all computed batches

The run endpoint pulls render events from the render_events store,
applicable evidence multipliers from evidence_service, and (for this
first slice) uses an empty asset_concept_tags map — graph-backed
lookup of per-asset concept tags is a follow-up. Concept pools fall
back to 'uncategorized' when tags are absent.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.settlement import SettlementBatch
from app.routers.render_events import _EVENTS as _RENDER_EVENTS
from app.services import evidence_service, settlement_service
from app.services.story_protocol_bridge import AssetConceptTag

router = APIRouter(prefix="/settlement", tags=["settlement"])


class RunRequest(BaseModel):
    batch_date: date_type


@router.post(
    "/run",
    response_model=SettlementBatch,
    status_code=201,
    summary="Compute the settlement batch for a date",
)
async def run_settlement(body: RunRequest) -> SettlementBatch:
    """Aggregate render events for the given date, apply evidence
    multipliers per asset, and store the resulting batch.
    """
    events = list(_RENDER_EVENTS.values())
    # Pull evidence multipliers for every asset that has events that day.
    assets_on_date = {
        e.asset_id for e in events if e.timestamp.date() == body.batch_date
    }
    multipliers: Dict[str, Decimal] = {
        asset_id: evidence_service.applicable_multiplier_for_asset(asset_id)
        for asset_id in assets_on_date
    }
    # Asset concept tags: empty in this slice; graph lookup is follow-up.
    asset_concept_tags: Dict[str, List[AssetConceptTag]] = {}

    batch = settlement_service.run_daily_settlement(
        batch_date=body.batch_date,
        events=events,
        asset_concept_tags=asset_concept_tags,
        evidence_multipliers=multipliers,
    )
    settlement_service.store_batch(batch)
    return batch


@router.get(
    "/{batch_date}",
    response_model=SettlementBatch,
    summary="Retrieve a stored settlement batch for a date",
)
async def get_settlement(batch_date: date_type) -> SettlementBatch:
    batch = settlement_service.get_batch(batch_date)
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail=f"no settlement batch computed for {batch_date}",
        )
    return batch


@router.get(
    "",
    response_model=List[SettlementBatch],
    summary="List all stored settlement batches, most recent first",
)
async def list_settlements(
    limit: int = Query(30, ge=1, le=365),
) -> List[SettlementBatch]:
    return settlement_service.list_batches()[:limit]
