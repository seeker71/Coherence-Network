"""File configuration for the existing MCP transport carrier, without env fallbacks."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

_REPO = Path(__file__).resolve().parents[2]


class SettingsError(ValueError):
    """Persisted MCP configuration cannot safely select a transport."""


def load_settings(*, repo: Path | None = None, home: Path | None = None) -> dict:
    """Read defaults, repository configuration, then the person's local overlay.

    This is packaging I/O for the Python MCP bridge, not a second policy engine.
    Malformed configured files fail closed instead of selecting another service.
    """
    root = repo if repo is not None else _REPO
    personal = home if home is not None else Path.home()
    result = {
        "api_base": "https://api.coherencycoin.com",
        "api_key": "",
        "capability_profile": "companion",
        "grounded_ask_timeout_seconds": 90,
        "catalog_path": str(personal / ".coherence-network" / "form-cli-catalog.jsonl"),
        "kernel_path": str(root / "form" / "fkwu"),
    }
    for path in (root / "api" / "config" / "api.json", personal / ".coherence-network" / "config.json"):
        try:
            with path.open(encoding="utf-8") as source:
                document = json.load(source)
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            raise SettingsError(f"Cannot read MCP configuration at {path}; check file access and JSON syntax.") from None
        if not isinstance(document, dict) or not isinstance(document.get("mcp", {}), dict):
            raise SettingsError(f"MCP configuration at {path} must contain an object named mcp.")
        result.update({key: value for key, value in document.get("mcp", {}).items() if key in result})
    if any(not isinstance(value, str) for key, value in result.items() if key != "grounded_ask_timeout_seconds"):
        raise SettingsError("MCP connection and path configuration fields must be strings.")
    if result["capability_profile"] not in {"companion", "advanced"}:
        raise SettingsError("mcp.capability_profile must be companion or advanced.")
    timeout = result["grounded_ask_timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= 900:
        raise SettingsError("mcp.grounded_ask_timeout_seconds must be an integer from 1 to 900.")
    try:
        url = urlsplit(result["api_base"])
        valid = url.scheme in {"https", "http"} and bool(url.hostname) and not (
            url.username or url.password or url.query or url.fragment
        )
        _ = url.port
    except ValueError:
        valid = False
    if not valid:
        raise SettingsError("mcp.api_base must be an HTTP(S) URL without credentials, query or fragment.")
    result["api_base"] = result["api_base"].rstrip("/")
    for key in ("catalog_path", "kernel_path"):
        path = Path(result[key]).expanduser()
        if not path.is_absolute():
            raise SettingsError(f"mcp.{key} must be an absolute path or start with ~/.")
        result[key] = str(path)
    return result
