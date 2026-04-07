#!/usr/bin/env python3
"""Show active worktrees, their branches, and potential conflicts.

Usage:
    python3 scripts/agent_status.py          # summary view
    python3 scripts/agent_status.py --diff   # include changed-file overlap detection
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def run(cmd: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def get_worktrees(repo_root: str) -> list[dict[str, str]]:
    raw = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line == "detached":
            current["branch"] = "(detached)"
    if current:
        worktrees.append(current)
    return worktrees


def get_changed_files(worktree_path: str) -> list[str]:
    """Return files changed vs main (staged + unstaged + untracked)."""
    diff_vs_main = run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=worktree_path,
    )
    diff_local = run(
        ["git", "diff", "--name-only"],
        cwd=worktree_path,
    )
    staged = run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=worktree_path,
    )
    files = set()
    for output in (diff_vs_main, diff_local, staged):
        for f in output.splitlines():
            if f.strip():
                files.add(f.strip())
    return sorted(files)


def detect_conflicts(worktrees: list[dict[str, str]]) -> list[str]:
    """Find files modified in more than one worktree."""
    file_to_worktrees: dict[str, list[str]] = defaultdict(list)
    for wt in worktrees:
        path = wt["path"]
        branch = wt.get("branch", "?")
        for f in get_changed_files(path):
            file_to_worktrees[f].append(branch)

    conflicts = []
    for filepath, branches in sorted(file_to_worktrees.items()):
        if len(branches) > 1:
            conflicts.append(f"  {filepath}  ({', '.join(branches)})")
    return conflicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Show active agent worktrees and conflict warnings")
    parser.add_argument("--diff", action="store_true", help="Check for file-level conflicts across worktrees")
    args = parser.parse_args()

    # Find repo root
    repo_root = run(["git", "rev-parse", "--show-toplevel"])
    if not repo_root:
        print("Not in a git repository", file=sys.stderr)
        sys.exit(1)

    # If we're in a worktree, go to the main working tree
    common_dir = run(["git", "rev-parse", "--git-common-dir"])
    if common_dir and not common_dir.endswith("/.git"):
        repo_root = str(Path(common_dir).parent)

    worktrees = get_worktrees(repo_root)

    print(f"Active worktrees: {len(worktrees)}\n")
    for wt in worktrees:
        path = wt["path"]
        branch = wt.get("branch", "(detached)")
        head = wt.get("head", "?")[:8]
        is_main = "main" in branch or path == repo_root
        label = " [main]" if is_main else ""
        print(f"  {branch}{label}")
        print(f"    path: {path}")
        print(f"    HEAD: {head}")
        if args.diff and not is_main:
            changed = get_changed_files(path)
            if changed:
                print(f"    changed: {len(changed)} files")
            else:
                print("    changed: (clean)")
        print()

    if args.diff:
        non_main = [wt for wt in worktrees if "main" not in wt.get("branch", "") and wt["path"] != repo_root]
        if len(non_main) >= 2:
            conflicts = detect_conflicts(non_main)
            if conflicts:
                print("CONFLICT WARNING — files modified in multiple worktrees:")
                for c in conflicts:
                    print(c)
            else:
                print("No file conflicts detected across worktrees.")
        else:
            print("Only one active worktree branch — no conflict check needed.")


if __name__ == "__main__":
    main()
