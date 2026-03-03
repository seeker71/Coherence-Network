"""Lifecycle hook registry for agent task execution."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service

LifecycleHookPayload = dict[str, Any]
LifecycleHook = Callable[[LifecycleHookPayload], None]

_LIFECYCLE_HOOKS: list[LifecycleHook] = []
_PIPELINE_IDEA_ID = "coherence-network-agent-pipeline"


def register_lifecycle_hook(hook: LifecycleHook) -> None:
    if hook not in _LIFECYCLE_HOOKS:
        _LIFECYCLE_HOOKS.append(hook)


def clear_lifecycle_hooks() -> None:
    _LIFECYCLE_HOOKS.clear()


def list_lifecycle_hooks() -> list[LifecycleHook]:
    return list(_LIFECYCLE_HOOKS)


def _event_status_code(payload: LifecycleHookPayload) -> int:
    status = str(payload.get("task_status") or "").strip().lower()
    if status == "failed":
        return 500
    return 200


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _runtime_telemetry_enabled() -> bool:
    return _truthy(os.getenv("AGENT_LIFECYCLE_TELEMETRY_ENABLED", "1"))


def _jsonl_telemetry_enabled() -> bool:
    return _truthy(os.getenv("AGENT_LIFECYCLE_JSONL_ENABLED", "1"))


def _jsonl_path() -> Path:
    configured = str(os.getenv("AGENT_LIFECYCLE_JSONL_PATH", "")).strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "agent_lifecycle_events.jsonl"


def _jsonl_max_lines() -> int | None:
    raw = str(os.getenv("AGENT_LIFECYCLE_JSONL_MAX_LINES", "")).strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return min(parsed, 1_000_000)


def _parse_subscribers(raw: str | None) -> set[str]:
    value = str(raw or "").strip().lower()
    if not value:
        return {"runtime"}

    tokens = {piece.strip().lower() for piece in value.split(",") if piece.strip()}
    if not tokens:
        return {"runtime"}
    if "all" in tokens:
        return {"runtime", "jsonl"}
    if tokens.intersection({"none", "off", "0", "false"}):
        return set()

    allowed = {"runtime", "jsonl", "audit"}
    return {token for token in tokens if token in allowed}


def enabled_subscribers() -> dict[str, bool]:
    subscribers = _parse_subscribers(os.getenv("AGENT_LIFECYCLE_SUBSCRIBERS"))
    jsonl_enabled = ("jsonl" in subscribers or "audit" in subscribers) and _jsonl_telemetry_enabled()
    return {
        "runtime": ("runtime" in subscribers) and _runtime_telemetry_enabled(),
        "jsonl": jsonl_enabled,
    }


def _runtime_subscriber_enabled() -> bool:
    return bool(enabled_subscribers().get("runtime"))


def _jsonl_subscriber_enabled() -> bool:
    return bool(enabled_subscribers().get("jsonl"))


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def _runtime_metadata(payload: LifecycleHookPayload) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {
        "tracking_kind": "agent_task_lifecycle",
        "lifecycle_event": _to_text(payload.get("event")),
        "task_id": _to_text(payload.get("task_id")),
        "task_status": _to_text(payload.get("task_status")),
        "task_type": _to_text(payload.get("task_type")),
        "worker_id": str(payload.get("worker_id") or ""),
        "model": str(payload.get("model") or ""),
    }
    if "route_is_paid" in payload:
        metadata["route_is_paid"] = bool(payload.get("route_is_paid"))
    if "ok" in payload:
        metadata["ok"] = bool(payload.get("ok"))
    if payload.get("reason"):
        metadata["reason"] = str(payload.get("reason") or "")
    if payload.get("error"):
        metadata["error"] = str(payload.get("error") or "")[:800]
    if payload.get("failure_category"):
        metadata["failure_category"] = str(payload.get("failure_category") or "")
    if "retry_count" in payload:
        try:
            metadata["retry_count"] = int(payload.get("retry_count") or 0)
        except (TypeError, ValueError):
            pass
    if payload.get("blind_spot"):
        metadata["blind_spot"] = str(payload.get("blind_spot") or "")[:200]
    return metadata


def _record_runtime_lifecycle_event(payload: LifecycleHookPayload) -> None:
    if not _runtime_subscriber_enabled():
        return
    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-lifecycle",
            method="RUN",
            status_code=_event_status_code(payload),
            runtime_ms=1.0,
            idea_id=_PIPELINE_IDEA_ID,
            metadata=_runtime_metadata(payload),
        )
    )


def _append_jsonl_lifecycle_event(payload: LifecycleHookPayload) -> None:
    if not _jsonl_subscriber_enabled():
        return

    row = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "tracking_kind": "agent_task_lifecycle",
        "event": _to_text(payload.get("event")),
        "task_id": _to_text(payload.get("task_id")),
        "task_type": _to_text(payload.get("task_type")),
        "task_status": _to_text(payload.get("task_status")),
        "worker_id": _to_text(payload.get("worker_id")),
        "model": _to_text(payload.get("model")),
        "ok": bool(payload.get("ok")) if "ok" in payload else None,
        "reason": _to_text(payload.get("reason")),
        "error": _to_text(payload.get("error"))[:800],
    }
    if "route_is_paid" in payload:
        row["route_is_paid"] = bool(payload.get("route_is_paid"))

    path = _jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")

    max_lines = _jsonl_max_lines()
    if max_lines is None:
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= max_lines:
        return
    trimmed = lines[-max_lines:]
    path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")


def dispatch_lifecycle_event(
    event: str,
    *,
    task_id: str,
    task: dict[str, Any],
    **extra: Any,
) -> None:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    payload: LifecycleHookPayload = {
        "event": str(event or "").strip(),
        "task_id": str(task_id or "").strip(),
        "task_type": _to_text(task.get("task_type")),
        "task_status": _to_text(task.get("status")),
        "model": str(task.get("model") or context.get("model_override") or ""),
    }
    if context.get("last_failure_category"):
        payload["failure_category"] = str(context.get("last_failure_category") or "")
    if "retry_count" in context:
        payload["retry_count"] = context.get("retry_count")
    if context.get("blind_spot"):
        payload["blind_spot"] = str(context.get("blind_spot") or "")
    payload.update(extra)

    try:
        _record_runtime_lifecycle_event(payload)
    except Exception:
        pass
    try:
        _append_jsonl_lifecycle_event(payload)
    except Exception:
        pass

    for hook in list_lifecycle_hooks():
        try:
            hook(dict(payload))
        except Exception:
            continue


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
    path = _jsonl_path()
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
