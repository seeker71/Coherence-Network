"""Agent status-report and pipeline-status routes."""

import json
import os

from fastapi import APIRouter
from datetime import datetime, timezone

from app.routers import agent_monitor_helpers
from app.routers.agent_monitor_helpers import (
    build_fallback_status_report,
    merge_meta_questions_into_report,
    read_json_dict,
    resolve_monitor_issues_payload,
    status_report_max_age_seconds,
    timestamp_is_fresh,
)
from app.services import agent_service

router = APIRouter()


@router.get("/status-report")
async def get_status_report() -> dict:
    """Hierarchical pipeline status (Layer 0 Goal → 1 Orchestration → 2 Execution → 3 Attention).
    Machine and human readable. Written by monitor each check. Includes meta_questions (unanswered/failed) when present."""
    logs_dir = agent_monitor_helpers.agent_logs_dir()
    path = os.path.join(logs_dir, "pipeline_status_report.json")
    now = datetime.now(timezone.utc)
    report = read_json_dict(path)
    if report is not None and timestamp_is_fresh(
        report.get("generated_at"),
        now=now,
        max_age_seconds=status_report_max_age_seconds(),
    ):
        report = dict(report)
        report.setdefault("fallback_reason", None)
        report.setdefault("source", "monitor_report")
        report.setdefault("fallbacks_used", [])
        return merge_meta_questions_into_report(report, logs_dir)

    if not os.path.isfile(path):
        fallback_reason = "missing_status_report_file"
        stale_generated_at = None
    elif report is None:
        fallback_reason = "unreadable_status_report_file"
        stale_generated_at = None
    else:
        fallback_reason = "stale_status_report_file"
        stale_generated_at = report.get("generated_at")

    monitor_payload = resolve_monitor_issues_payload(logs_dir, now=now)
    try:
        from app.services.effectiveness_service import get_effectiveness as _get_effectiveness

        effectiveness = _get_effectiveness()
    except Exception:
        effectiveness = None

    fallback_report = build_fallback_status_report(
        now=now,
        fallback_reason=fallback_reason,
        monitor_payload=monitor_payload,
        effectiveness=effectiveness if isinstance(effectiveness, dict) else None,
        stale_report_generated_at=stale_generated_at,
    )
    return merge_meta_questions_into_report(fallback_report, logs_dir)


@router.get("/pipeline-status")
async def get_pipeline_status() -> dict:
    """Pipeline visibility: running task, pending with wait times, recent completed with duration.
    Includes project manager state when available. For running tasks, includes live_tail (last 20 lines of streamed log).
    Returns 200 in empty state (no running task) per spec 039; body always includes running, pending, recent_completed, attention, running_by_phase."""
    status = agent_service.get_pipeline_status()
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase", "diagnostics"):
        if key not in status:
            if key in ("running", "pending", "recent_completed"):
                status[key] = []
            elif key == "attention":
                status[key] = {}
            elif key == "running_by_phase":
                status[key] = {"spec": 0, "impl": 0, "test": 0, "review": 0}
            else:
                status[key] = {}
    if "attention" in status and isinstance(status["attention"], dict):
        for att_key in ("stuck", "repeated_failures", "low_success_rate", "flags"):
            if att_key not in status["attention"]:
                status["attention"][att_key] = False if att_key != "flags" else []
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    state_file = os.path.join(logs_dir, "project_manager_state.json")
    overnight_file = os.path.join(logs_dir, "project_manager_state_overnight.json")
    if os.path.isfile(overnight_file) and (
        not os.path.isfile(state_file) or os.path.getmtime(overnight_file) > os.path.getmtime(state_file)
    ):
        state_file = overnight_file
    if os.path.isfile(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                status["project_manager"] = json.load(f)
        except Exception:
            status["project_manager"] = None
    else:
        status["project_manager"] = None
    running = status.get("running") or []
    if running:
        rid = running[0].get("id")
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", f"task_{rid}.log")
        if os.path.isfile(log_path):
            try:
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()
                status["running"][0]["live_tail"] = [ln.rstrip() for ln in lines[-20:] if ln.strip()]
            except Exception:
                status["running"][0]["live_tail"] = None
        else:
            status["running"][0]["live_tail"] = None
    return status
