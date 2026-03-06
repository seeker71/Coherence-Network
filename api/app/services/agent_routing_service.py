"""Deterministic agent routing and provider classification utilities."""

from __future__ import annotations

import re
from typing import Any

from app.models.agent import TaskType

from app.services.agent_routing import (
    CLAUDE_CODE_MODEL_BY_TYPE,
    CODEX_MODEL_BY_TYPE,
    CURSOR_MODEL_BY_TYPE,
    EXECUTOR_VALUES,
    GEMINI_MODEL_BY_TYPE,
    OPENCLAW_MODEL_BY_TYPE,
    REPO_SCOPE_PATTERNS,
    ROUTING,
    cheap_executor_default,
    classify_provider,
    claude_command_template,
    codex_command_template,
    cursor_command_template,
    enforce_openrouter_free_model,
    escalation_executor_default,
    executor_available,
    executor_binary_name,
    executor_policy_enabled,
    first_available_executor,
    gemini_command_template,
    int_env,
    is_paid_model,
    is_repo_scoped_question,
    normalize_executor,
    normalize_model_name,
    open_question_executor_default,
    openrouter_command_template,
    repo_question_executor_default,
    resolve_codex_default_model,
)


def route_for_executor(
    task_type: TaskType, executor: str, default_command_template: str
) -> dict[str, Any]:
    normalized = normalize_executor(executor, default="claude")
    if normalized == "cursor":
        model = f"cursor/{CURSOR_MODEL_BY_TYPE[task_type]}"
        template = cursor_command_template(task_type)
        tier = "cursor"
    elif normalized == "codex":
        resolved_model = resolve_codex_default_model(task_type)
        model = f"codex/{resolved_model}"
        template = codex_command_template(task_type)
        tier = "codex"
    elif normalized == "openrouter":
        resolved_model, _provider_tier = ROUTING[task_type]
        model = enforce_openrouter_free_model(resolved_model)
        template = openrouter_command_template(task_type)
        tier = "openrouter"
    elif normalized == "gemini":
        model = f"gemini/{GEMINI_MODEL_BY_TYPE[task_type]}"
        template = gemini_command_template(task_type)
        tier = "gemini"
    elif normalized == "claude":
        cc_model = CLAUDE_CODE_MODEL_BY_TYPE[task_type]
        model = f"claude/{cc_model}" if cc_model else "claude/default"
        template = claude_command_template(task_type)
        tier = "claude"
    else:
        model, tier = ROUTING[task_type]
        template = default_command_template

    provider, billing_provider, is_paid_provider = classify_provider(
        executor=normalized,
        model=model,
        command=template,
        worker_id=None,
    )
    return {
        "task_type": task_type.value,
        "model": model,
        "command_template": template,
        "tier": tier,
        "executor": normalized,
        "provider": provider,
        "billing_provider": billing_provider,
        "is_paid_provider": is_paid_provider,
    }


def apply_model_override(command: str, override: str) -> tuple[str, str]:
    cleaned = normalize_model_name(override.strip())
    if not cleaned:
        return command, ""
    applied = cleaned
    if command.lstrip().startswith("openrouter-exec "):
        applied = enforce_openrouter_free_model(cleaned)
    if command.lstrip().startswith("codex ") and cleaned.startswith("openai/"):
        _, _, codex_model = cleaned.partition("/")
        if codex_model.strip():
            applied = codex_model.strip()
    if re.search(r"--model\s+\S+", command):
        return re.sub(r"--model\s+\S+", f"--model {applied}", command), applied
    return command.rstrip() + f" --model {applied}", applied


def normalize_open_responses_model(model: str) -> str:
    cleaned = str(model or "").strip()
    if "/" in cleaned:
        prefix, _, suffix = cleaned.partition("/")
        if prefix in EXECUTOR_VALUES and suffix.strip():
            return suffix.strip()
    return cleaned


def build_normalized_response_call(
    *,
    task_id: str,
    executor: str,
    provider: str,
    model: str,
    direction: str,
) -> dict[str, Any]:
    """Build a provider-agnostic Open Responses-compatible request envelope."""
    normalized_model = normalize_open_responses_model(model)
    prompt = str(direction or "").strip()
    return {
        "task_id": str(task_id or "").strip(),
        "executor": normalize_executor(executor, default="claude"),
        "provider": str(provider or "").strip().lower() or "unknown",
        "model": normalized_model,
        "request_schema": "open_responses_v1",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
    }


# Re-export for backward compatibility; all symbols above also available via agent_routing package.
__all__ = [
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
    "openrouter_command_template",
    "gemini_command_template",
    "claude_command_template",
    "route_for_executor",
    "apply_model_override",
    "normalize_open_responses_model",
    "build_normalized_response_call",
    "classify_provider",
    "is_paid_model",
]
