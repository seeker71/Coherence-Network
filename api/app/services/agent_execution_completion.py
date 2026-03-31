"""Task completion helpers for agent execution flow."""

from __future__ import annotations

import logging
from typing import Any

from app.services import agent_execution_service as execution_service
from app.services import grounded_measurement_service

_log = logging.getLogger(__name__)


def complete_success(
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
            idea_id=execution_service.agent_service.resolve_runtime_idea_id_for_task(task),
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
    # Record grounded A/B measurement if this task is part of a variant test
    try:
        runtime_cost_est = execution_service.runtime_service.estimate_runtime_cost(float(elapsed_ms))
        grounded_measurement_service.record_grounded_measurement(
            task_id=task_id,
            task=task,
            status="completed",
            elapsed_ms=elapsed_ms,
            actual_cost_usd=actual_cost_usd,
            runtime_cost_estimate=runtime_cost_est,
            output_metrics=output_metrics,
        )
    except Exception:
        _log.debug("grounded measurement recording skipped", exc_info=True)

    # Record model outcome for data-driven slot selection
    try:
        from app.services.agent_routing.model_routing_loader import record_model_outcome

        _task_type = str(task.get("task_type") or task.get("type") or "unknown")
        _executor = str(task.get("executor") or "unknown")  # TODO: pass executor explicitly if available
        _model = str(task.get("model") or model or "unknown")
        _token_cost = float(actual_cost_usd) if actual_cost_usd is not None else 1.0  # TODO: use real token count when available
        _duration_s = elapsed_ms / 1000.0

        record_model_outcome(
            task_type=_task_type,
            executor=_executor,
            model=_model,
            success=True,
            token_cost=_token_cost,
            duration_seconds=_duration_s,
        )
    except Exception:
        _log.debug("model outcome recording skipped (success)", exc_info=True)

    return {"ok": True, "status": "completed", "elapsed_ms": elapsed_ms, "model": model}


def complete_failure(
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
            idea_id=execution_service.agent_service.resolve_runtime_idea_id_for_task(task),
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
    # Record grounded A/B measurement if this task is part of a variant test
    try:
        runtime_cost_est = execution_service.runtime_service.estimate_runtime_cost(float(elapsed_ms))
        grounded_measurement_service.record_grounded_measurement(
            task_id=task_id,
            task=task,
            status="failed",
            elapsed_ms=elapsed_ms,
            actual_cost_usd=actual_cost_usd,
            runtime_cost_estimate=runtime_cost_est,
        )
    except Exception:
        _log.debug("grounded measurement recording skipped", exc_info=True)

    # Record model outcome for data-driven slot selection
    try:
        from app.services.agent_routing.model_routing_loader import record_model_outcome

        _task_type = str(task.get("task_type") or task.get("type") or "unknown")
        _executor = str(task.get("executor") or "unknown")  # TODO: pass executor explicitly if available
        _model = str(task.get("model") or model or "unknown")
        _token_cost = float(actual_cost_usd) if actual_cost_usd is not None else 1.0  # TODO: use real token count when available
        _duration_s = elapsed_ms / 1000.0

        record_model_outcome(
            task_type=_task_type,
            executor=_executor,
            model=_model,
            success=False,
            token_cost=_token_cost,
            duration_seconds=_duration_s,
        )
    except Exception:
        _log.debug("model outcome recording skipped (failure)", exc_info=True)

    return {"ok": False, "status": "failed", "elapsed_ms": elapsed_ms, "model": model}
