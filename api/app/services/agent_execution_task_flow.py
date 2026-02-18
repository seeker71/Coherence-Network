"""Agent execution orchestration helpers."""

from __future__ import annotations

from typing import Any

from app.models.spec_registry import SpecRegistryUpdate
from app.services import agent_execution_service as execution_service


def _resolve_cost_controls(
    task: dict[str, Any],
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> dict[str, float | None]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    context_max_cost = execution_service._normalize_positive_float(ctx.get("max_cost_usd")) or execution_service._normalize_positive_float(
        ctx.get("max_cost")
    )
    context_estimated_cost = execution_service._normalize_positive_float(ctx.get("estimated_cost_usd")) or execution_service._normalize_positive_float(
        ctx.get("estimated_cost")
    )
    context_slack = execution_service._normalize_ratio(ctx.get("cost_slack_ratio"), default=1.25)

    env_max_cost = execution_service._normalize_positive_float(execution_service.os.getenv("AGENT_TASK_MAX_COST_USD"))
    env_estimated_cost = execution_service._normalize_positive_float(execution_service.os.getenv("AGENT_TASK_ESTIMATED_COST_USD"))
    env_slack = execution_service._normalize_ratio(execution_service.os.getenv("AGENT_TASK_COST_SLACK_RATIO"), default=1.25)

    resolved_max_cost = execution_service._normalize_positive_float(max_cost_usd) or context_max_cost or env_max_cost
    resolved_estimated_cost = (
        execution_service._normalize_positive_float(estimated_cost_usd)
        or context_estimated_cost
        or env_estimated_cost
    )
    resolved_slack = execution_service._normalize_ratio(cost_slack_ratio, default=context_slack or env_slack or 1.25)

    if resolved_max_cost is None and resolved_estimated_cost is not None:
        resolved_max_cost = max(resolved_estimated_cost * resolved_slack, 0.0001)

    return {
        "max_cost_usd": resolved_max_cost,
        "estimated_cost_usd": resolved_estimated_cost,
        "cost_slack_ratio": resolved_slack,
    }


def _safe_parse_output_metrics(output: str) -> dict[str, Any]:
    try:
        parsed = execution_service.json.loads(output)
    except execution_service.json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


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
        "actual_cost": _extract_output_metric(parsed, ("actual_cost", "actual_cost_usd", "cost_actual")),
    }


def _task_target_ids(task: dict[str, Any]) -> tuple[str | None, str | None]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    idea_id = str(ctx.get("idea_id") or "").strip() or None
    spec_id = str(ctx.get("spec_id") or "").strip() or None
    return idea_id, spec_id


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
        return {"ok": False, "error": "paid_provider_blocked"}

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
            return {"ok": False, "error": "paid_provider_window_budget_exceeded"}

    return None


def _resolve_execution_plan(
    task: dict[str, Any],
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> tuple[str, str, dict[str, float | None]]:
    default_model = execution_service.os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free").strip() or "openrouter/free"
    model = execution_service._resolve_openrouter_model(task, default_model)
    prompt = execution_service._resolve_prompt(task)
    cost_budget = _resolve_cost_controls(task, max_cost_usd, estimated_cost_usd, cost_slack_ratio)
    return model, prompt, cost_budget


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


def execute_task(
    task_id: str,
    *,
    worker_id: str = "openclaw-worker:server",
    force_paid_providers: bool = False,
    max_cost_usd: float | None = None,
    estimated_cost_usd: float | None = None,
    cost_slack_ratio: float | None = None,
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
        return payment_error

    model, prompt, cost_budget = _resolve_execution_plan(
        task,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )

    if not prompt:
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
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=1,
            msg="Empty direction",
        )

    return _run_execution(
        task_id=task_id,
        task=task,
        route_is_paid=route_is_paid,
        worker_id=worker_id,
        model=model,
        prompt=prompt,
        cost_budget=cost_budget,
    )
