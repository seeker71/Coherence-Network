"""Agent execution orchestration helpers."""

from __future__ import annotations

import json
import math
import re

from typing import Any

from app.models.spec_registry import SpecRegistryUpdate
from app.services import agent_execution_metrics as metrics_service
from app.services import agent_execution_retry as retry_service
from app.services import agent_execution_service as execution_service
from app.services import agent_task_continuation_service as continuation_service


_SMART_WORKFLOW_FLAG = "AGENT_SMART_WORKFLOW_ENABLED"
_SMART_ROUTER_MODEL = "AGENT_SMART_ROUTER_MODEL"
_SMART_WORKER_MODEL = "AGENT_SMART_WORKER_MODEL"
_SMART_REVIEWER_MODEL = "AGENT_SMART_REVIEWER_MODEL"
_SMART_MAX_RETRIES = 2
_SMART_REPEAT_LIMIT = 2
_SMART_WORKFLOW_TARGET_COMPLEXITY = 0.3
_SMART_FOLLOWUP_COMPLEXITY = 0.25


def _smart_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _smart_env_enabled() -> bool:
    return _smart_truthy(execution_service.os.getenv(_SMART_WORKFLOW_FLAG, "0"))


def _smart_float(raw: object, default: float | None = None) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value


def _smart_int(raw: object, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _smart_normalize_text(raw: object, max_len: int = 220) -> str:
    text = str(raw or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _smart_context(task: dict[str, Any]) -> dict[str, Any]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    return dict(ctx)


def _smart_signature(raw: str) -> str:
    compact = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    return compact[:240]


def _smart_split_by_goals(text: str) -> list[str]:
    chunks = [part.strip() for part in re.split(r"[\n.;:!?,]", text or "") if part.strip()]
    if not chunks:
        return [str(text or "").strip()] if str(text or "").strip() else []

    expanded: list[str] = []
    for chunk in chunks:
        words = chunk.split()
        if len(words) <= 12:
            expanded.append(chunk)
            continue
        for idx in range(0, len(words), 12):
            expanded.append(" ".join(words[idx : idx + 12]).strip())

    return [goal for goal in expanded if goal]


def _smart_complexity_assessment(task: dict[str, Any]) -> dict[str, Any]:
    ctx = _smart_context(task)
    complexity = _smart_float(ctx.get("complexity_score"), default=1.0)
    if complexity is None:
        complexity = 1.0
    complexity = max(0.0, min(1.0, complexity))
    if "complexity_score" not in ctx:
        complexity = 1.0
        complexity_reason = "missing context complexity_score, defaulted to 1.0"
    else:
        complexity_reason = str(ctx.get("complexity_reason") or "").strip()

    explicit_decompose = ctx.get("decompose_required")
    if explicit_decompose is not None:
        decompose_required = _smart_truthy(explicit_decompose)
    else:
        decompose_required = complexity > 0.4

    if not complexity_reason:
        direction = str(task.get("direction") or "").strip()
        if complexity > 0.7:
            complexity_reason = "high task breadth; assume complex"
        elif len(direction) > 380:
            complexity_reason = "direction text suggests multi-step scope"
        else:
            complexity_reason = "derived from provided context score"

    return {
        "complexity_score": complexity,
        "complexity_reason": complexity_reason,
        "decompose_required": decompose_required,
    }


def _smart_plan_micro_tasks(task: dict[str, Any], *, complexity_score: float, decompose_required: bool) -> list[dict[str, Any]]:
    direction = str(task.get("direction") or "")
    goals = _smart_split_by_goals(direction)
    if not goals:
        return []

    max_tasks = max(
        1,
        min(7, int(math.ceil(complexity_score / _SMART_WORKFLOW_TARGET_COMPLEXITY))),
    )
    if not decompose_required:
        max_tasks = 1

    if len(goals) > max_tasks:
        chunk_size = max(1, math.ceil(len(goals) / max_tasks))
        packed: list[str] = []
        for idx in range(0, len(goals), chunk_size):
            packed.append(" ".join(goals[idx : idx + chunk_size]).strip())
        goals = packed

    complexity = complexity_score if max_tasks == 0 else min(_SMART_WORKFLOW_TARGET_COMPLEXITY, complexity_score / max(1, len(goals)))
    complexity = round(max(0.01, complexity), 4)
    return [
        {
            "goal": goal,
            "inputs": {"goal": goal, "source": "decomposition"},
            "done_checks": [f"Output includes the result for: {goal}"],
            "fail_checks": [f"Output is incomplete for: {goal}"],
            "max_attempts": _SMART_MAX_RETRIES,
            "token_budget_in": 1200,
            "token_budget_out": 2200,
            "complexity": complexity,
        }
        for goal in goals
    ]


def _smart_model_name(env_name: str, default: str) -> str:
    model = str(execution_service.os.getenv(env_name, default)).strip()
    return model or default


def _smart_is_paid_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return False
    if "free" in normalized:
        return False
    return any(token in normalized for token in ("gpt", "claude", "openai", "anthropic", "gemini", "xai", "cohere", "mistral"))


def _smart_sanitize_micro_task(
    raw: dict[str, Any],
    *,
    complexity_cap: float,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    goal = str(raw.get("goal") or "").strip()
    if not goal:
        return None
    complexity = _smart_float(raw.get("complexity"), default=None)
    if complexity is None:
        complexity = complexity_cap
    complexity = min(max(0.01, complexity), complexity_cap)
    return {
        "goal": goal,
        "inputs": raw.get("inputs") or {"goal": goal},
        "done_checks": list(raw.get("done_checks") or [f"Output includes result for: {goal}"]),
        "fail_checks": list(raw.get("fail_checks") or [f"Output is incomplete for: {goal}"]),
        "max_attempts": _smart_int(raw.get("max_attempts"), default=_SMART_MAX_RETRIES),
        "token_budget_in": _smart_int(raw.get("token_budget_in"), default=1200),
        "token_budget_out": _smart_int(raw.get("token_budget_out"), default=2200),
        "complexity": complexity,
    }


def _smart_followups(raw: object) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        raw = _smart_parse_json_output(raw)
    if not isinstance(raw, dict):
        return []

    items = raw.get("followup_tasks")
    if not isinstance(items, list):
        return []

    followups: list[dict[str, Any]] = []
    for item in items:
        task = _smart_sanitize_micro_task(
            item if isinstance(item, dict) else {"goal": str(item or "")},
            complexity_cap=_SMART_FOLLOWUP_COMPLEXITY,
        )
        if task is not None:
            followups.append(task)
    return followups


def _smart_state(task: dict[str, Any]) -> dict[str, Any]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    state = ctx.get("smart_workflow_state")
    if isinstance(state, dict):
        return dict(state)
    return {}


def _smart_state_from_assessment(task: dict[str, Any]) -> dict[str, Any]:
    baseline = _smart_complexity_assessment(task)
    state = _smart_state(task)
    updated = {
        "task_id": str(task.get("id") or ""),
        "complexity_score": baseline.get("complexity_score", 1.0),
        "complexity_reason": baseline.get("complexity_reason", ""),
        "decompose_required": bool(baseline.get("decompose_required", True)),
        "attempts": _smart_int(state.get("attempts"), 0),
        "failure_signature": str(state.get("failure_signature") or ""),
        "accepted": bool(state.get("accepted")),
        "next_action": str(state.get("next_action") or "continue"),
    }

    return updated


def _smart_worker_prompt(microtask: dict[str, Any]) -> str:
    goal = str(microtask.get("goal") or "").strip()
    inputs = microtask.get("inputs") or {}
    return (
        "You are a fast executor. Return JSON only. "
        f"Goal: {goal}. Inputs: {json.dumps(inputs, sort_keys=True)[:2200]}. "
        "Complete only this micro-task and include {\"result\",\"done_checks\"}."
    )


def _smart_reviewer_prompt(microtask: dict[str, Any], worker_result: str) -> str:
    goal = str(microtask.get("goal") or "").strip()
    done_checks = microtask.get("done_checks") or []
    fail_checks = microtask.get("fail_checks") or []
    return (
        "Validate only this micro-task output. Return JSON only. "
        f"Goal: {goal}. done_checks={json.dumps(list(done_checks), sort_keys=True)[:2500]} "
        f"fail_checks={json.dumps(list(fail_checks), sort_keys=True)[:2500]} "
        f"worker_result={json.dumps(_smart_normalize_text(worker_result, 1600))}. "
        'Use format {"accepted":true/false,"gaps":[...],"followup_tasks":[{...}]}. '
    )


def _smart_parse_json_output(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return dict(parsed)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return dict(parsed)
    except Exception:
        return None
    return None


def _smart_record_event(
    *,
    task_id: str,
    task: dict[str, Any],
    stage: str,
    microtask_index: int,
    model: str,
    accepted: bool,
    attempts: int,
    elapsed_ms: int,
    metadata: dict[str, Any],
    status_code: int,
) -> None:
    execution_service.runtime_service.record_event(
        execution_service.RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-smart-workflow",
            method="RUN",
            status_code=status_code,
            runtime_ms=float(max(1, elapsed_ms)),
            idea_id="coherence-network-agent-pipeline",
            metadata=execution_service._compact_metadata(
                {
                    "tracking_kind": "agent_smart_workflow",
                    "task_id": task_id,
                    "task_type": str(task.get("task_type") or ""),
                    "stage": stage,
                    "microtask_index": microtask_index,
                    "microtask_model": str(model),
                    "accepted": bool(accepted),
                    "attempts": attempts,
                    **metadata,
                }
            ),
        )
    )

def _apply_value_attribution(
    task: dict[str, Any],
    *,
    output: str,
    actual_cost_usd: float | None,
) -> None:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    idea_id = str(ctx.get("idea_id") or "").strip() or None
    spec_id = str(ctx.get("spec_id") or "").strip() or None
    if not idea_id and not spec_id:
        return

    metrics = metrics_service.attribution_values_from_output(output)
    potential_value = metrics.get("estimated_value")
    estimated_cost = metrics.get("estimated_cost")
    actual_value = metrics.get("actual_value")
    confidence = metrics.get("confidence")

    if actual_cost_usd is not None:
        estimated_cost = actual_cost_usd if estimated_cost is None else estimated_cost

    if idea_id:
        try:
            execution_service.idea_service.update_idea(
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
            execution_service.spec_registry_service.update_spec(spec_id, update)
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
    execution_service._record_friction_event(
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
    execution_service._write_task_log(
        task_id,
        [
            f"[openrouter] status=200 elapsed_ms={elapsed_ms} request_id={request_id}",
            f"[usage] {usage_json}",
            "[output]",
            content,
        ],
    )
    execution_service._finish_task(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        status=execution_service.TaskStatus.COMPLETED,
        output=content,
        model_for_metrics=str(task.get("model") or model or "unknown"),
        elapsed_ms=elapsed_ms,
    )
    execution_service.runtime_service.record_event(
        execution_service.RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-execution-summary",
            method="RUN",
            status_code=200,
            runtime_ms=float(max(1, elapsed_ms)),
            idea_id="coherence-network-agent-pipeline",
            metadata=execution_service._compact_metadata(
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
                    "is_paid_provider": execution_service._task_route_is_paid(task),
                    "paid_provider_override": execution_service._paid_route_override_requested(task),
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
    execution_service._write_task_log(task_id, [msg])
    execution_service._finish_task(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        status=execution_service.TaskStatus.FAILED,
        output=msg,
        model_for_metrics=str(task.get("model") or model or "unknown"),
        elapsed_ms=elapsed_ms,
    )
    execution_service.runtime_service.record_event(
        execution_service.RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-execution-summary",
            method="RUN",
            status_code=500,
            runtime_ms=float(max(1, elapsed_ms)),
            idea_id="coherence-network-agent-pipeline",
            metadata=execution_service._compact_metadata(
                {
                    "tracking_kind": "agent_task_execution",
                    "task_id": task_id,
                    "model": str(task.get("model") or model or "unknown"),
                    "failure_reason": msg,
                    "actual_cost": actual_cost_usd,
                    "usage_json": usage_json,
                    "provider_request_id": request_id or "",
                    "is_paid_provider": execution_service._task_route_is_paid(task),
                    "paid_provider_override": execution_service._paid_route_override_requested(task),
                }
            ),
        )
    )
    return {"ok": False, "status": "failed", "elapsed_ms": elapsed_ms, "model": model}


def _handle_paid_route_guard(
    task_id: str,
    task: dict[str, Any],
    *,
    worker_id: str,
    route_is_paid: bool,
    force_paid_providers: bool,
) -> dict[str, Any] | None:
    if not route_is_paid:
        return None

    if not (
        execution_service._paid_providers_allowed()
        or force_paid_providers
        or execution_service._paid_route_override_requested(task)
    ):
        msg = "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled."
        execution_service._record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="paid_provider_blocked",
            endpoint="tool:agent-task-execution-summary",
            severity="high",
            notes=msg,
            energy_loss_estimate=0.0,
        )
        execution_service._write_task_log(task_id, [msg])
        execution_service._finish_task(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            status=execution_service.TaskStatus.FAILED,
            output=msg,
            model_for_metrics=str(task.get("model") or "unknown"),
            elapsed_ms=1,
        )
        return {"ok": False, "status": "failed", "error": "paid_provider_blocked"}

    if route_is_paid and not force_paid_providers:
        allowed, budget_msg = execution_service._check_paid_provider_window_budget(
            route_is_paid=True,
            task=task,
            task_id=task_id,
        )
        if not allowed:
            execution_service._write_task_log(task_id, [budget_msg or "Paid-provider window budget blocked"])
            execution_service._finish_task(
                task_id=task_id,
                task=task,
                worker_id=worker_id,
                status=execution_service.TaskStatus.FAILED,
                output=budget_msg or "Paid-provider window budget blocked",
                model_for_metrics=str(task.get("model") or "unknown"),
                elapsed_ms=1,
            )
            return {
                "ok": False,
                "status": "failed",
                "error": "paid_provider_window_budget_exceeded",
            }

    return None


def _finalize_with_retry(
    *,
    task_id: str,
    task: dict[str, Any],
    result: dict[str, Any],
    worker_id: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    retry_depth: int,
) -> dict[str, Any]:
    refreshed = execution_service.agent_service.get_task(task_id) or task
    return retry_service.record_failure_hits_and_retry(
        task_id=task_id,
        task=refreshed,
        result=result,
        worker_id=worker_id,
        retry_depth=retry_depth,
        env_retry_max=execution_service.os.getenv("AGENT_TASK_RETRY_MAX"),
        pending_status=execution_service.TaskStatus.PENDING,
        update_task=execution_service.agent_service.update_task,
        execute_again=execute_task,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )


def _resolve_execution_plan(
    task: dict[str, Any],
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> tuple[str, str, dict[str, float | None]]:
    default_model = execution_service.os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free").strip() or "openrouter/free"
    model = execution_service._resolve_openrouter_model(task, default_model)
    prompt = execution_service._resolve_prompt(task)
    cost_budget = metrics_service.resolve_cost_controls(task, max_cost_usd, estimated_cost_usd, cost_slack_ratio)
    return model, prompt, cost_budget


def _handle_empty_prompt_failure(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    retry_depth: int,
) -> dict[str, Any]:
    execution_service._record_friction_event(
        task_id=task_id,
        task=task,
        stage="agent_execution",
        block_type="validation_failure",
        endpoint="tool:agent-task-execution-summary",
        severity="high",
        notes="Execution blocked: empty direction.",
        energy_loss_estimate=0.0,
    )
    failure = _complete_failure(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        model=model,
        elapsed_ms=1,
        msg="Empty direction",
    )
    return _finalize_with_retry(
        task_id=task_id,
        task=task,
        result=failure,
        worker_id=worker_id,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=retry_depth,
    )


def _handle_openrouter_success(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    elapsed_ms: int,
    result: dict[str, Any],
    cost_budget: dict[str, float | None],
) -> dict[str, Any]:
    content = str(result.get("content") or "")
    usage_json = str(result.get("usage_json") or "{}")
    request_id = str(result.get("provider_request_id") or "")
    actual_cost_usd = float(result.get("actual_cost_usd") or execution_service._runtime_cost_usd(elapsed_ms))
    output_metrics = metrics_service.attribution_values_from_output(content)

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


def _handle_openrouter_failure(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    elapsed_ms: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    msg = str(result.get("error") or "Execution failed (OpenRouter)")
    execution_service._record_friction_event(
        task_id=task_id,
        task=task,
        stage="agent_execution",
        block_type="tool_failure",
        endpoint="tool:agent-task-execution-summary",
        severity="high",
        notes=msg,
        energy_loss_estimate=execution_service._runtime_cost_usd(elapsed_ms),
    )
    return _complete_failure(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        model=model,
        elapsed_ms=elapsed_ms,
        msg=msg,
        actual_cost_usd=execution_service._runtime_cost_usd(elapsed_ms),
    )


def _run_execution(
    *,
    task_id: str,
    task: dict[str, Any],
    route_is_paid: bool,
    worker_id: str,
    model: str,
    prompt: str,
    cost_budget: dict[str, float | None],
) -> dict[str, Any]:
    started = execution_service.time.perf_counter()
    execution_service._write_task_log(task_id, [f"[execute] worker_id={worker_id} model={model}", f"[prompt]\n{prompt}"])

    try:
        result = execution_service._run_openrouter(
            task_id=task_id,
            model=model,
            route_is_paid=route_is_paid,
            prompt=prompt,
            started_perf=started,
            cost_budget=cost_budget,
        )
        elapsed_ms = int(result.get("elapsed_ms") or 1)
        if result.get("ok") is True:
            return _handle_openrouter_success(
                task_id=task_id,
                task=task,
                worker_id=worker_id,
                model=model,
                elapsed_ms=elapsed_ms,
                result=result,
                cost_budget=cost_budget,
            )

        return _handle_openrouter_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            result=result,
        )
    except Exception as exc:
        elapsed_ms = max(1, int(round((execution_service.time.perf_counter() - started) * 1000)))
        msg = f"Execution failed: {exc}"
        execution_service._record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="unexpected_execution_exception",
            endpoint="tool:agent-task-execution-summary",
            severity="critical",
            notes=msg,
            energy_loss_estimate=execution_service._runtime_cost_usd(elapsed_ms),
        )
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            msg=msg,
            actual_cost_usd=execution_service._runtime_cost_usd(elapsed_ms),
        )


def _smart_signature_from_failure(*parts: object) -> str:
    return _smart_signature(" | ".join(_smart_normalize_text(part) for part in parts))


def _smart_router_prompt(task: dict[str, Any]) -> str:
    direction = _smart_normalize_text(task.get("direction") or "", 900)
    return (
        "You are the router for the smart-workflow. "
        "Given one task direction, return compact JSON only with: "
        '{"complexity_score":0.0-1.0, "complexity_reason":"brief", "decompose_required":true|false}. '
        "Use complexity_score=1.0 by default for unknowns or unclear multi-step tasks. "
        f"direction={json.dumps(direction)}"
    )


def _smart_update_state(
    task_id: str,
    task: dict[str, Any],
    state: dict[str, Any],
    *,
    worker_id: str,
) -> None:
    execution_service.agent_service.update_task(
        task_id,
        context={
            "smart_workflow_state": {
                "task_id": str(state.get("task_id") or task_id),
                "complexity_score": float(state.get("complexity_score") or 1.0),
                "attempts": int(state.get("attempts") or 0),
                "failure_signature": str(state.get("failure_signature") or ""),
                "accepted": bool(state.get("accepted")),
                "next_action": str(state.get("next_action") or ""),
            }
        },
        worker_id=worker_id,
    )


def _smart_paid_call_allowed(
    task_id: str,
    task: dict[str, Any],
    model: str,
    route_is_paid: bool,
    force_paid_providers: bool,
    *,
    stage: str,
) -> tuple[bool, str]:
    call_paid = bool(route_is_paid or _smart_is_paid_model(model))
    if not call_paid:
        return True, ""

    if execution_service._paid_providers_allowed() or force_paid_providers or execution_service._paid_route_override_requested(task):
        allowed, msg = execution_service._check_paid_provider_window_budget(
            route_is_paid=True,
            task=task,
            task_id=task_id,
        )
        if allowed:
            return True, ""
        return False, msg or f"Smart {stage} call blocked by paid-provider window policy."

    return False, f"Smart {stage} call blocked: paid model requires AGENT_ALLOW_PAID_PROVIDERS."


def _smart_run_smart_model(
    *,
    task_id: str,
    task: dict[str, Any],
    stage: str,
    microtask_index: int,
    model: str,
    prompt: str,
    worker_id: str,
    route_is_paid: bool,
    force_paid_providers: bool,
    attempts: int,
    cost_budget: dict[str, float | None],
) -> dict[str, Any]:
    allowed, block_msg = _smart_paid_call_allowed(
        task_id=task_id,
        task=task,
        model=model,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        stage=stage,
    )
    if not allowed:
        execution_service._record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="provider_access_blocked",
            endpoint="tool:agent-task-smart-workflow",
            severity="high",
            notes=block_msg,
            energy_loss_estimate=0.0,
        )
        return {
            "ok": False,
            "elapsed_ms": 1,
            "content": block_msg,
            "error": block_msg,
        }

    started = execution_service.time.perf_counter()
    execution_service._write_task_log(
        task_id,
        [
            f"[smart:{stage}] microtask={microtask_index} model={model}",
            f"[prompt]{_smart_normalize_text(prompt, 900)}",
        ],
    )
    try:
        result = execution_service._run_openrouter(
            task_id=task_id,
            model=model,
            route_is_paid=bool(route_is_paid or _smart_is_paid_model(model)),
            prompt=prompt,
            started_perf=started,
            cost_budget=cost_budget,
        )
        elapsed_ms = int(result.get("elapsed_ms") or 1)
        _smart_record_event(
            task_id=task_id,
            task=task,
            stage=stage,
            microtask_index=microtask_index,
            model=model,
            accepted=bool(result.get("ok")),
            attempts=attempts,
            elapsed_ms=elapsed_ms,
            metadata={"model": model, "result_ok": bool(result.get("ok"))},
            status_code=200 if result.get("ok") else 500,
        )
        return result
    except Exception as exc:
        elapsed_ms = max(1, int(round((execution_service.time.perf_counter() - started) * 1000)))
        msg = f"Smart model execution failed: {exc}"
        execution_service._record_friction_event(
            task_id=task_id,
            task=task,
            stage="agent_execution",
            block_type="unexpected_execution_exception",
            endpoint="tool:agent-task-smart-workflow",
            severity="high",
            notes=msg,
            energy_loss_estimate=execution_service._runtime_cost_usd(elapsed_ms),
        )
        return {
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "content": msg,
            "error": msg,
        }


def _smart_assess_complexity(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    route_is_paid: bool,
    force_paid_providers: bool,
    cost_budget: dict[str, float | None],
    default_model: str,
    existing_state: dict[str, Any],
) -> dict[str, Any]:
    existing = dict(existing_state)
    has_score = "complexity_score" in _smart_context(task)
    if has_score:
        return existing

    router_model = _smart_model_name(_SMART_ROUTER_MODEL, default_model)
    router_prompt = _smart_router_prompt(task)
    result = _smart_run_smart_model(
        task_id=task_id,
        task=task,
        stage="router",
        microtask_index=0,
        model=router_model,
        prompt=router_prompt,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        attempts=1,
        cost_budget=cost_budget,
    )
    parsed = _smart_parse_json_output(str(result.get("content") or ""))
    if not isinstance(parsed, dict):
        existing["next_action"] = "router_fallback"
        existing["complexity_reason"] = str(existing.get("complexity_reason") or "smart_router_parse_failed")
        return existing

    complexity = _smart_float(parsed.get("complexity_score"), default=float(existing.get("complexity_score", 1.0)))
    complexity = max(0.0, min(1.0, float(complexity)))
    existing["complexity_score"] = complexity
    existing["complexity_reason"] = str(parsed.get("complexity_reason") or "smart_router_assessed")
    existing["decompose_required"] = _smart_truthy(parsed.get("decompose_required")) if parsed.get("decompose_required") is not None else existing.get("decompose_required", complexity > 0.4)
    existing["next_action"] = "router_complete" if result.get("ok") else "router_fallback"
    return existing


def _smart_fail_block(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    state: dict[str, Any],
    msg: str,
    elapsed_ms: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state["next_action"] = "blocked"
    state["accepted"] = False
    _smart_record_event(
        task_id=task_id,
        task=task,
        stage="blocked",
        microtask_index=int(state.get("microtask_index") or 0),
        model=str(model),
        accepted=False,
        attempts=int(state.get("microtask_attempts") or 0),
        elapsed_ms=elapsed_ms,
        metadata={"reason": "smart_workflow_blocked", "message": msg},
        status_code=500,
    )
    failure = _complete_failure(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        model=model,
        elapsed_ms=elapsed_ms,
        msg=msg,
    )
    return failure, state


def _smart_execute_task_workflow(
    task_id: str,
    *,
    task: dict[str, Any],
    route_is_paid: bool,
    worker_id: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> dict[str, Any]:
    default_model = execution_service.os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free").strip() or "openrouter/free"
    worker_model = _smart_model_name(_SMART_WORKER_MODEL, default_model)
    reviewer_model = _smart_model_name(_SMART_REVIEWER_MODEL, default_model)
    cost_budget = metrics_service.resolve_cost_controls(task, max_cost_usd, estimated_cost_usd, cost_slack_ratio)

    state = _smart_state_from_assessment(task)
    state["attempts"] = int(state.get("attempts") or 0) + 1
    state["failure_signature"] = ""
    state["next_action"] = "planning"
    state = _smart_assess_complexity(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        cost_budget=cost_budget,
        default_model=worker_model,
        existing_state=state,
    )
    micro_tasks = _smart_plan_micro_tasks(
        task,
        complexity_score=float(state.get("complexity_score") or _SMART_WORKFLOW_TARGET_COMPLEXITY),
        decompose_required=bool(state.get("decompose_required")),
    )
    _smart_update_state(task_id, task, state, worker_id=worker_id)

    if not micro_tasks:
        failure, state = _smart_fail_block(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=worker_model,
            state=state,
            msg="Smart workflow blocked: no micro-tasks could be derived from task direction.",
            elapsed_ms=1,
        )
        _smart_update_state(task_id, task, state, worker_id=worker_id)
        return failure

    completed: list[dict[str, Any]] = []
    microtask_index = 0
    while microtask_index < len(micro_tasks):
        microtask = micro_tasks[microtask_index]
        if not isinstance(microtask, dict):
            microtask = {"goal": str(microtask or "")}
            micro_tasks[microtask_index] = microtask
        goal = str(microtask.get("goal") or "").strip()
        if not goal:
            failure, state = _smart_fail_block(
                task_id=task_id,
                task=task,
                worker_id=worker_id,
                model=worker_model,
                state=state,
                msg="Smart workflow blocked: micro-task has empty goal.",
                elapsed_ms=1,
            )
            _smart_update_state(task_id, task, state, worker_id=worker_id)
            return failure

        attempt_limit = max(1, int(microtask.get("max_attempts") or _SMART_MAX_RETRIES))
        microtask_attempts = int(state.get("microtask_attempts") or 0)
        repeat_count = 0
        last_signature = str(state.get("failure_signature") or "")

        while True:
            state["microtask_index"] = microtask_index
            microtask_attempts += 1
            state["microtask_attempts"] = microtask_attempts
            state["next_action"] = "executing"
            _smart_update_state(task_id, task, state, worker_id=worker_id)
            if microtask_attempts > attempt_limit or microtask_attempts > _SMART_REPEAT_LIMIT + 1:
                failure, state = _smart_fail_block(
                    task_id=task_id,
                    task=task,
                    worker_id=worker_id,
                    model=worker_model,
                    state=state,
                    msg=f"Smart workflow blocked: micro-task '{goal}' exceeded attempts ({attempt_limit}).",
                    elapsed_ms=1,
                )
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                return failure

            worker_prompt = _smart_worker_prompt(microtask)
            worker_result = _smart_run_smart_model(
                task_id=task_id,
                task=task,
                stage="worker",
                microtask_index=microtask_index,
                model=worker_model,
                prompt=worker_prompt,
                worker_id=worker_id,
                route_is_paid=route_is_paid,
                force_paid_providers=force_paid_providers,
                attempts=microtask_attempts,
                cost_budget=cost_budget,
            )
            if not worker_result.get("ok"):
                signature = _smart_signature_from_failure(goal, "worker", worker_result.get("error") or worker_result.get("content"))
                if signature == last_signature:
                    repeat_count += 1
                else:
                    last_signature = signature
                    repeat_count = 1
                state["failure_signature"] = signature
                state["next_action"] = "worker_retry"
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                if repeat_count >= _SMART_REPEAT_LIMIT or microtask_attempts >= _SMART_REPEAT_LIMIT:
                    failure, state = _smart_fail_block(
                        task_id=task_id,
                        task=task,
                        worker_id=worker_id,
                        model=worker_model,
                        state=state,
                        msg=f"Smart workflow blocked: repeated worker failure for '{goal}'.",
                        elapsed_ms=int(worker_result.get("elapsed_ms") or 1),
                    )
                    _smart_update_state(task_id, task, state, worker_id=worker_id)
                    return failure
                continue

            worker_payload = _smart_parse_json_output(str(worker_result.get("content") or ""))
            if not isinstance(worker_payload, dict):
                signature = _smart_signature_from_failure(goal, "worker_payload", "invalid_json")
                if signature == last_signature:
                    repeat_count += 1
                else:
                    last_signature = signature
                    repeat_count = 1
                state["failure_signature"] = signature
                state["next_action"] = "review_blocked"
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                if repeat_count >= _SMART_REPEAT_LIMIT or microtask_attempts >= _SMART_REPEAT_LIMIT:
                    failure, state = _smart_fail_block(
                        task_id=task_id,
                        task=task,
                        worker_id=worker_id,
                        model=worker_model,
                        state=state,
                        msg=f"Smart workflow blocked: worker output not parseable for '{goal}'.",
                        elapsed_ms=int(worker_result.get("elapsed_ms") or 1),
                    )
                    _smart_update_state(task_id, task, state, worker_id=worker_id)
                    return failure
                continue

            worker_result_text = str(worker_payload.get("result") or "")
            review_prompt = _smart_reviewer_prompt(microtask, str(worker_result.get("result") or ""))
            review_result = _smart_run_smart_model(
                task_id=task_id,
                task=task,
                stage="reviewer",
                microtask_index=microtask_index,
                model=reviewer_model,
                prompt=review_prompt,
                worker_id=worker_id,
                route_is_paid=route_is_paid,
                force_paid_providers=force_paid_providers,
                attempts=microtask_attempts,
                cost_budget=cost_budget,
            )
            if not review_result.get("ok"):
                signature = _smart_signature_from_failure(goal, "reviewer", review_result.get("error") or review_result.get("content"))
                if signature == last_signature:
                    repeat_count += 1
                else:
                    last_signature = signature
                    repeat_count = 1
                state["failure_signature"] = signature
                state["next_action"] = "review_retry"
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                if repeat_count >= _SMART_REPEAT_LIMIT or microtask_attempts >= _SMART_REPEAT_LIMIT:
                    failure, state = _smart_fail_block(
                        task_id=task_id,
                        task=task,
                        worker_id=worker_id,
                        model=reviewer_model,
                        state=state,
                        msg=f"Smart workflow blocked: reviewer failure for '{goal}'.",
                        elapsed_ms=int(review_result.get("elapsed_ms") or 1),
                    )
                    _smart_update_state(task_id, task, state, worker_id=worker_id)
                    return failure
                continue

            review_payload = _smart_parse_json_output(str(review_result.get("content") or ""))
            if not isinstance(review_payload, dict):
                signature = _smart_signature_from_failure(goal, "reviewer_payload", "invalid_json")
                if signature == last_signature:
                    repeat_count += 1
                else:
                    last_signature = signature
                    repeat_count = 1
                state["failure_signature"] = signature
                state["next_action"] = "review_retry"
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                if repeat_count >= _SMART_REPEAT_LIMIT or microtask_attempts >= _SMART_REPEAT_LIMIT:
                    failure, state = _smart_fail_block(
                        task_id=task_id,
                        task=task,
                        worker_id=worker_id,
                        model=reviewer_model,
                        state=state,
                        msg=f"Smart workflow blocked: reviewer output invalid for '{goal}'.",
                        elapsed_ms=int(review_result.get("elapsed_ms") or 1),
                    )
                    _smart_update_state(task_id, task, state, worker_id=worker_id)
                    return failure
                continue

            accepted = bool(review_payload.get("accepted"))
            followups = _smart_followups(review_payload)
            if accepted and worker_result_text:
                completed.append(
                    {
                        "goal": goal,
                        "result": worker_result_text,
                        "done_checks": list(worker_payload.get("done_checks") or microtask.get("done_checks", [])),
                    }
                )
                micro_tasks[microtask_index] = dict(microtask, result=worker_result_text, accepted=True)
                microtask_index += 1
                state["failure_signature"] = ""
                state["next_action"] = "accepted"
                state["microtask_attempts"] = 0
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                break

            signature = _smart_signature_from_failure(
                goal,
                "reviewer_reject",
                json.dumps(review_payload.get("gaps") or [], sort_keys=True),
            )
            if signature == last_signature:
                repeat_count += 1
            else:
                last_signature = signature
                repeat_count = 1
            state["failure_signature"] = signature
            if not followups:
                failure, state = _smart_fail_block(
                    task_id=task_id,
                    task=task,
                    worker_id=worker_id,
                    model=reviewer_model,
                    state=state,
                    msg=f"Smart workflow blocked: reviewer rejected '{goal}' with no follow-up.",
                    elapsed_ms=int(review_result.get("elapsed_ms") or 1),
                )
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                return failure

            if repeat_count >= _SMART_REPEAT_LIMIT or microtask_attempts >= _SMART_REPEAT_LIMIT:
                failure, state = _smart_fail_block(
                    task_id=task_id,
                    task=task,
                    worker_id=worker_id,
                    model=reviewer_model,
                    state=state,
                    msg=f"Smart workflow blocked: repeated rejection for '{goal}'.",
                    elapsed_ms=int(review_result.get("elapsed_ms") or 1),
                )
                _smart_update_state(task_id, task, state, worker_id=worker_id)
                return failure

            micro_tasks[microtask_index : microtask_index + 1] = followups
            state["next_action"] = "followup_created"
            state["microtask_attempts"] = 0
            _smart_update_state(task_id, task, state, worker_id=worker_id)
            break

    state["accepted"] = True
    state["next_action"] = "completed"
    state["failure_signature"] = ""
    _smart_update_state(task_id, task, state, worker_id=worker_id)

    content = json.dumps(
        {
            "smart_workflow": True,
            "attempts": int(state.get("attempts") or 0),
            "completed": len(completed),
            "results": completed,
        },
        sort_keys=True,
    )
    return _complete_success(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        model=worker_model,
        elapsed_ms=1,
        content=content,
        usage_json="{}",
        request_id="smart-workflow",
        output_metrics={
            "estimated_value": None,
            "actual_value": None,
            "confidence": 1.0,
            "estimated_cost": cost_budget.get("estimated_cost_usd"),
        },
        actual_cost_usd=execution_service._runtime_cost_usd(1),
        max_cost_usd=cost_budget.get("max_cost_usd"),
        cost_slack_ratio=cost_budget.get("cost_slack_ratio"),
    )


def execute_task(
    task_id: str,
    *,
    worker_id: str = "openclaw-worker:server",
    force_paid_providers: bool = False,
    max_cost_usd: float | None = None,
    estimated_cost_usd: float | None = None,
    cost_slack_ratio: float | None = None,
    _retry_depth: int = 0,
) -> dict[str, Any]:
    """Execute a task using OpenRouter (free model by default)."""
    task = execution_service.agent_service.get_task(task_id)
    if task is None:
        return {"ok": False, "error": "task_not_found"}
    claimed, claim_error = execution_service._claim_task(task_id, worker_id)
    if not claimed:
        return {"ok": False, "error": f"claim_failed:{claim_error}"}
    task = execution_service.agent_service.get_task(task_id) or {}
    route_is_paid = execution_service._task_route_is_paid(task)
    payment_error = _handle_paid_route_guard(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
    )
    if payment_error is not None:
        return _finalize_with_retry(
            task_id=task_id,
            task=task,
            result=payment_error,
            worker_id=worker_id,
            force_paid_providers=force_paid_providers,
            max_cost_usd=max_cost_usd,
            estimated_cost_usd=estimated_cost_usd,
            cost_slack_ratio=cost_slack_ratio,
            retry_depth=_retry_depth,
        )

    if _smart_env_enabled():
        result = _smart_execute_task_workflow(
            task_id=task_id,
            task=task,
            route_is_paid=route_is_paid,
            worker_id=worker_id,
            force_paid_providers=force_paid_providers,
            max_cost_usd=max_cost_usd,
            estimated_cost_usd=estimated_cost_usd,
            cost_slack_ratio=cost_slack_ratio,
        )
        continuation_service.maybe_continue_after_finish(
            previous_task_id=task_id,
            result=result,
            worker_id=worker_id,
            force_paid_providers=force_paid_providers,
            max_cost_usd=max_cost_usd,
            estimated_cost_usd=estimated_cost_usd,
            cost_slack_ratio=cost_slack_ratio,
            execute_callback=execute_task,
        )
        return result

    model, prompt, cost_budget = _resolve_execution_plan(
        task,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    if not prompt:
        return _handle_empty_prompt_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            force_paid_providers=force_paid_providers,
            max_cost_usd=max_cost_usd,
            estimated_cost_usd=estimated_cost_usd,
            cost_slack_ratio=cost_slack_ratio,
            retry_depth=_retry_depth,
        )
    result = _run_execution(
        task_id=task_id,
        task=task,
        route_is_paid=route_is_paid,
        worker_id=worker_id,
        model=model,
        prompt=prompt,
        cost_budget=cost_budget,
    )
    finalized = _finalize_with_retry(
        task_id=task_id,
        task=task,
        result=result,
        worker_id=worker_id,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=_retry_depth,
    )
    continuation_service.maybe_continue_after_finish(
        previous_task_id=task_id,
        result=finalized,
        worker_id=worker_id,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        execute_callback=execute_task,
    )
    return finalized
