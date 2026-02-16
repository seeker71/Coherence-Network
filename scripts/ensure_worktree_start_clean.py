#!/usr/bin/env python3
"""Start-task gate: enforce worktree-only execution and clean git state."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)


def _repo_root() -> Path:
    proc = _run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if proc.returncode != 0:
        raise RuntimeError("not a git repository")
    return Path((proc.stdout or "").strip())


def _status_lines(repo: Path) -> list[str]:
    proc = _run(["git", "status", "--porcelain"], cwd=repo)
    if proc.returncode != 0:
        return [f"git status failed in {repo}"]
    return [line for line in (proc.stdout or "").splitlines() if line.strip()]


def _worktree_rows(repo: Path) -> list[tuple[Path, str | None]]:
    proc = _run(["git", "worktree", "list", "--porcelain"], cwd=repo)
    if proc.returncode != 0:
        return []
    rows: list[tuple[Path, str | None]] = []
    current_path: Path | None = None
    current_branch: str | None = None
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if line.startswith("worktree "):
            if current_path is not None:
                rows.append((current_path, current_branch))
            current_path = Path(line.removeprefix("worktree ").strip())
            current_branch = None
        elif line.startswith("branch "):
            current_branch = line.removeprefix("branch ").strip()
    if current_path is not None:
        rows.append((current_path, current_branch))
    return rows


def _primary_workspace(rows: list[tuple[Path, str | None]]) -> Path | None:
    for path, _branch in rows:
        if (path / ".git").is_dir():
            return path
    return rows[0][0] if rows else None


@dataclass
class GateResult:
    name: str
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Block new task starts unless running from a clean worktree."
    )
    parser.add_argument(
        "--allow-dirty-primary",
        action="store_true",
        help="Do not fail when primary workspace has local changes.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo = _repo_root()
    rows = _worktree_rows(repo)
    primary = _primary_workspace(rows)
    in_linked_worktree = (repo / ".git").is_file()
    current_dirty = _status_lines(repo)
    primary_dirty = _status_lines(primary) if primary else []

    checks = [
        GateResult(
            name="running_in_worktree",
            ok=in_linked_worktree,
            detail=f"repo={repo}",
        ),
        GateResult(
            name="current_worktree_clean",
            ok=len(current_dirty) == 0,
            detail="clean" if not current_dirty else f"dirty: {len(current_dirty)} file(s)",
        ),
    ]

    if primary is not None:
        checks.append(
            GateResult(
                name="primary_workspace_clean",
                ok=args.allow_dirty_primary or len(primary_dirty) == 0,
                detail=(
                    "clean"
                    if not primary_dirty
                    else f"dirty: {len(primary_dirty)} file(s) at {primary}"
                ),
            )
        )

    ok = all(c.ok for c in checks)
    payload = {
        "ok": ok,
        "repo_root": str(repo),
        "primary_workspace": str(primary) if primary else None,
        "checks": [asdict(c) for c in checks],
        "current_worktree_dirty_files": current_dirty,
        "primary_workspace_dirty_files": primary_dirty[:50],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for c in checks:
            status = "OK" if c.ok else "FAIL"
            print(f"{status}: {c.name} ({c.detail})")
        if current_dirty:
            print("Current worktree dirty files:")
            for line in current_dirty:
                print(f"  {line}")
        if primary_dirty:
            print("Primary workspace dirty files:")
            for line in primary_dirty[:20]:
                print(f"  {line}")
        print(f"overall_ok={ok}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
