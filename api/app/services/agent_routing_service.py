"""Deterministic agent routing and provider classification utilities."""

from __future__ import annotations

import os
import re
import shutil
from typing import Any

from app.models.agent import TaskType

# Routing defaults (see docs/MODEL-ROUTING.md)
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openrouter/free")
_OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_CLOUD_MODEL", "openrouter/free")
_CLAUDE_MODEL = os.environ.get("CLAUDE_FALLBACK_MODEL", "openrouter/free")

_CURSOR_MODEL_DEFAULT = os.environ.get("CURSOR_CLI_MODEL", "openrouter/free")
_CURSOR_MODEL_REVIEW = os.environ.get("CURSOR_CLI_REVIEW_MODEL", "openrouter/free")

DEFAULT_MODEL_ALIAS_MAP = (
    "gpt-5.3-codex-spark:gpt-5.3-codex,"
    "gtp-5.3-codex-spark:gpt-5.3-codex,"
    "gtp-5.3-codex:gpt-5.3-codex"
)


def _parse_model_alias_map(raw: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for pair in str(raw or "").split(","):
        item = pair.strip()
        if not item or ":" not in item:
            continue
        source, target = item.split(":", 1)
        source_key = source.strip().lower()
        target_value = target.strip()
        if source_key and target_value:
            aliases[source_key] = target_value
    return aliases


def _model_alias_map() -> dict[str, str]:
    aliases = _parse_model_alias_map(DEFAULT_MODEL_ALIAS_MAP)
    raw = os.environ.get("AGENT_MODEL_ALIAS_MAP", "")
    if raw:
        aliases.update(_parse_model_alias_map(str(raw)))
    return aliases


def normalize_model_name(model: str) -> str:
    cleaned = str(model or "").strip()
    if not cleaned:
        return ""
    aliases = _model_alias_map()
    direct = aliases.get(cleaned.lower())
    if direct:
        return direct
    if "/" in cleaned:
        prefix, _, suffix = cleaned.partition("/")
        mapped_suffix = aliases.get(suffix.strip().lower())
        if mapped_suffix:
            return f"{prefix}/{mapped_suffix}"
    return cleaned


_OPENCLAW_MODEL_DEFAULT = normalize_model_name(os.environ.get("OPENCLAW_MODEL", "gpt-5-codex"))
_OPENCLAW_MODEL_REVIEW = normalize_model_name(os.environ.get("OPENCLAW_REVIEW_MODEL", _OPENCLAW_MODEL_DEFAULT))

ROUTING: dict[TaskType, tuple[str, str]] = {
    TaskType.SPEC: (_OLLAMA_MODEL, "openrouter"),
    TaskType.TEST: (_OLLAMA_CLOUD_MODEL, "openrouter"),
    TaskType.IMPL: (_OLLAMA_CLOUD_MODEL, "openrouter"),
    TaskType.REVIEW: (_CLAUDE_MODEL, "openrouter"),
    TaskType.HEAL: (_CLAUDE_MODEL, "openrouter"),
}

CURSOR_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _CURSOR_MODEL_DEFAULT,
    TaskType.TEST: _CURSOR_MODEL_DEFAULT,
    TaskType.IMPL: _CURSOR_MODEL_DEFAULT,
    TaskType.REVIEW: _CURSOR_MODEL_REVIEW,
    TaskType.HEAL: _CURSOR_MODEL_REVIEW,
}

OPENCLAW_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _OPENCLAW_MODEL_DEFAULT,
    TaskType.TEST: _OPENCLAW_MODEL_DEFAULT,
    TaskType.IMPL: _OPENCLAW_MODEL_DEFAULT,
    TaskType.REVIEW: _OPENCLAW_MODEL_REVIEW,
    TaskType.HEAL: _OPENCLAW_MODEL_REVIEW,
}

_CANONICAL_EXECUTOR_VALUES = ("claude", "cursor", "openclaw")
_EXECUTOR_ALIASES = {"clawwork": "openclaw"}
EXECUTOR_VALUES = _CANONICAL_EXECUTOR_VALUES + tuple(_EXECUTOR_ALIASES.keys())

REPO_SCOPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bthis repo\b", re.IGNORECASE),
    re.compile(r"\bthis repository\b", re.IGNORECASE),
    re.compile(r"\bcodebase\b", re.IGNORECASE),
    re.compile(r"\bin (?:the )?repo\b", re.IGNORECASE),
    re.compile(r"\bAGENTS\.md\b", re.IGNORECASE),
    re.compile(r"\bCLAUDE\.md\b", re.IGNORECASE),
    re.compile(r"\bdocs/[A-Za-z0-9_.\-\/]+\b", re.IGNORECASE),
    re.compile(r"\bapi/[A-Za-z0-9_.\-\/]+\b", re.IGNORECASE),
    re.compile(r"\bweb/[A-Za-z0-9_.\-\/]+\b", re.IGNORECASE),
    re.compile(r"`[^`]+\.(?:py|ts|tsx|js|jsx|md|json|toml|yaml|yml)`", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_.\-]+\.(?:py|ts|tsx|js|jsx|md|json|toml|yaml|yml)\b", re.IGNORECASE),
)


def int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return max(0, value)


def executor_policy_enabled() -> bool:
    raw = os.environ.get("AGENT_EXECUTOR_POLICY_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def normalize_executor(value: str | None, default: str = "claude") -> str:
    candidate = (value or "").strip().lower()
    candidate = _EXECUTOR_ALIASES.get(candidate, candidate)
    if candidate in _CANONICAL_EXECUTOR_VALUES:
        return candidate
    return default


def cheap_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_CHEAP_DEFAULT")
    if configured:
        return normalize_executor(configured, default="cursor")
    fallback = os.environ.get("AGENT_EXECUTOR_DEFAULT", "cursor")
    return normalize_executor(fallback, default="cursor")


def escalation_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_ESCALATE_TO")
    if configured:
        return normalize_executor(configured, default="claude")
    cheap = cheap_executor_default()
    return "claude" if cheap != "claude" else "openclaw"


def executor_binary_name(executor: str) -> str:
    normalized = normalize_executor(executor, default=executor.strip().lower())
    if normalized == "cursor":
        return "agent"
    if normalized == "openclaw":
        for candidate in ("openclaw", "codex"):
            if shutil.which(candidate):
                return candidate
        configured = os.environ.get("OPENCLAW_EXECUTABLE")
        return configured.strip() if configured else "openclaw"
    return "aider"


def executor_available(executor: str) -> bool:
    return shutil.which(executor_binary_name(executor)) is not None


def first_available_executor(preferred: list[str]) -> str:
    for executor in preferred:
        candidate = normalize_executor(executor, default="")
        if candidate and executor_available(candidate):
            return candidate
    return normalize_executor(os.environ.get("AGENT_EXECUTOR_DEFAULT"), default="claude")


def is_repo_scoped_question(direction: str, context: dict[str, Any]) -> bool:
    scope_hint = str(context.get("question_scope") or context.get("scope") or "").strip().lower()
    if scope_hint in {"repo", "repository", "codebase"}:
        return True
    if scope_hint in {"open", "general"}:
        return False

    text = direction.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in REPO_SCOPE_PATTERNS)


def repo_question_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_REPO_DEFAULT")
    if configured:
        return normalize_executor(configured, default="cursor")
    return "cursor"


def open_question_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT")
    if configured:
        return normalize_executor(configured, default="openclaw")
    return "openclaw"


def cursor_command_template(task_type: TaskType) -> str:
    model = CURSOR_MODEL_BY_TYPE[task_type]
    return f'agent "{{{{direction}}}}" --model {model}'


def openclaw_command_template(task_type: TaskType) -> str:
    model = normalize_model_name(OPENCLAW_MODEL_BY_TYPE[task_type])
    template = os.environ.get(
        "OPENCLAW_COMMAND_TEMPLATE",
        'codex exec "{{direction}}" --model {{model}} --reasoning-effort high --worktree --skip-git-repo-check --json',
    )
    if "{{direction}}" not in template:
        template = template.strip() + ' "{{direction}}"'
    return template.replace("{{model}}", model)


def route_for_executor(task_type: TaskType, executor: str, default_command_template: str) -> dict[str, Any]:
    normalized = normalize_executor(executor, default="claude")
    if normalized == "cursor":
        model = f"cursor/{CURSOR_MODEL_BY_TYPE[task_type]}"
        template = cursor_command_template(task_type)
        tier = "cursor"
    elif normalized == "openclaw":
        resolved_model = normalize_model_name(OPENCLAW_MODEL_BY_TYPE[task_type])
        model = f"openclaw/{resolved_model}"
        template = openclaw_command_template(task_type)
        tier = "openclaw"
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
    if re.search(r"--model\s+\S+", command):
        return re.sub(r"--model\s+\S+", f"--model {cleaned}", command), cleaned
    return command.rstrip() + f" --model {cleaned}", cleaned


def classify_provider(*, executor: str, model: str, command: str, worker_id: str | None) -> tuple[str, str, bool]:
    normalized_executor = normalize_executor(executor, default=(executor or "").strip().lower())
    lower_model = (model or "").strip().lower()
    lower_command = (command or "").strip().lower()
    normalized_worker = (worker_id or "").strip().lower()
    command_model_match = re.search(r"--model\s+([^\s]+)", lower_command)
    command_model = command_model_match.group(1).strip().lower() if command_model_match else ""

    provider = "unknown"
    if normalized_worker == "openai-codex" or normalized_worker.startswith("openai-codex:"):
        provider = "openai-codex"
    elif "openrouter" in command_model or "openrouter" in lower_model:
        provider = "openrouter"
    elif command_model.startswith("openai/") or command_model.startswith(("gpt", "o1", "o3", "o4")):
        provider = "openai-codex" if "codex" in command_model else "openai"
    elif "codex" in lower_model:
        provider = "openai-codex"
    elif lower_model.startswith("openai/") or lower_model.startswith(("gpt", "o1", "o3", "o4")):
        provider = "openai"
    elif lower_command.startswith("codex "):
        provider = "openai-codex"
    elif normalized_executor == "openclaw":
        provider = "openclaw"
    elif normalized_executor == "cursor":
        provider = "cursor"
    elif normalized_executor in {"claude", "aider"}:
        provider = "claude"

    billing_provider = provider
    is_paid_provider = is_paid_model(provider=provider, model=lower_model, command_model=command_model)
    return provider, billing_provider, is_paid_provider


def is_paid_model(*, provider: str, model: str, command_model: str) -> bool:
    if provider == "openrouter":
        ref = command_model or model
        if "openrouter/free" in ref or ref.endswith("/free"):
            return False
        return True
    if provider in {"openai", "openai-codex", "claude", "cursor"}:
        return True
    return False
