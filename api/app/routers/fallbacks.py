"""Fallback visibility — read the witness of silent degradation paths."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import fallback_witness_service

router = APIRouter()


@router.get(
    "/fallbacks",
    summary="Recent silent-fallback events (running-on-reserve witness)",
    description=(
        "When the body falls back — graph lookup to legacy, primary executor "
        "to backup, model alias remap, translator pass-through — the witness "
        "records it here. A few per hour is healthy breath; a spike reveals "
        "a tender place worth attending to."
    ),
)
async def list_fallbacks(
    limit: int = Query(100, ge=1, le=500),
    source: str | None = Query(None, description="Optional source prefix filter (e.g. 'graph', 'executor', 'translator')."),
) -> dict:
    events = fallback_witness_service.recent(limit=limit, source_prefix=source)
    return {
        "events": events,
        "count": len(events),
        "summary": fallback_witness_service.summary(),
    }


@router.get(
    "/fallbacks/summary",
    summary="Aggregate fallback counts by source",
)
async def fallback_summary() -> dict:
    return fallback_witness_service.summary()
