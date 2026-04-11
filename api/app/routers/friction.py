"""Friction ledger API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.friction import (
    FrictionCategoryReport,
    FrictionEntryPointReport,
    FrictionEvent,
    FrictionReport,
)
from app.services import friction_service

router = APIRouter()


@router.get("/friction/events", response_model=list[FrictionEvent], summary="List Events")
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
) -> list[FrictionEvent]:
    events, _ignored = friction_service.load_events()
    if status:
        events = [e for e in events if e.status == status]
    return events[:limit]


@router.post("/friction/events", response_model=FrictionEvent, status_code=201, summary="Create Event")
async def create_event(event: FrictionEvent) -> FrictionEvent:
    friction_service.append_event(event)
    return event


@router.get("/friction/report", response_model=FrictionReport, summary="Report")
async def report(
    window_days: int = Query(7, ge=1),
    limit: int = Query(500, ge=1, le=5000, description="Max events to scan"),
) -> FrictionReport:
    max_window_days = friction_service.report_window_limit_days()
    if window_days > max_window_days:
        raise HTTPException(
            status_code=422,
            detail=f"window_days must be between 1 and {max_window_days}",
        )
    events, ignored = friction_service.load_events()
    # Cap events scanned to prevent slow page loads
    events = events[-limit:] if len(events) > limit else events
    data = friction_service.summarize(events, window_days=window_days)
    data["source_file"] = str(friction_service.friction_file_path())
    data["ignored_lines"] = ignored
    return FrictionReport(**data)


@router.get("/friction/entry-points", response_model=FrictionEntryPointReport, summary="Entry Points")
async def entry_points(
    window_days: int = Query(7, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
) -> FrictionEntryPointReport:
    data = friction_service.friction_entry_points(window_days=window_days, limit=limit)
    return FrictionEntryPointReport(**data)


@router.get("/friction/categories", response_model=FrictionCategoryReport, summary="Categories")
async def categories(
    window_days: int = Query(7, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
) -> FrictionCategoryReport:
    data = friction_service.friction_categories(window_days=window_days, limit=limit)
    return FrictionCategoryReport(**data)
