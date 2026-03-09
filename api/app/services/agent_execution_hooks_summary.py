"""Lifecycle event summary: row loading, guidance, and summarize API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import runtime_service
from app.services.agent_execution_hooks_config import (
    enabled_subscribers,
    jsonl_path,
)


def _parse_recorded_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _runtime_lifecycle_rows(
    *,
    cutoff: datetime,
    requested_limit: int,
    task_filter: str,
) -> list[dict[str, Any]]:
    rows = runtime_service.list_events(limit=requested_limit, since=cutoff, source="worker")
    lifecycle_rows: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        if str(metadata.get("tracking_kind") or "").strip() != "agent_task_lifecycle":
            continue
        row_task_id = str(metadata.get("task_id") or "").strip()
        if task_filter and row_task_id != task_filter:
            continue
        lifecycle_rows.append(
            {
                "recorded_at": row.recorded_at.isoformat(),
                "task_id": row_task_id,
                "event": str(metadata.get("lifecycle_event") or "").strip() or "unknown",
                "task_status": str(metadata.get("task_status") or "").strip() or "unknown",
                "worker_id": str(metadata.get("worker_id") or ""),
                "model": str(metadata.get("model") or ""),
                "ok": bool(metadata.get("ok")) if "ok" in metadata else None,
                "reason": str(metadata.get("reason") or ""),
                "error": str(metadata.get("error") or ""),
                "source": "runtime",
            }
        )
    return lifecycle_rows


def _jsonl_lifecycle_rows(
    *,
    cutoff: datetime,
    requested_limit: int,
    task_filter: str,
) -> list[dict[str, Any]]:
    path = jsonl_path()
    if not path.exists():
        return []

    rows: list[tuple[datetime, dict[str, Any]]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if str(parsed.get("tracking_kind") or "").strip() != "agent_task_lifecycle":
            continue
        row_task_id = str(parsed.get("task_id") or "").strip()
        if task_filter and row_task_id != task_filter:
            continue

        recorded_at = _parse_recorded_at(parsed.get("recorded_at"))
        if recorded_at is None or recorded_at < cutoff:
            continue

        rows.append(
            (
                recorded_at,
                {
                    "recorded_at": recorded_at.isoformat(),
                    "task_id": row_task_id,
                    "event": str(parsed.get("event") or "").strip() or "unknown",
                    "task_status": str(parsed.get("task_status") or "").strip() or "unknown",
                    "worker_id": str(parsed.get("worker_id") or ""),
                    "model": str(parsed.get("model") or ""),
                    "ok": bool(parsed.get("ok")) if "ok" in parsed else None,
                    "reason": str(parsed.get("reason") or ""),
                    "error": str(parsed.get("error") or ""),
                    "source": "jsonl",
                },
            )
        )

    rows.sort(key=lambda item: item[0], reverse=True)
    return [row for _dt, row in rows[:requested_limit]]


def _guidance_item(
    *,
    item_id: str,
    severity: str,
    title: str,
    detail: str,
    action: str,
) -> dict[str, str]:
    return {
        "id": item_id,
        "severity": severity,
        "title": title,
        "detail": detail,
        "action": action,
    }


def _guidance_for_no_events(
    *,
    subscribers: dict[str, bool],
    requested_source: str,
    total_events: int,
) -> list[dict[str, str]]:
    if total_events > 0:
        return []
    if requested_source == "runtime" and not bool(subscribers.get("runtime")):
        return [
            _guidance_item(
                item_id="runtime_source_disabled",
                severity="medium",
                title="Runtime source requested but disabled",
                detail="Summary requested runtime source while runtime subscriber is disabled.",
                action="Enable runtime subscriber or query source=jsonl/auto.",
            )
        ]
    if requested_source == "jsonl" and not bool(subscribers.get("jsonl")):
        return [
            _guidance_item(
                item_id="jsonl_source_disabled",
                severity="medium",
                title="JSONL source requested but disabled",
                detail="Summary requested jsonl source while jsonl subscriber is disabled.",
                action="Enable jsonl subscriber or query source=runtime/auto.",
            )
        ]
    return [
        _guidance_item(
            item_id="no_recent_lifecycle_events",
            severity="info",
            title="No recent lifecycle events",
            detail="No lifecycle events were found in the selected window.",
            action="Execute a task and recheck /api/agent/lifecycle/summary.",
        )
    ]


def _append_event_guidance(guidance: list[dict[str, str]], by_event: dict[str, int]) -> None:
    guard_blocks = int(by_event.get("guard_blocked") or 0)
    if guard_blocks > 0:
        guidance.append(
            _guidance_item(
                item_id="paid_guard_blocks",
                severity="high",
                title="Paid-provider guard blocks detected",
                detail=f"{guard_blocks} lifecycle events were blocked by paid-provider guard checks.",
                action="Use force_paid_providers=true when appropriate, or adjust paid-provider policy.",
            )
        )
    validation_failed = int(by_event.get("validation_failed") or 0)
    if validation_failed > 0:
        guidance.append(
            _guidance_item(
                item_id="direction_required",
                severity="medium",
                title="Validation failures detected",
                detail=f"{validation_failed} lifecycle events failed validation (for example empty direction).",
                action="Ensure task directions are explicit and non-empty.",
            )
        )


def _append_failure_ratio_guidance(
    guidance: list[dict[str, str]],
    *,
    by_event: dict[str, int],
    by_status: dict[str, int],
) -> None:
    finalized = int(by_event.get("finalized") or 0)
    failed = int(by_status.get("failed") or 0)
    if finalized <= 0 or failed <= 0:
        return
    failure_ratio = float(failed) / float(finalized)
    severity = "high" if failure_ratio >= 0.5 else "medium"
    guidance.append(
        _guidance_item(
            item_id="high_failure_ratio",
            severity=severity,
            title="Finalized task failures present",
            detail=f"Failure ratio is {round(failure_ratio * 100.0, 1)}% ({failed}/{finalized}).",
            action="Inspect failed tasks and prioritize top repeated failure causes.",
        )
    )


def _append_source_override_guidance(
    guidance: list[dict[str, str]],
    *,
    subscribers: dict[str, bool],
    requested_source: str,
    summary_source: str,
) -> None:
    if requested_source == "auto" and bool(subscribers.get("runtime")) and bool(subscribers.get("jsonl")):
        guidance.append(
            _guidance_item(
                item_id="source_override_available",
                severity="info",
                title="Multiple lifecycle sources available",
                detail=f"Auto mode currently used source={summary_source}.",
                action="Use source=runtime or source=jsonl to compare backend perspectives.",
            )
        )


def _build_summary_guidance(
    *,
    subscribers: dict[str, bool],
    requested_source: str,
    summary_source: str,
    total_events: int,
    by_event: dict[str, int],
    by_status: dict[str, int],
) -> list[dict[str, str]]:
    guidance: list[dict[str, str]] = []
    if not any(bool(value) for value in subscribers.values()):
        guidance.append(
            _guidance_item(
                item_id="no_subscribers_enabled",
                severity="high",
                title="Lifecycle subscribers disabled",
                detail="No lifecycle subscribers are active, so lifecycle traces are not being recorded.",
                action="Set AGENT_LIFECYCLE_SUBSCRIBERS=runtime, jsonl, or all.",
            )
        )
        return guidance

    guidance.extend(
        _guidance_for_no_events(subscribers=subscribers, requested_source=requested_source, total_events=total_events)
    )
    _append_event_guidance(guidance, by_event)
    _append_failure_ratio_guidance(guidance, by_event=by_event, by_status=by_status)
    _append_source_override_guidance(
        guidance, subscribers=subscribers, requested_source=requested_source, summary_source=summary_source
    )
    return guidance


def summarize_lifecycle_events(
    *,
    seconds: int = 3600,
    limit: int = 500,
    task_id: str | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    window_seconds = max(60, min(int(seconds), 60 * 60 * 24 * 30))
    requested_limit = max(1, min(int(limit), 5000))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    task_filter = str(task_id or "").strip()
    subscribers = enabled_subscribers()
    requested_source = str(source or "auto").strip().lower() or "auto"
    if requested_source not in {"auto", "runtime", "jsonl"}:
        requested_source = "auto"
    summary_source = "none"

    lifecycle_rows: list[dict[str, Any]]
    if requested_source == "runtime":
        summary_source = "runtime"
        lifecycle_rows = _runtime_lifecycle_rows(
            cutoff=cutoff,
            requested_limit=requested_limit,
            task_filter=task_filter,
        )
    elif requested_source == "jsonl":
        summary_source = "jsonl"
        lifecycle_rows = _jsonl_lifecycle_rows(
            cutoff=cutoff,
            requested_limit=requested_limit,
            task_filter=task_filter,
        )
    elif bool(subscribers.get("runtime")):
        summary_source = "runtime"
        lifecycle_rows = _runtime_lifecycle_rows(
            cutoff=cutoff,
            requested_limit=requested_limit,
            task_filter=task_filter,
        )
    elif bool(subscribers.get("jsonl")):
        summary_source = "jsonl"
        lifecycle_rows = _jsonl_lifecycle_rows(
            cutoff=cutoff,
            requested_limit=requested_limit,
            task_filter=task_filter,
        )
    else:
        lifecycle_rows = []

    by_event: dict[str, int] = {}
    by_status: dict[str, int] = {}
    task_ids: set[str] = set()

    for row in lifecycle_rows:
        row_task_id = str(row.get("task_id") or "").strip()
        lifecycle_event = str(row.get("event") or "").strip() or "unknown"
        task_status = str(row.get("task_status") or "").strip() or "unknown"
        if row_task_id:
            task_ids.add(row_task_id)
        by_event[lifecycle_event] = by_event.get(lifecycle_event, 0) + 1
        by_status[task_status] = by_status.get(task_status, 0) + 1

    guidance = _build_summary_guidance(
        subscribers=subscribers,
        requested_source=requested_source,
        summary_source=summary_source,
        total_events=len(lifecycle_rows),
        by_event=by_event,
        by_status=by_status,
    )

    return {
        "window_seconds": window_seconds,
        "limit": requested_limit,
        "task_id": task_filter or None,
        "requested_source": requested_source,
        "subscribers": subscribers,
        "summary_source": summary_source,
        "total_events": len(lifecycle_rows),
        "task_count": len(task_ids),
        "by_event": by_event,
        "by_status": by_status,
        "guidance": guidance,
        "recent": lifecycle_rows[:50],
    }
