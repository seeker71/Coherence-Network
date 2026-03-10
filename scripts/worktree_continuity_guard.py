#!/usr/bin/env python3
"""Detect stranded changes across sibling worktrees.

Purpose:
- prevent silent abandonment of in-flight work when prompts switch worktrees
- fail fast when another worktree has risky uncommitted/unpushed state
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorktreeRisk:
    path: str
    branch: str
    dirty: bool
    detached: bool
    ahead_of_main: int
    behind_main: int
    has_upstream: bool
    risks: list[str]


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
        raise RuntimeError(proc.stderr.strip() or "failed to resolve repository root")
    return Path(proc.stdout.strip()).resolve()


def _current_worktree_path(repo_root: Path) -> Path:
    proc = _run_git(["rev-parse", "--path-format=absolute", "--git-dir"], repo_root)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "failed to resolve current worktree path")
    # <worktree>/.git in linked checkout is a file, so use cwd as canonical current worktree.
    return Path.cwd().resolve()


def _parse_worktrees(repo_root: Path) -> list[dict[str, str]]:
    proc = _run_git(["worktree", "list", "--porcelain"], repo_root)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "failed to list git worktrees")
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


def _branch_name(worktree_path: Path, branch_ref_from_porcelain: str) -> str:
    if branch_ref_from_porcelain.startswith("refs/heads/"):
        return branch_ref_from_porcelain.replace("refs/heads/", "", 1)
    proc = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], worktree_path)
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip() or "unknown"


def _status_short(worktree_path: Path) -> str:
    proc = _run_git(["status", "--short", "--untracked-files=all"], worktree_path)
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _upstream_exists(worktree_path: Path) -> bool:
    proc = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], worktree_path)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _ahead_behind_vs_main(worktree_path: Path) -> tuple[int, int]:
    proc = _run_git(["rev-list", "--left-right", "--count", "origin/main...HEAD"], worktree_path)
    if proc.returncode != 0:
        return 0, 0
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return 0, 0
    try:
        behind = int(parts[0])
        ahead = int(parts[1])
    except ValueError:
        return 0, 0
    return ahead, behind


def collect_risks(repo_root: Path, current_path: Path) -> list[WorktreeRisk]:
    risks: list[WorktreeRisk] = []
    for row in _parse_worktrees(repo_root):
        wt_path = Path(str(row.get("worktree", "")).strip()).resolve()
        if not wt_path.exists():
            continue
        if wt_path == current_path:
            continue
        branch = _branch_name(wt_path, str(row.get("branch", "")))
        detached = branch == "HEAD"
        dirty = bool(_status_short(wt_path))
        ahead, behind = _ahead_behind_vs_main(wt_path)
        has_upstream = _upstream_exists(wt_path)
        risk_labels: list[str] = []
        if detached:
            risk_labels.append("detached_head")
        if dirty:
            risk_labels.append("dirty_worktree")
        if ahead > 0 and not has_upstream:
            risk_labels.append("ahead_without_upstream")
        if risk_labels:
            risks.append(
                WorktreeRisk(
                    path=str(wt_path),
                    branch=branch,
                    dirty=dirty,
                    detached=detached,
                    ahead_of_main=ahead,
                    behind_main=behind,
                    has_upstream=has_upstream,
                    risks=risk_labels,
                )
            )
    return risks


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect sibling worktree continuity risks.")
    parser.add_argument("--fail-on-risk", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = _repo_root()
    current_path = _current_worktree_path(repo_root)
    risks = collect_risks(repo_root, current_path)

    payload = {
        "repo_root": str(repo_root),
        "current_worktree": str(current_path),
        "risk_count": len(risks),
        "risks": [
            {
                "path": item.path,
                "branch": item.branch,
                "dirty": item.dirty,
                "detached": item.detached,
                "ahead_of_main": item.ahead_of_main,
                "behind_main": item.behind_main,
                "has_upstream": item.has_upstream,
                "risks": item.risks,
            }
            for item in risks
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"worktree-continuity: repo={payload['repo_root']}")
        print(f"worktree-continuity: current={payload['current_worktree']}")
        print(f"worktree-continuity: risk_count={payload['risk_count']}")
        for item in payload["risks"]:
            labels = ",".join(item["risks"])
            print(
                " - "
                f"{item['path']} branch={item['branch']} "
                f"ahead={item['ahead_of_main']} behind={item['behind_main']} "
                f"upstream={'yes' if item['has_upstream'] else 'no'} "
                f"risks={labels}"
            )

    if args.fail_on_risk and risks:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
