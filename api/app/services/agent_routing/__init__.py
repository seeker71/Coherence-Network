"""Deterministic agent routing and provider classification (reusable submodules)."""

from app.services.agent_routing.command_templates import (
    claude_command_template,
    codex_command_template,
    cursor_command_template,
    gemini_command_template,
    openclaw_command_template,
    openrouter_command_template,
    resolve_codex_default_model,
)
from app.services.agent_routing.executor_config import (
    EXECUTOR_VALUES,
    REPO_SCOPE_PATTERNS,
    cheap_executor_default,
    escalation_executor_default,
    executor_available,
    executor_binary_name,
    executor_policy_enabled,
    first_available_executor,
    int_env,
    is_repo_scoped_question,
    normalize_executor,
    open_question_executor_default,
    repo_question_executor_default,
)
from app.services.agent_routing.model_config import (
    DEFAULT_MODEL_ALIAS_MAP,
    enforce_openrouter_free_model,
    normalize_model_name,
)
from app.services.agent_routing.provider_classification import (
    classify_provider,
    is_paid_model,
)
from app.services.agent_routing.routing_config import (
    CLAUDE_CODE_MODEL_BY_TYPE,
    CODEX_MODEL_BY_TYPE,
    CURSOR_MODEL_BY_TYPE,
    GEMINI_MODEL_BY_TYPE,
    OPENCLAW_MODEL_BY_TYPE,
    ROUTING,
)

__all__ = [
    "DEFAULT_MODEL_ALIAS_MAP",
    "ROUTING",
    "CURSOR_MODEL_BY_TYPE",
    "OPENCLAW_MODEL_BY_TYPE",
    "CODEX_MODEL_BY_TYPE",
    "GEMINI_MODEL_BY_TYPE",
    "CLAUDE_CODE_MODEL_BY_TYPE",
    "REPO_SCOPE_PATTERNS",
    "EXECUTOR_VALUES",
    "int_env",
    "executor_policy_enabled",
    "normalize_executor",
    "cheap_executor_default",
    "escalation_executor_default",
    "executor_binary_name",
    "executor_available",
    "first_available_executor",
    "is_repo_scoped_question",
    "repo_question_executor_default",
    "open_question_executor_default",
    "normalize_model_name",
    "enforce_openrouter_free_model",
    "cursor_command_template",
    "codex_command_template",
    "openclaw_command_template",
    "openrouter_command_template",
    "gemini_command_template",
    "claude_command_template",
    "resolve_codex_default_model",
    "classify_provider",
    "is_paid_model",
]
