"""Inventory cache TTL, read/write, and key helpers."""

from __future__ import annotations

import copy
import os
import time
from typing import Any

from app.services.inventory.constants import _INVENTORY_CACHE


def _inventory_cache_ttl_seconds() -> float:
    raw = os.getenv("INVENTORY_CACHE_TTL_SECONDS", "30").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 30.0


def _inventory_timing_ms_threshold() -> float:
    raw = os.getenv("INVENTORY_TIMING_LOG_MS", "750").strip()
    try:
        return max(50.0, float(raw))
    except ValueError:
        return 750.0


def _inventory_timing_enabled() -> bool:
    raw = os.getenv("INVENTORY_TIMING_ENABLED", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _cache_key(*parts: object) -> str:
    return "|".join(str(part) for part in parts)


def _inventory_environment_cache_key() -> str:
    return "|".join(
        [
            f"idea_portfolio={os.getenv('IDEA_PORTFOLIO_PATH', '')}",
            f"value_lineage={os.getenv('VALUE_LINEAGE_PATH', '')}",
            f"runtime_events={os.getenv('RUNTIME_EVENTS_PATH', '')}",
            f"runtime_idea_map={os.getenv('RUNTIME_IDEA_MAP_PATH', '')}",
            f"idea_registry_db={os.getenv('IDEA_REGISTRY_DATABASE_URL', '')}|{os.getenv('IDEA_REGISTRY_DB_URL', '')}|{os.getenv('DATABASE_URL', '')}",
            f"commit_evidence_db={os.getenv('COMMIT_EVIDENCE_DATABASE_URL', '')}|{os.getenv('DATABASE_URL', '')}",
            f"commit_evidence_dir={os.getenv('IDEA_COMMIT_EVIDENCE_DIR', '')}",
            f"spec_registry_db={os.getenv('GOVERNANCE_DATABASE_URL', '')}|{os.getenv('GOVERNANCE_DB_URL', '')}|{os.getenv('DATABASE_URL', '')}",
        ]
    )


def _read_inventory_cache(cache_name: str, key: str) -> dict[str, Any] | None:
    cache = _INVENTORY_CACHE.get(cache_name, {})
    if not isinstance(cache, dict):
        return None
    if cache.get("expires_at", 0.0) <= time.time():
        return None
    items = cache.get("items", {})
    if not isinstance(items, dict):
        return None
    cached_payload = items.get(key)
    if not isinstance(cached_payload, dict):
        return None
    try:
        return copy.deepcopy(cached_payload)
    except Exception:
        return None


def _write_inventory_cache(cache_name: str, key: str, payload: dict[str, Any]) -> None:
    cache = _INVENTORY_CACHE.setdefault(cache_name, {"expires_at": 0.0, "items": {}})
    items = cache.setdefault("items", {})
    try:
        items[key] = copy.deepcopy(payload)
    except Exception:
        items[key] = payload
    cache["expires_at"] = time.time() + _inventory_cache_ttl_seconds()


def _row_signature(rows: list[dict[str, Any]] | None) -> str:
    if not isinstance(rows, list) or not rows:
        return "rows=0"
    first = rows[0] if isinstance(rows[0], dict) else {}
    last = rows[-1] if isinstance(rows[-1], dict) else {}
    if not isinstance(first, dict):
        first = {}
    if not isinstance(last, dict):
        last = {}
    return "rows=%s:first=%s:last=%s" % (
        len(rows),
        str(first.get("id") or "").strip(),
        str(last.get("id") or "").strip(),
    )
