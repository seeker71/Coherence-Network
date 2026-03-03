"""Preflight helpers for agent execution orchestration."""

from __future__ import annotations

from typing import Any

from app.services import agent_execution_completion as completion_service
from app.services import agent_execution_metrics as metrics_service
from app.services import agent_execution_service as execution_service


def resolve_execution_plan(
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


def handle_empty_prompt_failure(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
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
    return completion_service.complete_failure(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        model=model,
        elapsed_ms=1,
        msg="Empty direction",
    )
