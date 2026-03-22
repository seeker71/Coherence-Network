import json, shutil, socket, logging, os
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".coherence-network"
_CONFIG_PATH = _CONFIG_DIR / "config.json"
_KEYS_PATH = _CONFIG_DIR / "keys.json"
_CACHE = None

def _auto_detect():
    """Auto-detect environment without requiring any config."""
    config = {
        "api_base": "http://localhost:8000",
        "hub_url": "https://api.coherencycoin.com",
        "database_url": _detect_database(),
        "providers": _detect_providers(),
        "contributor_id": None,
        "environment": "development",
    }
    # If running on the VPS, switch to production
    hostname = socket.gethostname()
    if "srv1482815" in hostname or "hostinger" in hostname.lower():
        config["environment"] = "production"
        config["api_base"] = "https://api.coherencycoin.com"
    return config

def _detect_database():
    """Check if postgres is reachable, else use sqlite."""
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1)
        s.close()
        return "postgresql://coherence:coherence@localhost:5432/coherence"
    except (OSError, ConnectionRefusedError):
        return "sqlite:///data/coherence.db"

def _detect_providers():
    """Auto-detect which AI provider CLIs are installed."""
    providers = []
    for name, binary in [("claude", "claude"), ("codex", "codex"), ("gemini", "gemini"), ("cursor", "agent")]:
        if shutil.which(binary):
            providers.append(name)
    # Check ollama
    if shutil.which("ollama"):
        providers.append("ollama")
    return providers

def get_config():
    """Load config with precedence: ~/.coherence-network/config.json > auto-detect.
    Env vars override individual fields."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    
    # Start with auto-detect
    config = _auto_detect()
    
    # Merge user config if exists
    if _CONFIG_PATH.exists():
        try:
            user_config = json.loads(_CONFIG_PATH.read_text())
            for k, v in user_config.items():
                if v != "auto" and v is not None:
                    config[k] = v
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load %s", _CONFIG_PATH, exc_info=True)
    
    # Merge keys
    if _KEYS_PATH.exists():
        try:
            keys = json.loads(_KEYS_PATH.read_text())
            config["keys"] = keys
        except (json.JSONDecodeError, OSError):
            config["keys"] = {}
    else:
        config["keys"] = {}
    
    # Env var overrides (optional, not required)
    for env_key, config_key in [
        ("COHERENCE_API_BASE", "api_base"),
        ("DATABASE_URL", "database_url"),
        ("COHERENCE_HUB_URL", "hub_url"),
        ("COHERENCE_ENV", "environment"),
        ("COHERENCE_CONTRIBUTOR_ID", "contributor_id"),
    ]:
        val = os.environ.get(env_key, "").strip()
        if val:
            config[config_key] = val
    
    _CACHE = config
    logger.info("Config loaded: env=%s api=%s db=%s providers=%s",
                config["environment"], config["api_base"],
                config["database_url"][:30] + "...", config["providers"])
    return config

def get_api_base(): return get_config()["api_base"]
def get_database_url(): return get_config()["database_url"]
def get_hub_url(): return get_config()["hub_url"]
def get_environment(): return get_config()["environment"]
def get_contributor_id(): return get_config().get("contributor_id")
def get_key(provider, key_name): return get_config().get("keys", {}).get(provider, {}).get(key_name, "")
def is_production(): return get_config()["environment"] == "production"
def reset_config_cache():
    global _CACHE
    _CACHE = None
