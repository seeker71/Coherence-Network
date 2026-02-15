"""Friction ledger API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.friction import FrictionEvent, FrictionReport
from app.services import friction_service

router = APIRouter()


@router.get("/friction/events", response_model=list[FrictionEvent])
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
) -> list[FrictionEvent]:
    events, _ignored = friction_service.load_events()
    if status:
        events = [e for e in events if e.status == status]
    return events[:limit]


@router.post("/friction/events", response_model=FrictionEvent, status_code=201)
async def create_event(event: FrictionEvent) -> FrictionEvent:
    friction_service.append_event(event)
    return event


@router.get("/friction/report", response_model=FrictionReport)
async def report(
    window_days: int = Query(7, ge=1, le=365),
) -> FrictionReport:
    events, ignored = friction_service.load_events()
    data = friction_service.summarize(events, window_days=window_days)
    data["source_file"] = str(friction_service.friction_file_path())
    data["ignored_lines"] = ignored
    return FrictionReport(**data)
