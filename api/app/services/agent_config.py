"""Agent configuration: model routing, command templates, and executor selection."""

import os
import re
from typing import Optional

from app.models.agent import TaskType

# Model fallback chain: local → cloud → claude (see docs/MODEL-ROUTING.md)
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openrouter/free")
_OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_CLOUD_MODEL", "openrouter/free")
_CLAUDE_MODEL = os.environ.get("CLAUDE_FALLBACK_MODEL", "openrouter/free")

# Cursor CLI models (when context.executor == "cursor") — see docs/CURSOR-CLI.md
_CURSOR_MODEL_DEFAULT = os.environ.get("CURSOR_CLI_MODEL", "openrouter/free")
_CURSOR_MODEL_REVIEW = os.environ.get("CURSOR_CLI_REVIEW_MODEL", "openrouter/free")

# Routing: local first; use model_override in context for cloud/claude
ROUTING: dict[TaskType, tuple[str, str]] = {
    TaskType.SPEC: (f"openrouter/free", "openrouter"),
    TaskType.TEST: (f"openrouter/free", "openrouter"),
    TaskType.IMPL: (f"openrouter/free", "openrouter"),
    TaskType.REVIEW: (f"openrouter/free", "openrouter"),
    TaskType.HEAL: (f"openrouter/free", "openrouter"),
}

# Subagent mapping: task_type → Claude Code --agent name (from .claude/agents/)
# HEAL uses default tools, no subagent
AGENT_BY_TASK_TYPE: dict[TaskType, Optional[str]] = {
    TaskType.SPEC: "product-manager",
    TaskType.TEST: "qa-engineer",
    TaskType.IMPL: "dev-engineer",
    TaskType.REVIEW: "reviewer",
    TaskType.HEAL: None,
}

# Command templates: {{direction}} placeholder; uses --agent when subagent defined
_COMMAND_LOCAL_AGENT = 'aider --model ollama/glm-4.7-flash:q8_0 --map-tokens 8192 --reasoning-effort high --yes "{{direction}}"'
_COMMAND_HEAL = 'aider --model ollama/glm-4.7-flash:q8_0 --map-tokens 8192 --reasoning-effort high --yes "{{direction}}"'

# Cursor CLI model mapping by task type
_CURSOR_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _CURSOR_MODEL_DEFAULT,
    TaskType.TEST: _CURSOR_MODEL_DEFAULT,
    TaskType.IMPL: _CURSOR_MODEL_DEFAULT,
    TaskType.REVIEW: _CURSOR_MODEL_REVIEW,
    TaskType.HEAL: _CURSOR_MODEL_REVIEW,
}


def _command_template(task_type: TaskType) -> str:
    """Get command template for task type using local agent or heal."""
    agent = AGENT_BY_TASK_TYPE.get(task_type)
    if agent:
        return _COMMAND_LOCAL_AGENT.replace("{{agent}}", agent)
    return _COMMAND_HEAL


def _cursor_command_template(task_type: TaskType) -> str:
    """Cursor CLI: agent "{{direction}}" --model X. Escapes direction for shell."""
    model = _CURSOR_MODEL_BY_TYPE[task_type]
    return f'agent "{{{{direction}}}}" --model {model}'


COMMAND_TEMPLATES: dict[TaskType, str] = {
    TaskType.SPEC: _command_template(TaskType.SPEC),
    TaskType.TEST: _command_template(TaskType.TEST),
    TaskType.IMPL: _command_template(TaskType.IMPL),
    TaskType.REVIEW: _command_template(TaskType.REVIEW),
    TaskType.HEAL: _command_template(TaskType.HEAL),
}


def build_command(direction: str, task_type: TaskType, executor: str = "claude") -> str:
    """Build command for task. executor: 'claude' (default) or 'cursor'."""
    if executor == "cursor":
        template = _cursor_command_template(task_type)
    else:
        template = COMMAND_TEMPLATES[task_type]
    # Escape direction for shell (double-quoted string)
    escaped = direction.replace("\\", "\\\\").replace('"', '\\"')
    return template.replace("{{direction}}", escaped)


def get_model_and_tier(task_type: TaskType, executor: str = "claude") -> tuple[str, str]:
    """Get model and tier for task type and executor."""
    if executor == "cursor":
        model = f"cursor/{_CURSOR_MODEL_BY_TYPE[task_type]}"
        tier = "cursor"
    else:
        model, tier = ROUTING[task_type]
    return model, tier


def apply_model_override(command: str, model_override: str) -> str:
    """Apply model override to command string."""
    return re.sub(r"--model\s+\S+", f"--model {model_override}", command)
