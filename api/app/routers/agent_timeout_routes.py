"""Agent timeout sample and recommendation routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import timeout_adaptive_service

router = APIRouter()


@router.get("/timeout-metrics", summary="Agent timeout efficiency metrics")
async def get_timeout_metrics() -> dict:
    return timeout_adaptive_service.timeout_metrics()


@router.get("/timeout-recommendation", summary="Adaptive timeout recommendation")
async def get_timeout_recommendation(
    task_type: str = Query(..., min_length=1),
    provider: str = Query(..., min_length=1),
    baseline_seconds: int | None = Query(default=None, ge=1),
) -> dict:
    return timeout_adaptive_service.timeout_recommendation(
        task_type=task_type,
        provider=provider,
        baseline_seconds=baseline_seconds,
    )


@router.post("/timeout-samples", status_code=201, summary="Record a timeout sample")
async def create_timeout_sample(sample: dict) -> dict:
    try:
        return timeout_adaptive_service.record_timeout_sample(sample)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
