"""Task-type → model/tier routing tables (see docs/MODEL-ROUTING.md)."""

from __future__ import annotations

import os

from app.models.agent import TaskType

from app.services.agent_routing.model_config import normalize_model_name

_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openrouter/free")
_OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_CLOUD_MODEL", "openrouter/free")
_CLAUDE_MODEL = os.environ.get("CLAUDE_FALLBACK_MODEL", "openrouter/free")

_CURSOR_MODEL_DEFAULT = os.environ.get("CURSOR_CLI_MODEL", "auto")
_CURSOR_MODEL_REVIEW = os.environ.get("CURSOR_CLI_REVIEW_MODEL", "auto")
_GEMINI_MODEL_DEFAULT = os.environ.get("GEMINI_CLI_MODEL", "gemini-3.1-pro-preview")
_GEMINI_MODEL_REVIEW = os.environ.get("GEMINI_CLI_REVIEW_MODEL", _GEMINI_MODEL_DEFAULT)

_CODEX_MODEL_DEFAULT = normalize_model_name(
    os.environ.get("CODEX_MODEL", os.environ.get("OPENCLAW_MODEL", "gpt-5.3-codex-spark"))
)
_CODEX_MODEL_REVIEW = normalize_model_name(
    os.environ.get("CODEX_REVIEW_MODEL", os.environ.get("OPENCLAW_REVIEW_MODEL", _CODEX_MODEL_DEFAULT))
)

_CLAUDE_CODE_MODEL_DEFAULT = os.environ.get("CLAUDE_CODE_MODEL", "claude-sonnet-4-5-20250929")
_CLAUDE_CODE_MODEL_REVIEW = os.environ.get("CLAUDE_CODE_REVIEW_MODEL", "claude-opus-4-5")

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
    TaskType.SPEC: _CODEX_MODEL_DEFAULT,
    TaskType.TEST: _CODEX_MODEL_DEFAULT,
    TaskType.IMPL: _CODEX_MODEL_DEFAULT,
    TaskType.REVIEW: _CODEX_MODEL_REVIEW,
    TaskType.HEAL: _CODEX_MODEL_REVIEW,
}
CODEX_MODEL_BY_TYPE = OPENCLAW_MODEL_BY_TYPE

GEMINI_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _GEMINI_MODEL_DEFAULT,
    TaskType.TEST: _GEMINI_MODEL_DEFAULT,
    TaskType.IMPL: _GEMINI_MODEL_DEFAULT,
    TaskType.REVIEW: _GEMINI_MODEL_REVIEW,
    TaskType.HEAL: _GEMINI_MODEL_REVIEW,
}

CLAUDE_CODE_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _CLAUDE_CODE_MODEL_DEFAULT,
    TaskType.TEST: _CLAUDE_CODE_MODEL_DEFAULT,
    TaskType.IMPL: _CLAUDE_CODE_MODEL_DEFAULT,
    TaskType.REVIEW: _CLAUDE_CODE_MODEL_REVIEW,
    TaskType.HEAL: _CLAUDE_CODE_MODEL_REVIEW,
}
