"""Idea lineage resolution for mapping implementation ideas to origin ideas."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _config_path() -> Path:
    configured = os.getenv("IDEA_LINEAGE_MAP_PATH")
    if configured:
        return Path(configured)
    return _project_root() / "config" / "idea_lineage.json"


def _default_origin_map() -> dict[str, str]:
    return {
        "portfolio-governance": "portfolio-governance",
        "oss-interface-alignment": "portfolio-governance",
        "coherence-signal-depth": "portfolio-governance",
        "coherence-network-agent-pipeline": "portfolio-governance",
        "coherence-network-api-runtime": "portfolio-governance",
        "coherence-network-value-attribution": "portfolio-governance",
        "coherence-network-web-interface": "portfolio-governance",
        "deployment-gate-reliability": "portfolio-governance",
    }


def _normalize_idea_id(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized or "unmapped"


def _parse_origin_map(payload: dict[str, Any]) -> dict[str, str]:
    origin_map: dict[str, str] = {}

    raw_map = payload.get("origin_map")
    if isinstance(raw_map, dict):
        for key, value in raw_map.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            k = _normalize_idea_id(key)
            v = _normalize_idea_id(value)
            if k and v:
                origin_map[k] = v

    raw_rows = payload.get("ideas")
    if isinstance(raw_rows, list):
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            idea_id = _normalize_idea_id(row.get("idea_id"))
            origin_idea_id = _normalize_idea_id(row.get("origin_idea_id"))
            if idea_id and origin_idea_id:
                origin_map[idea_id] = origin_idea_id

    return origin_map


def _load_origin_map() -> dict[str, str]:
    defaults = _default_origin_map()
    path = _config_path()
    if not path.exists():
        return defaults

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(payload, dict):
        return defaults

    configured = _parse_origin_map(payload)
    if not configured:
        return defaults
    return {**defaults, **configured}


def resolve_origin_idea_id(idea_id: str | None) -> str:
    """Resolve an idea id to its origin/root idea id."""
    current = _normalize_idea_id(idea_id)
    origin_map = _load_origin_map()

    # Follow configured parent links safely and stop on cycles.
    visited: set[str] = set()
    while current in origin_map and current not in visited:
        visited.add(current)
        nxt = _normalize_idea_id(origin_map.get(current))
        if nxt == current:
            return current
        current = nxt

    return current


def get_idea_lineage_map() -> dict[str, Any]:
    """Return the currently active idea->origin mapping."""
    path = _config_path()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(path),
        "origin_map": _load_origin_map(),
    }
