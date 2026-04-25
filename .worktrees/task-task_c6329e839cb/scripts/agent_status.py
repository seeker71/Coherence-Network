#!/usr/bin/env python3
"""Show active work across all coding agents (worktrees + tasks).

Usage:
    python3 scripts/agent_status.py          # human-readable output
    python3 scripts/agent_status.py --json   # machine-readable output

Cross-references git worktrees with running tasks from the API to show:
- Which worktrees exist and their git state (branch, dirty, ahead/behind)
- Which tasks are claimed/running and by whom
- File-level conflict warnings when two worktrees touch the same files
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


API = os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com")


# ── Git helpers (reused from worktree_continuity_guard.py patterns) ──


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _repo_root() -> Path:
    proc = _run_git(["rev-parse", "--show-toplevel"], Path.cwd())
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "not a git repository")
    return Path(proc.stdout.strip()).resolve()


def _parse_worktrees(repo_root: Path) -> list[dict[str, str]]:
    proc = _run_git(["worktree", "list", "--porcelain"], repo_root)
    if proc.returncode != 0:
        return []
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line:
            if current:
                rows.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        rows.append(current)
    return rows


def _branch_name(wt_path: Path, branch_ref: str) -> str:
    if branch_ref.startswith("refs/heads/"):
        return branch_ref.replace("refs/heads/", "", 1)
    proc = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], wt_path)
    return proc.stdout.strip() if proc.returncode == 0 else "(detached)"


def _ahead_behind(wt_path: Path) -> tuple[int, int]:
    proc = _run_git(["rev-list", "--left-right", "--count", "origin/main...HEAD"], wt_path)
    if proc.returncode != 0:
        return 0, 0
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[1]), int(parts[0])  # ahead, behind
    except ValueError:
        return 0, 0


def _dirty_files(wt_path: Path) -> list[str]:
    proc = _run_git(["status", "--short", "--untracked-files=all"], wt_path)
    if proc.returncode != 0:
        return []
    paths: list[str] = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        payload = raw[3:] if len(raw) >= 4 else ""
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        payload = payload.strip()
        if payload:
            paths.append(payload)
    return paths


def _worktree_name(wt_path: str) -> str:
    """Extract a short name from a worktree path."""
    p = Path(wt_path)
    # .claude/worktrees/{name} pattern
    if ".claude" in p.parts and "worktrees" in p.parts:
        return p.name
    # .codex/worktrees/{hash}/RepoName pattern
    if ".codex" in p.parts and "worktrees" in p.parts:
        parts = list(p.parts)
        try:
            idx = parts.index("worktrees")
            return f"codex-{parts[idx + 1][:6]}"
        except (ValueError, IndexError):
            pass
    # Main repo
    return p.name


# ── API helpers ──


def _api_get(path: str) -> Any:
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5", f"{API}{path}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def _fetch_running_tasks() -> list[dict]:
    """Fetch tasks with status=running from the API."""
    data = _api_get("/api/agent/tasks?status=running&limit=50")
    if isinstance(data, dict):
        return data.get("items", data.get("tasks", []))
    if isinstance(data, list):
        return data
    return []


# ── Spec source map ──


def _spec_source_files(spec_slug: str, repo_root: Path) -> list[str]:
    """Read a spec's frontmatter source: map to get files it touches."""
    specs_dir = repo_root / "specs"
    # Try with slug directly, then with common prefixes
    candidates = [specs_dir / f"{spec_slug}.md"]
    if not candidates[0].exists():
        # Try finding by suffix match
        for f in specs_dir.glob("*.md"):
            if f.stem.endswith(spec_slug) or spec_slug in f.stem:
                candidates.append(f)

    for spec_path in candidates:
        if not spec_path.exists():
            continue
        try:
            text = spec_path.read_text()
        except OSError:
            continue
        # Extract file: entries from frontmatter source: block
        in_frontmatter = False
        in_source = False
        files: list[str] = []
        for line in text.splitlines():
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if not in_frontmatter:
                continue
            if line.startswith("source:"):
                in_source = True
                continue
            if in_source:
                if line.startswith("  - file:"):
                    files.append(line.split("file:", 1)[1].strip())
                elif not line.startswith("  "):
                    in_source = False
        if files:
            return files
    return []


# ── Data model ──


@dataclass
class WorktreeInfo:
    path: str
    name: str
    branch: str
    ahead: int = 0
    behind: int = 0
    dirty_files: list[str] = field(default_factory=list)
    matched_task: dict | None = None
    is_main: bool = False


def _match_task_to_worktree(task: dict, worktree_names: list[str]) -> str | None:
    """Try to match a task to a worktree by claimed_by/session_key/worker_id."""
    for field_name in ("claimed_by", "session_key", "worker_id"):
        val = task.get(field_name, "") or ""
        for name in worktree_names:
            if name in val:
                return name
    return None


# ── Main ──


def collect(repo_root: Path) -> tuple[list[WorktreeInfo], list[dict], list[str]]:
    """Collect worktree info, running tasks, and conflict warnings."""
    raw_worktrees = _parse_worktrees(repo_root)
    tasks = _fetch_running_tasks()
    worktrees: list[WorktreeInfo] = []

    for row in raw_worktrees:
        wt_path = row.get("worktree", "").strip()
        if not wt_path or not Path(wt_path).exists():
            continue

        p = Path(wt_path)
        branch = _branch_name(p, row.get("branch", ""))
        ahead, behind = _ahead_behind(p)
        dirty = _dirty_files(p)
        name = _worktree_name(wt_path)
        is_main = (p == repo_root)

        worktrees.append(WorktreeInfo(
            path=wt_path,
            name=name,
            branch=branch,
            ahead=ahead,
            behind=behind,
            dirty_files=dirty,
            is_main=is_main,
        ))

    # Match tasks to worktrees
    wt_names = [w.name for w in worktrees]
    unmatched_tasks: list[dict] = []
    for task in tasks:
        matched_name = _match_task_to_worktree(task, wt_names)
        if matched_name:
            for w in worktrees:
                if w.name == matched_name:
                    w.matched_task = task
                    break
        else:
            unmatched_tasks.append(task)

    # Detect file-level conflicts
    warnings: list[str] = []
    wt_files: dict[str, set[str]] = {}
    for w in worktrees:
        if w.is_main:
            continue
        files = set(w.dirty_files)
        # Also include files from matched task's spec source map
        if w.matched_task:
            spec_id = w.matched_task.get("spec_id") or ""
            idea_id = w.matched_task.get("idea_id") or ""
            direction = w.matched_task.get("direction") or ""
            # Try to extract spec slug from task context
            for slug_candidate in [spec_id, idea_id]:
                if slug_candidate:
                    files.update(_spec_source_files(slug_candidate, repo_root))
        if files:
            wt_files[w.name] = files

    # Cross-check for overlaps
    names = list(wt_files.keys())
    for i, name_a in enumerate(names):
        for name_b in names[i + 1:]:
            overlap = wt_files[name_a] & wt_files[name_b]
            if overlap:
                file_list = ", ".join(sorted(overlap)[:5])
                extra = f" (+{len(overlap) - 5} more)" if len(overlap) > 5 else ""
                warnings.append(
                    f"CONFLICT RISK: {name_a} and {name_b} both touch: {file_list}{extra}"
                )

    return worktrees, unmatched_tasks, warnings


def print_human(worktrees: list[WorktreeInfo], unmatched: list[dict], warnings: list[str]) -> None:
    print()
    print("ACTIVE WORK ACROSS AGENTS")
    print("\u2501" * 50)

    for w in worktrees:
        status_parts: list[str] = []
        if w.dirty_files:
            status_parts.append(f"dirty ({len(w.dirty_files)} files)")
        else:
            status_parts.append("clean")
        if w.ahead:
            status_parts.append(f"{w.ahead} ahead")
        if w.behind:
            status_parts.append(f"{w.behind} behind")
        status_str = ", ".join(status_parts)

        label = "(main)" if w.is_main else ""
        task_str = "(no task)"
        if w.matched_task:
            direction = w.matched_task.get("direction", "")[:60]
            task_id = w.matched_task.get("id", "")
            task_str = f"task {task_id}: {direction}"

        print(f"\n  {w.name} {label}")
        print(f"    Branch:  {w.branch}")
        print(f"    Status:  {status_str}")
        print(f"    Task:    {task_str}")

    if unmatched:
        print(f"\n  Unmatched running tasks:")
        for t in unmatched:
            tid = t.get("id", "?")
            direction = (t.get("direction") or "")[:60]
            claimed = t.get("claimed_by", "?")
            print(f"    - task {tid}: {direction} (claimed_by: {claimed})")

    print()
    if warnings:
        for w in warnings:
            print(f"  \u26a0  {w}")
    else:
        print("  No conflicts detected")
    print()


def print_json(worktrees: list[WorktreeInfo], unmatched: list[dict], warnings: list[str]) -> None:
    data = {
        "worktrees": [
            {
                "name": w.name,
                "path": w.path,
                "branch": w.branch,
                "ahead": w.ahead,
                "behind": w.behind,
                "dirty_files": w.dirty_files,
                "is_main": w.is_main,
                "task": w.matched_task,
            }
            for w in worktrees
        ],
        "unmatched_tasks": unmatched,
        "warnings": warnings,
    }
    print(json.dumps(data, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="Show active work across all coding agents.")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()

    repo_root = _repo_root()
    worktrees, unmatched, warnings = collect(repo_root)

    if args.json:
        print_json(worktrees, unmatched, warnings)
    else:
        print_human(worktrees, unmatched, warnings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
