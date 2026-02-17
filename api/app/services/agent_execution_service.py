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
from app.models.spec_registry import SpecRegistryUpdate
from app.services import (
    agent_service,
    friction_service,
    idea_service,
    metrics_service,
    runtime_service,
    spec_registry_service,
)
from app.services.openrouter_client import OpenRouterError, chat_completion


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
    if cleaned.startswith("openclaw/"):
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
    return str(task.get("direction") or "").strip()


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


def _task_target_ids(task: dict[str, Any]) -> tuple[str | None, str | None]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    idea_id = str(ctx.get("idea_id") or "").strip() or None
    spec_id = str(ctx.get("spec_id") or "").strip() or None
    return idea_id, spec_id


def _resolve_cost_controls(
    task: dict[str, Any],
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> dict[str, float | None]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    context_max_cost = _normalize_positive_float(ctx.get("max_cost_usd")) or _normalize_positive_float(
        ctx.get("max_cost")
    )
    context_estimated_cost = _normalize_positive_float(ctx.get("estimated_cost_usd")) or _normalize_positive_float(
        ctx.get("estimated_cost")
    )
    context_slack = _normalize_ratio(ctx.get("cost_slack_ratio"), default=1.25)

    env_max_cost = _normalize_positive_float(os.getenv("AGENT_TASK_MAX_COST_USD"))
    env_estimated_cost = _normalize_positive_float(os.getenv("AGENT_TASK_ESTIMATED_COST_USD"))
    env_slack = _normalize_ratio(os.getenv("AGENT_TASK_COST_SLACK_RATIO"), default=1.25)

    resolved_max_cost = _normalize_positive_float(max_cost_usd) or context_max_cost or env_max_cost
    resolved_estimated_cost = (
        _normalize_positive_float(estimated_cost_usd)
        or context_estimated_cost
        or env_estimated_cost
    )
    resolved_slack = _normalize_ratio(cost_slack_ratio, default=context_slack or env_slack or 1.25)

    if resolved_max_cost is None and resolved_estimated_cost is not None:
        resolved_max_cost = max(resolved_estimated_cost * resolved_slack, 0.0001)

    return {
        "max_cost_usd": resolved_max_cost,
        "estimated_cost_usd": resolved_estimated_cost,
        "cost_slack_ratio": resolved_slack,
    }


def _safe_parse_output_metrics(output: str) -> dict[str, Any]:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _compact_metadata(values: dict[str, Any]) -> dict[str, str | float | int | bool]:
    return {key: value for key, value in values.items() if value is not None}


def _extract_output_metric(parsed: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in parsed:
            continue
        raw = parsed.get(key)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value < 0.0:
            continue
        return value
    return None


def _attribution_values_from_output(output: str) -> dict[str, float | None]:
    parsed = _safe_parse_output_metrics(output)
    if not parsed:
        return {}

    return {
        "actual_value": _extract_output_metric(
            parsed, ("actual_value", "actual_value_to_whole", "actual_impact")
        ),
        "confidence": _extract_output_metric(parsed, ("confidence",)),
        "estimated_value": _extract_output_metric(
            parsed, ("estimated_value", "estimated_value_to_whole", "potential_value")
        ),
        "estimated_cost": _extract_output_metric(
            parsed, ("estimated_cost", "estimated_cost_usd", "estimated_budget", "cost_budget")
        ),
        "actual_cost": _extract_output_metric(
            parsed, ("actual_cost", "actual_cost_usd", "cost_actual")
        ),
    }


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


def _apply_value_attribution(
    task: dict[str, Any],
    *,
    output: str,
    actual_cost_usd: float | None,
) -> None:
    idea_id, spec_id = _task_target_ids(task)
    if not idea_id and not spec_id:
        return

    metrics = _attribution_values_from_output(output)
    potential_value = metrics.get("estimated_value")
    estimated_cost = metrics.get("estimated_cost")
    actual_value = metrics.get("actual_value")
    confidence = metrics.get("confidence")

    if actual_cost_usd is not None:
        estimated_cost = actual_cost_usd if estimated_cost is None else estimated_cost

    if idea_id:
        try:
            idea_service.update_idea(
                idea_id=idea_id,
                actual_value=actual_value,
                actual_cost=actual_cost_usd,
                confidence=confidence,
                manifestation_status=None,
                potential_value=potential_value,
                estimated_cost=estimated_cost,
            )
        except Exception:
            pass

    if spec_id:
        update = SpecRegistryUpdate(
            actual_value=actual_value,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost_usd,
            potential_value=potential_value,
        )
        try:
            spec_registry_service.update_spec(spec_id, update)
        except Exception:
            pass


def _cost_overrun_blocked(
    task: dict[str, Any],
    task_id: str,
    elapsed_ms: int,
    actual_cost_usd: float,
    cost_budget: dict[str, float | None],
    model: str,
    worker_id: str,
    usage_json: str,
    request_id: str,
) -> dict[str, Any] | None:
    max_cost = cost_budget.get("max_cost_usd")
    if max_cost is None or actual_cost_usd <= max_cost:
        return None

    msg = (
        f"Execution budget exceeded: actual_cost_usd={round(actual_cost_usd, 6)} > "
        f"max_cost_usd={round(max_cost, 6)}."
    )
    _record_friction_event(
        task_id=task_id,
        task=task,
        stage="agent_execution",
        block_type="cost_overrun",
        endpoint="tool:agent-task-execution-summary",
        severity="critical",
        notes=msg,
        energy_loss_estimate=actual_cost_usd,
    )
    return _complete_failure(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        model=model,
        elapsed_ms=elapsed_ms,
        msg=msg,
        actual_cost_usd=actual_cost_usd,
        usage_json=usage_json,
        request_id=request_id,
    )


def _complete_success(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    elapsed_ms: int,
    content: str,
    usage_json: str,
    request_id: str,
    output_metrics: dict[str, float | None] | None = None,
    actual_cost_usd: float | None = None,
    max_cost_usd: float | None = None,
    cost_slack_ratio: float | None = None,
) -> dict[str, Any]:
    _write_task_log(
        task_id,
        [
            f"[openrouter] status=200 elapsed_ms={elapsed_ms} request_id={request_id}",
            f"[usage] {usage_json}",
            "[output]",
            content,
        ],
    )
    _finish_task(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        status=TaskStatus.COMPLETED,
        output=content,
        model_for_metrics=str(task.get("model") or model or "unknown"),
        elapsed_ms=elapsed_ms,
    )
    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-execution-summary",
            method="RUN",
            status_code=200,
            runtime_ms=float(max(1, elapsed_ms)),
            idea_id="coherence-network-agent-pipeline",
            metadata=_compact_metadata(
                {
                "tracking_kind": "agent_task_execution",
                "task_id": task_id,
                "model": str(task.get("model") or model or "unknown"),
                "confidence": output_metrics.get("confidence") if output_metrics else None,
                "estimated_value": output_metrics.get("estimated_value") if output_metrics else None,
                "actual_value": output_metrics.get("actual_value") if output_metrics else None,
                "estimated_cost": output_metrics.get("estimated_cost") if output_metrics else None,
                "actual_cost": actual_cost_usd,
                "max_cost_usd": max_cost_usd,
                "cost_slack_ratio": cost_slack_ratio,
                "is_paid_provider": _task_route_is_paid(task),
                }
            ),
        )
    )
    return {"ok": True, "status": "completed", "elapsed_ms": elapsed_ms, "model": model}


def _complete_failure(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    elapsed_ms: int,
    msg: str,
    actual_cost_usd: float | None = None,
    usage_json: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    _write_task_log(task_id, [msg])
    _finish_task(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        status=TaskStatus.FAILED,
        output=msg,
        model_for_metrics=str(task.get("model") or model or "unknown"),
        elapsed_ms=elapsed_ms,
    )
    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-execution-summary",
            method="RUN",
            status_code=500,
            runtime_ms=float(max(1, elapsed_ms)),
            idea_id="coherence-network-agent-pipeline",
            metadata=_compact_metadata(
                {
                "tracking_kind": "agent_task_execution",
                "task_id": task_id,
                "model": str(task.get("model") or model or "unknown"),
                "failure_reason": msg,
                "actual_cost": actual_cost_usd,
                "usage_json": usage_json,
                "provider_request_id": request_id or "",
                "is_paid_provider": _task_route_is_paid(task),
                }
            ),
        )
    )
    return {"ok": False, "status": "failed", "elapsed_ms": elapsed_ms, "model": model}


def execute_task(
    task_id: str,
    *,
    worker_id: str = "openclaw-worker:server",
    force_paid_providers: bool = False,
    max_cost_usd: float | None = None,
    estimated_cost_usd: float | None = None,
    cost_slack_ratio: float | None = None,
) -> dict[str, Any]:
    """Execute a task using OpenRouter (free model by default).

    Returns a small summary dict (also useful for unit tests). This is safe to
    call from FastAPI BackgroundTasks.
    """
    task = agent_service.get_task(task_id)
    if task is None:
        return {"ok": False, "error": "task_not_found"}

    claimed, claim_error = _claim_task(task_id, worker_id)
    if not claimed:
        return {"ok": False, "error": f"claim_failed:{claim_error}"}

    task = agent_service.get_task(task_id) or {}

    route_is_paid = _task_route_is_paid(task)
    if route_is_paid and not (
        _paid_providers_allowed()
        or force_paid_providers
        or _paid_route_override_requested(task)
    ):
        msg = "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled."
        _record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="paid_provider_blocked",
            endpoint="tool:agent-task-execution-summary",
            severity="high",
            notes=msg,
            energy_loss_estimate=0.0,
        )
        _write_task_log(task_id, [msg])
        _finish_task(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            status=TaskStatus.FAILED,
            output=msg,
            model_for_metrics=str(task.get("model") or "unknown"),
            elapsed_ms=1,
        )
        return {"ok": False, "error": "paid_provider_blocked"}

    if route_is_paid and not force_paid_providers:
        allowed, budget_msg = _check_paid_provider_window_budget(
            route_is_paid=True,
            task=task,
            task_id=task_id,
        )
        if not allowed:
            _write_task_log(task_id, [budget_msg or "Paid provider window budget blocked"])
            _finish_task(
                task_id=task_id,
                task=task,
                worker_id=worker_id,
                status=TaskStatus.FAILED,
                output=budget_msg or "Paid provider window budget blocked",
                model_for_metrics=str(task.get("model") or "unknown"),
                elapsed_ms=1,
            )
            return {"ok": False, "error": "paid_provider_window_budget_exceeded"}

    default_model = os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free").strip() or "openrouter/free"
    model = _resolve_openrouter_model(task, default_model)

    prompt = _resolve_prompt(task)
    if not prompt:
        _record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="validation_failure",
            endpoint="tool:agent-task-execution-summary",
            severity="high",
            notes="Execution blocked: empty direction.",
            energy_loss_estimate=0.0,
        )
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=1,
            msg="Empty direction",
        )

    started = time.perf_counter()
    cost_budget = _resolve_cost_controls(task, max_cost_usd, estimated_cost_usd, cost_slack_ratio)
    _write_task_log(task_id, [f"[execute] worker_id={worker_id} model={model}", f"[prompt]\n{prompt}"])

    try:
        result = _run_openrouter(
            task_id=task_id,
            model=model,
            route_is_paid=route_is_paid,
            prompt=prompt,
            started_perf=started,
            cost_budget=cost_budget,
        )
        elapsed_ms = int(result.get("elapsed_ms") or 1)
        if result.get("ok") is True:
            content = str(result.get("content") or "")
            usage_json = str(result.get("usage_json") or "{}")
            request_id = str(result.get("provider_request_id") or "")
            actual_cost_usd = float(result.get("actual_cost_usd") or _runtime_cost_usd(elapsed_ms))

            output_metrics = _attribution_values_from_output(content)
            _apply_value_attribution(task, output=content, actual_cost_usd=actual_cost_usd)

            over_budget = _cost_overrun_blocked(
                task=task,
                task_id=task_id,
                elapsed_ms=elapsed_ms,
                actual_cost_usd=actual_cost_usd,
                cost_budget=cost_budget,
                model=model,
                worker_id=worker_id,
                usage_json=usage_json,
                request_id=request_id,
            )
            if over_budget:
                return over_budget

            return _complete_success(
                task_id=task_id,
                task=task,
                worker_id=worker_id,
                model=model,
                elapsed_ms=elapsed_ms,
                content=content,
                usage_json=usage_json,
                request_id=request_id,
                output_metrics=output_metrics,
                actual_cost_usd=actual_cost_usd,
                max_cost_usd=cost_budget.get("max_cost_usd"),
                cost_slack_ratio=cost_budget.get("cost_slack_ratio"),
            )

        msg = str(result.get("error") or "Execution failed (OpenRouter)")
        _record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="tool_failure",
            endpoint="tool:agent-task-execution-summary",
            severity="high",
            notes=msg,
            energy_loss_estimate=_runtime_cost_usd(elapsed_ms),
        )
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            msg=msg,
            actual_cost_usd=_runtime_cost_usd(elapsed_ms),
        )
    except Exception as exc:
        elapsed_ms = max(1, int(round((time.perf_counter() - started) * 1000)))
        msg = f"Execution failed: {exc}"
        _record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="unexpected_execution_exception",
            endpoint="tool:agent-task-execution-summary",
            severity="critical",
            notes=msg,
            energy_loss_estimate=_runtime_cost_usd(elapsed_ms),
        )
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            msg=msg,
            actual_cost_usd=_runtime_cost_usd(elapsed_ms),
        )
