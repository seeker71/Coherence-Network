#!/usr/bin/env python3
"""Local guard: ensure Vercel does not auto-deploy on PR/non-main branches.

This repo is a monorepo. Depending on the Vercel project's configured Root Directory,
Vercel will read either:

- ./vercel.json (project root = repo root)
- ./web/vercel.json (project root = web/)

We validate both to avoid accidental regressions when the Vercel configuration changes.

Policy:
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


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")


def _validate_policy(path: Path) -> None:
    data = _load(path)

    git_cfg = data.get("git")
    if not isinstance(git_cfg, dict):
        raise ValueError('Expected top-level "git" object')

    dep_enabled = git_cfg.get("deploymentEnabled")
    if not isinstance(dep_enabled, dict):
        raise ValueError('Expected "git.deploymentEnabled" object')

    if dep_enabled.get("main") is not True:
        raise ValueError('Expected "git.deploymentEnabled.main" to be true')
    if dep_enabled.get("*") is not False:
        raise ValueError('Expected "git.deploymentEnabled.\"*\"" to be false')


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    candidates = [
        repo_root / "vercel.json",
        repo_root / "web" / "vercel.json",
    ]

    missing = [p for p in candidates if not p.exists()]
    if missing:
        # Keep this strict: missing either file means the policy can silently stop applying
        # depending on how the Vercel project is configured.
        return _fail("Missing required Vercel config file(s): " + ", ".join(str(p) for p in missing))

    for path in candidates:
        try:
            _validate_policy(path)
        except Exception as e:
            return _fail(f"{path}: {e}")

    print("OK: Vercel deployments enabled only for main (root + web configs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
