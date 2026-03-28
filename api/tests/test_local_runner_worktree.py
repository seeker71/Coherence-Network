"""Tests for local_runner git worktree creation (impl/test isolation)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local_runner.py"


def _load_local_runner():
    spec = importlib.util.spec_from_file_location("local_runner_worktree", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_bare_upstream(tmp_path: Path) -> Path:
    """Minimal repo with refs/remotes/origin/main (what ``git worktree add ... origin/main`` needs)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# t\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def test_create_worktree_succeeds_in_clean_repo(tmp_path: Path) -> None:
    mod = _load_local_runner()
    repo = _init_bare_upstream(tmp_path)
    wt = mod._create_worktree("task_aaaaaaaaaaaaaaaa", repo_root=repo)
    assert wt is not None
    assert wt.is_dir()
    assert (wt / "README.md").is_file()


def test_create_worktree_recreates_after_worktree_removed_leaving_branch(tmp_path: Path) -> None:
    """If worktree was removed but local branch remains, a second create must succeed."""
    mod = _load_local_runner()
    repo = _init_bare_upstream(tmp_path)
    tid = "task_bbbbbbbbbbbbbbbb"
    slug = tid[:16]
    branch = f"task/{slug}"

    first = mod._create_worktree(tid, repo_root=repo)
    assert first is not None
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(first)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # Branch often remains after worktree removal — next add would fail without cleanup.
    br = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert br.returncode == 0, "expected local branch to remain so cleanup path is exercised"

    second = mod._create_worktree(tid, repo_root=repo)
    assert second is not None
    assert (second / "README.md").is_file()


def test_remove_stale_worktree_slot_idempotent(tmp_path: Path) -> None:
    mod = _load_local_runner()
    repo = _init_bare_upstream(tmp_path)
    tid = "task_cccccccccccccccc"
    slug = tid[:16]
    branch = f"task/{slug}"
    wt = repo / ".worktrees" / f"task-{slug}"
    mod._remove_stale_worktree_slot(str(repo), branch, wt)
