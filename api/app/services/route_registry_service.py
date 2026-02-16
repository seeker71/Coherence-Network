"""Canonical route registry service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _default_registry() -> dict:
    return {
        "version": "fallback",
        "milestone": "runtime-value-attribution",
        "api_routes": [],
        "web_routes": [],
    }


def _registry_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "canonical_routes.json"


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
