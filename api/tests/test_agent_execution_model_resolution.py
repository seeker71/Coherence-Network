from __future__ import annotations

import pytest

from app.services import agent_execution_service


def test_resolve_openrouter_model_normalizes_claude_alias_to_openrouter_id() -> None:
    task = {
        "model": "claude/claude-sonnet-4-5-20250929",
        "context": {"executor": "claude"},
    }
    resolved = agent_execution_service._resolve_openrouter_model(task, default="openrouter/free")
    assert resolved == "anthropic/claude-sonnet-4.5"


def test_resolve_openrouter_model_normalizes_gemini_alias_to_openrouter_id() -> None:
    task = {
        "model": "gemini/gemini-2.5-pro",
        "context": {"executor": "gemini"},
    }
    resolved = agent_execution_service._resolve_openrouter_model(task, default="openrouter/free")
    assert resolved == "google/gemini-2.5-pro"


def test_resolve_openrouter_model_normalizes_codex_spark_alias_to_openrouter_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_DISABLE_CODEX_EXECUTOR", "0")
    task = {
        "model": "codex/gpt-5.3-codex-spark",
        "context": {"executor": "codex"},
    }
    resolved = agent_execution_service._resolve_openrouter_model(task, default="openrouter/free")
    assert resolved == "openai/gpt-5.3-codex"


def test_resolve_openrouter_model_normalizes_claude_opus_minor_version() -> None:
    task = {
        "model": "claude/claude-opus-4-5",
        "context": {"executor": "claude"},
    }
    resolved = agent_execution_service._resolve_openrouter_model(task, default="openrouter/free")
    assert resolved == "anthropic/claude-opus-4.5"


def test_resolve_openrouter_model_keeps_openrouter_executor_free_model_policy() -> None:
    task = {
        "model": "openrouter/anthropic/claude-sonnet-4.5",
        "context": {"executor": "openrouter"},
    }
    resolved = agent_execution_service._resolve_openrouter_model(task, default="openrouter/free")
    assert resolved == "openrouter/free"
