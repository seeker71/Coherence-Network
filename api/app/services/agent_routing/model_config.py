"""Model normalization and OpenRouter policy (see docs/MODEL-ROUTING.md). No aliasing; model ids from config used as-is."""

from __future__ import annotations

from app.services.agent_routing.model_routing_loader import get_openrouter_free_model as _loader_openrouter_free


def normalize_model_name(model: str) -> str:
    """Return trimmed model id. No alias map; use provider model ids directly."""
    return str(model or "").strip()


def get_openrouter_free_model() -> str:
    return normalize_model_name(_loader_openrouter_free())


def enforce_openrouter_free_model(model: str | None) -> str:
    """OpenRouter execution policy: force free-tier model usage."""
    _openrouter_free = get_openrouter_free_model()
    cleaned = normalize_model_name(str(model or "").strip())
    if cleaned == _openrouter_free:
        return cleaned
    if cleaned.startswith("openrouter/"):
        return _openrouter_free
    if cleaned in {"free", "openrouter", "openrouter:free"}:
        return _openrouter_free
    if not cleaned:
        return _openrouter_free
    return _openrouter_free
