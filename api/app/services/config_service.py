"""Unified configuration service — single source of truth.

Layered config (highest priority wins):
  1. ~/.coherence-network/config.json  (user overrides)
  2. Auto-detection                    (smart defaults)
  3. Environment variables             (backward compat, lowest priority)

Never raises — always returns safe defaults.
"""

import hashlib
import json
import shutil
import socket
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".coherence-network"
_CONFIG_PATH = _CONFIG_DIR / "config.json"
_KEYS_PATH = _CONFIG_DIR / "keys.json"
_NODE_ID_PATH = _CONFIG_DIR / "node_id"
_CACHE = None


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------

def _detect_database() -> str:
    """Check if postgres is reachable, else use sqlite."""
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1)
        s.close()
        return "postgresql://coherence:coherence@localhost:5432/coherence"
    except (OSError, ConnectionRefusedError):
        return "sqlite:///data/coherence.db"


def _detect_providers() -> list[str]:
    """Auto-detect which AI provider CLIs are installed."""
    providers = []
    for name, binary in [("claude", "claude"), ("codex", "codex"), ("gemini", "gemini"), ("cursor", "agent")]:
        if shutil.which(binary):
            providers.append(name)
    if shutil.which("ollama"):
        providers.append("ollama")
    return providers


def _detect_environment(database_url: str) -> str:
    """'development' if localhost, 'production' if DATABASE_URL is postgres."""
    hostname = socket.gethostname()
    if "srv1482815" in hostname or "hostinger" in hostname.lower():
        return "production"
    if "postgres" in database_url:
        # Check env var hint — a remote postgres URL signals production
        env_db = os.environ.get("DATABASE_URL", "").strip()
        if env_db and "postgres" in env_db and "localhost" not in env_db:
            return "production"
    return "development"


def _detect_node_id() -> str:
    """Get or create stable node identity from ~/.coherence-network/node_id."""
    try:
        if _NODE_ID_PATH.exists():
            node_id = _NODE_ID_PATH.read_text().strip()
            if node_id:
                return node_id
    except OSError:
        pass
    # Generate from hostname + MAC
    hostname = socket.gethostname()
    mac = uuid.getnode()
    node_id = hashlib.sha256(f"{hostname}:{mac}".encode()).hexdigest()[:16]
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _NODE_ID_PATH.write_text(node_id)
    except OSError:
        logger.debug("Could not persist node_id to %s", _NODE_ID_PATH)
    return node_id


def _detect_cors_origins(environment: str) -> list[str]:
    """Auto CORS origins based on environment."""
    if environment == "production":
        return [
            "https://coherencycoin.com",
            "https://www.coherencycoin.com",
        ]
    return ["http://localhost:3000"]


def _load_keystore() -> dict:
    """Load ~/.coherence-network/keys.json safely."""
    if _KEYS_PATH.exists():
        try:
            keys = json.loads(_KEYS_PATH.read_text())
            if isinstance(keys, dict):
                return keys
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load keystore %s", _KEYS_PATH, exc_info=True)
    return {}


def _auto_detect() -> dict:
    """Auto-detect environment without requiring any config."""
    database_url = _detect_database()
    environment = _detect_environment(database_url)
    node_id = _detect_node_id()
    cors_origins = _detect_cors_origins(environment)
    providers = _detect_providers()

    config = {
        "environment": environment,
        "database_url": database_url,
        "api_base": "https://api.coherencycoin.com" if environment == "production" else "http://localhost:8000",
        "hub_url": "https://api.coherencycoin.com",
        "providers": providers,
        "node_id": node_id,
        "cors_origins": cors_origins,
        "contributor_id": None,
    }
    return config


# ---------------------------------------------------------------------------
# Core config loader
# ---------------------------------------------------------------------------

def get_config() -> dict:
    """Load config with precedence:
      1. ~/.coherence-network/config.json  (highest — user overrides)
      2. Auto-detection                    (smart defaults)
      3. Environment variables             (lowest — backward compat)

    Never raises.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    # Layer 3 (lowest): start with env-var based values
    config: dict = {}
    for env_key, config_key in [
        ("COHERENCE_API_BASE", "api_base"),
        ("DATABASE_URL", "database_url"),
        ("COHERENCE_HUB_URL", "hub_url"),
        ("COHERENCE_ENV", "environment"),
        ("COHERENCE_CONTRIBUTOR_ID", "contributor_id"),
        ("COHERENCE_NODE_ID", "node_id"),
        ("COHERENCE_API_KEY", "api_key"),
        ("OPENROUTER_API_KEY", "openrouter_api_key"),
    ]:
        val = os.environ.get(env_key, "").strip()
        if val:
            config[config_key] = val

    # ALLOWED_ORIGINS env var -> cors_origins (backward compat)
    allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if allowed_origins_env:
        config["cors_origins"] = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

    # Layer 2: auto-detection overwrites env vars
    auto = _auto_detect()
    for k, v in auto.items():
        if v is not None:
            config[k] = v

    # Layer 1 (highest): user config file overrides everything
    if _CONFIG_PATH.exists():
        try:
            user_config = json.loads(_CONFIG_PATH.read_text())
            if isinstance(user_config, dict):
                for k, v in user_config.items():
                    if k.startswith("_"):
                        continue  # skip comments
                    if v != "auto" and v is not None:
                        config[k] = v
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load %s", _CONFIG_PATH, exc_info=True)

    # Merge keystore
    config["keys"] = _load_keystore()

    # Resolve api_key: keystore -> config -> env -> "dev-key"
    if "api_key" not in config or not config["api_key"]:
        ks_key = config["keys"].get("coherence", {}).get("api_key", "")
        config["api_key"] = ks_key if ks_key else "dev-key"

    # Resolve openrouter_api_key: keystore -> config -> env -> ""
    if "openrouter_api_key" not in config or not config["openrouter_api_key"]:
        ks_key = config["keys"].get("openrouter", {}).get("api_key", "")
        config["openrouter_api_key"] = ks_key if ks_key else ""

    _CACHE = config
    logger.info(
        "Config loaded: env=%s api=%s db=%s providers=%s node=%s cors=%s",
        config.get("environment"),
        config.get("api_base"),
        (config.get("database_url", "") or "")[:30] + "...",
        config.get("providers"),
        config.get("node_id", "")[:8] + "...",
        config.get("cors_origins"),
    )
    return config


# ---------------------------------------------------------------------------
# Typed accessor functions
# ---------------------------------------------------------------------------

def get_database_url() -> str:
    return get_config().get("database_url", "sqlite:///data/coherence.db")


def get_api_key() -> str:
    return get_config().get("api_key", "dev-key")


def get_hub_url() -> str:
    return get_config().get("hub_url", "https://api.coherencycoin.com")


def get_cors_origins() -> list[str]:
    origins = get_config().get("cors_origins")
    if isinstance(origins, list) and origins:
        return origins
    return ["http://localhost:3000"]


def get_openrouter_key() -> str:
    return get_config().get("openrouter_api_key", "")


def get_node_id() -> str:
    return get_config().get("node_id", "")


def is_production() -> bool:
    return get_config().get("environment") == "production"


def get_providers() -> list[str]:
    providers = get_config().get("providers")
    if isinstance(providers, list):
        return providers
    return []


def get_api_base() -> str:
    return get_config().get("api_base", "http://localhost:8000")


def get_environment() -> str:
    return get_config().get("environment", "development")


def get_contributor_id():
    return get_config().get("contributor_id")


def get_key(provider, key_name):
    return get_config().get("keys", {}).get(provider, {}).get(key_name, "")


def get_treasury_config() -> dict:
    """Load treasury config from ~/.coherence-network/config.json"""
    config = get_config()
    return config.get("treasury", {
        "eth_address": "",
        "btc_address": "",
        "cc_per_eth": 1000.0,
        "cc_per_btc": 10000.0,
    })


def reset_config_cache():
    global _CACHE
    _CACHE = None
