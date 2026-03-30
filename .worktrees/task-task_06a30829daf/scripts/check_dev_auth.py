#!/usr/bin/env python3
"""Preflight: verify local GitHub auth is usable for Codex automation.

This script is safe to run in CI or locally. It never prints token values.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from shutil import which


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str | None = None


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _gh_auth_status() -> CheckResult:
    if which("gh") is None:
        return CheckResult(name="gh_installed", ok=False, detail="gh not found on PATH")
    r = _run(["gh", "auth", "status"])
    ok = r.returncode == 0
    # Keep detail short and non-sensitive.
    detail = None
    if not ok:
        detail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or None
        detail = detail[0] if isinstance(detail, list) and detail else "gh auth status failed"
    return CheckResult(name="gh_auth", ok=ok, detail=detail)


def _gh_token_env() -> CheckResult:
    token = os.getenv("GH_TOKEN", "")
    ok = bool(token)
    return CheckResult(
        name="gh_token_env",
        ok=ok,
        detail=f"len={len(token)}" if ok else "GH_TOKEN is empty",
    )


def _gh_token_login_shell() -> CheckResult:
    if which("zsh") is None:
        return CheckResult(name="gh_token_login_shell", ok=False, detail="zsh not found on PATH")
    # Do not echo token. Only print length.
    r = _run(["zsh", "-lc", "echo ${#GH_TOKEN}"])
    if r.returncode != 0:
        return CheckResult(name="gh_token_login_shell", ok=False, detail="zsh -lc failed")
    value = (r.stdout or "").strip()
    try:
        length = int(value)
    except ValueError:
        length = 0
    ok = length > 0
    return CheckResult(
        name="gh_token_login_shell",
        ok=ok,
        detail=f"len={length}" if ok else "GH_TOKEN not set in login shell",
    )


def _api_env_has_github_token(repo_root: Path) -> CheckResult:
    env_path = repo_root / "api" / ".env"
    if not env_path.exists():
        return CheckResult(name="api_env_github_token", ok=True, detail="api/.env missing (ok)")
    try:
        keys = {
            line.split("=", 1)[0].strip()
            for line in env_path.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        }
    except OSError as exc:
        return CheckResult(name="api_env_github_token", ok=False, detail=str(exc))
    ok = "GITHUB_TOKEN" in keys
    return CheckResult(
        name="api_env_github_token",
        ok=ok,
        detail="present" if ok else "missing GITHUB_TOKEN key",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    gh_auth = _gh_auth_status()
    token_env = _gh_token_env()
    token_login = _gh_token_login_shell()
    api_env = _api_env_has_github_token(repo_root)

    gh_token_ok = token_env.ok or token_login.ok
    derived = [
        CheckResult(
            name="gh_token_available",
            ok=gh_token_ok,
            detail="env_or_login_shell" if gh_token_ok else "missing",
        )
    ]

    checks = [gh_auth, token_env, token_login, api_env, *derived]
    ok = bool(gh_auth.ok and gh_token_ok and api_env.ok)
    payload = {"ok": ok, "checks": [asdict(c) for c in checks]}

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for c in checks:
            status = "OK" if c.ok else "FAIL"
            detail = f" ({c.detail})" if c.detail else ""
            print(f"{status}: {c.name}{detail}")
        print(f"overall_ok={payload['ok']}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
