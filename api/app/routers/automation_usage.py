"""Automation provider usage and capacity endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from app.services import automation_usage_service

router = APIRouter()


@router.get("/automation/usage")
async def get_automation_usage(
    force_refresh: bool = Query(False),
    compact: bool = Query(False, description="Return a trimmed payload for lower-bandwidth clients"),
    include_raw: bool = Query(False, description="Include provider raw payload in compact mode"),
) -> dict:
    timeout_seconds = automation_usage_service.usage_endpoint_timeout_seconds()
    try:
        overview = await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.collect_usage_overview,
                force_refresh=force_refresh,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        overview = automation_usage_service.usage_overview_from_snapshots()
    overview = automation_usage_service.coalesce_usage_overview_families(overview)
    if compact:
        return automation_usage_service.compact_usage_overview_payload(
            overview,
            include_raw=include_raw,
        )
    return overview.model_dump(mode="json")


@router.get("/automation/usage/snapshots")
async def get_automation_usage_snapshots(limit: int = Query(200, ge=1, le=2000)) -> dict:
    rows = automation_usage_service.list_usage_snapshots(limit=limit)
    return {
        "count": len(rows),
        "snapshots": [row.model_dump(mode="json") for row in rows],
    }


@router.get("/automation/usage/external-tools")
async def get_external_tool_usage_events(
    limit: int = Query(200, ge=1, le=5000),
    provider: str = Query("", description="Optional provider filter (e.g. github-actions)"),
    tool_name: str = Query("", description="Optional tool filter (e.g. github-api, gh-cli)"),
) -> dict:
    rows = automation_usage_service.list_external_tool_usage_events(
        limit=limit,
        provider=provider,
        tool_name=tool_name,
    )
    return {"count": len(rows), "events": rows}


@router.get("/automation/usage/alerts")
async def get_automation_usage_alerts(
    threshold_ratio: float = Query(0.2, ge=0.0, le=1.0),
    force_refresh: bool = Query(False),
) -> dict:
    report = automation_usage_service.evaluate_usage_alerts(
        threshold_ratio=threshold_ratio,
        force_refresh=force_refresh,
    )
    return report.model_dump(mode="json")


@router.get("/automation/usage/subscription-estimator")
async def get_subscription_upgrade_estimator() -> dict:
    report = automation_usage_service.estimate_subscription_upgrades()
    return report.model_dump(mode="json")


@router.get("/automation/usage/readiness")
async def get_provider_readiness(
    required_providers: str = Query("", description="Comma-separated provider ids to require"),
    force_refresh: bool = Query(False),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    timeout_seconds = automation_usage_service.usage_endpoint_timeout_seconds()
    try:
        report = await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.provider_readiness_report,
                required_providers=requested or None,
                force_refresh=force_refresh,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        report = automation_usage_service.provider_readiness_report_from_snapshots(
            required_providers=requested or None,
        )
    return report.model_dump(mode="json")


@router.get("/automation/usage/daily-summary")
async def get_automation_usage_daily_summary(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    top_n: int = Query(3, ge=1, le=20),
    force_refresh: bool = Query(False),
) -> dict:
    return automation_usage_service.daily_system_summary(
        window_hours=window_hours,
        top_n=top_n,
        force_refresh=force_refresh,
    )


@router.post("/automation/usage/provider-validation/run")
async def run_provider_validation_probes(
    required_providers: str = Query("", description="Comma-separated provider ids to probe"),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    report = automation_usage_service.run_provider_validation_probes(
        required_providers=requested or None,
    )
    return report


@router.post("/automation/usage/provider-heal/run")
async def run_provider_auto_heal(
    required_providers: str = Query("", description="Comma-separated provider ids to heal"),
    max_rounds: int = Query(2, ge=1, le=6),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    min_execution_events: int = Query(1, ge=1, le=10),
    enable_cli_installs: bool = Query(False, description="Attempt provider-specific CLI installers when binaries are missing"),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    report = automation_usage_service.run_provider_auto_heal(
        required_providers=requested or None,
        max_rounds=max_rounds,
        runtime_window_seconds=runtime_window_seconds,
        min_execution_events=min_execution_events,
        enable_cli_installs=enable_cli_installs,
    )
    return report


@router.get("/automation/usage/provider-validation")
async def get_provider_validation_report(
    required_providers: str = Query("", description="Comma-separated provider ids to validate"),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    min_execution_events: int = Query(1, ge=1, le=50),
    force_refresh: bool = Query(False),
) -> dict:
    requested = [item.strip().lower() for item in required_providers.split(",") if item.strip()]
    report = automation_usage_service.provider_validation_report(
        required_providers=requested or None,
        runtime_window_seconds=runtime_window_seconds,
        min_execution_events=min_execution_events,
        force_refresh=force_refresh,
    )
    return report.model_dump(mode="json")
