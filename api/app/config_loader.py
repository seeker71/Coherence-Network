"""API configuration loader — single source of truth.

All configuration comes from api/config/api.json.
No environment variables are read for application config.

Usage:
    from app.config_loader import api_config, database_url
    db_url = api_config("database", "url")
    api_key = api_config("auth", "api_key")
    db = database_url("agent_tasks")  # falls back to main DB
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CONFIG: dict[str, Any] = {}
_LOADED = False


def _find_config_path() -> Path:
    app_dir = Path(__file__).resolve().parent
    api_dir = app_dir.parent
    return api_dir / "config" / "api.json"


def _load() -> dict[str, Any]:
    global _CONFIG, _LOADED
    if _LOADED:
        return _CONFIG

    defaults: dict[str, Any] = {
        "database": {"url": "sqlite:///data/coherence.db"},
        "database_overrides": {},
        "auth": {"api_key": "dev-key", "admin_key": "dev-admin"},
        "cors": {"allowed_origins": ["http://localhost:3000"]},
        "telegram": {"bot_token": None, "chat_ids": [], "allowed_user_ids": [],
                     "failed_alert_max_per_window": 5, "failed_alert_window_seconds": 3600},
        "storage": {},
        "server": {"environment": "development", "enable_hsts": False},
    }

    config_path = _find_config_path()
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
            for section, section_defaults in defaults.items():
                if section in loaded and isinstance(loaded[section], dict) and isinstance(section_defaults, dict):
                    section_defaults.update(
                        {k: v for k, v in loaded[section].items() if not k.startswith("_")}
                    )
            _CONFIG = defaults
            log.info("API config loaded from %s", config_path)
        except Exception as e:
            log.warning("Failed to load %s: %s. Using defaults.", config_path, e)
            _CONFIG = defaults
    else:
        log.info("No config file at %s — using defaults", config_path)
        _CONFIG = defaults

    _LOADED = True
    return _CONFIG


def api_config(section: str, key: str, default: Any = None) -> Any:
    config = _load()
    return config.get(section, {}).get(key, default)


def database_url(service: str | None = None) -> str:
    config = _load()
    if service:
        override = config.get("database_overrides", {}).get(service)
        if override:
            return str(override)
    return str(config.get("database", {}).get("url", "sqlite:///data/coherence.db"))


def get_float(section: str, key: str, default: float = 0.0) -> float:
    """Read a float config value."""
    val = api_config(section, key, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def get_int(section: str, key: str, default: int = 0) -> int:
    """Read an int config value."""
    val = api_config(section, key, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def get_bool(section: str, key: str, default: bool = False) -> bool:
    """Read a bool config value."""
    val = api_config(section, key, default)
    if isinstance(val, bool):
        return val
    return str(val).lower().strip() in ("true", "1", "yes", "on")


def get_str(section: str, key: str, default: str = "") -> str:
    """Read a string config value."""
    val = api_config(section, key, default)
    return str(val) if val is not None else default


def get_list(section: str, key: str, default: list | None = None) -> list:
    """Read a list config value."""
    val = api_config(section, key, default or [])
    return val if isinstance(val, list) else default or []


def reload_config() -> None:
    global _LOADED
    _LOADED = False
    _load()


def set_config_value(section: str, key: str, value: Any) -> None:
    """Override one loaded config value without leaving the JSON config path."""
    config = _load()
    section_config = config.setdefault(section, {})
    if not isinstance(section_config, dict):
        section_config = {}
        config[section] = section_config
    section_config[key] = value
