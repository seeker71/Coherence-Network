"""Canonical route registry service."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config_loader import get_str

logger = logging.getLogger(__name__)


def _default_registry() -> dict:
    return {
        "version": "fallback",
        "milestone": "runtime-value-attribution",
        "api_routes": [
            {
                "path": "/api/runtime/events",
                "methods": ["POST", "GET"],
                "purpose": "Runtime event ingestion and inspection",
                "idea_id": "oss-interface-alignment",
            }
        ],
        "web_routes": [],
    }


def _registry_path() -> Path:
    env_value = get_str("route_registry", "canonical_routes_path", default="").strip()
    if env_value:
        return Path(env_value)

    repo_level = Path(__file__).resolve().parents[3] / "config" / "canonical_routes.json"
    if repo_level.exists():
        return repo_level

    api_level = Path(__file__).resolve().parents[2] / "config" / "canonical_routes.json"
    if api_level.exists():
        return api_level

    return repo_level


def get_canonical_routes() -> dict:
    path = _registry_path()
    if not path.exists():
        base = _default_registry()
    else:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            base = data if isinstance(data, dict) else _default_registry()
        except (OSError, json.JSONDecodeError):
            logger.warning("Route registry load failed, using defaults", exc_info=True)
            base = _default_registry()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": base.get("version", "unknown"),
        "milestone": base.get("milestone", "unknown"),
        "api_routes": base.get("api_routes", []),
        "web_routes": base.get("web_routes", []),
    }
