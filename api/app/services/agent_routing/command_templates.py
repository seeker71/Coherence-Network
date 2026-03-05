"""Per-executor command templates with {{direction}} and {{model}} placeholders."""

from __future__ import annotations

import os

from app.models.agent import TaskType

from app.services.agent_routing.model_config import (
    enforce_openrouter_free_model,
    normalize_model_name,
)
from app.services.agent_routing.routing_config import (
    CLAUDE_CODE_MODEL_BY_TYPE,
    CURSOR_MODEL_BY_TYPE,
    GEMINI_MODEL_BY_TYPE,
    OPENCLAW_MODEL_BY_TYPE,
    ROUTING,
)


def cursor_command_template(task_type: TaskType) -> str:
    model = CURSOR_MODEL_BY_TYPE[task_type]
    template = (
        os.environ.get("CURSOR_COMMAND_TEMPLATE", "").strip()
        or 'agent --trust --print --output-format json "{{direction}}" --model {{model}} --sandbox disabled'
    )
    if "{{direction}}" not in template:
        template = template.strip() + ' "{{direction}}"'
    return template.replace("{{model}}", model)


def _resolve_codex_default_model(task_type: TaskType) -> str:
    resolved_model = normalize_model_name(OPENCLAW_MODEL_BY_TYPE[task_type])
    if not resolved_model:
        return "gpt-5.3-codex"
    lower_model = resolved_model.lower()
    if lower_model.startswith("openrouter/") or lower_model.endswith("/free") or "openrouter/free" in lower_model:
        return "gpt-5.3-codex"
    return resolved_model


def codex_command_template(task_type: TaskType) -> str:
    model = _resolve_codex_default_model(task_type)
    template = (
        os.environ.get("CODEX_COMMAND_TEMPLATE", "").strip()
        or os.environ.get("OPENCLAW_COMMAND_TEMPLATE", "").strip()
        or 'codex exec "{{direction}}" --model {{model}} --skip-git-repo-check --json'
    )
    if "{{direction}}" not in template:
        template = template.strip() + ' "{{direction}}"'
    return template.replace("{{model}}", model)


def openclaw_command_template(task_type: TaskType) -> str:
    return codex_command_template(task_type)


def openrouter_command_template(task_type: TaskType) -> str:
    model, _tier = ROUTING[task_type]
    resolved_model = enforce_openrouter_free_model(model)
    template = (
        os.environ.get("OPENROUTER_EXEC_COMMAND_TEMPLATE", "").strip()
        or 'openrouter-exec "{{direction}}" --model {{model}}'
    )
    if "{{direction}}" not in template:
        template = template.strip() + ' "{{direction}}"'
    return template.replace("{{model}}", resolved_model)


def gemini_command_template(task_type: TaskType) -> str:
    model = GEMINI_MODEL_BY_TYPE[task_type]
    template = (
        os.environ.get("GEMINI_COMMAND_TEMPLATE", "").strip()
        or 'gemini -p "{{direction}}" --model {{model}} --sandbox=false'
    )
    if "{{direction}}" not in template:
        template = template.strip() + ' "{{direction}}"'
    return template.replace("{{model}}", model)


def claude_command_template(task_type: TaskType) -> str:
    """Claude Code CLI template: headless -p mode with --dangerously-skip-permissions.

    Uses --output-format json for modelUsage/cost observability.
    Uses --max-budget-usd from CLAUDE_CODE_MAX_BUDGET_USD env (default 2.00).
    """
    model = CLAUDE_CODE_MODEL_BY_TYPE[task_type]
    template = os.environ.get("CLAUDE_CODE_COMMAND_TEMPLATE", "")
    if template:
        if "{{direction}}" not in template:
            template = template.strip() + ' "{{direction}}"'
        return template.replace("{{model}}", model)
    model_flag = f" --model {model}" if model else ""
    budget = os.environ.get("CLAUDE_CODE_MAX_BUDGET_USD", "2.00")
    return (
        'claude -p "{{direction}}"'
        + model_flag
        + " --dangerously-skip-permissions"
        + " --output-format json"
        + f" --max-budget-usd {budget}"
    )


def resolve_codex_default_model(task_type: TaskType) -> str:
    """Public alias for route_for_executor and callers that need codex model resolution."""
    return _resolve_codex_default_model(task_type)
