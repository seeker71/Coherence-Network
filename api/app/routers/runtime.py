"""Runtime telemetry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models.runtime import RuntimeEvent, RuntimeEventCreate
from app.services import runtime_service

router = APIRouter()


@router.post("/runtime/events", response_model=RuntimeEvent, status_code=201)
async def create_runtime_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    return runtime_service.record_event(payload)


@router.get("/runtime/events", response_model=list[RuntimeEvent])
async def list_runtime_events(
    limit: int = Query(100, ge=1, le=2000),
    endpoint: str | None = Query(None, description="Canonical endpoint template (e.g. /api/spec-registry/{spec_id})"),
    method: str | None = Query(None, description="HTTP method filter (e.g. GET)"),
    min_runtime_ms: float | None = Query(None, ge=0.0, description="Minimum runtime_ms filter"),
    status_code: int | None = Query(None, ge=100, le=599, description="HTTP status filter"),
) -> list[RuntimeEvent]:
    if endpoint or method or min_runtime_ms is not None or status_code is not None:
        return runtime_service.list_events_filtered(
            limit=limit,
            endpoint=endpoint,
            method=method,
            min_runtime_ms=min_runtime_ms,
            status_code=status_code,
        )
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


@router.get("/runtime/endpoints/slow")
async def runtime_slow_endpoints(
    seconds: int = Query(3600, ge=60, le=2592000),
    threshold_ms: int | None = Query(None, ge=1, le=300000),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    threshold = int(threshold_ms) if threshold_ms is not None else runtime_service.slow_threshold_ms()
    rows = runtime_service.slow_endpoints_report(seconds=seconds, threshold_ms=threshold, limit=limit)
    return {
        "window_seconds": seconds,
        "threshold_ms": threshold,
        "endpoints": [row.model_dump(mode="json") for row in rows],
    }


@router.post("/runtime/exerciser/run")
async def run_runtime_get_endpoint_exerciser(
    request: Request,
    cycles: int = Query(1, ge=1, le=200),
    max_endpoints: int = Query(250, ge=1, le=2000),
    delay_ms: int = Query(0, ge=0, le=30000),
    timeout_seconds: float = Query(8.0, ge=1.0, le=60.0),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return await runtime_service.run_get_endpoint_exerciser(
        app=request.app,
        base_url=str(request.base_url),
        cycles=cycles,
        max_endpoints=max_endpoints,
        delay_ms=delay_ms,
        timeout_seconds=timeout_seconds,
        runtime_window_seconds=runtime_window_seconds,
    )


@router.get("/runtime/usage/verification")
async def verify_runtime_usage_internal_vs_public(
    public_api_base: str = Query(
        "https://coherence-network-production.up.railway.app",
        description="Public API base used for external usage comparison",
    ),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    timeout_seconds: float = Query(8.0, ge=1.0, le=60.0),
) -> dict:
    return runtime_service.verify_internal_vs_public_usage(
        public_api_base=public_api_base,
        runtime_window_seconds=runtime_window_seconds,
        timeout_seconds=timeout_seconds,
    )
