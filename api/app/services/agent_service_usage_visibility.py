"""Agent usage, visibility, and orchestration guidance summaries."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.agent import TaskType

from app.services import agent_routing_service as routing_service
from app.services.agent_service_store import _ensure_store_loaded, _now, _parse_dt, _store
from app.services.agent_service_task_derive import status_value
from app.services.agent_service_executor import (
    executor_binary_name,
    get_route,
    cheap_executor_default,
    escalation_executor_default,
)
from app.services.agent_service_pipeline_status import get_pipeline_status
from app.services.agent_service_completion_tracking import has_completion_tracking_event, record_completion_tracking_event
from app.services.agent_service_friction import linked_task_ids_from_friction_events, record_task_failure_friction


def _metadata_text(value: Any, default: str = "unknown") -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or default
    if value is None:
        return default
    return str(value).strip() or default


def _metadata_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _execution_usage_summary(completed_or_failed_task_ids: list[str]) -> dict[str, Any]:
    tracked_task_ids = set()
    by_executor = {}
    by_agent = {}
    by_tool = {}
    recent_runs = []
    tracked_runs = failed_runs = codex_runs = 0
    try:
        from app.services import runtime_service
        events = runtime_service.list_events(limit=5000, source="worker")
    except Exception:
        events = []
    for event in events:
        if str(getattr(event, "source", "")).strip() != "worker":
            continue
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        task_id = _metadata_text(metadata.get("task_id"), default="")
        if not task_id:
            continue
        tracked_runs += 1
        tracked_task_ids.add(task_id)
        executor = _metadata_text(metadata.get("executor"))
        agent_id = _metadata_text(metadata.get("agent_id"), default="") or _metadata_text(metadata.get("worker_id"))
        is_openai_codex = _metadata_bool(metadata.get("is_openai_codex")) or (agent_id.lower() == "openai-codex")
        provider = _metadata_text(metadata.get("provider"), default="")
        if not provider:
            provider = "openai-codex" if is_openai_codex else ("claude" if executor == "claude" else "")
        if is_openai_codex:
            codex_runs += 1
        status_key = "failed" if int(getattr(event, "status_code", 0)) >= 400 else "completed"
        if status_key == "failed":
            failed_runs += 1
        endpoint = _metadata_text(getattr(event, "endpoint", ""), default="unknown")
        endpoint_norm = endpoint.lstrip("/")
        tool_name = endpoint_norm.split("tool:", 1)[1].strip() if endpoint_norm.startswith("tool:") else endpoint_norm
        if tool_name == "agent" and executor:
            tool_name = executor
        tool_name = tool_name or "unknown"
        by_executor.setdefault(executor, {"count": 0, "completed": 0, "failed": 0})
        by_executor[executor]["count"] += 1
        by_executor[executor][status_key] += 1
        by_agent.setdefault(agent_id, {"count": 0, "completed": 0, "failed": 0})
        by_agent[agent_id]["count"] += 1
        by_agent[agent_id][status_key] += 1
        by_tool.setdefault(tool_name, {"count": 0, "completed": 0, "failed": 0})
        by_tool[tool_name]["count"] += 1
        by_tool[tool_name][status_key] += 1
        recent_runs.append({
            "event_id": getattr(event, "id", ""),
            "task_id": task_id,
            "endpoint": endpoint,
            "tool": tool_name,
            "status_code": int(getattr(event, "status_code", 0)),
            "executor": executor,
            "agent_id": agent_id,
            "provider": provider,
            "is_openai_codex": is_openai_codex,
            "runtime_ms": float(getattr(event, "runtime_ms", 0.0)),
            "recorded_at": getattr(event, "recorded_at").isoformat() if hasattr(getattr(event, "recorded_at"), "isoformat") else str(getattr(event, "recorded_at", "")),
        })
    completed_or_failed_set = {t for t in completed_or_failed_task_ids if t}
    tracked_set = completed_or_failed_set.intersection(tracked_task_ids)
    coverage_rate = 1.0 if len(completed_or_failed_set) == 0 else round(len(tracked_set) / len(completed_or_failed_set), 4)
    success_runs = max(0, tracked_runs - failed_runs)
    success_rate = 1.0 if tracked_runs == 0 else round(success_runs / tracked_runs, 4)
    for values in by_tool.values():
        total = int(values.get("count", 0) or 0)
        failures = int(values.get("failed", 0) or 0)
        values["success_rate"] = 1.0 if total == 0 else round(max(0, total - failures) / total, 4)
    return {
        "tracked_runs": tracked_runs,
        "failed_runs": failed_runs,
        "success_runs": success_runs,
        "success_rate": success_rate,
        "codex_runs": codex_runs,
        "by_executor": by_executor,
        "by_agent": by_agent,
        "by_tool": by_tool,
        "coverage": {
            "completed_or_failed_tasks": len(completed_or_failed_set),
            "tracked_task_runs": len(tracked_set),
            "coverage_rate": coverage_rate,
            "untracked_task_ids": sorted(completed_or_failed_set - tracked_set),
        },
        "recent_runs": recent_runs[:50],
    }


def _task_activity_time(task: dict[str, Any]) -> datetime | None:
    for key in ("updated_at", "created_at", "started_at"):
        value = task.get(key)
        if isinstance(value, datetime):
            return value
        parsed = _parse_dt(value)
        if parsed is not None:
            return parsed
    return None


def _is_host_runner_claimant(claimed_by: str) -> bool:
    cleaned = claimed_by.strip().lower()
    if not cleaned:
        return False
    return "railway-runner" in cleaned or cleaned.startswith("openai-codex:")


def _host_runner_usage_summary(tasks: list[dict[str, Any]], *, window_hours: int = 24) -> dict[str, Any]:
    now = _now()
    cutoff = now - timedelta(hours=max(1, min(int(window_hours), 24 * 30)))
    host_tasks = []
    for task in tasks:
        if not _is_host_runner_claimant(str(task.get("claimed_by") or "")):
            continue
        task_time = _task_activity_time(task)
        if task_time is None or task_time < cutoff:
            continue
        host_tasks.append(task)
    status_counts = {}
    task_type_counts = {}
    for task in host_tasks:
        st = status_value(task.get("status")) or "unknown"
        status_counts[st] = status_counts.get(st, 0) + 1
        tt = status_value(task.get("task_type")) or "unknown"
        row = task_type_counts.setdefault(tt, {"total": 0})
        row["total"] += 1
        row[st] = row.get(st, 0) + 1
    return {
        "window_hours": max(1, min(int(window_hours), 24 * 30)),
        "generated_at": now.isoformat(),
        "total_runs": len(host_tasks),
        "failed_runs": status_counts.get("failed", 0),
        "completed_runs": status_counts.get("completed", 0),
        "running_runs": status_counts.get("running", 0),
        "pending_runs": status_counts.get("pending", 0) + status_counts.get("needs_decision", 0),
        "status_counts": status_counts,
        "by_task_type": task_type_counts,
    }


def get_usage_summary() -> dict[str, Any]:
    _ensure_store_loaded(include_output=False)
    by_model = {}
    completed_or_failed_task_ids = []
    tasks = list(_store.values())
    for t in tasks:
        m = t.get("model", "unknown")
        if m not in by_model:
            by_model[m] = {"count": 0, "by_status": {}, "last_used": None}
        u = by_model[m]
        u["count"] += 1
        s = (t.get("status").value if hasattr(t.get("status"), "value") else str(t.get("status", ""))) or "pending"
        u["by_status"][s] = u["by_status"].get(s, 0) + 1
        ts = t.get("updated_at") or t.get("created_at")
        if ts:
            u["last_used"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        if s in {"completed", "failed"}:
            completed_or_failed_task_ids.append(str(t.get("id", "")).strip())
    return {
        "by_model": by_model,
        "execution": _execution_usage_summary(completed_or_failed_task_ids),
        "host_runner": _host_runner_usage_summary(tasks, window_hours=24),
    }


def backfill_host_runner_failure_observability(*, window_hours: int = 24) -> dict[str, Any]:
    _ensure_store_loaded()
    bounded_window = max(1, min(int(window_hours), 24 * 30))
    now = _now()
    cutoff = now - timedelta(hours=bounded_window)
    host_failed_tasks = []
    for task in _store.values():
        if status_value(task.get("status")) != "failed":
            continue
        if not _is_host_runner_claimant(str(task.get("claimed_by") or "")):
            continue
        task_time = _task_activity_time(task)
        if task_time is None or task_time < cutoff:
            continue
        host_failed_tasks.append(task)
    completion_backfilled = friction_backfilled = 0
    affected_task_ids = []
    linked_task_ids = linked_task_ids_from_friction_events()
    for task in host_failed_tasks:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            continue
        if not has_completion_tracking_event(task_id, "failed"):
            record_completion_tracking_event(task)
            completion_backfilled += 1
            affected_task_ids.append(task_id)
        if record_task_failure_friction(task, linked_task_ids=linked_task_ids):
            friction_backfilled += 1
            if task_id not in affected_task_ids:
                affected_task_ids.append(task_id)
    return {
        "window_hours": bounded_window,
        "host_failed_tasks": len(host_failed_tasks),
        "completion_events_backfilled": completion_backfilled,
        "friction_events_backfilled": friction_backfilled,
        "affected_task_ids": affected_task_ids[:50],
    }


def _friction_note_value(notes: str, key: str) -> str:
    pattern = rf"(?:^|\s){re.escape(key)}=([^\s]+)"
    match = re.search(pattern, notes or "")
    return str(match.group(1) or "").strip() if match else ""


def _friction_rate(numerator: int, denominator: int) -> float:
    return 1.0 if denominator <= 0 else round(float(numerator) / float(denominator), 4)


def _event_has_task_model_tool_trace(event: Any) -> bool:
    notes = str(getattr(event, "notes", "") or "")
    task_id = str(getattr(event, "task_id", "") or "").strip() or _friction_note_value(notes, "task_id")
    model = str(getattr(event, "model", "") or "").strip() or _friction_note_value(notes, "model")
    tool = str(getattr(event, "tool", "") or "").strip() or _friction_note_value(notes, "tool")
    return bool(task_id and model and tool)


def _partition_events_by_recent(events: list, *, cutoff: datetime, timestamp_field: str = "timestamp") -> tuple[list, list]:
    recent, prior = [], []
    for event in events:
        ts = getattr(event, timestamp_field, None)
        if not isinstance(ts, datetime):
            prior.append(event)
            continue
        ts_norm = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        (recent if ts_norm >= cutoff else prior).append(event)
    return recent, prior


def _resolved_with_action(event: Any) -> bool:
    return (
        str(getattr(event, "status", "")).strip() == "resolved"
        and bool(str(getattr(event, "resolution_action", "") or "").strip())
    )


def _count_runs_with_provider_trace(recent_runs: list[dict]) -> int:
    return sum(
        1 for run in recent_runs
        if isinstance(run, dict)
        and str(run.get("task_id") or "").strip()
        and str(run.get("tool") or "").strip()
        and str(run.get("provider") or "").strip()
    )


def _visibility_area_rows(
    *,
    hosted_events: list,
    hosted_recent: list,
    hosted_prior: list,
    hosted_with_trace: int,
    hosted_recent_with_trace: int,
    hosted_prior_with_trace: int,
    recent_runs: list[dict],
    recent_with_provider: int,
    recoverable_events: list,
    recoverable_recent: list,
    recoverable_prior: list,
    recovered_or_learned: int,
    recovered_recent: int,
    recovered_prior: int,
    threshold: float,
) -> list[dict]:
    return [
        {
            "id": "hosted_failure_reporting",
            "label": "Hosted Worker Failure Reporting",
            "numerator": hosted_with_trace,
            "denominator": len(hosted_events),
            "rate": _friction_rate(hosted_with_trace, len(hosted_events)),
            "recent_rate": _friction_rate(hosted_recent_with_trace, len(hosted_recent)),
            "prior_rate": _friction_rate(hosted_prior_with_trace, len(hosted_prior)),
            "threshold": threshold,
        },
        {
            "id": "provider_task_visibility",
            "label": "Task-Provider Visibility",
            "numerator": recent_with_provider,
            "denominator": len(recent_runs),
            "rate": _friction_rate(recent_with_provider, len(recent_runs)),
            "recent_rate": _friction_rate(recent_with_provider, len(recent_runs)),
            "prior_rate": None,
            "threshold": threshold,
        },
        {
            "id": "recovery_learning_capture",
            "label": "Recovery/Learning Capture",
            "numerator": recovered_or_learned,
            "denominator": len(recoverable_events),
            "rate": _friction_rate(recovered_or_learned, len(recoverable_events)),
            "recent_rate": _friction_rate(recovered_recent, len(recoverable_recent)),
            "prior_rate": _friction_rate(recovered_prior, len(recoverable_prior)),
            "threshold": threshold,
        },
    ]


def _visibility_proof_summary(usage: dict[str, Any]) -> dict[str, Any]:
    from app.services import friction_service
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    recent_runs = execution.get("recent_runs") if isinstance(execution.get("recent_runs"), list) else []
    events, _ = friction_service.load_events()
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=3)
    hosted_events = [e for e in events if str(getattr(e, "stage", "")).strip() == "agent_runner"]
    hosted_recent, hosted_prior = _partition_events_by_recent(hosted_events, cutoff=recent_cutoff)
    hosted_with_trace = sum(1 for e in hosted_events if _event_has_task_model_tool_trace(e))
    hosted_recent_with_trace = sum(1 for e in hosted_recent if _event_has_task_model_tool_trace(e))
    hosted_prior_with_trace = sum(1 for e in hosted_prior if _event_has_task_model_tool_trace(e))
    recent_with_provider = _count_runs_with_provider_trace(recent_runs)
    recoverable_events = [e for e in hosted_events if str(getattr(e, "block_type", "")).strip() == "tool_failure"]
    recoverable_recent, recoverable_prior = _partition_events_by_recent(recoverable_events, cutoff=recent_cutoff)
    recovered_or_learned = sum(1 for e in recoverable_events if _resolved_with_action(e))
    recovered_recent = sum(1 for e in recoverable_recent if _resolved_with_action(e))
    recovered_prior = sum(1 for e in recoverable_prior if _resolved_with_action(e))
    threshold = 0.75
    areas = _visibility_area_rows(
        hosted_events=hosted_events,
        hosted_recent=hosted_recent,
        hosted_prior=hosted_prior,
        hosted_with_trace=hosted_with_trace,
        hosted_recent_with_trace=hosted_recent_with_trace,
        hosted_prior_with_trace=hosted_prior_with_trace,
        recent_runs=recent_runs,
        recent_with_provider=recent_with_provider,
        recoverable_events=recoverable_events,
        recoverable_recent=recoverable_recent,
        recoverable_prior=recoverable_prior,
        recovered_or_learned=recovered_or_learned,
        recovered_recent=recovered_recent,
        recovered_prior=recovered_prior,
        threshold=threshold,
    )
    for row in areas:
        row["pass"] = bool(row["rate"] >= row["threshold"])
        row["guidance_status"] = "on_track" if row["pass"] else "below_target"
        row["progress_to_target"] = round(min(1.0, float(row["rate"]) / float(row["threshold"])), 4)
        row["gap_to_target"] = round(max(0.0, float(row["threshold"]) - float(row["rate"])), 4)
        row["trend_delta"] = round(float(row["recent_rate"]) - float(row.get("prior_rate") or 0), 4) if isinstance(row.get("prior_rate"), (int, float)) else None
    return {
        "generated_at": now.isoformat(),
        "threshold": threshold,
        "all_pass": all(bool(row["pass"]) for row in areas),
        "mode": "guidance",
        "note": "Guidance target only: these metrics are for awareness and prioritization, not automatic blocking.",
        "areas": areas,
    }


def get_visibility_summary() -> dict[str, Any]:
    pipeline = get_pipeline_status()
    usage = get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    coverage = execution.get("coverage") if isinstance(execution.get("coverage"), dict) else {}
    untracked_ids = coverage.get("untracked_task_ids")
    if not isinstance(untracked_ids, list):
        untracked_ids = []
    normalized_untracked_ids = [str(t).strip() for t in untracked_ids if str(t).strip()]
    coverage_rate = float(coverage.get("coverage_rate", 0.0) or 0.0)
    remaining_to_full_coverage = len(normalized_untracked_ids)
    health = "green" if (remaining_to_full_coverage == 0 and coverage_rate >= 1.0) else ("yellow" if coverage_rate >= 0.7 else "red")
    running = pipeline.get("running") if isinstance(pipeline.get("running"), list) else []
    pending = pipeline.get("pending") if isinstance(pipeline.get("pending"), list) else []
    recent_completed = pipeline.get("recent_completed") if isinstance(pipeline.get("recent_completed"), list) else []
    attention = pipeline.get("attention") if isinstance(pipeline.get("attention"), dict) else {}
    attention_flags = attention.get("flags") if isinstance(attention.get("flags"), list) else []
    return {
        "pipeline": {
            "running_count": len(running),
            "pending_count": len(pending),
            "recent_completed_count": len(recent_completed),
            "running_by_phase": pipeline.get("running_by_phase", {}),
            "attention_flags": attention_flags,
        },
        "usage": usage,
        "proof": _visibility_proof_summary(usage),
        "remaining_usage": {
            "coverage_rate": coverage_rate,
            "remaining_to_full_coverage": remaining_to_full_coverage,
            "untracked_task_ids": normalized_untracked_ids,
            "health": health,
        },
    }


def _route_guidance_view(route: dict[str, Any]) -> dict[str, Any]:
    executor = str(route.get("executor") or "").strip()
    return {
        "executor": executor,
        "tool": executor_binary_name(executor) if executor else "",
        "model": str(route.get("model") or ""),
        "tier": str(route.get("tier") or ""),
        "provider": str(route.get("provider") or ""),
        "is_paid_provider": bool(route.get("is_paid_provider")),
        "command_template": str(route.get("command_template") or ""),
    }


def _orchestration_route_matrix(cheap_executor: str, escalation_executor: str) -> dict[str, Any]:
    matrix = {}
    for task_type in TaskType:
        cheap_route = get_route(task_type, executor=cheap_executor)
        escalation_route = get_route(task_type, executor=escalation_executor)
        matrix[task_type.value] = {
            "cheap": _route_guidance_view(cheap_route),
            "escalation": _route_guidance_view(escalation_route),
            "escalation_changes_route": bool(
                cheap_route.get("executor") != escalation_route.get("executor")
                or cheap_route.get("model") != escalation_route.get("model")
            ),
        }
    return matrix


def _top_failing_tools(execution: dict[str, Any], *, limit: int = 5) -> list[dict]:
    by_tool = execution.get("by_tool") if isinstance(execution.get("by_tool"), dict) else {}
    rows = []
    for tool, payload in by_tool.items():
        if not isinstance(payload, dict):
            continue
        failed = int(payload.get("failed") or 0)
        if failed <= 0:
            continue
        rows.append({
            "tool": str(tool or ""),
            "failed": failed,
            "count": int(payload.get("count") or 0),
            "success_rate": float(payload.get("success_rate") or 0.0),
        })
    rows.sort(key=lambda row: (-row["failed"], row["success_rate"], -row["count"], row["tool"]))
    return rows[:limit]


def _guidance_item(*, item_id: str, severity: str, title: str, detail: str, action: str) -> dict[str, str]:
    return {"id": item_id, "severity": severity, "title": title, "detail": detail, "action": action}


def _dedupe_guidance_rows(guidance_rows: list[dict]) -> list[dict]:
    deduped = []
    seen_ids = set()
    for row in guidance_rows:
        item_id = str(row.get("id") or "").strip()
        if item_id and item_id in seen_ids:
            continue
        if item_id:
            seen_ids.add(item_id)
        deduped.append(row)
    return deduped


def _lifecycle_awareness_snapshot(window_seconds: int, sample_limit: int) -> dict[str, Any]:
    from app.services import agent_execution_hooks
    lifecycle = agent_execution_hooks.summarize_lifecycle_events(seconds=window_seconds, limit=sample_limit, source="auto")
    by_event = lifecycle.get("by_event") if isinstance(lifecycle.get("by_event"), dict) else {}
    by_status = lifecycle.get("by_status") if isinstance(lifecycle.get("by_status"), dict) else {}
    finalized_events = int(by_event.get("finalized") or 0)
    failed_finalized_events = int(by_status.get("failed") or 0)
    lifecycle_failure_ratio = round(float(failed_finalized_events) / float(finalized_events), 4) if finalized_events > 0 else 0.0
    return {
        "lifecycle": lifecycle,
        "finalized_events": finalized_events,
        "failed_finalized_events": failed_finalized_events,
        "lifecycle_failure_ratio": lifecycle_failure_ratio,
    }


def _build_orchestration_guidance_rows(
    *,
    execution_success_rate: float,
    coverage_rate: float,
    top_failing_tools: list[dict],
    finalized_events: int,
    lifecycle_failure_ratio: float,
    lifecycle_guidance: list[dict],
) -> list[dict]:
    guidance_rows = [dict(row) for row in (lifecycle_guidance or [])[:5] if isinstance(row, dict)]
    if execution_success_rate < 0.8:
        guidance_rows.append(_guidance_item(
            item_id="execution_success_low",
            severity="medium",
            title="Execution success rate is below target",
            detail=f"Execution success rate is {round(execution_success_rate * 100.0, 1)}% in the current window.",
            action="Prefer cheap executor path first, narrow task scopes, and escalate once for reasoning-heavy failures.",
        ))
    if coverage_rate < 0.95:
        guidance_rows.append(_guidance_item(
            item_id="coverage_gap",
            severity="medium",
            title="Execution tracking coverage is incomplete",
            detail=f"Coverage rate is {round(coverage_rate * 100.0, 1)}% for completed/failed tasks.",
            action="Ensure worker runtime events include task_id, executor, and provider metadata.",
        ))
    if top_failing_tools:
        top_tools = ", ".join(str(r.get("tool") or "") for r in top_failing_tools[:3])
        guidance_rows.append(_guidance_item(
            item_id="tool_failure_hotspots",
            severity="medium",
            title="Tool failure hotspots detected",
            detail=f"Most frequent failing tools: {top_tools or 'unknown'}.",
            action="Run failing tools in smaller deterministic loops before broad orchestration retries.",
        ))
    if finalized_events > 0 and lifecycle_failure_ratio >= 0.25:
        guidance_rows.append(_guidance_item(
            item_id="lifecycle_failures_present",
            severity="medium",
            title="Lifecycle failures are elevated",
            detail=f"Lifecycle finalized failure ratio is {round(lifecycle_failure_ratio * 100.0, 1)}%.",
            action="Inspect /api/agent/lifecycle/summary guidance and resolve repeated guard/validation causes first.",
        ))
    if not guidance_rows:
        guidance_rows.append(_guidance_item(
            item_id="stable_guidance_baseline",
            severity="info",
            title="Signals are stable",
            detail="Current orchestration signals are stable and guidance targets are on track.",
            action="Continue cheap-first routing with one escalation only when needed.",
        ))
    return _dedupe_guidance_rows(guidance_rows)


def get_orchestration_guidance_summary(*, seconds: int = 6 * 3600, limit: int = 500) -> dict[str, Any]:
    from app.services import friction_service
    window_seconds = max(300, min(int(seconds), 30 * 24 * 3600))
    sample_limit = max(1, min(int(limit), 5000))
    window_days = max(1, min(30, int((window_seconds + 86399) // 86400)))
    cheap_executor = cheap_executor_default()
    escalation_executor = escalation_executor_default()
    usage = get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    coverage = execution.get("coverage") if isinstance(execution.get("coverage"), dict) else {}
    execution_success_rate = float(execution.get("success_rate") or 0.0)
    coverage_rate = float(coverage.get("coverage_rate") or 0.0)
    top_failing_tools = _top_failing_tools(execution, limit=5)
    lifecycle_snapshot = _lifecycle_awareness_snapshot(window_seconds, sample_limit)
    lifecycle = lifecycle_snapshot["lifecycle"]
    finalized_events = int(lifecycle_snapshot["finalized_events"])
    failed_finalized_events = int(lifecycle_snapshot["failed_finalized_events"])
    lifecycle_failure_ratio = float(lifecycle_snapshot["lifecycle_failure_ratio"])
    friction_events, _ = friction_service.load_events()
    friction_summary = friction_service.summarize(friction_events, window_days=window_days)
    top_friction_blocks = list(friction_summary.get("top_block_types") or [])[:5]
    lifecycle_guidance = lifecycle.get("guidance") if isinstance(lifecycle.get("guidance"), list) else []
    guidance = _build_orchestration_guidance_rows(
        execution_success_rate=execution_success_rate,
        coverage_rate=coverage_rate,
        top_failing_tools=top_failing_tools,
        finalized_events=finalized_events,
        lifecycle_failure_ratio=lifecycle_failure_ratio,
        lifecycle_guidance=lifecycle_guidance,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "guidance",
        "enforcement": "advisory",
        "window_seconds": window_seconds,
        "defaults": {
            "cheap_executor": cheap_executor,
            "escalation_executor": escalation_executor,
            "repo_question_executor": routing_service.repo_question_executor_default(),
            "open_question_executor": routing_service.open_question_executor_default(),
        },
        "recommended_routes": _orchestration_route_matrix(cheap_executor, escalation_executor),
        "awareness": {
            "execution_success_rate": round(execution_success_rate, 4),
            "coverage_rate": round(coverage_rate, 4),
            "lifecycle_failure_ratio": lifecycle_failure_ratio,
            "finalized_events": finalized_events,
            "failed_finalized_events": failed_finalized_events,
            "subscribers": lifecycle.get("subscribers") if isinstance(lifecycle.get("subscribers"), dict) else {},
            "summary_source": str(lifecycle.get("summary_source") or "none"),
            "top_failing_tools": top_failing_tools,
            "top_friction_blocks": top_friction_blocks,
        },
        "guidance": guidance[:10],
    }
