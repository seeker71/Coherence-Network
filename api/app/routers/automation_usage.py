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


@router.get("/automation/usage/subscription-estimator")
async def get_subscription_upgrade_estimator() -> dict:
    report = automation_usage_service.estimate_subscription_upgrades()
    return report.model_dump(mode="json")


@router.get("/automation/usage/readiness")
async def get_provider_readiness(
    required_providers: str = Query("", description="Comma-separated provider ids to require"),
    force_refresh: bool = Query(True),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    report = automation_usage_service.provider_readiness_report(
        required_providers=requested or None,
        force_refresh=force_refresh,
    )
    return report.model_dump(mode="json")


@router.post("/automation/usage/provider-validation/run")
async def run_provider_validation_probes(
    required_providers: str = Query("", description="Comma-separated provider ids to probe"),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    report = automation_usage_service.run_provider_validation_probes(
        required_providers=requested or None,
    )
    return report


@router.get("/automation/usage/provider-validation")
async def get_provider_validation_report(
    required_providers: str = Query("", description="Comma-separated provider ids to validate"),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    min_execution_events: int = Query(1, ge=1, le=50),
    force_refresh: bool = Query(True),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    report = automation_usage_service.provider_validation_report(
        required_providers=requested or None,
        runtime_window_seconds=runtime_window_seconds,
        min_execution_events=min_execution_events,
        force_refresh=force_refresh,
    )
    return report.model_dump(mode="json")
