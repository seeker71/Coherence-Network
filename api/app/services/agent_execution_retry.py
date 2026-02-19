"""Retry bookkeeping helpers for agent task execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

_RETRY_MAX_DEFAULT = 1
_RETRY_MAX_CAP = 5
_FAILURE_OUTPUT_MAX = 1200
_RETRY_HINT_MAX = 900


def _non_negative_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return default


def _context_non_negative_int(context: dict[str, Any], key: str, default: int = 0) -> int:
    return _non_negative_int(context.get(key), default=default)


def _resolve_retry_max(context: dict[str, Any], env_retry_max: Any) -> int:
    candidates: list[Any] = [
        context.get("retry_max"),
        context.get("max_retries"),
        env_retry_max,
    ]
    for raw in candidates:
        value = _non_negative_int(raw, default=-1)
        if value >= 0:
            return max(1, min(value, _RETRY_MAX_CAP))
    return _RETRY_MAX_DEFAULT


def _failure_excerpt(text: str, *, limit: int = 260) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _retry_fix_hint(failure_output: str, retry_number: int) -> str:
    lower = failure_output.lower()
    guidance = (
        "Find the root cause, make the smallest fix that addresses it, and verify with a focused check."
    )
    if "paid provider" in lower:
        guidance = (
            "Switch to an allowed/free provider route or run with explicit paid-provider override when policy permits."
        )
    elif "window budget" in lower or "usage blocked" in lower:
        guidance = (
            "Use a cheaper route, wait for budget window reset, or reduce paid-provider usage before retrying."
        )
    elif "execution budget exceeded" in lower or "cost overrun" in lower:
        guidance = (
            "Reduce scope/output size or raise max_cost_usd so execution stays within budget."
        )
    elif "empty direction" in lower:
        guidance = "Provide a concrete non-empty direction with an explicit goal and expected output."
    elif "timeout" in lower or "timed out" in lower:
        guidance = "Narrow the task scope and prioritize one concrete fix for this retry."
    elif "claim_failed" in lower:
        guidance = "Ensure no other worker owns the task lease before retrying."
    return (
        f"Retry attempt {retry_number}: previous failure was '{_failure_excerpt(failure_output)}'. "
        f"Hint: {guidance}"
    )[:_RETRY_HINT_MAX]


def record_failure_hits_and_retry(
    *,
    task_id: str,
    task: dict[str, Any],
    result: dict[str, Any],
    worker_id: str,
    retry_depth: int,
    env_retry_max: Any,
    pending_status: Any,
    update_task: Callable[..., Any],
    execute_again: Callable[..., dict[str, Any]],
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> dict[str, Any]:
    status_value = str(result.get("status") or "").strip().lower()
    if status_value != "failed":
        return result

    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    failure_hits = _context_non_negative_int(context, "failure_hits", default=0) + 1
    retry_count = _context_non_negative_int(context, "retry_count", default=0)
    retry_max = _resolve_retry_max(context, env_retry_max)

    failure_output = (
        str(task.get("output") or "").strip()
        or str(result.get("error") or "").strip()
        or "task_failed"
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    context_patch: dict[str, Any] = {
        "failure_hits": failure_hits,
        "last_failure_output": failure_output[:_FAILURE_OUTPUT_MAX],
        "last_failure_at": now_iso,
        "retry_max": retry_max,
    }

    can_retry = retry_count < retry_max and retry_depth < retry_max
    if not can_retry:
        update_task(
            task_id,
            context=context_patch,
            worker_id=worker_id,
        )
        return result

    next_retry = retry_count + 1
    context_patch.update(
        {
            "retry_count": next_retry,
            "retry_hint": _retry_fix_hint(failure_output, next_retry),
            "retry_requested_at": now_iso,
            "last_retry_source": "auto_failure_recovery",
        }
    )
    update_task(
        task_id,
        status=pending_status,
        current_step=f"retrying ({next_retry}/{retry_max})",
        context=context_patch,
        worker_id=worker_id,
    )
    return execute_again(
        task_id,
        worker_id=worker_id,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        _retry_depth=retry_depth + 1,
    )
