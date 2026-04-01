"""Inventory cache TTL, read/write, and key helpers."""

from __future__ import annotations

import copy
import time
from typing import Any

from app.config_loader import get_bool, get_float, get_str
from app.services.inventory.constants import _INVENTORY_CACHE


def _inventory_cache_ttl_seconds() -> float:
    return max(1.0, get_float("inventory", "cache_ttl_seconds", 30.0))


def _inventory_timing_ms_threshold() -> float:
    return max(50.0, get_float("inventory", "timing_log_ms", 750.0))


def _inventory_timing_enabled() -> bool:
    return get_bool("inventory", "timing_enabled", False)


def _cache_key(*parts: object) -> str:
    return "|".join(str(part) for part in parts)


def _inventory_environment_cache_key() -> str:
    from app.services import unified_db as _udb
    return "|".join(
        [
            f"db={_udb.database_url()}",
            f"idea_portfolio={get_str('storage', 'idea_portfolio_path')}",
            f"value_lineage={get_str('storage', 'value_lineage_path')}",
            f"runtime_events={get_str('runtime', 'events_path')}",
            f"runtime_idea_map={get_str('runtime', 'idea_map_path')}",
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
