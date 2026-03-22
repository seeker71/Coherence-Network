#!/usr/bin/env python3
"""Coherence Network — Auto-Setup.

Detects environment, configures everything, creates database tables,
registers this node. No manual steps unless something needs user input.

Usage:
    python scripts/setup.py
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
AMBER = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

CONFIG_DIR = Path.home() / ".coherence-network"
CONFIG_PATH = CONFIG_DIR / "config.json"
KEYS_PATH = CONFIG_DIR / "keys.json"


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    suffix = f" ({detail})" if detail else ""
    print(f"  {icon} {label}{suffix}")
    return ok


def detect_python() -> bool:
    ver = sys.version_info
    return check("Python", ver >= (3, 10), f"{ver.major}.{ver.minor}.{ver.micro}")


def detect_database() -> tuple[bool, str]:
    """Check for PostgreSQL, fall back to SQLite."""
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1)
        s.close()
        url = os.environ.get("DATABASE_URL", "postgresql://coherence:coherence@localhost:5432/coherence")
        check("PostgreSQL", True, "localhost:5432")
        return True, url
    except (OSError, ConnectionRefusedError):
        db_path = Path(__file__).resolve().parents[1] / "api" / "data" / "coherence.db"
        url = f"sqlite:///{db_path}"
        check("Database", True, f"SQLite at {db_path.name}")
        return True, url


def detect_providers() -> list[str]:
    """Auto-detect which AI provider CLIs are installed."""
    providers = []
    checks = [
        ("claude", "claude"),
        ("codex", "codex"),
        ("gemini", "gemini"),
        ("cursor", "agent"),
        ("ollama", "ollama"),
    ]
    for name, binary in checks:
        path = shutil.which(binary)
        if path:
            providers.append(name)
            check(f"Provider: {name}", True, path)
        # Don't print missing providers — not an error

    if not providers:
        check("Providers", False, "No AI providers found. Install claude, codex, gemini, or ollama.")

    return providers


def detect_node_identity() -> str:
    """Get or create stable node identity."""
    node_id_path = CONFIG_DIR / "node_id"
    if node_id_path.exists():
        node_id = node_id_path.read_text().strip()
        check("Node ID", True, node_id)
        return node_id

    # Generate from hostname + MAC
    import hashlib
    import uuid
    hostname = socket.gethostname()
    mac = uuid.getnode()
    node_id = hashlib.sha256(f"{hostname}:{mac}".encode()).hexdigest()[:16]

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    node_id_path.write_text(node_id)
    check("Node ID", True, f"{node_id} (created)")
    return node_id


def detect_config() -> dict:
    """Load or create config."""
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
            check("Config", True, str(CONFIG_PATH))
            return config
        except json.JSONDecodeError:
            check("Config", False, f"{CONFIG_PATH} is invalid JSON")
    else:
        check("Config", True, "auto-detected (no config file needed)")
    return {}


def detect_keys() -> dict:
    """Load keystore."""
    if KEYS_PATH.exists():
        try:
            keys = json.loads(KEYS_PATH.read_text())
            key_names = [f"{p}:{k}" for p, ks in keys.items() for k in ks]
            check("Keys", True, f"{len(key_names)} keys loaded")
            return keys
        except json.JSONDecodeError:
            check("Keys", False, f"{KEYS_PATH} is invalid JSON")
    else:
        check("Keys", True, "no keys file (optional)")
    return {}


def create_tables(db_url: str) -> bool:
    """Create database tables if they don't exist."""
    try:
        # Add api/ to path so imports work
        api_dir = Path(__file__).resolve().parents[1] / "api"
        sys.path.insert(0, str(api_dir))

        os.environ.setdefault("DATABASE_URL", db_url)

        from app.services.unified_models import Base
        from sqlalchemy import create_engine

        # Ensure directory exists for SQLite
        if "sqlite" in db_url:
            db_file = db_url.replace("sqlite:///", "")
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        engine.dispose()

        return check("Database tables", True, "created/verified")
    except Exception as e:
        return check("Database tables", False, str(e)[:80])


def register_node(node_id: str, providers: list[str]) -> bool:
    """Register this node with the federation hub."""
    hub_url = os.environ.get("COHERENCE_HUB_URL", "https://api.coherencycoin.com")
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "node_id": node_id,
            "hostname": socket.gethostname(),
            "os_type": sys.platform,
            "providers": providers,
            "capabilities": {},
        }).encode()

        req = urllib.request.Request(
            f"{hub_url}/api/federation/nodes",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            if status in (200, 201):
                return check("Node registration", True, f"registered with {hub_url}")
            return check("Node registration", False, f"HTTP {status}")
    except urllib.error.URLError:
        return check("Node registration", False, f"hub unreachable at {hub_url} (will retry later)")
    except Exception as e:
        return check("Node registration", False, str(e)[:60])


def save_config(db_url: str, providers: list[str], node_id: str) -> None:
    """Save detected config for future runs."""
    if CONFIG_PATH.exists():
        return  # Don't overwrite user config

    config = {
        "api_base": "auto",
        "database_url": db_url,
        "hub_url": "https://api.coherencycoin.com",
        "contributor_id": None,
        "providers": providers,
        "environment": "development",
        "node_id": node_id,
    }

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"\n  Config saved to {CONFIG_PATH}")


def main() -> None:
    print(f"\n{BOLD}Coherence Network Setup{RESET}")
    print("=" * 40)
    print()
    print("Detecting environment...")

    # Detect everything
    python_ok = detect_python()
    db_ok, db_url = detect_database()
    providers = detect_providers()
    node_id = detect_node_identity()
    config = detect_config()
    keys = detect_keys()

    print()

    # Set up
    if db_ok:
        create_tables(db_url)

    register_node(node_id, providers)
    save_config(db_url, providers, node_id)

    # Summary
    print()
    print(f"{BOLD}Ready!{RESET} Run:")
    print()

    api_dir = Path(__file__).resolve().parents[1] / "api"
    print(f"  cd {api_dir}")
    print(f"  python -m uvicorn app.main:app        {AMBER}# Start API{RESET}")
    print(f"  python scripts/local_runner.py         {AMBER}# Execute tasks{RESET}")
    print()

    if not providers:
        print(f"  {AMBER}Note: Install at least one AI provider (claude, codex, gemini, ollama){RESET}")
        print(f"  {AMBER}to start executing tasks.{RESET}")
        print()


if __name__ == "__main__":
    main()
