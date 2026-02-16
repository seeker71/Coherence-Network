#!/usr/bin/env python3
"""Validate per-worktree bootstrap/readiness before local validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_module(python_bin: Path, module: str) -> bool:
    cmd = [str(python_bin), "-c", f"import {module}"]
    return subprocess.run(cmd, capture_output=True, text=True, check=False).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default="",
        help="Optional repository root path. Defaults to git top-level from current working directory.",
    )
    args = parser.parse_args()

    if str(args.repo_root).strip():
        repo_root = Path(str(args.repo_root).strip()).resolve()
    else:
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()
            repo_root = Path(out).resolve()
        except Exception:
            repo_root = Path.cwd().resolve()

    doc_path = repo_root / "docs" / "WORKTREE-SETUP.md"
    ack_path = repo_root / ".worktree-state" / "setup_ack.json"
    python_bin = repo_root / "api" / ".venv" / "bin" / "python"
    node_modules = repo_root / "web" / "node_modules"

    errors: list[str] = []

    if not doc_path.is_file():
        errors.append(f"missing setup guide: {doc_path}")

    if not ack_path.is_file():
        errors.append("missing worktree bootstrap ack (.worktree-state/setup_ack.json)")
    else:
        try:
            ack = json.loads(ack_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"cannot parse ack file: {exc}")
            ack = {}
        expected_sha = _hash_file(doc_path) if doc_path.is_file() else ""
        ack_sha = str(ack.get("doc_sha256") or "").strip()
        if expected_sha and ack_sha != expected_sha:
            errors.append("worktree bootstrap ack is stale (doc hash mismatch)")

    if not python_bin.is_file():
        errors.append("missing api virtualenv python (api/.venv/bin/python)")
    else:
        for module in ("pytest", "fastapi", "uvicorn"):
            if not _has_module(python_bin, module):
                errors.append(f"api virtualenv missing required module: {module}")

    if not node_modules.is_dir():
        errors.append("missing web/node_modules (run npm ci)")

    if errors:
        print("ERROR: worktree bootstrap guard failed:")
        for err in errors:
            print(f"- {err}")
        print("Run: ./scripts/worktree_bootstrap.sh")
        return 1

    print("OK: worktree bootstrap guard passed")
    print(f"ack_file={ack_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
