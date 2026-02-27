"""Recover orphaned running tasks when a runner heartbeats as idle."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import BackgroundTasks

from app.models.agent import TaskStatus
from app.services import agent_service, telegram_adapter

logger = logging.getLogger(__name__)


def _int_env(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = default
    else:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _running_seconds(task: dict[str, Any], now: datetime) -> int | None:
    started = _parse_dt(task.get("started_at")) or _parse_dt(task.get("updated_at")) or _parse_dt(task.get("created_at"))
    if started is None:
        return None
    return max(0, int((now - started).total_seconds()))


def _fallback_alert(task: dict[str, Any]) -> str:
    task_id = str(task.get("id") or "").strip() or "unknown"
    return f"⚠️ *orphan recovered*\nTask ID: `{task_id}`\nStatus: `failed`"


def _threshold_seconds() -> int:
    fallback_threshold = _int_env(
        "ORPHAN_RUNNING_SEC",
        _int_env(
            "PIPELINE_ORPHAN_RUNNING_SECONDS",
            _int_env("PIPELINE_STALE_RUNNING_SECONDS", 1800, minimum=60, maximum=7 * 24 * 3600),
            minimum=60,
            maximum=7 * 24 * 3600,
        ),
        minimum=60,
        maximum=7 * 24 * 3600,
    )
    return _int_env(
        "AGENT_ORPHAN_RUNNING_SEC",
        fallback_threshold,
        minimum=60,
        maximum=7 * 24 * 3600,
    )


def _max_recoveries() -> int:
    return _int_env("AGENT_ORPHAN_REAP_MAX_TASKS", 10, minimum=1, maximum=50)


def recover_stale_running_tasks(
    *,
    trigger: str,
    reason: str,
    runner_id: str | None = None,
    claimed_by_runner_only: bool = False,
) -> list[dict[str, Any]]:
    """Auto-fail stale running tasks so queue flow can resume."""
    threshold_seconds = _threshold_seconds()
    max_recoveries = _max_recoveries()
    running_tasks, _ = agent_service.list_tasks(status=TaskStatus.RUNNING, limit=500, offset=0)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")

    normalized_runner = str(runner_id or "").strip()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for task in running_tasks:
        if not isinstance(task, dict):
            continue
        claimed_by = str(task.get("claimed_by") or "").strip()
        if claimed_by_runner_only and (not normalized_runner or claimed_by != normalized_runner):
            continue
        running_seconds = _running_seconds(task, now)
        if running_seconds is None or running_seconds < threshold_seconds:
            continue
        candidates.append((running_seconds, task))

    candidates.sort(key=lambda item: item[0], reverse=True)
    recovered: list[dict[str, Any]] = []
    for running_seconds, task in candidates[:max_recoveries]:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            continue
        worker_id = normalized_runner or str(task.get("claimed_by") or "").strip() or "orphan-recovery"
        output = (
            "Orphan: stale running task auto-recovered; "
            f"source={trigger}; reason={reason}; running_for={running_seconds}s "
            f"(threshold {threshold_seconds}s)."
        )
        context: dict[str, Any] = {
            "orphan_recovered_at": now_iso,
            "orphan_recovered_trigger": trigger,
            "orphan_recovered_reason": reason,
            "orphan_recovered_running_seconds": running_seconds,
            "orphan_recovered_threshold_seconds": threshold_seconds,
        }
        if normalized_runner:
            context["orphan_recovered_by_runner"] = normalized_runner
        updated = agent_service.update_task(
            task_id,
            status=TaskStatus.FAILED,
            output=output,
            context=context,
            worker_id=worker_id,
        )
        if updated is not None:
            recovered.append(updated)

    if recovered:
        logger.warning(
            "runner_orphan_recovery_applied trigger=%s reason=%s recovered=%s threshold_seconds=%s claimed_by_runner_only=%s",
            trigger,
            reason,
            len(recovered),
            threshold_seconds,
            claimed_by_runner_only,
        )
    return recovered


async def maybe_recover_on_idle_heartbeat(
    *,
    snapshot: dict[str, Any],
    background_tasks: BackgroundTasks,
    alert_builder: Callable[[dict[str, Any]], str] | None = None,
) -> list[dict[str, Any]]:
    """Auto-fail stale running tasks claimed by an idle runner and notify Telegram."""
    try:
        status = str(snapshot.get("status") or "").strip().lower()
        active_task_id = str(snapshot.get("active_task_id") or "").strip()
        runner_id = str(snapshot.get("runner_id") or "").strip()
        if status != "idle" or active_task_id or not runner_id:
            return []

        recovered = recover_stale_running_tasks(
            trigger="runner_idle_heartbeat",
            reason="runner_reported_idle_no_active_task",
            runner_id=runner_id,
            claimed_by_runner_only=True,
        )

        if recovered:
            if telegram_adapter.is_configured():
                for task in recovered:
                    try:
                        message = alert_builder(task) if alert_builder else _fallback_alert(task)
                    except Exception:
                        message = _fallback_alert(task)
                    output = str(task.get("output") or "").strip()
                    if output:
                        message += f"\n\nOutput: {output[:200]}"
                    background_tasks.add_task(telegram_adapter.send_alert, message)

        return recovered
    except Exception:
        logger.warning("runner_orphan_recovery_failed", exc_info=True)
        return []
