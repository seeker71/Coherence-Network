"""Canonical route registry service."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


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
    env_value = os.getenv("CANONICAL_ROUTES_PATH", "").strip()
    if env_value:
        env_override = Path(env_value)
        return env_override

    repo_level = Path(__file__).resolve().parents[3] / "config" / "canonical_routes.json"
    if repo_level.exists():
        return repo_level

    # Railway API deployments can use api/ as service root; keep a mirrored config there.
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
            base = _default_registry()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": base.get("version", "unknown"),
        "milestone": base.get("milestone", "unknown"),
        "api_routes": base.get("api_routes", []),
        "web_routes": base.get("web_routes", []),
    }
