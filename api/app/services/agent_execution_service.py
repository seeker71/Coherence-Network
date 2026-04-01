"""Server-side execution for agent tasks.

Execution policy:
- paid providers are allowed by default unless explicitly disabled by env
- records runtime events for diagnostics and usage visibility
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config_loader import get_bool, get_float, get_int
from app.models.agent import TaskStatus
from app.models.friction import FrictionEvent
from app.models.runtime import RuntimeEventCreate
from app.services import (
    agent_execution_codex_service,
    agent_service,
    automation_usage_service,
    friction_service,
    idea_service,
    metrics_service,
    spec_registry_service,
    runtime_service,
    agent_routing_service,
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
    return get_bool("agent_cost", "allow_paid_providers", default=True)


def _codex_execution_disabled() -> bool:
    return get_bool("agent_executor", "disable_codex_executor", default=True)


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
    if cleaned.startswith("codex/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("openclaw/") or cleaned.startswith("clawwork/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("claude/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("cursor/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("gemini/"):
        return cleaned.split("/", 1)[1].strip()
    return cleaned


_OPENROUTER_MODEL_ALIAS_MAP: dict[str, str] = {
    # CLI-facing aliases -> OpenRouter catalog IDs.
    "gpt-5-codex": "openai/gpt-5-codex",
    "gpt-5-codex-spark": "openai/gpt-5-codex",
    "gpt-5.3-codex": "openai/gpt-5.3-codex",
    "gpt-5.3-codex-spark": "openai/gpt-5.3-codex",
    "claude-sonnet-4-5-20250929": "anthropic/claude-sonnet-4.5",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4.5",
    "claude-opus-4-5": "anthropic/claude-opus-4.5",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
}
_CLAUDE_OPENROUTER_ALIAS_RE = re.compile(
    r"^claude-(?P<tier>sonnet|opus)-(?P<major>\d+)(?:-(?P<minor>\d+))?(?:[.-].*)?$",
    re.IGNORECASE,
)


def _normalize_model_for_openrouter(model: str) -> str:
    cleaned = agent_routing_service.normalize_model_name(str(model or "").strip()).strip()
    if not cleaned:
        return ""
    if "/" in cleaned:
        return cleaned

    lowered = cleaned.lower()
    alias = _OPENROUTER_MODEL_ALIAS_MAP.get(lowered)
    if alias:
        return alias

    if lowered.startswith("gemini-"):
        return f"google/{lowered}"

    match = _CLAUDE_OPENROUTER_ALIAS_RE.match(lowered)
    if match:
        tier = str(match.group("tier") or "sonnet").lower()
        major = str(match.group("major") or "").strip()
        minor = str(match.group("minor") or "").strip()
        if major:
            version = f"{major}.{minor}" if minor else major
            return f"anthropic/claude-{tier}-{version}"

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
    if route_decision.get("is_paid_provider") is not None:
        return bool(route_decision.get("is_paid_provider"))

    # Fallback: classify based on executor/model
    executor = str(ctx.get("executor") or "").strip().lower()
    model = str(task.get("model") or ctx.get("model_override") or "").strip().lower()
    command = str(ctx.get("command") or "").strip().lower()

    from app.services.agent_routing.provider_classification import classify_provider
    _, _, is_paid = classify_provider(executor=executor, model=model, command=command, worker_id=None)
    return is_paid


def _task_route_provider(task: dict[str, Any]) -> str:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = ctx.get("route_decision") if isinstance(ctx.get("route_decision"), dict) else {}
    provider = str(
        route_decision.get("billing_provider")
        or route_decision.get("provider")
        or ""
    ).strip().lower()
    if provider:
        return provider

    model = _extract_underlying_model(str(task.get("model") or "")).strip().lower()
    if "openrouter" in model:
        return "openrouter"
    if "codex" in model:
        return "openai-codex"
    if "claude" in model:
        return "claude"
    if "gemini" in model:
        return "gemini"
    if model.startswith(("gpt", "o1", "o3", "o4", "openai/")):
        return "openai"
    return "unknown"


def _friction_metadata_from_task(task_id: str, task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = context.get("route_decision") if isinstance(context.get("route_decision"), dict) else {}

    provider = str(
        route_decision.get("provider")
        or route_decision.get("billing_provider")
        or _task_route_provider(task)
    ).strip()
    billing_provider = str(
        route_decision.get("billing_provider")
        or route_decision.get("provider")
        or provider
    ).strip()

    task_model = str(task.get("model") or "").strip()
    normalized_tool = "agent-task-execution-summary"
    run_id = str(
        context.get("active_run_id")
        or context.get("run_id")
        or context.get("last_run_id")
        or ""
    ).strip()

    return {
        "task_id": (task_id or "").strip() or None,
        "run_id": run_id or None,
        "provider": provider or None,
        "billing_provider": billing_provider or None,
        "tool": normalized_tool,
        "model": task_model or None,
    }


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
    infra_cost_usd = _runtime_cost_usd(elapsed_ms)
    external_cost_usd = _external_provider_cost_usd(
        is_paid_provider=bool(is_paid_provider),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    total_cost_usd = round(infra_cost_usd + external_cost_usd, 6)
    metadata: dict[str, str | float | int | bool] = {
        "tracking_kind": "agent_tool_call",
        "task_id": task_id,
        "model": model,
        "provider": "openrouter",
        "is_paid_provider": bool(is_paid_provider),
        "infrastructure_cost_usd": round(infra_cost_usd, 6),
        "external_provider_cost_usd": external_cost_usd,
        "total_cost_usd": total_cost_usd,
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
        # Grounded cost: prefer provider-reported cost (most accurate), then
        # token-based cost (real token counts × configured rates), then
        # time-based estimate (elapsed_ms × rate) as last resort.
        # OpenRouter may include native_tokens_cost or cost in the usage dict.
        provider_native_cost = None
        for cost_key in ("cost", "native_tokens_cost", "total_cost"):
            raw_cost = usage_dict.get(cost_key)
            if raw_cost is not None:
                try:
                    provider_native_cost = float(raw_cost)
                    break
                except (TypeError, ValueError):
                    pass
        token_based_cost = _external_provider_cost_usd(
            is_paid_provider=route_is_paid,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        time_based_cost = _runtime_cost_usd(elapsed_ms)
        # Priority: provider-reported > token-based > time-based
        if provider_native_cost is not None and provider_native_cost > 0:
            grounded_cost = provider_native_cost
        elif (prompt_tokens + completion_tokens) > 0:
            grounded_cost = token_based_cost
        else:
            grounded_cost = time_based_cost
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
            actual_cost_usd=grounded_cost,
        )
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "content": content,
            "usage_json": usage_json,
            "provider_request_id": str(meta.get("provider_request_id") or ""),
            "actual_cost_usd": grounded_cost,
            "max_cost_usd": cost_budget.get("max_cost_usd"),
            "cost_slack_ratio": cost_budget.get("cost_slack_ratio"),
        }
    except OpenRouterError as exc:
        fallback_error = str(exc)
        if (not _codex_execution_disabled()) and agent_execution_codex_service.should_fallback_to_codex_exec(
            model, fallback_error
        ):
            fallback_result = agent_execution_codex_service.run_codex_exec(
                task_id=task_id,
                model=model,
                prompt=prompt,
                route_is_paid=route_is_paid,
                started_perf=started_perf,
                cost_budget=cost_budget,
            )
            if fallback_result.get("ok") is True:
                return fallback_result

        elapsed_ms = max(1, int(round((time.perf_counter() - started_perf) * 1000)))
        _record_openrouter_tool_event(
            task_id=task_id,
            model=model,
            is_paid_provider=route_is_paid,
            elapsed_ms=elapsed_ms,
            ok=False,
            actual_cost_usd=_runtime_cost_usd(elapsed_ms),
            error=fallback_error,
        )
        return {"ok": False, "elapsed_ms": elapsed_ms, "error": f"Execution failed (OpenRouter): {fallback_error}"}


def _resolve_openrouter_model(task: dict[str, Any], default: str) -> str:
    model = _extract_underlying_model(str(task.get("model") or ""))
    resolved = model or default
    normalized = _normalize_model_for_openrouter(resolved)
    if _codex_execution_disabled() and "codex" in str(normalized).lower():
        return agent_routing_service.enforce_openrouter_free_model(normalized)
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    route = context.get("route_decision") if isinstance(context.get("route_decision"), dict) else {}
    executor = str(route.get("executor") or context.get("executor") or "").strip().lower()
    if executor == "openrouter" or str(normalized).strip().lower().startswith("openrouter/"):
        return agent_routing_service.enforce_openrouter_free_model(normalized)
    return normalized


def _resolve_prompt(task: dict[str, Any]) -> str:
    prompt = str(task.get("direction") or "").strip()
    if not prompt:
        return ""
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    retry_hint = str(context.get("retry_hint") or "").strip()
    if not retry_hint:
        return prompt

    def _clean_line(value: Any, *, max_chars: int = 220) -> str:
        text = " ".join(str(value or "").split()).strip()
        return text[:max_chars]

    memory_lines: list[str] = [
        "Retry memory packet:",
        "- Preserve prior work and patch incrementally (do not restart from scratch).",
    ]
    category = _clean_line(context.get("last_failure_category"), max_chars=80)
    signature = _clean_line(context.get("last_failure_signature"), max_chars=120)
    summary = _clean_line(context.get("last_failure_summary"), max_chars=240)
    action = _clean_line(context.get("last_failure_action"), max_chars=240)
    output_excerpt = _clean_line(context.get("last_failure_output"), max_chars=120)
    if category:
        memory_lines.append(f"- last_failure_category={category}")
    if signature:
        memory_lines.append(f"- last_failure_signature={signature}")
    if summary:
        memory_lines.append(f"- last_failure_summary={summary}")
    if action:
        memory_lines.append(f"- last_failure_action={action}")
    if output_excerpt:
        memory_lines.append(f"- last_failure_output_excerpt={output_excerpt}")

    reflections = context.get("retry_reflections")
    if isinstance(reflections, list) and reflections:
        latest = reflections[-1] if isinstance(reflections[-1], dict) else {}
        blind_spot = _clean_line(latest.get("blind_spot"), max_chars=180)
        next_action = _clean_line(latest.get("next_action"), max_chars=180)
        if blind_spot:
            memory_lines.append(f"- last_retry_blind_spot={blind_spot}")
        if next_action:
            memory_lines.append(f"- last_retry_next_action={next_action}")

    return f"{prompt}\n\nRetry guidance:\n{retry_hint}\n\n" + "\n".join(memory_lines)


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


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _paid_provider_block_on_soft_quota_threshold() -> bool:
    return get_bool("agent_cost", "block_on_soft_quota_threshold", default=False)


def _quota_guard_indicates_exhausted(quota_guard: dict[str, Any]) -> bool:
    blocked_metrics = quota_guard.get("blocked_metrics")
    if isinstance(blocked_metrics, list):
        observed_signal = False
        for item in blocked_metrics:
            if not isinstance(item, dict):
                continue
            remaining = _to_float(item.get("remaining"))
            remaining_ratio = _to_float(item.get("remaining_ratio"))
            if remaining is not None:
                observed_signal = True
                if remaining <= 0.0:
                    return True
            if remaining_ratio is not None:
                observed_signal = True
                if remaining_ratio <= 0.0:
                    return True
        if observed_signal:
            return False

    reason = str(quota_guard.get("reason") or "").strip().lower()
    if not reason:
        return False
    if "exhaust" in reason or "deplet" in reason:
        return True
    return bool(re.search(r"(remaining|ratio)\s*[:=]\s*0+(?:\.0+)?\b", reason))


def _paid_tool_windows_budget() -> tuple[int | None, int | None, float]:
    env_limit_8h = get_int("agent_cost", "paid_tool_8h_limit", default=None)
    env_limit_week = get_int("agent_cost", "paid_tool_week_limit", default=None)
    if env_limit_8h is not None:
        env_limit_8h = max(1, env_limit_8h)
    if env_limit_week is not None:
        env_limit_week = max(1, env_limit_week)

    budget_fraction = get_float("agent_cost", "paid_tool_window_budget_fraction", default=1.0 / 3.0)
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

    provider = _task_route_provider(task)
    try:
        quota_guard = automation_usage_service.provider_limit_guard_decision(
            provider,
            force_refresh=False,
        )
    except Exception:
        quota_guard = {"allowed": True}

    if not bool(quota_guard.get("allowed", True)):
        if not _paid_provider_block_on_soft_quota_threshold() and not _quota_guard_indicates_exhausted(quota_guard):
            return True, None
        detail = str(quota_guard.get("reason") or "provider quota threshold reached").strip()
        msg = (
            "Paid-provider usage blocked by provider quota policy: "
            f"provider={provider}; {detail}"
        )
        _record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="provider_usage_limit_exceeded",
            endpoint="tool:agent-task-execution-summary",
            severity="high",
            notes=msg,
            energy_loss_estimate=0.0,
        )
        return False, msg

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
    return get_float("agent_cost", "runtime_cost_per_second", default=0.002)


def _runtime_cost_usd(runtime_ms: int) -> float:
    return max(0.0, float(runtime_ms)) / 1000.0 * _runtime_cost_per_second()


def _external_provider_cost_per_1k_input_tokens() -> float:
    return get_float("agent_cost", "external_input_cost_per_1k", default=0.00015)


def _external_provider_cost_per_1k_output_tokens() -> float:
    return get_float("agent_cost", "external_output_cost_per_1k", default=0.0006)


def _external_provider_cost_usd(
    *,
    is_paid_provider: bool,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    if not is_paid_provider:
        return 0.0
    in_tokens = max(0, int(prompt_tokens))
    out_tokens = max(0, int(completion_tokens))
    in_cost = (float(in_tokens) / 1000.0) * _external_provider_cost_per_1k_input_tokens()
    out_cost = (float(out_tokens) / 1000.0) * _external_provider_cost_per_1k_output_tokens()
    return round(max(0.0, in_cost + out_cost), 6)


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
    metadata = _friction_metadata_from_task(task_id, task)
    event = FrictionEvent(
        id=f"fric_{uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc),
        task_id=task_id,
        endpoint=endpoint,
        run_id=metadata.get("run_id"),
        provider=metadata.get("provider"),
        billing_provider=metadata.get("billing_provider"),
        tool=metadata.get("tool"),
        model=metadata.get("model"),
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
    try:
        friction_service.append_event(event)
    except Exception:
        return
