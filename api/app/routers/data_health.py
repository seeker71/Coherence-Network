"""Data hygiene API — row counts, growth, snapshots, health score."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.data_health import DataHealthResponse, SnapshotCreateResponse, SnapshotsListResponse
from app.services.data_hygiene_service import (
    DataHealthUnavailable,
    build_data_health_payload,
    list_snapshots_api,
    persist_snapshot,
)

router = APIRouter()


@router.get("/data-health", response_model=DataHealthResponse)
async def get_data_health() -> DataHealthResponse:
    """Operational row counts and growth vs stored snapshots (read-only; no friction side effects)."""
    try:
        payload = build_data_health_payload(evaluate_friction=False)
        return DataHealthResponse(**payload)
    except DataHealthUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "data_health_unavailable", "reason": str(exc.reason)},
        ) from exc


@router.get("/data-health/snapshots", response_model=SnapshotsListResponse)
async def get_snapshots(
    limit: int = Query(20, ge=1, le=100, description="Capped at 100 for safety"),
) -> SnapshotsListResponse:
    try:
        data = list_snapshots_api(limit=limit)
        return SnapshotsListResponse(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "data_health_unavailable", "reason": str(exc)},
        ) from exc


@router.post("/data-health/snapshot", response_model=SnapshotCreateResponse)
async def post_snapshot() -> SnapshotCreateResponse:
    """Record a new row-count snapshot and evaluate growth thresholds (may open friction events)."""
    try:
        out = persist_snapshot(source="api")
        return SnapshotCreateResponse(**out)
    except DataHealthUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "data_health_unavailable", "reason": str(exc.reason)},
        ) from exc
