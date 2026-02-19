"""Server-side execution for agent tasks.

This is intentionally conservative:
- default-deny for paid providers (can be overridden via env for emergencies)
- records runtime events for diagnostics and usage visibility
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.agent import TaskStatus
from app.models.friction import FrictionEvent
from app.models.runtime import RuntimeEventCreate
from app.services import (
    agent_service,
    friction_service,
    idea_service,
    metrics_service,
    spec_registry_service,
    runtime_service,
)
from app.services.agent_execution_task_flow import execute_task
from app.services.openrouter_client import OpenRouterError, chat_completion

# Re-exported and referenced indirectly by ``agent_execution_task_flow``.
_ = (
    idea_service,
    spec_registry_service,
    execute_task,
    agent_service,
    friction_service,
    metrics_service,
    runtime_service,
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _truthy_any(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    return _truthy(str(value) if value is not None else None)


def _paid_providers_allowed() -> bool:
    # Default: paid providers NOT allowed.
    return _truthy(os.getenv("AGENT_ALLOW_PAID_PROVIDERS", "0"))


def _paid_route_override_requested(task: dict[str, Any]) -> bool:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    override_keys = (
        "force_allow_paid_providers",
        "force_paid_provider",
        "force_paid_providers",
        "allow_paid_provider",
        "allow_paid_providers",
    )
    for key in override_keys:
        if key in ctx:
            return _truthy_any(ctx.get(key))
    return False


def _extract_underlying_model(task_model: str) -> str:
    cleaned = (task_model or "").strip()
    if cleaned.startswith("openclaw/") or cleaned.startswith("clawwork/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("cursor/"):
        return cleaned.split("/", 1)[1].strip()
    return cleaned


def _write_task_log(task_id: str, lines: list[str]) -> None:
    try:
        api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logs_dir = os.path.join(api_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        path = os.path.join(logs_dir, f"task_{task_id}.log")
        with open(path, "a", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln.rstrip() + "\n")
    except Exception:
        # Logging must never break execution.
        return


def _claim_task(task_id: str, worker_id: str) -> tuple[bool, str | None]:
    try:
        agent_service.update_task(task_id, status=TaskStatus.RUNNING, worker_id=worker_id)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _task_route_is_paid(task: dict[str, Any]) -> bool:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = ctx.get("route_decision") if isinstance(ctx.get("route_decision"), dict) else {}
    return bool(route_decision.get("is_paid_provider"))


def _finish_task(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    status: TaskStatus,
    output: str,
    model_for_metrics: str,
    elapsed_ms: int,
) -> None:
    agent_service.update_task(task_id, status=status, output=output, worker_id=worker_id)
    metrics_service.record_task(
        task_id=task_id,
        task_type=str(task.get("task_type") or "unknown"),
        model=model_for_metrics,
        duration_seconds=max(0.0, float(elapsed_ms) / 1000.0),
        status="completed" if status == TaskStatus.COMPLETED else "failed",
    )


def _record_openrouter_tool_event(
    *,
    task_id: str,
    model: str,
    is_paid_provider: bool,
    elapsed_ms: int,
    ok: bool,
    provider_request_id: str | None = None,
    response_id: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    usage_json: str = "{}",
    error: str | None = None,
    actual_cost_usd: float | None = None,
) -> None:
    status_code = 200 if ok else 500
    metadata: dict[str, str | float | int | bool] = {
        "tracking_kind": "agent_tool_call",
        "task_id": task_id,
        "model": model,
        "provider": "openrouter",
        "is_paid_provider": bool(is_paid_provider),
    }
    if actual_cost_usd is not None:
        metadata["runtime_cost_usd"] = round(float(actual_cost_usd), 6)
    if ok:
        metadata.update(
            {
                "usage_prompt_tokens": int(prompt_tokens),
                "usage_completion_tokens": int(completion_tokens),
                "usage_total_tokens": int(total_tokens),
                "usage_json": str(usage_json)[:2000],
                "provider_request_id": (provider_request_id or "")[:200],
                "response_id": (response_id or "")[:200],
            }
        )
    else:
        metadata["error"] = (error or "unknown")[:800]

    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:openrouter.chat_completion",
            method="RUN",
            status_code=status_code,
            runtime_ms=float(max(1, int(elapsed_ms))),
            idea_id="coherence-network-agent-pipeline",
            metadata=metadata,
        )
    )


def _run_openrouter(
    *,
    task_id: str,
    model: str,
    prompt: str,
    route_is_paid: bool,
    started_perf: float,
    cost_budget: dict[str, float | None],
) -> dict[str, Any]:
    try:
        content, usage, meta = chat_completion(model=model, prompt=prompt)
        elapsed_ms = max(1, int(meta.get("elapsed_ms") or int(round((time.perf_counter() - started_perf) * 1000))))
        usage_dict = usage if isinstance(usage, dict) else {}
        prompt_tokens = int(usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens") or 0)
        completion_tokens = int(usage_dict.get("completion_tokens") or usage_dict.get("output_tokens") or 0)
        total_tokens = int(usage_dict.get("total_tokens") or (prompt_tokens + completion_tokens))
        usage_json = json.dumps(usage_dict, sort_keys=True)[:2000]
        _record_openrouter_tool_event(
            task_id=task_id,
            model=model,
            is_paid_provider=route_is_paid,
            elapsed_ms=elapsed_ms,
            ok=True,
            provider_request_id=str(meta.get("provider_request_id") or ""),
            response_id=str(meta.get("response_id") or ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_json=usage_json,
            actual_cost_usd=_runtime_cost_usd(elapsed_ms),
        )
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "content": content,
            "usage_json": usage_json,
            "provider_request_id": str(meta.get("provider_request_id") or ""),
            "actual_cost_usd": _runtime_cost_usd(elapsed_ms),
            "max_cost_usd": cost_budget.get("max_cost_usd"),
            "cost_slack_ratio": cost_budget.get("cost_slack_ratio"),
        }
    except OpenRouterError as exc:
        elapsed_ms = max(1, int(round((time.perf_counter() - started_perf) * 1000)))
        _record_openrouter_tool_event(
            task_id=task_id,
            model=model,
            is_paid_provider=route_is_paid,
            elapsed_ms=elapsed_ms,
            ok=False,
            actual_cost_usd=_runtime_cost_usd(elapsed_ms),
            error=str(exc),
        )
        return {"ok": False, "elapsed_ms": elapsed_ms, "error": f"Execution failed (OpenRouter): {exc}"}


def _resolve_openrouter_model(task: dict[str, Any], default: str) -> str:
    model = _extract_underlying_model(str(task.get("model") or ""))
    return model or default


def _resolve_prompt(task: dict[str, Any]) -> str:
    prompt = str(task.get("direction") or "").strip()
    if not prompt:
        return ""
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    retry_hint = str(context.get("retry_hint") or "").strip()
    if not retry_hint:
        return prompt
    return f"{prompt}\n\nRetry guidance:\n{retry_hint}"


def _normalize_positive_float(value: Any, default: float | None = None) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return default
    if normalized <= 0.0:
        return default
    return normalized


def _normalize_ratio(value: Any, default: float = 1.25) -> float:
    parsed = _normalize_positive_float(value, default=None)
    if parsed is None:
        return default
    return max(1.0, parsed)


def _normalize_ratio_0_to_1(value: Any, default: float = 0.3333333) -> float:
    parsed = _normalize_positive_float(value, default=None)
    if parsed is None:
        return default
    return min(1.0, parsed)


def _normalize_int(value: Any, default: int | None = None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _resolve_window_paid_tool_limit(env_name: str) -> int | None:
    raw = os.getenv(env_name)
    return _normalize_int(raw, default=None)


def _paid_tool_windows_budget() -> tuple[int | None, int | None, float]:
    env_limit_8h = _resolve_window_paid_tool_limit("PAID_TOOL_8H_LIMIT")
    env_limit_week = _resolve_window_paid_tool_limit("PAID_TOOL_WEEK_LIMIT")
    if env_limit_8h is not None:
        env_limit_8h = max(1, env_limit_8h)
    if env_limit_week is not None:
        env_limit_week = max(1, env_limit_week)

    budget_fraction = _normalize_ratio_0_to_1(
        os.getenv("PAID_TOOL_WINDOW_BUDGET_FRACTION"),
        default=1.0 / 3.0,
    )
    return env_limit_8h, env_limit_week, budget_fraction


def _count_paid_openrouter_tool_events_within_window(window_seconds: int) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - max(60, int(window_seconds))
    target_endpoint = "tool:openrouter.chat_completion"
    canonical_target = target_endpoint if target_endpoint.startswith("/") else f"/{target_endpoint}"
    events = runtime_service.list_events(limit=4000)
    count = 0
    for event in events:
        if event.recorded_at.timestamp() < cutoff:
            continue
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        if event.endpoint not in {target_endpoint, canonical_target}:
            continue
        if not bool(metadata.get("is_paid_provider")):
            continue
        count += 1
    return count


def _check_paid_provider_window_budget(
    route_is_paid: bool,
    task: dict[str, Any],
    *,
    task_id: str,
) -> tuple[bool, str | None]:
    if not route_is_paid:
        return True, None

    limit_8h, limit_week, budget_fraction = _paid_tool_windows_budget()
    if limit_8h is None and limit_week is None:
        return True, None

    windows: list[tuple[str, int, int, int]] = []
    if limit_8h is not None:
        used_8h = _count_paid_openrouter_tool_events_within_window(8 * 60 * 60)
        allowed_8h = max(1, int(limit_8h * budget_fraction))
        windows.append(("8h", used_8h, limit_8h, allowed_8h))
    if limit_week is not None:
        used_week = _count_paid_openrouter_tool_events_within_window(7 * 24 * 60 * 60)
        allowed_week = max(1, int(limit_week * budget_fraction))
        windows.append(("1w", used_week, limit_week, allowed_week))

    blocked_windows = [item for item in windows if item[1] >= item[3]]
    if not blocked_windows:
        return True, None

    details = "; ".join(
        f"{label}_limit used={used}/{window_limit}, allowed={allowed} (fraction={budget_fraction:.3f})"
        for label, used, window_limit, allowed in blocked_windows
    )
    msg = f"Paid-provider usage blocked by window policy: {details}"
    _record_friction_event(
        task_id=task_id,
        task=task,
        stage="agent_execution",
        block_type="usage_window_budget_exceeded",
        endpoint="tool:agent-task-execution-summary",
        severity="high",
        notes=msg,
        energy_loss_estimate=0.0,
    )
    return False, msg


def _runtime_cost_per_second() -> float:
    return _normalize_positive_float(os.getenv("RUNTIME_COST_PER_SECOND", "0.002"), default=0.002) or 0.002


def _runtime_cost_usd(runtime_ms: int) -> float:
    return max(0.0, float(runtime_ms)) / 1000.0 * _runtime_cost_per_second()


def _compact_metadata(values: dict[str, Any]) -> dict[str, str | float | int | bool]:
    return {key: value for key, value in values.items() if value is not None}


def _record_friction_event(
    task_id: str,
    task: dict[str, Any],
    *,
    stage: str,
    block_type: str,
    notes: str,
    endpoint: str | None = None,
    severity: str = "high",
    energy_loss_estimate: float = 0.0,
) -> None:
    event = FrictionEvent(
        id=f"fric_{uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc),
        endpoint=endpoint,
        stage=stage,
        block_type=block_type,
        severity=severity,
        owner="agent_pipeline",
        unblock_condition="Re-run with valid inputs or explicit override, and keep failures in task context.",
        energy_loss_estimate=max(0.0, float(energy_loss_estimate)),
        cost_of_delay=0.0,
        status="open",
        notes=notes[:1200] if notes else None,
        resolved_at=None,
        time_open_hours=None,
        resolution_action=None,
    )
    _ = task
    try:
        friction_service.append_event(event)
    except Exception:
        return
