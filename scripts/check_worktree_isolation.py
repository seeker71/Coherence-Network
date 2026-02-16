#!/usr/bin/env python3
"""Ensure local automation runs from a linked git worktree, not the main checkout."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _is_linked_worktree(repo_root: Path) -> tuple[bool, str]:
    git_path = repo_root / ".git"
    if git_path.is_dir():
        return False, ".git is a directory (primary checkout)"
    if not git_path.is_file():
        return False, ".git file is missing"
    try:
        text = git_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return False, f"cannot read .git file: {exc}"
    if "gitdir:" not in text:
        return False, ".git file missing gitdir pointer"
    pointer = text.split("gitdir:", 1)[1].strip()
    normalized = pointer.replace("\\", "/")
    if "/.git/worktrees/" not in normalized:
        return False, ".git does not point to a linked worktree path"
    return True, "linked worktree detected"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-main-checkout", action="store_true")
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
    ok, reason = _is_linked_worktree(repo_root)
    print(f"repo_root={repo_root}")
    print(f"worktree_guard={reason}")

    if ok:
        return 0
    if args.allow_main_checkout:
        print("WARNING: main checkout override enabled; continuing.")
        return 0
    print("ERROR: run this from a linked git worktree, not the main repository checkout.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
