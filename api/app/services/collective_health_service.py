"""Collective health scoring for coherence, resonance, flow, and friction."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.agent import TaskStatus
from app.services import agent_service, friction_service, metrics_service, runtime_service


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator <= 0:
        return float(default)
    return float(numerator) / float(denominator)


def _score_with_neutral(task_count: int, score: float) -> float:
    if task_count <= 0:
        return 0.5
    return _clamp01(score)


def _task_context(task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context")
    return context if isinstance(context, dict) else {}


def _monitor_issue_rows() -> list[dict[str, Any]]:
    path = friction_service.monitor_issues_file_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("issues") if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _coherence_summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    task_count = len(tasks)
    target_state_count = 0
    evidence_count = 0
    task_card_count = 0
    task_card_scores: list[float] = []

    for task in tasks:
        context = _task_context(task)
        if isinstance(context.get("target_state_contract"), dict):
            target_state_count += 1
        if context.get("success_evidence") or context.get("abort_evidence"):
            evidence_count += 1
        validation = context.get("task_card_validation")
        if isinstance(validation, dict) and validation.get("present") is True:
            task_card_count += 1
            try:
                task_card_scores.append(_clamp01(float(validation.get("score") or 0.0)))
            except (TypeError, ValueError):
                task_card_scores.append(0.0)

    target_state_coverage = _safe_ratio(target_state_count, task_count)
    evidence_coverage = _safe_ratio(evidence_count, task_count)
    task_card_coverage = _safe_ratio(task_card_count, task_count)
    task_card_quality = _safe_ratio(sum(task_card_scores), len(task_card_scores), default=0.0)

    score = _score_with_neutral(
        task_count,
        (0.35 * target_state_coverage)
        + (0.30 * task_card_quality)
        + (0.20 * task_card_coverage)
        + (0.15 * evidence_coverage),
    )

    return {
        "score": round(score, 4),
        "task_count": task_count,
        "target_state_coverage": round(target_state_coverage, 4),
        "task_card_coverage": round(task_card_coverage, 4),
        "task_card_quality": round(task_card_quality, 4),
        "evidence_coverage": round(evidence_coverage, 4),
    }


def _resonance_summary(tasks: list[dict[str, Any]], *, window_days: int) -> dict[str, Any]:
    task_count = len(tasks)
    id_counts: dict[str, int] = {}
    failed_count = 0
    failed_with_learning = 0

    for task in tasks:
        context = _task_context(task)
        for key in ("spec_id", "idea_id"):
            value = str(context.get(key) or "").strip()
            if value:
                id_counts[value] = id_counts.get(value, 0) + 1
        status = task.get("status")
        if status == TaskStatus.FAILED:
            failed_count += 1
            reflections = context.get("retry_reflections")
            if isinstance(reflections, list) and reflections:
                failed_with_learning += 1

    reused_reference_count = sum(count for count in id_counts.values() if count > 1)
    tracked_reference_total = sum(id_counts.values())
    reference_reuse_ratio = _safe_ratio(reused_reference_count, tracked_reference_total, default=0.0)
    learning_capture_ratio = _safe_ratio(failed_with_learning, failed_count, default=0.5 if failed_count == 0 else 0.0)

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, window_days))
    completion_events = [
        event
        for event in runtime_service.list_events(limit=4000, since=cutoff, source="worker")
        if isinstance(getattr(event, "metadata", None), dict)
        and str(event.metadata.get("tracking_kind") or "") == "agent_task_completion"
    ]
    traceable_events = [
        event
        for event in completion_events
        if str((event.metadata or {}).get("repeatable_tool_call") or "").strip()
    ]
    traceability_ratio = _safe_ratio(len(traceable_events), len(completion_events), default=0.5 if not completion_events else 0.0)

    score = _score_with_neutral(
        task_count,
        (0.40 * reference_reuse_ratio) + (0.35 * traceability_ratio) + (0.25 * learning_capture_ratio),
    )

    return {
        "score": round(score, 4),
        "task_count": task_count,
        "tracked_reference_total": tracked_reference_total,
        "reused_reference_count": reused_reference_count,
        "reference_reuse_ratio": round(reference_reuse_ratio, 4),
        "completion_event_count": len(completion_events),
        "traceable_completion_ratio": round(traceability_ratio, 4),
        "learning_capture_ratio": round(learning_capture_ratio, 4),
    }


def _flow_summary(tasks: list[dict[str, Any]], *, metrics: dict[str, Any]) -> dict[str, Any]:
    task_count = len(tasks)
    status_counts: dict[str, int] = {status.value: 0 for status in TaskStatus}

    for task in tasks:
        status = task.get("status")
        key = status.value if isinstance(status, TaskStatus) else str(status or "").strip()
        if key in status_counts:
            status_counts[key] += 1

    completed = int(status_counts.get(TaskStatus.COMPLETED.value, 0))
    failed = int(status_counts.get(TaskStatus.FAILED.value, 0))
    running = int(status_counts.get(TaskStatus.RUNNING.value, 0))
    pending = int(status_counts.get(TaskStatus.PENDING.value, 0))
    needs_decision = int(status_counts.get(TaskStatus.NEEDS_DECISION.value, 0))

    terminal_total = completed + failed
    active_total = running + pending + needs_decision

    completion_ratio = _safe_ratio(completed, terminal_total, default=0.5 if terminal_total == 0 else 0.0)
    active_flow_ratio = _safe_ratio(running, active_total, default=0.5 if active_total == 0 else 0.0)

    throughput = metrics.get("success_rate") if isinstance(metrics.get("success_rate"), dict) else {}
    completed_7d = int(throughput.get("completed") or 0)
    throughput_factor = _clamp01(completed_7d / 20.0)

    exec_time = metrics.get("execution_time") if isinstance(metrics.get("execution_time"), dict) else {}
    p95_seconds = float(exec_time.get("p95_seconds") or 0.0)
    latency_factor = 1.0 - _clamp01(p95_seconds / 1800.0)

    score = _score_with_neutral(
        task_count,
        (0.35 * completion_ratio)
        + (0.25 * active_flow_ratio)
        + (0.25 * throughput_factor)
        + (0.15 * latency_factor),
    )

    return {
        "score": round(score, 4),
        "task_count": task_count,
        "completion_ratio": round(completion_ratio, 4),
        "active_flow_ratio": round(active_flow_ratio, 4),
        "throughput_factor": round(throughput_factor, 4),
        "latency_factor": round(latency_factor, 4),
        "status_counts": status_counts,
    }


def _friction_summary(*, window_days: int) -> dict[str, Any]:
    events, ignored = friction_service.load_events()
    summary = friction_service.summarize(events, window_days=window_days)
    issue_rows = _monitor_issue_rows()

    total_events = int(summary.get("total_events") or 0)
    open_events = int(summary.get("open_events") or 0)
    total_energy_loss = float(summary.get("total_energy_loss") or 0.0)

    open_density = _safe_ratio(open_events, total_events, default=0.0)
    energy_norm = _clamp01(_safe_ratio(total_energy_loss, max(total_events, 1), default=0.0) / 10.0)
    issue_norm = _clamp01(len(issue_rows) / 10.0)
    friction_score = _clamp01((0.5 * open_density) + (0.3 * energy_norm) + (0.2 * issue_norm))

    entry_report = friction_service.friction_entry_points(window_days=window_days, limit=5)
    entries = entry_report.get("entry_points") if isinstance(entry_report, dict) else []
    queue: list[dict[str, Any]] = []
    if isinstance(entries, list):
        for row in entries[:5]:
            if not isinstance(row, dict):
                continue
            signal = float(row.get("energy_loss") or 0.0) + (0.5 * float(row.get("event_count") or 0.0))
            queue.append(
                {
                    "key": str(row.get("key") or "unknown"),
                    "title": str(row.get("title") or "Friction entry"),
                    "severity": str(row.get("severity") or "info"),
                    "signal": round(signal, 4),
                    "recommended_action": str(row.get("recommended_action") or ""),
                }
            )

    return {
        "score": round(friction_score, 4),
        "event_count": total_events,
        "open_events": open_events,
        "ignored_events": int(ignored),
        "open_density": round(open_density, 4),
        "energy_loss": round(total_energy_loss, 4),
        "issue_count": len(issue_rows),
        "top_friction_queue": queue,
        "monitor_issue_preview": [
            {
                "condition": str(row.get("condition") or ""),
                "severity": str(row.get("severity") or ""),
                "message": str(row.get("message") or "")[:120],
            }
            for row in issue_rows[:5]
        ],
    }


def _top_opportunities(
    *,
    coherence: dict[str, Any],
    resonance: dict[str, Any],
    flow: dict[str, Any],
    friction: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if float(coherence.get("task_card_coverage") or 0.0) < 0.9:
        rows.append(
            {
                "pillar": "coherence",
                "signal": "task_card_coverage",
                "action": "Increase task-card completeness on new tasks.",
                "impact_estimate": round(1.0 - float(coherence.get("task_card_coverage") or 0.0), 4),
            }
        )
    if float(resonance.get("reference_reuse_ratio") or 0.0) < 0.5:
        rows.append(
            {
                "pillar": "resonance",
                "signal": "reference_reuse_ratio",
                "action": "Link tasks to shared spec_id/idea_id to amplify reusable outcomes.",
                "impact_estimate": round(0.5 - float(resonance.get("reference_reuse_ratio") or 0.0), 4),
            }
        )
    if float(flow.get("active_flow_ratio") or 0.0) < 0.5:
        rows.append(
            {
                "pillar": "flow",
                "signal": "active_flow_ratio",
                "action": "Reduce pending/needs_decision queue and keep active runners working.",
                "impact_estimate": round(0.5 - float(flow.get("active_flow_ratio") or 0.0), 4),
            }
        )
    if float(friction.get("score") or 0.0) > 0.2:
        rows.append(
            {
                "pillar": "friction",
                "signal": "friction_score",
                "action": "Work the top friction queue to remove highest-energy blockers first.",
                "impact_estimate": round(float(friction.get("score") or 0.0), 4),
            }
        )

    rows.sort(key=lambda row: float(row.get("impact_estimate") or 0.0), reverse=True)
    return rows[:5]


def get_collective_health(window_days: int = 7) -> dict[str, Any]:
    """Compute collective health scorecard for coherence, resonance, flow, and friction."""
    bounded_window = max(1, min(int(window_days), 30))
    tasks, _total = agent_service.list_tasks(limit=5000, offset=0)
    metrics = metrics_service.get_aggregates()

    coherence = _coherence_summary(tasks)
    resonance = _resonance_summary(tasks, window_days=bounded_window)
    flow = _flow_summary(tasks, metrics=metrics)
    friction = _friction_summary(window_days=bounded_window)

    coherence_score = float(coherence.get("score") or 0.0)
    resonance_score = float(resonance.get("score") or 0.0)
    flow_score = float(flow.get("score") or 0.0)
    friction_score = float(friction.get("score") or 0.0)

    collective_value = round(
        _clamp01(coherence_score)
        * _clamp01(resonance_score)
        * _clamp01(flow_score)
        * (1.0 - _clamp01(friction_score)),
        4,
    )

    scores = {
        "coherence": round(coherence_score, 4),
        "resonance": round(resonance_score, 4),
        "flow": round(flow_score, 4),
        "friction": round(friction_score, 4),
        "collective_value": collective_value,
    }

    opportunities = _top_opportunities(
        coherence=coherence,
        resonance=resonance,
        flow=flow,
        friction=friction,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "window_days": bounded_window,
        "scores": scores,
        "coherence": coherence,
        "resonance": resonance,
        "flow": flow,
        "friction": {
            key: value
            for key, value in friction.items()
            if key != "top_friction_queue"
        },
        "top_friction_queue": list(friction.get("top_friction_queue") or []),
        "top_opportunities": opportunities,
    }
