"""Task completion helpers for agent execution flow."""

from __future__ import annotations

from typing import Any

from app.services import agent_execution_service as execution_service


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
