"""Agent fatal issues, monitor issues, metrics, effectiveness, collective-health routes."""

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.routers import agent_monitor_helpers
from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/fatal-issues")
async def get_fatal_issues() -> dict:
    """Unrecoverable failures. Check when autonomous; no user interaction needed until fatal."""
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    path = os.path.join(logs_dir, "fatal_issues.json")
    if not os.path.isfile(path):
        return {"fatal": False}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {"fatal": True, **data}
    except Exception:
        logger.warning("Failed to read fatal issues from %s", path, exc_info=True)
        return {"fatal": False}


@router.get("/monitor-issues")
async def get_monitor_issues() -> dict:
    """Monitor issues from automated pipeline check. Checkable; use to react and improve. Spec 027."""
    logs_dir = agent_monitor_helpers.agent_logs_dir()
    return resolve_monitor_issues_payload(logs_dir, now=datetime.now(timezone.utc))


@router.get("/metrics", summary="Task metrics (success rate, duration, by task_type/model)")
async def get_metrics(
    metric: str | None = Query(
        None,
        description="Filter: time, success, by_task_type, by_model, or omit for full response.",
    ),
    window_days: int | None = Query(
        None,
        ge=1,
        le=90,
        description="Rolling window in days (default 7). Spec 026 / tracking-infrastructure-upgrade.",
    ),
) -> dict:
    """Task metrics: success rate, execution time, by task_type, by model. Spec 026 Phase 1."""
    try:
        from app.services.metrics_service import get_aggregates

        data = get_aggregates(window_days=window_days)
    except ImportError:
        logger.warning("metrics_service not available, returning empty metrics", exc_info=True)
        data = {
            "success_rate": {"completed": 0, "failed": 0, "total": 0, "rate": 0.0},
            "execution_time": {"p50_seconds": 0, "p95_seconds": 0},
            "by_task_type": {},
            "by_model": {},
        }

    if metric:
        m = metric.strip().lower()
        if m == "time":
            return {"execution_time": data.get("execution_time", {"p50_seconds": 0, "p95_seconds": 0})}
        if m == "success":
            return {"success_rate": data.get("success_rate", {"completed": 0, "failed": 0, "total": 0, "rate": 0.0})}
        if m == "by_task_type":
            return {"by_task_type": data.get("by_task_type", {})}
        if m == "by_model":
            return {"by_model": data.get("by_model", {})}
    return data


@router.get("/effectiveness")
async def get_effectiveness() -> dict:
    """Pipeline effectiveness: throughput, success rate, issue tracking, progress, goal proximity."""
    try:
        from app.services.effectiveness_service import get_effectiveness as _get

        return _get()
    except ImportError:
        logger.warning("effectiveness_service not available, returning empty effectiveness", exc_info=True)
        return {
            "throughput": {"completed_7d": 0, "tasks_per_day": 0},
            "success_rate": 0.0,
            "issues": {"open": 0, "resolved_7d": 0},
            "progress": {},
            "goal_proximity": 0.0,
            "heal_resolved_count": 0,
            "top_issues_by_priority": [],
        }


@router.get("/collective-health")
async def get_collective_health(
    window_days: int = Query(7, ge=1, le=30),
) -> dict:
    """Collective health scorecard focused on coherence, resonance, flow, and friction."""
    try:
        from app.services.collective_health_service import get_collective_health as _get

        return _get(window_days=window_days)
    except ImportError:
        logger.warning("collective_health_service not available, returning empty scorecard", exc_info=True)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "window_days": window_days,
            "scores": {
                "coherence": 0.0,
                "resonance": 0.0,
                "flow": 0.0,
                "friction": 0.0,
                "collective_value": 0.0,
            },
            "coherence": {},
            "resonance": {},
            "flow": {},
            "friction": {},
            "top_friction_queue": [],
            "top_opportunities": [],
        }
