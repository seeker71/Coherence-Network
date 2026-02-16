"""Runtime telemetry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.runtime import RuntimeEvent, RuntimeEventCreate
from app.services import runtime_service

router = APIRouter()


@router.post("/runtime/events", response_model=RuntimeEvent, status_code=201)
async def create_runtime_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    return runtime_service.record_event(payload)


@router.get("/runtime/events", response_model=list[RuntimeEvent])
async def list_runtime_events(limit: int = Query(100, ge=1, le=2000)) -> list[RuntimeEvent]:
    return runtime_service.list_events(limit=limit)


@router.get("/runtime/ideas/summary")
async def runtime_summary_by_idea(seconds: int = Query(3600, ge=60, le=2592000)) -> dict:
    rows = runtime_service.summarize_by_idea(seconds=seconds)
    return {
        "window_seconds": seconds,
        "ideas": [row.model_dump(mode="json") for row in rows],
    }


@router.get("/runtime/endpoints/summary")
async def runtime_summary_by_endpoint(seconds: int = Query(3600, ge=60, le=2592000)) -> dict:
    rows = runtime_service.summarize_by_endpoint(seconds=seconds)
    return {
        "window_seconds": seconds,
        "endpoints": [row.model_dump(mode="json") for row in rows],
    }
