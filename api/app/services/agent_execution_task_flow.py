"""Agent execution orchestration helpers."""

from __future__ import annotations

from typing import Any

from app.models.spec_registry import SpecRegistryUpdate
from app.services import agent_execution_completion as completion_service
from app.services import agent_execution_hooks as hooks_service
from app.services import agent_execution_metrics as metrics_service
from app.services import agent_execution_preflight as preflight_service
from app.services import agent_execution_retry as retry_service
from app.services import agent_execution_service as execution_service
from app.services import agent_task_continuation_service as continuation_service


def _emit_lifecycle_event(
    event: str,
    *,
    task_id: str,
    task: dict[str, Any],
    **extra: Any,
) -> None:
    try:
        hooks_service.dispatch_lifecycle_event(
            event,
            task_id=task_id,
            task=task,
            **extra,
        )
    except Exception:
        # Lifecycle hooks are observability helpers and must not break execution.
        return


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
    return completion_service.complete_failure(
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

    return completion_service.complete_success(
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
    return completion_service.complete_failure(
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
        return completion_service.complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            msg=msg,
            actual_cost_usd=execution_service._runtime_cost_usd(elapsed_ms),
        )


def _finalize_and_emit(
    *,
    task_id: str,
    task: dict[str, Any],
    result: dict[str, Any],
    worker_id: str,
    route_is_paid: bool,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    retry_depth: int,
    model: str = "",
) -> dict[str, Any]:
    finalized = _finalize_with_retry(
        task_id=task_id,
        task=task,
        result=result,
        worker_id=worker_id,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=retry_depth,
    )
    refreshed = execution_service.agent_service.get_task(task_id) or task
    payload: dict[str, Any] = {
        "task_id": task_id,
        "task": refreshed,
        "worker_id": worker_id,
        "route_is_paid": route_is_paid,
        "ok": bool(finalized.get("ok")),
        "task_status": refreshed.get("status") or finalized.get("status") or "",
        "error": str(finalized.get("error") or ""),
    }
    if model:
        payload["model"] = model
    _emit_lifecycle_event("finalized", **payload)
    return finalized


def _maybe_finalize_paid_guard(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    route_is_paid: bool,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    retry_depth: int,
) -> dict[str, Any] | None:
    payment_error = _handle_paid_route_guard(
        task_id=task_id, task=task, worker_id=worker_id, route_is_paid=route_is_paid, force_paid_providers=force_paid_providers
    )
    if payment_error is None:
        return None
    _emit_lifecycle_event(
        "guard_blocked",
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        error=str(payment_error.get("error") or payment_error.get("status") or "guard_blocked"),
        reason="paid_provider_guard",
    )
    return _finalize_and_emit(
        task_id=task_id,
        task=task,
        result=payment_error,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=retry_depth,
    )


def _maybe_finalize_empty_prompt(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    route_is_paid: bool,
    model: str,
    prompt: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    retry_depth: int,
) -> dict[str, Any] | None:
    if prompt:
        return None
    _emit_lifecycle_event("validation_failed", task_id=task_id, task=task, worker_id=worker_id, route_is_paid=route_is_paid, reason="empty_direction")
    prompt_failure = preflight_service.handle_empty_prompt_failure(task_id=task_id, task=task, worker_id=worker_id, model=model)
    return _finalize_and_emit(
        task_id=task_id,
        task=task,
        result=prompt_failure,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=retry_depth,
        model=model,
    )


def _claim_and_load_task(task_id: str, worker_id: str) -> tuple[dict[str, Any] | None, str | None]:
    task = execution_service.agent_service.get_task(task_id)
    if task is None:
        return None, "task_not_found"
    claimed, claim_error = execution_service._claim_task(task_id, worker_id)
    if not claimed:
        return None, f"claim_failed:{claim_error}"
    task = execution_service.agent_service.get_task(task_id) or {}
    _emit_lifecycle_event("claimed", task_id=task_id, task=task, worker_id=worker_id)
    return task, None


def execute_task(
    task_id: str,
    *,
    worker_id: str = "codex-worker:server",
    force_paid_providers: bool = False,
    max_cost_usd: float | None = None,
    estimated_cost_usd: float | None = None,
    cost_slack_ratio: float | None = None,
    _retry_depth: int = 0,
) -> dict[str, Any]:
    """Execute a task using OpenRouter (free model by default)."""
    task, claim_error = _claim_and_load_task(task_id, worker_id)
    if claim_error:
        return {"ok": False, "error": claim_error}
    assert task is not None

    route_is_paid = execution_service._task_route_is_paid(task)
    guarded = _maybe_finalize_paid_guard(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=_retry_depth,
    )
    if guarded:
        return guarded

    model, prompt, cost_budget = preflight_service.resolve_execution_plan(
        task,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    empty_prompt = _maybe_finalize_empty_prompt(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        model=model,
        prompt=prompt,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=_retry_depth,
    )
    if empty_prompt:
        return empty_prompt

    _emit_lifecycle_event("execution_started", task_id=task_id, task=task, worker_id=worker_id, route_is_paid=route_is_paid, model=model)
    result = _run_execution(
        task_id=task_id,
        task=task,
        route_is_paid=route_is_paid,
        worker_id=worker_id,
        model=model,
        prompt=prompt,
        cost_budget=cost_budget,
    )
    finalized = _finalize_and_emit(
        task_id=task_id,
        task=task,
        result=result,
        worker_id=worker_id,
        route_is_paid=route_is_paid,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
        retry_depth=_retry_depth,
        model=model,
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
