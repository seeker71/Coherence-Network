"""Load strong/fast tiers, task-type→tier, openrouter model per task type, and fallback chains from config."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.models.agent import TaskType

logger = logging.getLogger(__name__)

_CACHE: dict[str, Any] | None = None

# Task types we support for tier resolution
_TASK_TYPE_KEYS = ("spec", "test", "impl", "review", "heal")
_TIER_STRONG = "strong"
_TIER_FAST = "fast"


def _config_path() -> Path:
    env_value = os.environ.get("MODEL_ROUTING_CONFIG_PATH", "").strip()
    if env_value:
        return Path(env_value)
    for base in [
        Path(__file__).resolve().parents[3] / "config" / "model_routing.json",
        Path(__file__).resolve().parents[2] / "config" / "model_routing.json",
    ]:
        if base.exists():
            return base
    return Path(__file__).resolve().parents[2] / "config" / "model_routing.json"


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    path = _config_path()
    if not path.exists():
        _CACHE = _empty_cache()
        return _CACHE
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("Model routing config load failed", exc_info=True)
        _CACHE = _empty_cache()
        return _CACHE
    if not isinstance(data, dict):
        _CACHE = _empty_cache()
        return _CACHE
    # Support legacy key "routing" for backward compatibility
    openrouter_by_type = data.get("openrouter_models_by_task_type") or data.get("routing") or {}
    tiers = data.get("tiers_by_executor") if isinstance(data.get("tiers_by_executor"), dict) else {}
    task_type_tier = data.get("task_type_tier") if isinstance(data.get("task_type_tier"), dict) else {}
    fallback_chains = data.get("fallback_chains") if isinstance(data.get("fallback_chains"), dict) else {}
    _CACHE = {
        "openrouter_free_model": data.get("openrouter_free_model") or "openrouter/free",
        "auto_execute_default_model": (data.get("auto_execute_default_model") or "").strip() or None,
        "roi_spec_cheap_model": (data.get("roi_spec_cheap_model") or "").strip() or None,
        "default_models_by_executor": data.get("default_models_by_executor") if isinstance(data.get("default_models_by_executor"), dict) else {},
        "openrouter_models_by_task_type": openrouter_by_type if isinstance(openrouter_by_type, dict) else {},
        "tiers_by_executor": tiers,
        "task_type_tier": task_type_tier,
        "fallback_chains": fallback_chains,
    }
    return _CACHE


def _empty_cache() -> dict[str, Any]:
    return {
        "openrouter_free_model": "openrouter/free",
        "auto_execute_default_model": None,
        "roi_spec_cheap_model": None,
        "default_models_by_executor": {},
        "openrouter_models_by_task_type": {},
        "tiers_by_executor": {},
        "task_type_tier": {},
        "fallback_chains": {},
    }


def reset_model_routing_cache() -> None:
    global _CACHE
    _CACHE = None


def get_openrouter_free_model() -> str:
    return str((_load().get("openrouter_free_model") or "openrouter/free")).strip()


def get_auto_execute_default_model() -> str:
    """Default model for auto-execute. No fallback to openrouter — slot selector decides."""
    raw = _load().get("auto_execute_default_model")
    return str(raw or "").strip()


def get_roi_spec_cheap_model() -> str:
    """Model override for ROI spec progress tasks (inventory). No fallback to openrouter."""
    raw = _load().get("roi_spec_cheap_model")
    return str(raw or "").strip()


def get_model_for_executor(executor: str, kind: str = "default") -> str:
    """kind: 'default' (fast), 'review' (strong), 'strong', or 'fast'. Prefers tiers_by_executor when present."""
    tiers = _load().get("tiers_by_executor") or {}
    exec_tiers = tiers.get(executor) if isinstance(tiers.get(executor), dict) else {}
    if exec_tiers:
        if kind == "review" or kind == _TIER_STRONG:
            out = exec_tiers.get(_TIER_STRONG) or exec_tiers.get("review") or exec_tiers.get("fast") or ""
        else:
            out = exec_tiers.get(_TIER_FAST) or exec_tiers.get("default") or exec_tiers.get("strong") or ""
        if out:
            return str(out).strip()
    by_exec = _load().get("default_models_by_executor") or {}
    exec_models = by_exec.get(executor) if isinstance(by_exec.get(executor), dict) else {}
    return str(exec_models.get(kind) or exec_models.get("default") or "").strip()


def get_task_type_tier(task_type: TaskType) -> str:
    """Resolve task type to tier: 'strong' or 'fast' (from config task_type_tier)."""
    key = task_type.value if hasattr(task_type, "value") else str(task_type)
    tier = (_load().get("task_type_tier") or {}).get(key)
    if tier in (_TIER_STRONG, _TIER_FAST):
        return tier
    # Default: spec/impl/test/review/heal → strong (must produce real output)
    # Only status/heal-check tasks use fast tier
    if key in ("spec", "impl", "test", "review", "heal", "code-review"):
        return _TIER_STRONG
    return _TIER_FAST


def get_model_for_executor_and_task_type(executor: str, task_type: TaskType) -> str:
    """Resolve executor + task type to model id using task_type_tier and tiers_by_executor."""
    if executor == "openrouter":
        return get_openrouter_model_for_task_type(task_type)
    tier = get_task_type_tier(task_type)
    tiers = _load().get("tiers_by_executor") or {}
    exec_tiers = tiers.get(executor) if isinstance(tiers.get(executor), dict) else {}
    model = (exec_tiers or {}).get(tier) or exec_tiers.get("default") or ""
    if model:
        return str(model).strip()
    # Fallback to kind-based: default = impl tier (fast), review = review tier (strong)
    kind = "review" if tier == _TIER_STRONG else "default"
    return get_model_for_executor(executor, kind)


def get_fallback_model(executor: str, current_model: str) -> str | None:
    """Next model in this executor's fallback chain after current_model, or None if none.

    Fallback chains MUST stay within the same provider. A claude executor
    never falls back to an openrouter model, and vice versa.
    """
    chain = (_load().get("fallback_chains") or {}).get(executor)
    if not isinstance(chain, list) or not chain:
        return None
    current = (current_model or "").strip()
    try:
        idx = chain.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(chain):
        return None
    next_model = chain[idx + 1]
    fallback_model = str(next_model).strip() if next_model else None
    # Guard: reject cross-provider fallback
    if fallback_model and not validate_model_for_executor(executor, fallback_model):
        logger.warning(
            "model_fallback_rejected executor=%s model=%s — cross-provider fallback blocked",
            executor, fallback_model,
        )
        return None
    if fallback_model:
        logger.info("model_fallback executor=%s from=%s to=%s", executor, current_model, fallback_model)
    return fallback_model


# ── Provider model validation ──────────────────────────────────


# Each provider's model prefix or known model names.
# A provider can ONLY run models from its own catalog.
_PROVIDER_MODEL_PREFIXES: dict[str, list[str]] = {
    "claude": ["claude-"],
    "codex": ["gpt-", "o1-", "o3-", "codex-"],
    "cursor": ["auto", "cursor-"],
    "gemini": ["gemini-"],
    "openrouter": ["openrouter/"],
    # opencode runs Ollama Cloud models; CLI expects "ollama/<model>" refs
    "opencode": ["ollama/"],
    # pi is openclaw's embedded coding agent — also runs Ollama Cloud models
    "pi": ["ollama/"],
}


def validate_model_for_executor(executor: str, model: str) -> bool:
    """Check if a model belongs to the executor's catalog.

    Returns True if the model is valid for this executor, False if it's
    a cross-provider model that this executor cannot run.
    """
    normalized_exec = executor.lower().strip()
    normalized_model = model.lower().strip()
    if not normalized_model:
        return True  # Empty model = use provider default

    prefixes = _PROVIDER_MODEL_PREFIXES.get(normalized_exec)
    if prefixes is None:
        return True  # Unknown executor — allow anything

    return any(normalized_model.startswith(prefix) for prefix in prefixes)


def get_valid_models_for_executor(executor: str) -> list[str]:
    """Return the list of models this executor can run (from tiers + fallback chains)."""
    models = set()
    tiers = (_load().get("tiers_by_executor") or {}).get(executor, {})
    if isinstance(tiers, dict):
        for model in tiers.values():
            if model and validate_model_for_executor(executor, str(model)):
                models.add(str(model))
    chain = (_load().get("fallback_chains") or {}).get(executor, [])
    if isinstance(chain, list):
        for model in chain:
            if model and validate_model_for_executor(executor, str(model)):
                models.add(str(model))
    return sorted(models)


def get_openrouter_model_for_task_type(task_type: TaskType) -> str:
    """Model to use when executor is openrouter. Only this executor uses this table."""
    key = task_type.value if hasattr(task_type, "value") else str(task_type)
    by_type = _load().get("openrouter_models_by_task_type") or {}
    return str(by_type.get(key) or "openrouter/free").strip()


# ── Measurement recording & data-driven suggestion ─────────────────


def record_model_selection(task_type: str, executor: str, model: str) -> None:
    """Log which model was selected for observability. Non-blocking, fire-and-forget."""
    logger.info("model_selected task_type=%s executor=%s model=%s", task_type, executor, model)


def record_model_outcome(
    task_type: str,
    executor: str,
    model: str,
    success: bool,
    token_cost: float,
    duration_seconds: float,
) -> None:
    """Record model outcome for data-driven optimization."""
    try:
        from app.services.slot_selection_service import SlotSelector

        selector = SlotSelector(f"model_{executor}_{task_type}")
        selector.record(
            slot_id=model,
            value_score=1.0 if success else 0.0,
            resource_cost=max(token_cost, 0.01),
        )
    except Exception:
        logger.debug("Model outcome recording failed", exc_info=True)


def suggest_model(task_type: str, executor: str, available_models: list[str]) -> str | None:
    """Suggest a model based on historical outcomes. Returns None if insufficient data.

    Callers should fall back to config-driven routing when this returns None.
    """
    if len(available_models) < 2:
        return None
    try:
        from app.services.slot_selection_service import SlotSelector

        selector = SlotSelector(f"model_{executor}_{task_type}")
        return selector.select(available_models)
    except Exception:
        return None
