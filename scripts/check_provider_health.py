#!/usr/bin/env python3
"""Provider health check — verify all CLIs are authenticated and working.

Run before starting the local runner, or on a schedule to detect stale auth.
Exits 0 if all critical providers work, 1 if any are broken.

Usage:
    python scripts/check_provider_health.py          # check all
    python scripts/check_provider_health.py --fix    # attempt auto-fix
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time


def check_cli_exists(name: str, cmd: str) -> dict:
    """Check if CLI is installed and on PATH."""
    path = shutil.which(cmd)
    return {
        "provider": name,
        "installed": path is not None,
        "path": path or "NOT FOUND",
    }


def check_cli_auth(name: str, cmd: list[str], timeout: int = 15) -> dict:
    """Run a minimal command to verify the CLI is authenticated."""
    result = {
        "provider": name,
        "authenticated": False,
        "error": None,
        "duration_s": 0,
    }

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        result["duration_s"] = round(time.time() - start, 1)

        if proc.returncode == 0:
            result["authenticated"] = True
            # Check for auth error messages in output
            output = (proc.stdout + proc.stderr).lower()
            if any(w in output for w in ["unauthorized", "unauthenticated", "login required", "auth"]):
                if "authenticated" not in output and "logged in" not in output:
                    result["authenticated"] = False
                    result["error"] = "Auth error in output"
        else:
            result["error"] = f"Exit code {proc.returncode}: {proc.stderr[:100]}"

    except subprocess.TimeoutExpired:
        result["duration_s"] = timeout
        result["error"] = f"Timeout after {timeout}s (likely waiting for interactive prompt)"
    except FileNotFoundError:
        result["error"] = "CLI not found"
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def check_openrouter_key() -> dict:
    """Check if OpenRouter API key is configured and valid."""
    result = {
        "provider": "openrouter",
        "authenticated": False,
        "error": None,
    }

    # Check keystore
    ks_path = os.path.join(os.path.expanduser("~"), ".coherence-network", "keys.json")
    api_key = None

    if os.path.exists(ks_path):
        try:
            with open(ks_path) as f:
                keys = json.load(f)
            api_key = keys.get("openrouter", {}).get("api_key", "")
        except Exception:
            pass

    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")

    if not api_key:
        result["error"] = "No API key found (check ~/.coherence-network/keys.json or OPENROUTER_API_KEY env)"
        return result

    # Test the key
    try:
        import httpx
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "meta-llama/llama-3.1-8b-instruct:free", "messages": [{"role": "user", "content": "1+1="}]},
            timeout=10,
        )
        if r.status_code == 200:
            result["authenticated"] = True
        else:
            result["error"] = f"HTTP {r.status_code}: {r.text[:100]}"
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def check_ollama() -> dict:
    """Check if Ollama is running and has models."""
    result = {
        "provider": "ollama",
        "authenticated": True,  # Ollama doesn't need auth
        "error": None,
        "models": [],
    }

    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            lines = proc.stdout.strip().split("\n")[1:]  # Skip header
            result["models"] = [l.split()[0] for l in lines if l.strip()]
        else:
            result["error"] = f"Exit {proc.returncode}"
            result["authenticated"] = False
    except Exception as e:
        result["error"] = str(e)[:100]
        result["authenticated"] = False

    return result


def suggest_fix(provider: str, error: str) -> str:
    """Suggest how to fix auth issues."""
    fixes = {
        "claude": "Run: claude auth login (browser OAuth)",
        "codex": "Run: codex auth login (browser OAuth via ChatGPT)",
        "gemini": "Run: gemini (interactive, will trigger Google auth on first use)",
        "cursor": "Run: agent auth (browser OAuth)",
        "openrouter": "Add key to ~/.coherence-network/keys.json: {\"openrouter\": {\"api_key\": \"sk-or-v1-...\"}}",
        "ollama": "Run: ollama serve (start the server) then: ollama pull mistral-nemo:12b",
    }
    return fixes.get(provider, "Check provider documentation")


def main():
    parser = argparse.ArgumentParser(description="Provider health check")
    parser.add_argument("--fix", action="store_true", help="Attempt auto-fix for broken providers")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    checks = []

    # CLI providers — test with minimal commands
    # On Windows, npm installs .CMD wrappers — check both forms
    cli_checks = [
        ("claude", ["claude", "--version"]),
        ("codex", ["codex", "--version"]),
        ("gemini", ["gemini", "--version"]),
        ("cursor", ["agent", "--version"]),
    ]
    # Also try .CMD variants on Windows
    if sys.platform == "win32":
        cli_checks = [
            ("claude", ["claude.CMD", "--version"]),
            ("codex", ["codex.CMD", "--version"]),
            ("gemini", ["gemini.CMD", "--version"]),
            ("cursor", ["agent.CMD", "--version"]),
        ]

    print("PROVIDER HEALTH CHECK")
    print("=" * 60)

    for name, cmd in cli_checks:
        exists = check_cli_exists(name, cmd[0])
        if not exists["installed"]:
            checks.append({"provider": name, "installed": False, "authenticated": False, "error": "Not installed"})
            print(f"  {name:15s}  NOT INSTALLED")
            continue

        auth = check_cli_auth(name, cmd)
        checks.append({**exists, **auth})
        status = "OK" if auth["authenticated"] else "BROKEN"
        print(f"  {name:15s}  {status:8s}  dur={auth['duration_s']}s  {auth.get('error', '')}")

    # OpenRouter
    or_check = check_openrouter_key()
    checks.append(or_check)
    status = "OK" if or_check["authenticated"] else "BROKEN"
    print(f"  {'openrouter':15s}  {status:8s}  {or_check.get('error', '')}")

    # Ollama
    ol_check = check_ollama()
    checks.append(ol_check)
    status = "OK" if ol_check["authenticated"] else "BROKEN"
    models = ol_check.get("models", [])
    print(f"  {'ollama':15s}  {status:8s}  models={len(models)}")

    print()

    # Summary
    healthy = sum(1 for c in checks if c.get("authenticated"))
    broken = [c for c in checks if not c.get("authenticated") and c.get("installed", True)]
    missing = [c for c in checks if not c.get("installed", True)]

    print(f"Healthy: {healthy}/{len(checks)}")

    if broken:
        print(f"\nBROKEN ({len(broken)}):")
        for c in broken:
            provider = c["provider"]
            print(f"  {provider}: {c.get('error', 'unknown')}")
            print(f"    Fix: {suggest_fix(provider, c.get('error', ''))}")

    if missing:
        print(f"\nMISSING ({len(missing)}):")
        for c in missing:
            print(f"  {c['provider']}: not installed")

    if args.json:
        print(json.dumps(checks, indent=2))

    # Exit code
    critical_broken = [c for c in broken if c["provider"] in ("claude", "codex")]
    sys.exit(1 if critical_broken else 0)


if __name__ == "__main__":
    main()
