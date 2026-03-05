"""Model alias resolution and OpenRouter policy (see docs/MODEL-ROUTING.md)."""

from __future__ import annotations

import os

DEFAULT_MODEL_ALIAS_MAP = (
    "gtp-5.3-codex-spark:gpt-5.3-codex-spark,"
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


def get_openrouter_free_model() -> str:
    return normalize_model_name(
        os.environ.get("OPENROUTER_FREE_MODEL", "openrouter/free")
    )


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
