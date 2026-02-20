"""Agent execution orchestration helpers."""

from __future__ import annotations

import threading
from typing import Any

from app.models.spec_registry import SpecRegistryUpdate
from app.services import agent_execution_metrics as metrics_service
from app.services import agent_execution_retry as retry_service
from app.services import agent_execution_service as execution_service


def _task_target_ids(task: dict[str, Any]) -> tuple[str | None, str | None]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    idea_id = str(ctx.get("idea_id") or "").strip() or None
    spec_id = str(ctx.get("spec_id") or "").strip() or None
    return idea_id, spec_id


def _continuous_autofill_enabled() -> bool:
    configured = execution_service.os.getenv("AGENT_CONTINUOUS_AUTOFILL")
    if configured is not None and str(configured).strip():
        return execution_service._truthy(str(configured))
    return bool(str(execution_service.os.getenv("RAILWAY_ENVIRONMENT") or "").strip())


def _continuous_autofill_autorun_enabled() -> bool:
    configured = execution_service.os.getenv("AGENT_CONTINUOUS_AUTOFILL_AUTORUN")
    if configured is not None and str(configured).strip():
        return execution_service._truthy(str(configured))
    return bool(str(execution_service.os.getenv("RAILWAY_ENVIRONMENT") or "").strip())


def _open_task_count() -> int:
    total = 0
    for status in (
        execution_service.TaskStatus.PENDING,
        execution_service.TaskStatus.RUNNING,
        execution_service.TaskStatus.NEEDS_DECISION,
    ):
        _, count = execution_service.agent_service.list_tasks(status=status, limit=1, offset=0)
        total += int(count)
    return total


def _extract_created_task_ids(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return []

    ids: list[str] = []
    seen: set[str] = set()

    def _append(candidate: Any) -> None:
        task_id = str(candidate or "").strip()
        if not task_id or task_id in seen:
            return
        seen.add(task_id)
        ids.append(task_id)

    created = payload.get("created_task")
    if isinstance(created, dict):
        _append(created.get("id"))

    created_many = payload.get("created_tasks")
    if isinstance(created_many, list):
        for row in created_many:
            if not isinstance(row, dict):
                continue
            _append(row.get("task_id") or row.get("id"))

    return ids


def _seed_next_tasks() -> tuple[list[str], str]:
    from app.services import inventory_service

    spec_report = inventory_service.sync_spec_implementation_gap_tasks(create_task=True, limit=80)
    spec_ids = _extract_created_task_ids(spec_report)
    if spec_ids:
        return spec_ids, "spec_implementation_gap"

    roi_report = inventory_service.next_highest_roi_task_from_answered_questions(create_task=True)
    roi_ids = _extract_created_task_ids(roi_report)
    if roi_ids:
        return roi_ids, "idea_answered_question_roi"

    flow_report = inventory_service.next_unblock_task_from_flow(
        create_task=True,
        runtime_window_seconds=86400,
    )
    flow_ids = _extract_created_task_ids(flow_report)
    if flow_ids:
        return flow_ids, "idea_unblock_flow"
    return [], "none"


def _schedule_followup_execution(
    *,
    task_id: str,
    worker_id: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> None:
    def _runner() -> None:
        try:
            execute_task(
                task_id,
                worker_id=worker_id,
                force_paid_providers=force_paid_providers,
                max_cost_usd=max_cost_usd,
                estimated_cost_usd=estimated_cost_usd,
                cost_slack_ratio=cost_slack_ratio,
            )
        except Exception:
            return

    thread = threading.Thread(target=_runner, name=f"agent-followup-{task_id}", daemon=True)
    thread.start()


def _maybe_continue_after_finish(
    *,
    previous_task_id: str,
    result: dict[str, Any],
    worker_id: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
) -> None:
    if not _continuous_autofill_enabled():
        return

    final_status = str(result.get("status") or "").strip().lower()
    if final_status not in {"completed", "failed"}:
        return

    try:
        open_count = _open_task_count()
        if open_count > 0:
            return

        created_ids, source = _seed_next_tasks()
        if not created_ids:
            return

        if _continuous_autofill_autorun_enabled():
            next_task_id = created_ids[0]
            _schedule_followup_execution(
                task_id=next_task_id,
                worker_id=f"{worker_id}:autofill",
                force_paid_providers=force_paid_providers,
                max_cost_usd=max_cost_usd,
                estimated_cost_usd=estimated_cost_usd,
                cost_slack_ratio=cost_slack_ratio,
            )

        execution_service.runtime_service.record_event(
            execution_service.RuntimeEventCreate(
                source="worker",
                endpoint="tool:agent-task-continuation",
                method="RUN",
                status_code=200,
                runtime_ms=1.0,
                idea_id="coherence-network-agent-pipeline",
                metadata=execution_service._compact_metadata(
                    {
                        "tracking_kind": "agent_task_continuation",
                        "task_id": previous_task_id,
                        "source": source,
                        "created_count": len(created_ids),
                        "created_task_ids": ",".join(created_ids[:10]),
                        "auto_run": _continuous_autofill_autorun_enabled(),
                    }
                ),
            )
        )
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
    _maybe_continue_after_finish(
        previous_task_id=task_id,
        result=finalized,
        worker_id=worker_id,
        force_paid_providers=force_paid_providers,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    return finalized
