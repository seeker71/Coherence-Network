"""Load application configuration from config files.

Primary source: api/config/settings.json (or path from CONFIG_PATH env).
Environment variables override config values for deployment and tests (e.g. AGENT_TASKS_PERSIST, DATABASE_URL).
Secrets (tokens, DB URLs) typically stay in env.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] | None = None


def _config_path() -> Path:
    env_value = os.environ.get("CONFIG_PATH", "").strip()
    if env_value:
        return Path(env_value)
    return Path(__file__).resolve().parents[1] / "config" / "settings.json"


def _load_raw() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    path = _config_path()
    if not path.exists():
        _CACHE = {}
        return _CACHE
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        _CACHE = {}
        return _CACHE
    _CACHE = data if isinstance(data, dict) else {}
    return _CACHE


def reset_cache() -> None:
    """Clear cached config (for tests)."""
    global _CACHE
    _CACHE = None


def get(section: str, key: str, default: Any = None) -> Any:
    """Get config value: config[section][key]. Returns default if missing or blank string."""
    data = _load_raw()
    sect = data.get(section)
    if not isinstance(sect, dict):
        return default
    value = sect.get(key)
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    return value


def get_str(section: str, key: str, default: str = "") -> str:
    raw = get(section, key, default)
    return str(raw).strip() if raw is not None else default


def get_int(section: str, key: str, default: int = 0) -> int:
    raw = get(section, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_float(section: str, key: str, default: float = 0.0) -> float:
    raw = get(section, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def get_bool(section: str, key: str, default: bool = False) -> bool:
    raw = get(section, key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if not s:
        return default
    return s in ("1", "true", "yes", "on")


def get_section(section: str) -> dict[str, Any]:
    """Return full section dict (empty dict if missing)."""
    data = _load_raw()
    sect = data.get(section)
    return dict(sect) if isinstance(sect, dict) else {}
