"""Monitor and status-report helpers for agent routes. No routes."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.routers.agent_helpers import issue_priority_map
from app.services import agent_service
from app.services.agent_monitor_guidance_service import low_success_rate_suggested_action
from app.services.config_service import get_config

logger = logging.getLogger(__name__)


def agent_logs_dir() -> str:
    """Logs directory for status-report and meta_questions; overridable in tests."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")


def _get_config_int(key: str, default: int) -> int:
    """Get integer config value with fallback chain."""
    config = get_config()
    value = config.get(key)
    if value is not None:
        try:
            return max(60, int(value))
        except (TypeError, ValueError):
            pass
    return default


def orphan_threshold_seconds() -> int:
    """Get orphan threshold seconds from config."""
    return _get_config_int("pipeline_orphan_running_seconds", 1800)


def monitor_max_age_seconds() -> int:
    """Get monitor max age seconds from config."""
    return _get_config_int("monitor_issues_max_age_seconds", 900)


def status_report_max_age_seconds() -> int:
    """Get status report max age seconds from config."""
    return _get_config_int("pipeline_status_report_max_age_seconds", 900)


def pending_actionable_window_seconds() -> int:
    """Window where pending tasks imply an active runner should be moving."""
    return _get_config_int("pipeline_pending_actionable_window_seconds", 86400)


def parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def timestamp_is_fresh(value: Any, *, now: datetime, max_age_seconds: int) -> bool:
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return False
    age_seconds = (now - parsed).total_seconds()
    return 0 <= age_seconds <= max_age_seconds


def read_json_dict(path: str) -> dict[str, Any] | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        logger.warning("Failed to read JSON dict from %s", path, exc_info=True)
        return None
    return None


def derived_issue(
    condition: str,
    severity: str,
    message: str,
    suggested_action: str,
    *,
    now: datetime,
) -> dict[str, Any]:
    priority_map = issue_priority_map()
    normalized_severity = str(severity or "medium").strip().lower()
    priority = priority_map.get(normalized_severity, 2)
    return {
        "id": f"derived-{condition}",
        "condition": condition,
        "severity": normalized_severity,
        "priority": priority,
        "message": message,
        "suggested_action": suggested_action,
        "created_at": now.isoformat(),
        "resolved_at": None,
        "source": "derived_pipeline_status",
    }


def running_seconds(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def wait_seconds(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def actionable_pending_tasks(pending: list[Any]) -> list[dict[str, Any]]:
    window = pending_actionable_window_seconds()
    active: list[dict[str, Any]] = []
    for item in pending:
        if not isinstance(item, dict):
            continue
        wait = wait_seconds(item.get("wait_seconds"))
        if wait is None or 0 <= wait <= window:
            active.append(item)
    return active


def dormant_pending_tasks(pending: list[Any]) -> list[dict[str, Any]]:
    window = pending_actionable_window_seconds()
    dormant: list[dict[str, Any]] = []
    for item in pending:
        if not isinstance(item, dict):
            continue
        wait = wait_seconds(item.get("wait_seconds"))
        if wait is not None and wait > window:
            dormant.append(item)
    return dormant


def _diagnostic_count_fragments(
    diagnostics: dict[str, Any],
    key: str,
    label_key: str,
    *,
    limit: int = 3,
) -> list[str]:
    rows = diagnostics.get(key) if isinstance(diagnostics.get(key), list) else []
    fragments: list[str] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        label = str(row.get(label_key) or "").strip()
        count = row.get("count")
        try:
            normalized_count = int(count)
        except (TypeError, ValueError):
            normalized_count = 0
        if label and normalized_count > 0:
            fragments.append(f"{label} x{normalized_count}")
    return fragments


def low_success_rate_context(status: dict[str, Any] | None = None) -> tuple[str, str]:
    """Summarize current task-metric failure shape for monitor issue text."""
    try:
        from app.services.metrics_service import get_aggregates

        metrics = get_aggregates()
    except Exception:
        logger.warning("Failed to load metrics for low_success_rate context", exc_info=True)
        return (
            "7d success rate is below target (<80%).",
            "Run targeted prompt/model diagnostics and capture remediation in the meta pipeline.",
        )

    success = metrics.get("success_rate") if isinstance(metrics.get("success_rate"), dict) else {}
    completed = int(success.get("completed") or 0)
    failed = int(success.get("failed") or 0)
    total = int(success.get("total") or 0)
    rate = float(success.get("rate") or 0.0)
    message = (
        f"7d success rate is {int(round(rate * 100))}% "
        f"({completed} completed / {failed} failed / {total} resolved), below target (<80%)."
    )

    by_task_type = metrics.get("by_task_type") if isinstance(metrics.get("by_task_type"), dict) else {}
    weak_types: list[tuple[str, int, int, float]] = []
    for task_type, row in by_task_type.items():
        if not isinstance(row, dict):
            continue
        type_completed = int(row.get("completed") or 0)
        type_failed = int(row.get("failed") or 0)
        type_total = type_completed + type_failed
        if type_total <= 0 or type_failed <= 0:
            continue
        type_rate = float(row.get("success_rate") or 0.0)
        if type_rate < 0.8:
            weak_types.append((str(task_type), type_completed, type_failed, type_rate))
    weak_types.sort(key=lambda item: (-item[2], item[3], item[0]))
    diagnostics = status.get("diagnostics") if isinstance(status, dict) and isinstance(status.get("diagnostics"), dict) else {}
    if weak_types:
        fragments = [
            f"{task_type} {int(round(type_rate * 100))}% ({type_completed}/{type_failed})"
            for task_type, type_completed, type_failed, type_rate in weak_types[:3]
        ]
        message = f"{message} Weak task types: {', '.join(fragments)}."
        suggested = low_success_rate_suggested_action(diagnostics, weak_types[0][0])
    else:
        suggested = low_success_rate_suggested_action(diagnostics, "prompt/model")

    if diagnostics:
        reason_fragments = _diagnostic_count_fragments(diagnostics, "recent_failed_reasons", "reason")
        signature_fragments = _diagnostic_count_fragments(diagnostics, "recent_failed_signatures", "signature", limit=2)
        if reason_fragments:
            message = f"{message} Recent failure buckets: {', '.join(reason_fragments)}."
        if signature_fragments:
            message = f"{message} Top signatures: {', '.join(signature_fragments)}."
    return message, suggested


def derive_monitor_issues_from_pipeline_status(status: dict[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    running = status.get("running") if isinstance(status.get("running"), list) else []
    pending = status.get("pending") if isinstance(status.get("pending"), list) else []
    att = status.get("attention") if isinstance(status.get("attention"), dict) else {}
    issues: list[dict[str, Any]] = []

    active_pending = actionable_pending_tasks(pending)
    dormant_pending = dormant_pending_tasks(pending)
    wait_values = [wait_seconds(item.get("wait_seconds")) for item in active_pending]
    wait_seconds_list = [value for value in wait_values if value is not None]
    max_wait = max(wait_seconds_list) if wait_seconds_list else 0
    stuck = (bool(att.get("stuck")) and bool(active_pending)) or (
        bool(active_pending) and not bool(running) and max_wait > 600
    )
    if stuck:
        issues.append(
            derived_issue(
                "no_task_running",
                "high",
                f"No task running for {max_wait}s despite {len(active_pending)} actionable pending.",
                "Restart agent runner and verify task claims progress.",
                now=now,
            )
        )

    if dormant_pending:
        dormant_waits = [
            value
            for value in (wait_seconds(item.get("wait_seconds")) for item in dormant_pending)
            if value is not None
        ]
        oldest_wait = max(dormant_waits) if dormant_waits else 0
        issues.append(
            derived_issue(
                "dormant_pending_backlog",
                "medium",
                (
                    f"{len(dormant_pending)} pending task(s) are dormant beyond "
                    f"{pending_actionable_window_seconds()}s; oldest_wait={oldest_wait}s."
                ),
                (
                    "Review dormant pending tasks, then release completed/obsolete rows, "
                    "requeue still-valid work with fresh context, or restart a runner intentionally."
                ),
                now=now,
            )
        )

    if bool(att.get("repeated_failures")):
        issues.append(
            derived_issue(
                "repeated_failures",
                "high",
                "3+ consecutive failed tasks detected in recent completions.",
                "Review recent task logs and isolate root cause before continuing new executions.",
                now=now,
            )
        )
    if bool(att.get("output_empty")):
        issues.append(
            derived_issue(
                "output_empty",
                "high",
                "Recent completed task has empty output.",
                "Check agent runner log streaming/capture and task log persistence.",
                now=now,
            )
        )
    if bool(att.get("executor_fail")):
        issues.append(
            derived_issue(
                "executor_fail",
                "high",
                "Recent failed task has empty output (likely executor/tool failure).",
                "Validate executor path and dependency availability in runner environment.",
                now=now,
            )
        )
    if bool(att.get("low_success_rate")):
        message, suggested_action = low_success_rate_context(status)
        issues.append(
            derived_issue(
                "low_success_rate",
                "medium",
                message,
                suggested_action,
                now=now,
            )
        )

    threshold = orphan_threshold_seconds()
    stale_running: list[dict[str, Any]] = []
    for item in running:
        if not isinstance(item, dict):
            continue
        run_seconds = running_seconds(item.get("running_seconds"))
        if run_seconds is None or run_seconds <= threshold:
            continue
        stale_running.append(
            {
                "id": str(item.get("id") or "").strip(),
                "running_seconds": int(run_seconds),
            }
        )
    if stale_running:
        stale_ids = [row["id"] for row in stale_running if row.get("id")]
        preview = ", ".join(stale_ids[:5]) if stale_ids else "unknown"
        if len(stale_ids) > 5:
            preview = f"{preview}, ..."
        longest = max(row["running_seconds"] for row in stale_running)
        threshold_minutes = max(1, int(round(threshold / 60)))
        issues.append(
            derived_issue(
                "orphan_running",
                "high",
                (
                    f"{len(stale_running)} running task(s) exceeded stale threshold "
                    f"{threshold}s (~{threshold_minutes}m); longest={longest}s; ids={preview}"
                ),
                "Patch stale task(s) to failed and restart runner/watchdog to recover claims.",
                now=now,
            )
        )

    return issues


def derived_monitor_payload(
    status: dict[str, Any],
    *,
    now: datetime,
    fallback_reason: str,
    prior_last_check: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "issues": derive_monitor_issues_from_pipeline_status(status, now=now),
        "last_check": now.isoformat(),
        "history": [],
        "source": "derived_pipeline_status",
        "fallback_reason": fallback_reason,
    }
    prior_last = str(prior_last_check or "").strip()
    if prior_last:
        payload["monitor_last_check"] = prior_last
    return payload


def resolve_monitor_issues_payload(logs_dir: str, *, now: datetime) -> dict[str, Any]:
    path = os.path.join(logs_dir, "monitor_issues.json")
    raw_payload = read_json_dict(path)
    if raw_payload is not None and timestamp_is_fresh(
        raw_payload.get("last_check"),
        now=now,
        max_age_seconds=monitor_max_age_seconds(),
    ):
        return raw_payload

    if not os.path.isfile(path):
        reason = "missing_monitor_issues_file"
        prior_last_check = None
    elif raw_payload is None:
        reason = "unreadable_monitor_issues_file"
        prior_last_check = None
    else:
        reason = "stale_monitor_issues_file"
        prior_last_check = raw_payload.get("last_check")

    logger.warning("Monitor issues payload unavailable (%s), returning derived fallback", reason)
    status = agent_service.get_pipeline_status()
    return derived_monitor_payload(
        status,
        now=now,
        fallback_reason=reason,
        prior_last_check=prior_last_check,
    )


def build_fallback_status_report(
    *,
    now: datetime,
    fallback_reason: str,
    monitor_payload: dict[str, Any],
    effectiveness: dict[str, Any] | None,
    stale_report_generated_at: Any = None,
) -> dict[str, Any]:
    status = agent_service.get_pipeline_status()
    issues = (
        monitor_payload.get("issues")
        if isinstance(monitor_payload.get("issues"), list)
        else []
    )
    running = status.get("running") if isinstance(status.get("running"), list) else []
    pending = status.get("pending") if isinstance(status.get("pending"), list) else []
    active_pending = actionable_pending_tasks(pending)
    dormant_pending_count = len(dormant_pending_tasks(pending))
    recent_completed = (
        status.get("recent_completed")
        if isinstance(status.get("recent_completed"), list)
        else []
    )
    pm = status.get("project_manager") if isinstance(status.get("project_manager"), dict) else {}

    layer0: dict[str, Any] = {
        "status": "unknown",
        "summary": "Derived from live pipeline state; monitor report unavailable.",
    }
    if effectiveness:
        gp = float(effectiveness.get("goal_proximity", 0.0) or 0.0)
        throughput = (
            effectiveness.get("throughput")
            if isinstance(effectiveness.get("throughput"), dict)
            else {}
        )
        success_rate = float(effectiveness.get("success_rate", 0.0) or 0.0)
        layer0 = {
            "status": "ok" if gp >= 0.7 and not issues else "needs_attention",
            "goal_proximity": gp,
            "throughput_7d": throughput.get("completed_7d", 0),
            "tasks_per_day": throughput.get("tasks_per_day", 0),
            "success_rate": success_rate,
            "summary": (
                f"{throughput.get('completed_7d', 0)} tasks (7d), "
                f"{int(success_rate * 100)}% success"
            ),
        }
    elif issues:
        layer0["status"] = "needs_attention"
        layer0["summary"] = "Monitor report unavailable and live pipeline indicates active issues."

    pm_seen = bool(pm) and (
        pm.get("backlog_index") is not None
        or pm.get("phase") is not None
        or pm.get("in_flight")
    )
    runner_seen = bool(running)
    layer1 = {
        "status": "ok" if (pm_seen or runner_seen or not active_pending) else "needs_attention",
        "project_manager": "running" if pm_seen else ("idle" if pm else "unknown"),
        "pm_in_flight": len(pm.get("in_flight") or []) if isinstance(pm.get("in_flight"), list) else 0,
        "agent_runner": "running" if runner_seen else ("unknown" if not active_pending else "not_seen"),
        "runner_workers": None,
        "pm_parallel": None,
        "summary": (
            f"running={len(running)}, actionable_pending={len(active_pending)}, "
            f"dormant_pending={dormant_pending_count}, "
            f"pm_phase={pm.get('phase', '?') if isinstance(pm, dict) else '?'}"
        ),
    }

    issue_conditions = {
        str(item.get("condition") or "").strip()
        for item in issues
        if isinstance(item, dict)
    }
    execution_needs_attention = bool(
        {"api_unreachable", "metrics_unavailable", "no_task_running", "orphan_running"}
        & issue_conditions
    )
    layer2 = {
        "status": "needs_attention" if execution_needs_attention else "ok",
        "running": running,
        "pending": pending,
        "diagnostics": status.get("diagnostics") if isinstance(status.get("diagnostics"), dict) else {},
        "actionable_pending_count": len(active_pending),
        "dormant_pending_count": dormant_pending_count,
        "recent_completed": recent_completed,
        "summary": (
            f"running={len(running)}, actionable_pending={len(active_pending)}, "
            f"dormant_pending={dormant_pending_count}, recent_completed={len(recent_completed)}"
        ),
    }

    layer3 = {
        "status": "ok" if not issues else "needs_attention",
        "issues_count": len(issues),
        "issues": [
            {
                "priority": item.get("priority"),
                "condition": item.get("condition"),
                "severity": item.get("severity"),
                "message": (item.get("message") or "")[:120],
            }
            for item in issues[:10]
            if isinstance(item, dict)
        ],
        "summary": "No issues" if not issues else f"{len(issues)} issue(s) need attention",
    }

    going_well: list[str] = []
    if layer0.get("status") == "ok":
        going_well.append("goal_proximity")
    if layer1.get("status") == "ok":
        going_well.append("orchestration_active")
    if layer2.get("status") == "ok":
        going_well.append("execution_flow")
    if layer3.get("status") == "ok":
        going_well.append("no_issues")

    overall_status = "needs_attention" if any(
        layer.get("status") == "needs_attention"
        for layer in (layer0, layer1, layer2, layer3)
    ) else "ok"

    report: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "overall": {
            "status": overall_status,
            "going_well": going_well,
            "needs_attention": [cond for cond in sorted(issue_conditions) if cond],
        },
        "layer_0_goal": layer0,
        "layer_1_orchestration": layer1,
        "layer_2_execution": layer2,
        "layer_3_attention": layer3,
        "source": "derived_pipeline_status",
        "fallback_reason": fallback_reason,
        "fallbacks_used": [fallback_reason],
    }
    stale_generated = str(stale_report_generated_at or "").strip()
    if stale_generated:
        report["monitor_report_generated_at"] = stale_generated
    return report


def merge_meta_questions_into_report(report: dict, logs_dir: str) -> dict:
    """If report lacks meta_questions but api/logs/meta_questions.json exists, merge it (surface unanswered/failed)."""
    if "meta_questions" in report:
        return report
    mq_path = os.path.join(logs_dir, "meta_questions.json")
    if not os.path.isfile(mq_path):
        return report
    try:
        with open(mq_path, encoding="utf-8") as f:
            mq = json.load(f)
    except Exception:
        return report
    summary = mq.get("summary") or {}
    unanswered = summary.get("unanswered") or []
    failed = summary.get("failed") or []
    mq_status = "ok" if not unanswered and not failed else "needs_attention"
    report["meta_questions"] = {
        "status": mq_status,
        "last_run": mq.get("run_at"),
        "unanswered": unanswered,
        "failed": failed,
    }
    if mq_status == "needs_attention":
        report.setdefault("overall", {})
        report["overall"].setdefault("needs_attention", [])
        if "meta_questions" not in report["overall"]["needs_attention"]:
            report["overall"]["needs_attention"] = report["overall"]["needs_attention"] + ["meta_questions"]
        report["overall"]["status"] = "needs_attention"
    return report
