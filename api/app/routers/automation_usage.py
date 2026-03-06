"""Automation provider usage and capacity endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

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
        payload = await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.cached_usage_overview_payload,
                force_refresh=force_refresh,
                compact=compact,
                include_raw=include_raw,
            ),
            timeout=timeout_seconds,
        )
        if isinstance(payload, dict) and "meta" not in payload:
            payload = {**payload, "meta": {"data_source": "live_or_cache", "fallbacks_used": []}}
        return payload
    except TimeoutError:
        payload = automation_usage_service.usage_overview_payload_from_snapshots(
            compact=compact,
            include_raw=include_raw,
        )
        if isinstance(payload, dict):
            payload = {**payload, "meta": {"data_source": "snapshot_fallback", "fallback_reason": "timeout", "fallbacks_used": ["timeout"]}}
        return payload


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
    timeout_seconds = automation_usage_service.usage_endpoint_timeout_seconds(default=2.0)
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.cached_usage_alerts_payload,
                threshold_ratio=threshold_ratio,
                force_refresh=force_refresh,
            ),
            timeout=timeout_seconds,
        )
        if isinstance(payload, dict) and "meta" not in payload:
            payload = {**payload, "meta": {"data_source": "live_or_cache", "fallbacks_used": []}}
        return payload
    except TimeoutError:
        payload = automation_usage_service.evaluate_usage_alerts(
            threshold_ratio=threshold_ratio,
            force_refresh=False,
        ).model_dump(mode="json")
        if isinstance(payload, dict):
            payload = {**payload, "meta": {"data_source": "snapshot_fallback", "fallback_reason": "timeout", "fallbacks_used": ["timeout"]}}
        return payload


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
        payload = await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.cached_provider_readiness_payload,
                required_providers=requested or None,
                force_refresh=force_refresh,
            ),
            timeout=timeout_seconds,
        )
        if isinstance(payload, dict) and "meta" not in payload:
            payload = {**payload, "meta": {"data_source": "live_or_cache", "fallbacks_used": []}}
        return payload
    except TimeoutError:
        payload = automation_usage_service.provider_readiness_report_from_snapshots(
            required_providers=requested or None,
        ).model_dump(mode="json")
        if isinstance(payload, dict):
            payload = {**payload, "meta": {"data_source": "snapshot_fallback", "fallback_reason": "timeout", "fallbacks_used": ["timeout"]}}
        return payload


@router.get("/automation/usage/daily-summary")
async def get_automation_usage_daily_summary(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    top_n: int = Query(3, ge=1, le=20),
    force_refresh: bool = Query(False),
) -> dict:
    timeout_seconds = automation_usage_service.usage_endpoint_timeout_seconds(default=2.0)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.cached_daily_system_summary_payload,
                window_hours=window_hours,
                top_n=top_n,
                force_refresh=force_refresh,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        cached_payload = automation_usage_service.daily_system_summary_cached_payload(
            window_hours=window_hours,
            top_n=top_n,
        )
        if isinstance(cached_payload, dict):
            cached_payload = {**cached_payload, "meta": {"data_source": "cached_fallback", "fallback_reason": "timeout", "fallbacks_used": ["timeout"]}}
            return cached_payload
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_hours": int(window_hours),
            "meta": {"data_source": "empty_fallback", "fallback_reason": "timeout_no_cache", "fallbacks_used": ["timeout", "no_cache"]},
            "host_failure_observability_backfill": {
                "window_hours": int(window_hours),
                "host_failed_tasks": 0,
                "completion_events_backfilled": 0,
                "friction_events_backfilled": 0,
                "affected_task_ids": [],
                "error": "daily_summary_timeout",
            },
            "host_runner": {
                "window_hours": int(window_hours),
                "total_runs": 0,
                "failed_runs": 0,
                "completed_runs": 0,
                "running_runs": 0,
                "pending_runs": 0,
                "status_counts": {},
                "by_task_type": {},
            },
            "execution": {
                "tracked_runs": 0,
                "failed_runs": 0,
                "success_runs": 0,
                "coverage": {},
            },
            "tool_usage": {
                "worker_events": 0,
                "worker_failed_events": 0,
                "attention_worker_events": None,
                "attention_worker_failed_events": None,
                "attention_worker_event_gap": None,
                "attention_worker_failed_event_gap": None,
                "top_tools": [],
            },
            "friction": {
                "total_events": 0,
                "open_events": 0,
                "top_block_types": [],
                "top_stages": [],
                "entry_points": [],
            },
            "providers": [],
            "top_attention_areas": [],
            "tool_reliability_goal": {
                "target_success_rate": 0.75,
                "window_calls": 10,
                "target_successes": 8,
                "tracked_tools": 0,
                "tools_meeting_target": 0,
                "tools_below_target": 0,
                "rows": [],
            },
            "contract_gaps": [
                "daily summary timed out and no cached payload was available",
            ],
            "quality_awareness": {
                "status": "unavailable",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "intent_focus": [],
                "summary": {
                    "severity": "medium",
                    "risk_score": 0,
                    "regression": False,
                    "regression_reasons": [],
                    "python_module_count": 0,
                    "runtime_file_count": 0,
                    "layer_violations": 0,
                    "large_modules": 0,
                    "very_large_modules": 0,
                    "long_functions": 0,
                    "placeholder_findings": 0,
                },
                "hotspots": [],
                "guidance": [],
                "recommended_tasks": [],
            },
        }


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
    timeout_seconds = automation_usage_service.usage_endpoint_timeout_seconds(default=2.0)
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(
                automation_usage_service.cached_provider_validation_payload,
                required_providers=requested or None,
                runtime_window_seconds=runtime_window_seconds,
                min_execution_events=min_execution_events,
                force_refresh=force_refresh,
            ),
            timeout=timeout_seconds,
        )
        if isinstance(payload, dict) and "meta" not in payload:
            payload = {**payload, "meta": {"data_source": "live_or_cache", "fallbacks_used": []}}
        return payload
    except TimeoutError:
        payload = automation_usage_service.cached_provider_validation_payload(
            required_providers=requested or None,
            runtime_window_seconds=runtime_window_seconds,
            min_execution_events=min_execution_events,
            force_refresh=False,
        )
        if isinstance(payload, dict):
            payload = {**payload, "meta": {"data_source": "snapshot_fallback", "fallback_reason": "timeout", "fallbacks_used": ["timeout"]}}
        return payload
