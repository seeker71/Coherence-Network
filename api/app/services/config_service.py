"""Unified configuration service backed only by JSON config files."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import socket
import uuid
from pathlib import Path
from typing import Any

from app import config_loader

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".coherence-network"
_CONFIG_PATH = _CONFIG_DIR / "config.json"
_KEYS_PATH = _CONFIG_DIR / "keys.json"
_NODE_ID_PATH = _CONFIG_DIR / "node_id"
_CACHE: dict[str, Any] | None = None


def truthy(value: str | bool | None) -> bool:
    """Convert a value to boolean truthiness."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return bool(value)


def _load_keystore() -> dict[str, Any]:
    if _KEYS_PATH.exists():
        try:
            keys = json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
            if isinstance(keys, dict):
                return keys
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load keystore %s", _KEYS_PATH, exc_info=True)
    return {}


def _detect_node_id() -> str:
    try:
        if _NODE_ID_PATH.exists():
            node_id = _NODE_ID_PATH.read_text(encoding="utf-8").strip()
            if node_id:
                return node_id
    except OSError:
        pass

    hostname = socket.gethostname()
    mac = uuid.getnode()
    node_id = hashlib.sha256(f"{hostname}:{mac}".encode()).hexdigest()[:16]
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _NODE_ID_PATH.write_text(node_id, encoding="utf-8")
    except OSError:
        logger.debug("Could not persist node_id to %s", _NODE_ID_PATH)
    return node_id


def _detect_providers() -> list[str]:
    providers: list[str] = []
    for name, binary in [("claude", "claude"), ("codex", "codex"), ("gemini", "gemini"), ("cursor", "agent")]:
        if shutil.which(binary):
            providers.append(name)
    if shutil.which("ollama"):
        providers.append("ollama")
    return providers


def get_database_url() -> str:
    return config_loader.database_url()


def get_database_url_from_config() -> str:
    return get_database_url()


def get_config() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    config = dict(config_loader.full_config())
    keys = _load_keystore()

    api_key = (
        keys.get("coherence", {}).get("api_key")
        or keys.get("api_key")
        or config_loader.api_config("auth", "api_key", "dev-key")
    )
    openrouter_api_key = (
        keys.get("openrouter", {}).get("api_key")
        or config_loader.api_config("agent_providers", "openrouter_api_key", "")
    )
    github_token = (
        keys.get("github", {}).get("token")
        or keys.get("github_token")
        or config_loader.api_config("github", "token", None)
        or config_loader.api_config("github", "api_token", None)
        or config_loader.full_config().get("github_token")
    )

    config["keys"] = keys
    config["api_key"] = str(api_key or "dev-key")
    config["openrouter_api_key"] = str(openrouter_api_key or "")
    config["github_token"] = str(github_token) if github_token else None

    config["environment"] = config_loader.api_config("server", "environment", "development")
    config["database_url"] = config_loader.database_url()
    config["api_base"] = config_loader.api_config("agent_providers", "api_base_url", "https://api.coherencycoin.com")
    config["hub_url"] = config["api_base"]
    config["web_ui_base_url"] = config_loader.api_config("agent_providers", "web_ui_base_url", "https://coherencycoin.com")
    config["providers"] = _detect_providers()
    config["node_id"] = _detect_node_id()
    config["cors_origins"] = config_loader.get_list("cors", "allowed_origins", ["http://localhost:3000"])
    config["contributor_id"] = config_loader.load_user_config().get("contributor_id")
    config["agent_execute_token"] = config_loader.api_config("agent_executor", "execute_token", None)
    config["agent_execute_token_allow_unauth"] = config_loader.get_bool(
        "agent_executor",
        "execute_token_allow_unauth",
        False,
    )
    config["pipeline_orphan_running_seconds"] = config_loader.get_int("pipeline", "orphan_running_seconds", 1800)
    config["pipeline_stale_running_seconds"] = config_loader.get_int("pipeline", "stale_running_seconds", 1800)
    config["monitor_issues_max_age_seconds"] = config_loader.get_int("pipeline", "monitor_max_age_seconds", 900)
    config["pipeline_status_report_max_age_seconds"] = config_loader.get_int(
        "pipeline",
        "status_report_max_age_seconds",
        900,
    )
    config["pipeline_pending_actionable_window_seconds"] = config_loader.get_int(
        "pipeline",
        "pending_actionable_window_seconds",
        86400,
    )
    config["task_log_dir"] = config_loader.get_str("agent_tasks", "task_log_dir", "data/task_logs")
    _CACHE = config
    logger.info(
        "Config loaded: env=%s api=%s db=%s providers=%s node=%s cors=%s",
        config.get("environment"),
        config.get("api_base"),
        (config.get("database_url", "") or "")[:30] + "...",
        config.get("providers"),
        str(config.get("node_id", ""))[:8] + "...",
        config.get("cors_origins"),
    )
    return config


def get_editable_config() -> dict[str, Any]:
    """Return the user-editable config (from ~/.coherence-network/config.json).

    This is the subset that's safe to expose and modify — no secrets.
    """
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def update_editable_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge updates into ~/.coherence-network/config.json.

    Does a shallow merge at the top level — nested dicts are replaced,
    not deep-merged. Returns the new config.
    """
    current = get_editable_config()
    # Filter out sensitive keys that should never be set via API
    forbidden = {"keys", "api_key", "github_token", "openrouter_api_key", "database_url"}
    safe_updates = {k: v for k, v in updates.items() if k not in forbidden}
    current.update(safe_updates)

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Write atomically: write to temp, then rename
    tmp = _CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    shutil.move(str(tmp), str(_CONFIG_PATH))

    reset_config_cache()
    return current


def get_api_key() -> str:
    return str(get_config().get("api_key") or "dev-key")


def get_hub_url() -> str:
    return str(get_config().get("hub_url") or "https://api.coherencycoin.com")


def get_github_token() -> str | None:
    token = get_config().get("github_token")
    return str(token) if token else None


def resolve_cli_contributor_id() -> tuple[str | None, str]:
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cid = str(data.get("contributor_id") or "").strip()
                if cid:
                    return cid, "config.json"
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None, "none"


def get_cors_origins() -> list[str]:
    origins = get_config().get("cors_origins")
    if isinstance(origins, list) and origins:
        return origins
    return ["http://localhost:3000"]


def get_openrouter_key() -> str:
    return str(get_config().get("openrouter_api_key") or "")


def get_node_id() -> str:
    return str(get_config().get("node_id") or "")


def is_production() -> bool:
    # Honour the ENVIRONMENT env var (via config_loader.server_environment)
    # before the cached config, so a production container can declare
    # itself production without editing the checked-in config file.
    return config_loader.server_environment() == "production"


def get_providers() -> list[str]:
    providers = get_config().get("providers")
    return providers if isinstance(providers, list) else []


def get_api_base() -> str:
    return str(get_config().get("api_base") or "https://api.coherencycoin.com")


def get_environment() -> str:
    return config_loader.server_environment()


def get_contributor_id() -> str | None:
    contributor_id = get_config().get("contributor_id")
    return str(contributor_id) if contributor_id else None


def get_key(provider: str, key_name: str) -> str:
    return str(get_config().get("keys", {}).get(provider, {}).get(key_name, "") or "")


def get_treasury_config() -> dict[str, Any]:
    config = get_config()
    return config.get(
        "treasury",
        {
            "eth_address": "",
            "btc_address": "",
            "cc_per_eth": 1000.0,
            "cc_per_btc": 10000.0,
        },
    )


def get_oauth_config(provider: str) -> dict[str, Any]:
    config = get_config()
    oauth = config.get("oauth", {})
    return oauth.get(provider, {}) if isinstance(oauth, dict) else {}


def reset_config_cache() -> None:
    global _CACHE
    _CACHE = None
    config_loader.reload_config()
