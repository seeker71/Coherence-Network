#!/usr/bin/env python3
"""Local guard: ensure Vercel does not auto-deploy on PR/non-main branches.

This relies on Vercel project configuration via web/vercel.json:
  git.deploymentEnabled.main == true
  git.deploymentEnabled["*"] == false
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    vercel_config_path = repo_root / "web" / "vercel.json"

    if not vercel_config_path.exists():
        return _fail(f"Missing {vercel_config_path}")

    try:
        data = json.loads(vercel_config_path.read_text(encoding="utf-8"))
    except Exception as e:
        return _fail(f"Invalid JSON in {vercel_config_path}: {e}")

    git_cfg = data.get("git")
    if not isinstance(git_cfg, dict):
        return _fail('Expected top-level "git" object in web/vercel.json')

    dep_enabled = git_cfg.get("deploymentEnabled")
    if not isinstance(dep_enabled, dict):
        return _fail('Expected "git.deploymentEnabled" object in web/vercel.json')

    main_enabled = dep_enabled.get("main")
    wildcard_enabled = dep_enabled.get("*")

    if main_enabled is not True:
        return _fail('Expected "git.deploymentEnabled.main" to be true')
    if wildcard_enabled is not False:
        return _fail('Expected "git.deploymentEnabled.\\"*\\"" to be false')

    print("OK: Vercel deployments enabled only for main.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
