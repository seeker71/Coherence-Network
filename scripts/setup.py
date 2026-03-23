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


def ask_confirm(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question. Returns default if stdin is not a tty."""
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        if not sys.stdin.isatty():
            return default
        answer = input(f"  {prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return default


def save_config(
    db_url: str,
    providers: list[str],
    node_id: str,
    environment: str = "development",
    hub_url: str = "https://api.coherencycoin.com",
    cors_origins: list[str] | None = None,
    *,
    force: bool = False,
) -> None:
    """Save detected config to ~/.coherence-network/config.json."""
    if CONFIG_PATH.exists() and not force:
        return  # Don't overwrite user config

    config = {
        "_comment": "Auto-generated by scripts/setup.py. Edit to override auto-detection.",
        "environment": environment,
        "hub_url": hub_url,
        "database_url": db_url,
        "cors_origins": cors_origins or ["http://localhost:3000"],
        "providers": providers,
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

    # --- Phase 1: Auto-detect everything ---
    python_ok = detect_python()
    db_ok, db_url = detect_database()
    providers = detect_providers()
    node_id = detect_node_identity()
    existing_config = detect_config()
    keys = detect_keys()

    # --- Phase 2: Guided confirmation (only when ambiguous) ---
    print()
    print(f"{BOLD}Configuration{RESET}")
    print("-" * 40)

    # Database confirmation
    if "postgresql" in db_url:
        if not ask_confirm(f"PostgreSQL found at localhost:5432. Use it?"):
            db_path = Path(__file__).resolve().parents[1] / "api" / "data" / "coherence.db"
            db_url = f"sqlite:///{db_path}"
            check("Database", True, f"Switched to SQLite at {db_path.name}")

    # Environment
    environment = "development"
    hostname = socket.gethostname()
    if "srv1482815" in hostname or "hostinger" in hostname.lower():
        environment = "production"
        check("Environment", True, "production (VPS detected)")
    else:
        check("Environment", True, "development (localhost)")

    # Hub URL
    hub_url = "https://api.coherencycoin.com"
    check("Hub URL", True, hub_url)

    # CORS origins
    if environment == "production":
        cors_origins = ["https://coherencycoin.com", "https://www.coherencycoin.com"]
    else:
        cors_origins = ["http://localhost:3000"]
    check("CORS origins", True, ", ".join(cors_origins))

    print()

    # --- Phase 3: Create DB tables ---
    if db_ok:
        create_tables(db_url)

    # --- Phase 4: Register node ---
    register_node(node_id, providers)

    # --- Phase 5: Write config ---
    write_config = True
    if CONFIG_PATH.exists():
        write_config = ask_confirm(f"Config already exists at {CONFIG_PATH}. Overwrite?", default=False)

    if write_config:
        save_config(
            db_url, providers, node_id,
            environment=environment,
            hub_url=hub_url,
            cors_origins=cors_origins,
            force=True,
        )

    # --- Phase 6: Summary ---
    print()
    print(f"{BOLD}Summary{RESET}")
    print("-" * 40)
    print(f"  Environment:  {environment}")
    print(f"  Database:     {db_url[:60]}{'...' if len(db_url) > 60 else ''}")
    print(f"  Node ID:      {node_id}")
    print(f"  Providers:    {', '.join(providers) if providers else 'none detected'}")
    print(f"  Hub URL:      {hub_url}")
    print(f"  CORS:         {', '.join(cors_origins)}")
    print(f"  Config:       {CONFIG_PATH}")
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
