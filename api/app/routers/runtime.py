"""Runtime telemetry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models.runtime import EndpointAttentionReport, RuntimeEvent, RuntimeEventCreate
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
async def runtime_summary_by_idea(
    seconds: int = Query(3600, ge=60, le=2592000),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0, le=10000),
    force_refresh: bool = Query(False),
) -> dict:
    # Keep API latency bounded for UI summary requests by scaling event scan
    # with requested output size instead of always scanning the full default.
    event_limit = max(300, min(1500, int(limit) * 20))
    return runtime_service.cached_runtime_ideas_summary_payload(
        seconds=seconds,
        limit=limit,
        offset=offset,
        event_limit=event_limit,
        force_refresh=force_refresh,
    )


@router.get("/runtime/endpoints/summary")
async def runtime_summary_by_endpoint(
    seconds: int = Query(3600, ge=60, le=2592000),
    limit: int = Query(200, ge=1, le=2000),
) -> dict:
    rows = runtime_service.summarize_by_endpoint(seconds=seconds, summary_limit=limit)
    return {
        "window_seconds": seconds,
        "endpoints": [row.model_dump(mode="json") for row in rows],
    }


@router.get("/runtime/endpoints/attention", response_model=EndpointAttentionReport)
async def runtime_endpoint_attention(
    seconds: int = Query(3600, ge=60, le=2592000),
    min_event_count: int = Query(1, ge=1, le=5000),
    attention_threshold: float = Query(40.0, ge=0.0, le=1000.0),
    limit: int = Query(200, ge=1, le=2000),
) -> EndpointAttentionReport:
    return runtime_service.summarize_endpoint_attention(
        seconds=seconds,
        min_event_count=min_event_count,
        attention_threshold=attention_threshold,
        limit=limit,
    )


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
