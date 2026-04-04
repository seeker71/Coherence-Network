"""Model listing and routing configuration endpoints.

GET   /api/models          — list all configured models grouped by executor
GET   /api/models/routing  — current task-type → model routing config
PATCH /api/models/routing  — update routing config at runtime
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/models", tags=["models"])
log = logging.getLogger("coherence.api")

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
_ROUTING_PATH = _CONFIG_DIR / "model_routing.json"


# ── Response models ─────────────────────────────────────────────────


class ModelEntry(BaseModel):
    model_id: str
    tier: str  # "strong" | "fast" | "fallback"
    executor: str


class ModelsListResponse(BaseModel):
    executors: dict[str, list[ModelEntry]]
    total: int


class RoutingConfigResponse(BaseModel):
    task_type_tier_mapping: dict[str, str]
    executor_tiers: dict[str, dict[str, list[str]]]
    fallback_chains: dict[str, list[str]]
    openrouter_task_overrides: dict[str, str]


class RoutingUpdateRequest(BaseModel):
    """Partial update to model routing config."""
    task_type_tier_set: dict[str, str] | None = None  # e.g. {"spec": "fast"}
    executor_tier_add: dict[str, Any] | None = None   # e.g. {"claude": {"fast": ["claude-3-5-haiku"]}}
    openrouter_override_set: dict[str, str] | None = None


# ── Helpers ─────────────────────────────────────────────────────────


def _load_routing() -> dict:
    """Load model_routing.json with safe fallback."""
    try:
        return json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.warning("Could not load model_routing.json: %s", exc)
        return {}


def _save_routing(config: dict) -> None:
    """Persist model_routing.json."""
    _ROUTING_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    log.info("model_routing.json updated and saved")


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("")
async def list_models() -> ModelsListResponse:
    """List all configured models grouped by executor with tier info."""
    config = _load_routing()
    executor_tiers = config.get("executor_tiers", {})

    result: dict[str, list[ModelEntry]] = {}
    total = 0

    for executor, tiers in executor_tiers.items():
        entries = []
        for tier_name, models in tiers.items():
            if isinstance(models, list):
                for m in models:
                    entries.append(ModelEntry(model_id=m, tier=tier_name, executor=executor))
                    total += 1
        result[executor] = entries

    # Also include openrouter task overrides as a virtual executor group
    or_overrides = config.get("openrouter_task_overrides", {})
    if or_overrides:
        or_entries = []
        for task_type, model_id in or_overrides.items():
            or_entries.append(ModelEntry(
                model_id=model_id,
                tier=f"task:{task_type}",
                executor="openrouter",
            ))
            total += 1
        # Merge with existing openrouter entries
        existing = result.get("openrouter", [])
        # Deduplicate by model_id
        seen = {e.model_id for e in existing}
        for e in or_entries:
            if e.model_id not in seen:
                existing.append(e)
                seen.add(e.model_id)
        result["openrouter"] = existing

    return ModelsListResponse(executors=result, total=total)


@router.get("/routing")
async def get_routing_config() -> RoutingConfigResponse:
    """Return current task-type → model routing configuration."""
    config = _load_routing()
    return RoutingConfigResponse(
        task_type_tier_mapping=config.get("task_type_tier_mapping", {}),
        executor_tiers=config.get("executor_tiers", {}),
        fallback_chains=config.get("fallback_chains", {}),
        openrouter_task_overrides=config.get("openrouter_task_overrides", {}),
    )


@router.patch("/routing")
async def update_routing_config(body: RoutingUpdateRequest) -> RoutingConfigResponse:
    """Update model routing configuration at runtime.

    Changes are persisted to model_routing.json immediately.
    """
    config = _load_routing()

    if body.task_type_tier_set:
        mapping = config.setdefault("task_type_tier_mapping", {})
        for task_type, tier in body.task_type_tier_set.items():
            if tier not in ("strong", "fast"):
                raise HTTPException(400, f"Invalid tier '{tier}' for task type '{task_type}'. Use 'strong' or 'fast'.")
            mapping[task_type] = tier
            log.info("Routing update: %s → %s", task_type, tier)

    if body.executor_tier_add:
        tiers = config.setdefault("executor_tiers", {})
        for executor, tier_models in body.executor_tier_add.items():
            exec_tiers = tiers.setdefault(executor, {})
            for tier_name, models in tier_models.items():
                existing = exec_tiers.setdefault(tier_name, [])
                for m in (models if isinstance(models, list) else [models]):
                    if m not in existing:
                        existing.append(m)
                        log.info("Model added: %s/%s → %s", executor, tier_name, m)

    if body.openrouter_override_set:
        overrides = config.setdefault("openrouter_task_overrides", {})
        for task_type, model in body.openrouter_override_set.items():
            overrides[task_type] = model
            log.info("OpenRouter override: %s → %s", task_type, model)

    _save_routing(config)

    # Reload the routing loader cache if available
    try:
        from app.services.agent_routing import model_routing_loader
        if hasattr(model_routing_loader, "_reload_config"):
            model_routing_loader._reload_config()
    except Exception:
        pass  # best effort

    return RoutingConfigResponse(
        task_type_tier_mapping=config.get("task_type_tier_mapping", {}),
        executor_tiers=config.get("executor_tiers", {}),
        fallback_chains=config.get("fallback_chains", {}),
        openrouter_task_overrides=config.get("openrouter_task_overrides", {}),
    )
