"""Runtime telemetry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Body, Query, Request
from pydantic import BaseModel

from app.models.runtime import (
    EndpointAttentionReport,
    RuntimeEvent,
    RuntimeEventCreate,
    WebViewPerformanceReport,
)
from app.services import mvp_baseline_service, runtime_service

router = APIRouter()


class RuntimeExerciserRunRequest(BaseModel):
    cycles: int | None = None
    max_endpoints: int | None = None
    delay_ms: int | None = None
    timeout_seconds: float | None = None
    runtime_window_seconds: int | None = None


@router.post("/runtime/events", response_model=RuntimeEvent, status_code=201, summary="Create Runtime Event")
async def create_runtime_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    return runtime_service.record_event(payload)


@router.get("/runtime/events", response_model=list[RuntimeEvent], summary="List Runtime Events")
async def list_runtime_events(
    limit: int = Query(100, ge=1, le=2000),
    source: str | None = Query(default=None, max_length=64),
    force_refresh: bool = Query(False),
) -> list[RuntimeEvent]:
    return runtime_service.cached_runtime_events(limit=limit, source=source, force_refresh=force_refresh)


@router.get("/runtime/change-token", summary="Runtime Change Token")
async def runtime_change_token(force_refresh: bool = Query(False)) -> dict:
    return runtime_service.live_change_token(force_refresh=force_refresh)


@router.get("/runtime/ideas/summary", summary="Runtime Summary By Idea")
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


@router.get("/runtime/endpoints/summary", summary="Runtime Summary By Endpoint")
async def runtime_summary_by_endpoint(
    seconds: int = Query(3600, ge=60, le=2592000),
    limit: int = Query(200, ge=1, le=2000),
) -> dict:
    rows = runtime_service.summarize_by_endpoint(seconds=seconds, summary_limit=limit)
    return {
        "window_seconds": seconds,
        "endpoints": [row.model_dump(mode="json") for row in rows],
    }


@router.get("/runtime/web/views/summary", response_model=WebViewPerformanceReport, summary="Runtime Web View Summary")
async def runtime_web_view_summary(
    seconds: int = Query(21600, ge=60, le=2592000),
    limit: int = Query(100, ge=1, le=500),
    route_prefix: str | None = Query(default=None, max_length=200),
    force_refresh: bool = Query(False),
) -> WebViewPerformanceReport:
    event_limit = max(300, min(1500, int(limit) * 30))
    payload = runtime_service.cached_web_view_performance_payload(
        seconds=seconds,
        limit=limit,
        route_prefix=route_prefix,
        event_limit=event_limit,
        force_refresh=force_refresh,
    )
    return WebViewPerformanceReport.model_validate(payload)


@router.get("/runtime/endpoints/attention", response_model=EndpointAttentionReport, summary="Runtime Endpoint Attention")
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


@router.post("/runtime/exerciser/run", summary="Run Runtime Get Endpoint Exerciser")
async def run_runtime_get_endpoint_exerciser(
    request: Request,
    payload: RuntimeExerciserRunRequest | None = Body(default=None),
    cycles: int = Query(1, ge=1, le=200),
    max_endpoints: int = Query(15, ge=1, le=2000),
    delay_ms: int = Query(0, ge=0, le=30000),
    timeout_seconds: float = Query(2.0, ge=1.0, le=60.0),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    payload_values = payload.model_dump(exclude_none=True) if payload is not None else {}
    return await runtime_service.run_get_endpoint_exerciser(
        app=request.app,
        base_url=str(request.base_url),
        cycles=int(payload_values.get("cycles", cycles)),
        max_endpoints=int(payload_values.get("max_endpoints", max_endpoints)),
        delay_ms=int(payload_values.get("delay_ms", delay_ms)),
        timeout_seconds=float(payload_values.get("timeout_seconds", timeout_seconds)),
        runtime_window_seconds=int(payload_values.get("runtime_window_seconds", runtime_window_seconds)),
    )


@router.get("/runtime/usage/verification", summary="Verify Runtime Usage Internal Vs Public")
async def verify_runtime_usage_internal_vs_public(
    public_api_base: str = Query(
        "https://api.coherencycoin.com",
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


@router.get("/runtime/mvp/acceptance-summary", summary="Runtime Mvp Acceptance Summary")
async def runtime_mvp_acceptance_summary(
    seconds: int = Query(86400, ge=60, le=2592000),
    limit: int = Query(2000, ge=100, le=5000),
) -> dict:
    return runtime_service.summarize_mvp_acceptance(seconds=seconds, event_limit=limit)


@router.get("/runtime/mvp/acceptance-judge", summary="Runtime Mvp Acceptance Judge")
async def runtime_mvp_acceptance_judge(
    seconds: int = Query(86400, ge=60, le=2592000),
    limit: int = Query(2000, ge=100, le=5000),
) -> dict:
    return runtime_service.evaluate_mvp_acceptance_judge(seconds=seconds, event_limit=limit)


@router.get("/runtime/mvp/local-baselines", summary="Runtime Mvp Local Baselines")
async def runtime_mvp_local_baselines(
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    return mvp_baseline_service.list_local_mvp_baselines(limit=limit)
