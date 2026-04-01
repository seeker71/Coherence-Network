"""Unified configuration service — single source of truth.

Layered config (highest priority wins):
  1. ~/.coherence-network/config.json  (user overrides)
  2. api/config/api.json             (project defaults)
  3. Sensible defaults                (hard-coded)

NEVER use os.getenv() as fallback in application code.
All settings must be configurable via config files only.
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


def truthy(value: str | bool | None) -> bool:
    """Convert a value to boolean truthiness."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return bool(value)

_CONFIG_DIR = Path.home() / ".coherence-network"
_CONFIG_PATH = _CONFIG_DIR / "config.json"
_KEYS_PATH = _CONFIG_DIR / "keys.json"
_NODE_ID_PATH = _CONFIG_DIR / "node_id"
_CACHE = None


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------

def _detect_database() -> str:
    """Check if postgres is reachable, else use sqlite.
    
    DEPRECATED: This socket-based detection is a hack. Use get_database_url() instead.
    Kept for backward compatibility during transition.
    """
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1)
        s.close()
        return "postgresql://coherence:coherence@localhost:5432/coherence"
    except (OSError, ConnectionRefusedError):
        return "sqlite:///data/coherence.db"


def get_database_url() -> str:
    """Get database URL from config with config-based fallback.
    
    Priority:
      1. ~/.coherence-network/config.json -> database_url field
      2. ~/.coherence-network/config.json -> database -> url field  
      3. api/config/api.json -> database -> url field
      4. Socket detection (deprecated, last resort)
    """
    config = get_config()
    
    # Check direct database_url key
    db_url = config.get("database_url")
    if db_url and isinstance(db_url, str) and db_url.strip():
        return db_url
    
    # Check nested database.url structure
    db_config = config.get("database", {})
    if isinstance(db_config, dict):
        db_url = db_config.get("url")
        if db_url and isinstance(db_url, str) and db_url.strip():
            return db_url
    
    # Fall back to legacy detection (to be deprecated)
    return _detect_database()


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
    # Check explicit env var first
    env_val = os.environ.get("COHERENCE_ENV", "").strip().lower()
    if env_val in ("production", "prod"):
        return "production"
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
    """Auto CORS origins — always include production + dev for safety."""
    return [
        "https://coherencycoin.com",
        "https://www.coherencycoin.com",
        "http://localhost:3000",
        "http://localhost:3001",
    ]


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
    """Auto-detect environment without requiring any config.
    
    DEPRECATED: This function is being replaced by config-file-based approach.
    Use get_database_url() and get_environment() for config-based detection.
    """
    # First try to load from api.json config
    api_json_config = _load_api_json_config()
    
    database_url = api_json_config.get("database_url") or _detect_database()
    environment = _detect_environment(database_url)
    node_id = _detect_node_id()
    cors_origins = _detect_cors_origins(environment)
    providers = _detect_providers()

    # Agent execute token settings (from env for backward compat)
    agent_execute_token = os.environ.get("AGENT_EXECUTE_TOKEN", "").strip()
    agent_execute_token_allow_unauth = os.environ.get("AGENT_EXECUTE_TOKEN_ALLOW_UNAUTH", "").strip()

    config = {
        "environment": environment,
        "database_url": database_url,
        "api_base": "https://api.coherencycoin.com" if environment == "production" else "http://localhost:8000",
        "hub_url": "https://api.coherencycoin.com",
        "web_ui_base_url": "https://coherencycoin.com" if environment == "production" else "http://localhost:3000",
        "providers": providers,
        "node_id": node_id,
        "cors_origins": cors_origins,
        "contributor_id": None,
        # Agent execute token settings
        "agent_execute_token": agent_execute_token or None,
        "agent_execute_token_allow_unauth": truthy(agent_execute_token_allow_unauth) if agent_execute_token_allow_unauth else None,
        # Pipeline settings defaults
        "pipeline_orphan_running_seconds": 1800,
        "pipeline_stale_running_seconds": 1800,
        "monitor_issues_max_age_seconds": 900,
        "pipeline_status_report_max_age_seconds": 900,
    }
    
    # Merge api.json config if it exists
    if api_json_config:
        for key, value in api_json_config.items():
            if value is not None:
                config[key] = value
        # Handle nested pipeline config
        pipeline_config = api_json_config.get("pipeline", {})
        if isinstance(pipeline_config, dict):
            for key in ["orphan_running_seconds", "stale_running_seconds", "monitor_max_age_seconds", "status_report_max_age_seconds"]:
                if key in pipeline_config:
                    # Map to flat keys
                    flat_key = f"pipeline_{key}"
                    config[flat_key] = pipeline_config[key]
        # Handle nested agent_tasks config
        agent_tasks_config = api_json_config.get("agent_tasks", {})
        if isinstance(agent_tasks_config, dict):
            for key in ["task_log_dir", "smart_reap_max_age_minutes"]:
                if key in agent_tasks_config:
                    config[key] = agent_tasks_config[key]
    
    return config


def _load_api_json_config() -> dict:
    """Load configuration from api/config/api.json file.
    
    Returns the config dict from api.json, or empty dict if not found.
    """
    # Find api directory (parent of app directory where this file lives)
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(current_dir)
    api_dir = os.path.dirname(app_dir)
    api_json_path = os.path.join(api_dir, "config", "api.json")
    
    if os.path.exists(api_json_path):
        try:
            with open(api_json_path, encoding="utf-8") as f:
                api_config = json.load(f)
            if isinstance(api_config, dict):
                # Extract database URL from nested structure
                db_config = api_config.get("database", {})
                if isinstance(db_config, dict) and db_config.get("url"):
                    api_config["database_url"] = db_config.get("url")
                return api_config
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load api.json config: %s", e)
    return {}


# ---------------------------------------------------------------------------
# Core config loader
# ---------------------------------------------------------------------------

def get_config() -> dict:
    """Load config with precedence:
      1. ~/.coherence-network/config.json  (highest — user overrides)
      2. Auto-detection                    (smart defaults)

    Never raises.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    # Layer 2: start with auto-detection defaults
    config: dict = {}
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

def get_api_key() -> str:
    return get_config().get("api_key", "dev-key")


def get_hub_url() -> str:
    return get_config().get("hub_url", "https://api.coherencycoin.com")


def get_database_url_from_config() -> str:
    """Get database URL from config (uses get_config which includes api.json).
    
    This is the preferred way to get the database URL.
    """
    return get_database_url()


def get_github_token() -> str | None:
    """Get GitHub token from keystore or config.
    
    Priority:
      1. ~/.coherence-network/keys.json -> github.token
      2. ~/.coherence-network/keys.json -> github_token
      3. Config file github_token field
      4. None (caller should handle missing token)
    """
    # Try keystore first
    keystore = _load_keystore()
    token = keystore.get("github", {}).get("token")
    if token:
        return str(token)
    token = keystore.get("github_token")
    if token:
        return str(token)
    
    # Try config
    config = get_config()
    token = config.get("github_token")
    if token:
        return str(token)
    
    return None


def resolve_cli_contributor_id() -> tuple[str | None, str]:
    """CLI/runner identity resolution (R3): env ID → legacy env → config file only.

    Does not use full ``get_config()`` merge — matches npm ``cc`` precedence.

    Returns ``(contributor_id or None, source label)`` for logging and display.
    """
    cid = os.environ.get("COHERENCE_CONTRIBUTOR_ID", "").strip()
    if cid:
        return cid, "env:COHERENCE_CONTRIBUTOR_ID"
    cid = os.environ.get("COHERENCE_CONTRIBUTOR", "").strip()
    if cid:
        return cid, "env:COHERENCE_CONTRIBUTOR (legacy)"
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cid = (data.get("contributor_id") or "").strip()
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


def get_oauth_config(provider: str) -> dict:
    """Return OAuth config for a provider (github, google, etc.).

    Config structure in ~/.coherence-network/config.json:
      {"oauth": {"github": {"client_id": "", "client_secret": ""}, ...}}

    Returns empty dict if not configured.
    """
    config = get_config()
    return config.get("oauth", {}).get(provider, {})


def reset_config_cache():
    global _CACHE
    _CACHE = None
