"""Executor normalization, availability, and scope-based defaults. Canonical list from config only; no aliasing."""

from __future__ import annotations

import os
import re
import shutil
from typing import Any

from app.config_loader import get_bool, get_str
from app.services.agent_routing.executor_routing_loader import get_executors as _loader_executors


def _canonical_executors() -> tuple[str, ...]:
    executors = _loader_executors()
    if executors:
        return executors
    raw = os.environ.get("AGENT_EXECUTORS", "").strip()
    if not raw:
        return ()
    return tuple(s.strip().lower() for s in raw.split(",") if s.strip())


_CANONICAL_EXECUTOR_VALUES = _canonical_executors()
EXECUTOR_VALUES = _CANONICAL_EXECUTOR_VALUES

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
    if os.environ.get("AGENT_EXECUTOR_POLICY_ENABLED") is not None:
        return os.environ.get("AGENT_EXECUTOR_POLICY_ENABLED", "").strip().lower() not in {"0", "false", "no", "off"}
    return get_bool("executor", "policy_enabled", True)


def normalize_executor(value: str | None, default: str = "claude") -> str:
    candidate = (value or "").strip().lower()
    if candidate in _CANONICAL_EXECUTOR_VALUES:
        return candidate
    return default


def cheap_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_CHEAP_DEFAULT") or get_str("executor", "cheap_default")
    if configured:
        return normalize_executor(configured, default="cursor")
    fallback = os.environ.get("AGENT_EXECUTOR_DEFAULT") or get_str("executor", "default") or "cursor"
    return normalize_executor(fallback, default="cursor")


def escalation_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_ESCALATE_TO") or get_str("executor", "escalate_to")
    if configured:
        return normalize_executor(configured, default="claude")
    cheap = cheap_executor_default()
    if cheap == "gemini":
        return "gemini"
    return "claude" if cheap != "claude" else "gemini"


def executor_binary_name(executor: str) -> str:
    normalized = normalize_executor(executor, default=executor.strip().lower())
    if normalized == "cursor":
        return "agent"
    if normalized == "codex":
        configured = (
            os.environ.get("CODEX_EXECUTABLE")
            or os.environ.get("OPENCLAW_EXECUTABLE")
            or get_str("executor", "codex_executable")
        )
        if configured and str(configured).strip():
            return str(configured).strip()
        return "codex"
    if normalized == "gemini":
        configured = os.environ.get("GEMINI_EXECUTABLE") or get_str("executor", "gemini_executable")
        if configured and str(configured).strip():
            return str(configured).strip()
        return "gemini"
    if normalized == "openrouter":
        return "server-executor"
    return "claude"


def executor_available(executor: str) -> bool:
    if normalize_executor(executor, default=executor.strip().lower()) == "openrouter":
        return True
    return shutil.which(executor_binary_name(executor)) is not None


def first_available_executor(preferred: list[str]) -> str:
    for executor in preferred:
        candidate = normalize_executor(executor, default="")
        if candidate and executor_available(candidate):
            return candidate
    default_raw = os.environ.get("AGENT_EXECUTOR_DEFAULT") or get_str("executor", "default")
    return normalize_executor(default_raw, default="claude")


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
    configured = os.environ.get("AGENT_EXECUTOR_REPO_DEFAULT") or get_str("executor", "repo_default")
    if configured:
        return normalize_executor(configured, default="cursor")
    return "cursor"


def open_question_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT") or get_str("executor", "open_question_default")
    if configured:
        return normalize_executor(configured, default="cursor")
    return "cursor"
