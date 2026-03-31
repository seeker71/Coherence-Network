"""Provider and billing classification from executor/model/command."""

from __future__ import annotations

import re

from app.services.agent_routing.executor_config import normalize_executor


def is_paid_model(*, provider: str, model: str, command_model: str) -> bool:
    if provider == "openrouter":
        ref = command_model or model
        if "openrouter/free" in ref or ref.endswith("/free"):
            return False
        return True
    if provider in {"openai", "openai-codex", "claude", "cursor", "gemini"}:
        return True
    return False


def classify_provider(
    *, executor: str, model: str, command: str, worker_id: str | None
) -> tuple[str, str, bool]:
    normalized_executor = normalize_executor(executor, default=(executor or "").strip().lower())
    lower_model = (model or "").strip().lower()
    lower_command = (command or "").strip().lower()
    normalized_worker = (worker_id or "").strip().lower()
    command_model_match = re.search(r"--model\s+([^\s]+)", lower_command)
    command_model = command_model_match.group(1).strip().lower() if command_model_match else ""

    provider = "unknown"
    if normalized_worker == "openai-codex" or normalized_worker.startswith("openai-codex:"):
        provider = "openai-codex"
    elif normalized_executor == "codex":
        provider = "openai-codex"
    elif normalized_executor == "gemini":
        provider = "gemini"
    elif normalized_executor == "openrouter":
        provider = "openrouter"
    elif "openrouter" in command_model or "openrouter" in lower_model:
        provider = "openrouter"
    elif command_model.startswith(("gemini", "google/gemini")):
        provider = "gemini"
    elif command_model.startswith("openai/") or command_model.startswith(("gpt", "o1", "o3", "o4")):
        provider = "openai-codex" if "codex" in command_model else "openai"
    elif lower_model.startswith("gemini/") or lower_model.startswith("google/gemini"):
        provider = "gemini"
    elif "codex" in lower_model:
        provider = "openai-codex"
    elif lower_model.startswith("openai/") or lower_model.startswith(("gpt", "o1", "o3", "o4")):
        provider = "openai"
    elif lower_command.startswith("gemini "):
        provider = "gemini"
    elif lower_command.startswith("codex "):
        provider = "openai-codex"
    elif normalized_executor == "cursor":
        provider = "cursor"
    elif normalized_executor in {"claude", "aider"}:
        provider = "claude"

    billing_provider = provider
    is_paid_provider = is_paid_model(provider=provider, model=lower_model, command_model=command_model)
    return provider, billing_provider, is_paid_provider
