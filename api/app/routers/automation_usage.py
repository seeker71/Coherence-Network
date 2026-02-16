"""Automation provider usage and capacity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import automation_usage_service

router = APIRouter()


@router.get("/automation/usage")
async def get_automation_usage(force_refresh: bool = Query(False)) -> dict:
    overview = automation_usage_service.collect_usage_overview(force_refresh=force_refresh)
    return overview.model_dump(mode="json")


@router.get("/automation/usage/snapshots")
async def get_automation_usage_snapshots(limit: int = Query(200, ge=1, le=2000)) -> dict:
    rows = automation_usage_service.list_usage_snapshots(limit=limit)
    return {
        "count": len(rows),
        "snapshots": [row.model_dump(mode="json") for row in rows],
    }


@router.get("/automation/usage/alerts")
async def get_automation_usage_alerts(threshold_ratio: float = Query(0.2, ge=0.0, le=1.0)) -> dict:
    report = automation_usage_service.evaluate_usage_alerts(threshold_ratio=threshold_ratio)
    return report.model_dump(mode="json")
