from __future__ import annotations

import subprocess
from pathlib import Path

MAIN_BRANCHES = {"main", "master"}


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown failure").strip()
        raise SystemExit(f"start-gate: git {' '.join(args)} failed ({detail})")
    return (proc.stdout or "").strip()


def _current_branch_name() -> str:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch:
        raise SystemExit("start-gate: failed to detect current branch name")
    return branch


def _in_linked_worktree() -> bool:
    git_marker = Path(".git")
    if not git_marker.exists():
        raise SystemExit("start-gate: missing .git marker")
    if git_marker.is_dir():
        return False
    if not git_marker.is_file():
        raise SystemExit("start-gate: unrecognized .git marker type")

    gitdir_line = git_marker.read_text(encoding="utf-8").strip()
    if not gitdir_line.startswith("gitdir:"):
        raise SystemExit("start-gate: expected .git to be a gitdir pointer file")

    gitdir = gitdir_line.split(":", 1)[1].strip()
    gitdir_path = Path(gitdir).resolve().as_posix()
    return "/.git/worktrees/" in gitdir_path


def _validate_thread_context(branch_name: str, *, linked_worktree: bool) -> None:
    if branch_name == "HEAD":
        raise SystemExit(
            "start-gate: detached HEAD detected. Attach to a branch first: "
            "git switch -c codex/<thread-name> (new) or git switch codex/<thread-name> (existing)."
        )

    if branch_name in MAIN_BRANCHES:
        raise SystemExit(
            "start-gate: direct work on main/master is blocked. "
            "Create or switch to a thread branch (recommended: codex/<thread-name>)."
        )

    if linked_worktree:
        return

    if branch_name.startswith("codex/"):
        return

    raise SystemExit(
        "start-gate: not in a linked worktree and not on a codex/* thread branch. "
        "Use a linked worktree or switch to codex/<thread-name>."
    )


def main() -> None:
    _run_git(["rev-parse", "--is-inside-work-tree"])

    branch = _current_branch_name()
    linked_worktree = _in_linked_worktree()
    _validate_thread_context(branch, linked_worktree=linked_worktree)

    location = "linked-worktree" if linked_worktree else "branch-only"
    print(f"start-gate: passed ({location}, branch={branch})")


if __name__ == "__main__":
    main()
