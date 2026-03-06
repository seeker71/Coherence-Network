"""Task-type → model/tier routing (see docs/MODEL-ROUTING.md). All from config (model_routing.json); uniform across providers."""

from __future__ import annotations

from app.models.agent import TaskType

from app.services.agent_routing.model_routing_loader import (
    get_model_for_executor_and_task_type,
    get_openrouter_model_for_task_type,
)


def _model_by_type(executor: str) -> dict[TaskType, str]:
    return {tt: get_model_for_executor_and_task_type(executor, tt) for tt in TaskType}


# Only used when executor is openrouter: (model, tier) per task type.
ROUTING: dict[TaskType, tuple[str, str]] = {
    TaskType.SPEC: (get_openrouter_model_for_task_type(TaskType.SPEC), "openrouter"),
    TaskType.TEST: (get_openrouter_model_for_task_type(TaskType.TEST), "openrouter"),
    TaskType.IMPL: (get_openrouter_model_for_task_type(TaskType.IMPL), "openrouter"),
    TaskType.REVIEW: (get_openrouter_model_for_task_type(TaskType.REVIEW), "openrouter"),
    TaskType.HEAL: (get_openrouter_model_for_task_type(TaskType.HEAL), "openrouter"),
}

CURSOR_MODEL_BY_TYPE: dict[TaskType, str] = _model_by_type("cursor")
OPENCLAW_MODEL_BY_TYPE: dict[TaskType, str] = _model_by_type("codex")
CODEX_MODEL_BY_TYPE = OPENCLAW_MODEL_BY_TYPE
GEMINI_MODEL_BY_TYPE: dict[TaskType, str] = _model_by_type("gemini")
CLAUDE_CODE_MODEL_BY_TYPE: dict[TaskType, str] = _model_by_type("claude")
