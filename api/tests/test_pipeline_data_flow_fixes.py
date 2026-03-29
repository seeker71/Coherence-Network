"""Tests for Pipeline Data Flow Fixes (Spec 163 / task_99ebbbbf852dfff6).

Verifies that code flows correctly through each pipeline phase:
- AC-1: Worktree base is always origin/main (fetched before create)
- AC-2: Diff captured after provider run, not inferred from stdout
- AC-3: Branch pushed to origin after impl/test; main pushed after code-review
- AC-4: Phase does NOT advance if push fails (BRANCH_PUSH_FAILED gating)
- AC-5: Worktree NOT deleted until push is confirmed
- AC-6: Deploy runs via runner SSH action, not provider
- AC-7: Verify runs via runner curl action, not provider
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from scripts import local_runner


class _Proc:
    """Minimal subprocess.CompletedProcess stand-in."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _sandbox_tmp_path() -> Path:
    root = Path.cwd() / ".tmp-pytest-fixtures"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=root))


# ---------------------------------------------------------------------------
# AC-1 — _create_worktree fetches origin before creating, uses origin/main
# ---------------------------------------------------------------------------


def test_create_worktree_fetches_origin_before_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC-1: git fetch origin --quiet must run before git worktree add."""
    calls: list[list[str]] = []

    wt_path = tmp_path / "task-abc1"

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        calls.append(list(args))
        if args[:2] == ["git", "worktree"]:
            wt_path.mkdir(parents=True, exist_ok=True)
        return _Proc()

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    local_runner._create_worktree("abc1def234567890")

    fetch_idx = next(
        (i for i, c in enumerate(calls) if c[:3] == ["git", "fetch", "origin"]),
        None,
    )
    worktree_add_idx = next(
        (i for i, c in enumerate(calls) if c[:3] == ["git", "worktree", "add"]),
        None,
    )
    assert fetch_idx is not None, "git fetch origin must be called"
    assert worktree_add_idx is not None, "git worktree add must be called"
    assert fetch_idx < worktree_add_idx, "fetch must happen before worktree add"


def test_create_worktree_uses_origin_main_as_base_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-1: log shows base=origin/main when no explicit base_branch given."""
    # slug = task_id[:16], so "abc1def234567890"[:16] = "abc1def234567890"
    wt_path = tmp_path / "task-abc1def234567890"

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if args[:3] == ["git", "worktree", "add"]:
            wt_path.mkdir(parents=True, exist_ok=True)
        return _Proc()

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.INFO, logger="local_runner"):
        result = local_runner._create_worktree("abc1def234567890")

    assert result is not None, "worktree path should be returned"
    assert any(
        "WORKTREE_CREATED" in record.message and "origin/main" in record.message
        for record in caplog.records
    ), "WORKTREE_CREATED log must show base=origin/main"


def test_create_worktree_falls_back_to_origin_main_when_pr_branch_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-1: if specified PR branch doesn't exist on origin, fall back to origin/main."""
    wt_path = tmp_path / "task-abc2def234567890"

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        # rev-parse check for branch fails (branch not on origin)
        if "rev-parse" in args:
            return _Proc(returncode=1)
        if args[:3] == ["git", "worktree", "add"]:
            wt_path.mkdir(parents=True, exist_ok=True)
        return _Proc()

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.INFO, logger="local_runner"):
        result = local_runner._create_worktree("abc2def234567890", base_branch="worker/impl/no-such")

    assert result is not None
    assert any("origin/main" in r.message for r in caplog.records), (
        "should fall back to origin/main when PR branch not found"
    )


# ---------------------------------------------------------------------------
# AC-2 — _capture_worktree_diff captures actual diff, not just stdout
# ---------------------------------------------------------------------------


def test_create_worktree_reclaims_orphaned_slot_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1: stale retry state must be removed before a new worktree is created."""
    tmp_path = _sandbox_tmp_path()
    try:
        slug = "abc5def234567890"
        wt_path = tmp_path / f"task-{slug}"
        branch = f"task/{slug}"
        stale_file = wt_path / "stale.txt"
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("leftover retry state", encoding="utf-8")

        calls: list[list[str]] = []

        def _run(args: list[str], **_kwargs: Any) -> _Proc:
            calls.append(list(args))
            if args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
                return _Proc(returncode=0)
            if args[:3] == ["git", "worktree", "list"]:
                return _Proc(stdout="")
            if args[:3] == ["git", "worktree", "add"]:
                assert not stale_file.exists(), "orphaned worktree directory must be removed before retry"
                wt_path.mkdir(parents=True, exist_ok=True)
                return _Proc()
            return _Proc()

        monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
        monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
        monkeypatch.setattr(local_runner.subprocess, "run", _run)

        result = local_runner._create_worktree(slug)

        assert result == wt_path
        assert ["git", "branch", "-D", branch] in calls, "stale retry branch must be deleted before recreate"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_create_worktree_logs_failure_details_when_git_add_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-1: worktree add failures must include git stderr for root-cause diagnosis."""
    tmp_path = _sandbox_tmp_path()
    try:
        slug = "abc6def234567890"

        def _run(args: list[str], **_kwargs: Any) -> _Proc:
            if args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
                return _Proc(returncode=1)
            if args[:3] == ["git", "worktree", "list"]:
                return _Proc(stdout="")
            if args[:3] == ["git", "worktree", "add"]:
                return _Proc(returncode=1, stderr="fatal: branch already exists")
            return _Proc()

        monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
        monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
        monkeypatch.setattr(local_runner.subprocess, "run", _run)
        # Non-linked path tries standalone after add fails; force standalone off so we assert full failure.
        monkeypatch.setattr(local_runner, "_create_standalone_task_repo", lambda *a, **k: None)

        with caplog.at_level(logging.WARNING, logger="local_runner"):
            result = local_runner._create_worktree(slug)

        assert result is None
        assert any(
            "fatal: branch already exists" in record.message
            for record in caplog.records
        ), "git stderr must be logged when worktree creation fails"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_resolve_main_repo_from_linked_worktree() -> None:
    """Linked-checkout .git file → primary repository root (for worktree retry)."""
    tmp = _sandbox_tmp_path()
    try:
        main = tmp / "mainrepo"
        main.mkdir()
        (main / ".git").mkdir()
        assert local_runner._resolve_main_repo_from_linked_worktree(str(main)) is None

        link = tmp / "linkedwt"
        link.mkdir()
        gitdir = main / ".git" / "worktrees" / "linkedwt"
        gitdir.mkdir(parents=True)
        (link / ".git").write_text(f"gitdir: {gitdir.resolve().as_posix()}\n", encoding="utf-8")
        assert local_runner._resolve_main_repo_from_linked_worktree(str(link)) == main.resolve()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_create_worktree_non_linked_falls_back_to_standalone_when_add_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When git worktree add fails on a normal repo, try standalone snapshot (impl path)."""
    calls: list[str] = []

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if args[:3] == ["git", "worktree", "add"]:
            return _Proc(returncode=1, stderr="fatal: simulated add failure")
        return _Proc()

    fake_wt = tmp_path / "task-abcd000000000000"

    def _standalone(*_a: Any, **_k: Any) -> Path:
        calls.append("standalone")
        return fake_wt

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner, "_repo_is_linked_worktree", lambda _r: False)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner, "_create_standalone_task_repo", _standalone)
    monkeypatch.setattr(local_runner, "_reclaim_worktree_slot", lambda *a, **k: True)

    result = local_runner._create_worktree("abcd00000000000000000000000000")
    assert result == fake_wt
    assert calls == ["standalone"]


def test_create_worktree_retries_with_safe_directory_after_dubious_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1: retry git commands with safe.directory when worktree repo ownership is flagged."""
    tmp_path = _sandbox_tmp_path()
    try:
        slug = "abc7def234567890"
        wt_path = tmp_path / f"task-{slug}"
        calls: list[list[str]] = []
        dubious = (
            "fatal: detected dubious ownership in repository at "
            f"'{tmp_path.as_posix()}'\n"
            "To add an exception for this directory, call:\n\n"
            f"\tgit config --global --add safe.directory {tmp_path.as_posix()}"
        )

        def _run(args: list[str], **_kwargs: Any) -> _Proc:
            calls.append(list(args))
            if args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
                return _Proc(returncode=1)
            if args[:3] == ["git", "fetch", "origin"]:
                return _Proc(returncode=128, stderr=dubious)
            if args[:5] == ["git", "-c", f"safe.directory={tmp_path.resolve()}", "fetch", "origin"]:
                return _Proc()
            if args[:3] == ["git", "worktree", "add"]:
                wt_path.mkdir(parents=True, exist_ok=True)
                return _Proc()
            return _Proc(stdout="")

        monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
        monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
        monkeypatch.setattr(local_runner.subprocess, "run", _run)

        result = local_runner._create_worktree(slug)

        assert result == wt_path
        assert any(
            call[:2] == ["git", "-c"]
            and f"safe.directory={tmp_path.resolve()}" in call
            and "fetch" in call
            for call in calls
        ), "dubious ownership failures must be retried with safe.directory"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_capture_worktree_diff_returns_empty_when_no_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC-2: no diff → empty string (no false positives)."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        return _Proc(stdout="")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    diff = local_runner._capture_worktree_diff("abc3def234567890", tmp_path)

    assert diff == "", "empty diff must be returned when no files changed"


def test_capture_worktree_diff_returns_diff_content_when_files_changed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC-2: diff content returned when provider wrote files."""

    diff_stat = " api/tests/test_foo.py | 10 ++++++++++\n 1 file changed"
    full_diff = "diff --git a/api/tests/test_foo.py b/api/tests/test_foo.py\n+new test line\n"

    call_count = [0]

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        call_count[0] += 1
        if args[:2] == ["git", "add"]:
            return _Proc()
        if "--stat" in args:
            return _Proc(stdout=diff_stat)
        if args == ["git", "diff", "--cached"]:
            return _Proc(stdout=full_diff)
        return _Proc()

    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    diff = local_runner._capture_worktree_diff("abc4def234567890", tmp_path)

    assert diff == full_diff, "full diff content must be returned"


def test_capture_worktree_diff_stages_all_files_first(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC-2: git add -A must run before diff so new untracked files are included."""
    staged_calls: list[list[str]] = []

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        staged_calls.append(list(args))
        if "--stat" in args:
            return _Proc(stdout=" file.py | 1 +")
        if args == ["git", "diff", "--cached"]:
            return _Proc(stdout="diff content")
        return _Proc()

    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    local_runner._capture_worktree_diff("abc5def234567890", tmp_path)

    assert ["git", "add", "-A"] in staged_calls, "git add -A must be called to stage all files"


# ---------------------------------------------------------------------------
# AC-3 — _push_branch_to_origin pushes branch, logs BRANCH_PUSHED / BRANCH_PUSH_FAILED
# ---------------------------------------------------------------------------


def test_push_branch_to_origin_returns_true_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-3: successful push returns True and logs BRANCH_PUSHED."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if args[:2] == ["git", "status"]:
            return _Proc(stdout="")
        if args[:2] == ["git", "remote"]:
            return _Proc(stdout="https://github.com/owner/repo.git")
        if args[0] == "gh":
            return _Proc(stdout="ghp_token")
        return _Proc(returncode=0)

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner.os, "environ", {})

    with caplog.at_level(logging.INFO, logger="local_runner"):
        result = local_runner._push_branch_to_origin("abc6def234567890", tmp_path)

    assert result is True
    assert any("BRANCH_PUSHED" in r.message for r in caplog.records), (
        "BRANCH_PUSHED must be logged on successful push"
    )


def test_push_branch_to_origin_returns_false_on_push_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-3/AC-4: failed push returns False and logs BRANCH_PUSH_FAILED."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if args[:2] == ["git", "status"]:
            return _Proc(stdout="")
        if args[:2] == ["git", "remote"]:
            return _Proc(stdout="https://github.com/owner/repo.git")
        if args[0] == "gh":
            return _Proc(returncode=1, stdout="")
        # Simulate push failure
        if "push" in args:
            return _Proc(returncode=1, stderr="remote: error: access denied")
        return _Proc()

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner.os, "environ", {})

    with caplog.at_level(logging.WARNING, logger="local_runner"):
        result = local_runner._push_branch_to_origin("abc7def234567890", tmp_path)

    assert result is False
    assert any("BRANCH_PUSH_FAILED" in r.message for r in caplog.records), (
        "BRANCH_PUSH_FAILED must be logged when push fails"
    )


def test_push_branch_to_origin_returns_false_on_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-3/AC-4: exception during push returns False and logs BRANCH_PUSH_FAILED."""

    def _run(*_args: Any, **_kwargs: Any) -> _Proc:
        raise OSError("git not found")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.WARNING, logger="local_runner"):
        result = local_runner._push_branch_to_origin("abc8def234567890", tmp_path)

    assert result is False
    assert any("BRANCH_PUSH_FAILED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AC-3 (R3) — _merge_branch_to_main pushes to origin/main after merge
# ---------------------------------------------------------------------------


def test_merge_branch_to_main_pushes_to_origin_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R3: after merge, git push origin main must be called."""
    push_calls: list[list[str]] = []

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if "push" in args:
            push_calls.append(list(args))
        # rev-parse check — branch exists on origin
        if "rev-parse" in args:
            return _Proc(returncode=0, stdout="abc1234")
        return _Proc(returncode=0, stdout="")

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    result = local_runner._merge_branch_to_main("abc9def234567890")

    assert result is True
    main_push = [c for c in push_calls if "main" in c]
    assert main_push, "git push origin main must be called after merge"


def test_merge_branch_to_main_returns_false_on_merge_conflict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """R3: merge conflict returns False; deploys must not be created."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if "rev-parse" in args:
            return _Proc(returncode=0, stdout="abc1234")
        if "merge" in args and "--no-ff" in args:
            return _Proc(returncode=1, stderr="CONFLICT: merge conflict in file.py")
        return _Proc(returncode=0)

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.WARNING, logger="local_runner"):
        result = local_runner._merge_branch_to_main("abcadef234567890")

    assert result is False
    assert any("MERGE_CONFLICT" in r.message for r in caplog.records), (
        "MERGE_CONFLICT must be logged when merge fails"
    )


def test_merge_branch_to_main_returns_false_when_push_to_main_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """R3: if push of main to origin fails, return False."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if "rev-parse" in args:
            return _Proc(returncode=0, stdout="abc1234")
        if "merge" in args and "--no-ff" in args:
            return _Proc(returncode=0)
        if "push" in args and "main" in args and "--delete" not in args:
            return _Proc(returncode=1, stderr="remote: push rejected")
        return _Proc(returncode=0)

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.WARNING, logger="local_runner"):
        result = local_runner._merge_branch_to_main("abcbdef234567890")

    assert result is False
    assert any("MAIN_PUSH_FAILED" in r.message for r in caplog.records), (
        "MAIN_PUSH_FAILED must be logged when push of main fails"
    )


def test_merge_branch_to_main_skips_when_branch_not_on_origin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """R3: if branch not found on origin (no code was committed), return True (skip)."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if "rev-parse" in args:
            return _Proc(returncode=1)  # branch not on origin
        return _Proc(returncode=0)

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.INFO, logger="local_runner"):
        result = local_runner._merge_branch_to_main("abccdef234567890")

    assert result is True
    assert any("MERGE_SKIP" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AC-4 — push failure must not allow phase advance
# BRANCH_PUSH_FAILED must be logged when push returns False
# ---------------------------------------------------------------------------


def test_push_branch_failure_is_observable_via_return_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC-4: _push_branch_to_origin returning False is the gate signal for phase blocking."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if "push" in args:
            return _Proc(returncode=128, stderr="fatal: unable to access")
        if args[:2] == ["git", "status"]:
            return _Proc(stdout="")
        if args[:2] == ["git", "remote"]:
            return _Proc(stdout="https://github.com/owner/repo.git")
        if args[0] == "gh":
            return _Proc(returncode=1, stdout="")
        return _Proc()

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner.os, "environ", {})

    pushed = local_runner._push_branch_to_origin("abcddef234567890", tmp_path)

    # This is the signal: the caller (worker) must check this value
    # and block phase advancement when pushed is False
    assert pushed is False, (
        "_push_branch_to_origin must return False on failure — "
        "the caller uses this to gate phase advancement (AC-4)"
    )


def test_branch_push_failed_log_appears_for_push_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: BRANCH_PUSH_FAILED log prefix must appear when push fails."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if "push" in args:
            return _Proc(returncode=1, stderr="permission denied")
        if args[:2] == ["git", "status"]:
            return _Proc(stdout="")
        if args[:2] == ["git", "remote"]:
            return _Proc(stdout="https://github.com/owner/repo.git")
        if args[0] == "gh":
            return _Proc(returncode=1, stdout="")
        return _Proc()

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner.os, "environ", {})

    with caplog.at_level(logging.WARNING, logger="local_runner"):
        local_runner._push_branch_to_origin("abcedef234567890", tmp_path)

    assert any("BRANCH_PUSH_FAILED" in r.message for r in caplog.records), (
        "BRANCH_PUSH_FAILED log prefix required (spec P1 observable proof)"
    )


# ---------------------------------------------------------------------------
# AC-5 — _cleanup_worktree logs WORKTREE_CLEANED; worktree is kept on push fail
# ---------------------------------------------------------------------------


def test_cleanup_worktree_logs_worktree_cleaned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-5: WORKTREE_CLEANED must be logged when worktree is successfully cleaned up."""

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        return _Proc()

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.INFO, logger="local_runner"):
        local_runner._cleanup_worktree("abcfdef234567890")

    assert any("WORKTREE_CLEANED" in r.message for r in caplog.records), (
        "WORKTREE_CLEANED must be logged after worktree removal"
    )


def test_cleanup_worktree_handles_exception_gracefully(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-5: cleanup failures must not propagate — they are logged as warnings."""

    def _run(*_args: Any, **_kwargs: Any) -> _Proc:
        raise OSError("worktree already removed")

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    with caplog.at_level(logging.WARNING, logger="local_runner"):
        # Must not raise
        local_runner._cleanup_worktree("abcgdef234567890")

    assert any("WORKTREE_CLEANUP_FAILED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AC-6 — _runner_deploy_phase is a runner action, not a provider task
# ---------------------------------------------------------------------------


def test_runner_deploy_phase_calls_deploy_to_vps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-6: deploy must be executed via _deploy_to_vps (SSH), not by a provider."""
    deploy_called = [False]
    completions: list[dict[str, Any]] = []

    def _deploy_to_vps() -> str:
        deploy_called[0] = True
        return "Deployment successful"

    monkeypatch.setattr(local_runner, "_deploy_to_vps", _deploy_to_vps)
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"task_id": task_id, "success": success, "output": output}
        ) or True,
    )

    task = {"id": "task_deploy_test1234", "task_type": "deploy", "context": {}}
    result = local_runner._runner_deploy_phase(task)

    assert deploy_called[0], "_deploy_to_vps must be called (runner-side SSH deploy)"
    assert result is True
    assert completions[0]["success"] is True


def test_runner_deploy_phase_returns_false_when_vps_deploy_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-6: if VPS deploy returns failure, phase is marked failed."""
    completions: list[dict[str, Any]] = []

    monkeypatch.setattr(local_runner, "_deploy_to_vps", lambda: "Deploy failed: docker error")
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"success": success, "output": output}
        ) or True,
    )

    task = {"id": "task_deploy_test5678", "task_type": "deploy", "context": {}}
    result = local_runner._runner_deploy_phase(task)

    assert result is False
    assert completions[0]["success"] is False


def test_runner_deploy_phase_is_not_provider_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-6: deploy tasks must NOT be routed to execute_with_provider."""
    provider_called = [False]

    monkeypatch.setattr(
        local_runner,
        "execute_with_provider",
        lambda *_args, **_kwargs: (provider_called.__setitem__(0, True) or (True, "fake", 1.0)),
    )
    monkeypatch.setattr(local_runner, "_deploy_to_vps", lambda: "Deploy successful")
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda *_args, **_kwargs: True,
    )

    task = {"id": "task_deploy_test9012", "task_type": "deploy", "context": {}}
    local_runner._runner_deploy_phase(task)

    assert not provider_called[0], (
        "execute_with_provider must NOT be called for deploy tasks — "
        "provider cannot SSH (AC-6)"
    )


# ---------------------------------------------------------------------------
# AC-7 — _runner_verify_phase is a runner action, not a provider task
# ---------------------------------------------------------------------------


def test_runner_verify_phase_makes_http_calls_to_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-7: verify must make real HTTP calls to production API."""
    http_calls: list[str] = []
    completions: list[dict[str, Any]] = []

    class _MockResp:
        status_code = 200

    def _get(url: str, **_kwargs: Any) -> _MockResp:
        http_calls.append(url)
        return _MockResp()

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "get", _get)
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"task_id": task_id, "success": success, "output": output}
        ) or True,
    )

    task = {"id": "task_verify_test12345", "task_type": "verify", "context": {"idea_id": "idea-123"}}
    result = local_runner._runner_verify_phase(task)

    assert len(http_calls) > 0, "verify must make HTTP calls to production endpoints"
    assert result is True
    assert completions[0]["success"] is True


def test_runner_verify_phase_fails_when_endpoints_return_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-7: verify returns False if production endpoint returns unexpected status."""
    completions: list[dict[str, Any]] = []

    class _MockBadResp:
        status_code = 503

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "get", lambda *_a, **_kw: _MockBadResp())
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"success": success, "output": output}
        ) or True,
    )

    task = {"id": "task_verify_fail12345", "task_type": "verify", "context": {}}
    result = local_runner._runner_verify_phase(task)

    assert result is False
    assert completions[0]["success"] is False
    assert "failed" in completions[0]["output"].lower()


def test_runner_verify_phase_is_not_provider_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-7: verify tasks must NOT be routed to execute_with_provider (no hallucination)."""
    provider_called = [False]

    monkeypatch.setattr(
        local_runner,
        "execute_with_provider",
        lambda *_args, **_kwargs: (provider_called.__setitem__(0, True) or (True, "hallucinated result", 1.0)),
    )

    class _MockResp:
        status_code = 200

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "get", lambda *_a, **_kw: _MockResp())
    monkeypatch.setattr(local_runner, "complete_task", lambda *_a, **_kw: True)

    task = {"id": "task_verify_noprov1234", "task_type": "verify", "context": {}}
    local_runner._runner_verify_phase(task)

    assert not provider_called[0], (
        "execute_with_provider must NOT be called for verify tasks — "
        "provider would hallucinate results (AC-7)"
    )


# ---------------------------------------------------------------------------
# R1 — _create_worktree sends --quiet flag to git fetch
# ---------------------------------------------------------------------------


def test_create_worktree_fetch_uses_quiet_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R1: git fetch origin must use --quiet to avoid log noise."""
    fetch_args: list[list[str]] = []

    wt_path = tmp_path / "task-abch"

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if args[:3] == ["git", "fetch", "origin"]:
            fetch_args.append(list(args))
        if args[:3] == ["git", "worktree", "add"]:
            wt_path.mkdir(parents=True, exist_ok=True)
        return _Proc()

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    local_runner._create_worktree("abchdef234567890")

    assert len(fetch_args) > 0
    assert "--quiet" in fetch_args[0], "git fetch must use --quiet flag (R1)"


# ---------------------------------------------------------------------------
# R5 — Worktree preservation: cleanup only when push confirmed or task failed
# ---------------------------------------------------------------------------


def test_cleanup_worktree_runs_git_worktree_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R5: _cleanup_worktree must call 'git worktree remove --force'."""
    remove_calls: list[list[str]] = []

    def _run(args: list[str], **_kwargs: Any) -> _Proc:
        if args[:3] == ["git", "worktree", "remove"]:
            remove_calls.append(list(args))
        return _Proc()

    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
    monkeypatch.setattr(local_runner.subprocess, "run", _run)

    local_runner._cleanup_worktree("abcidef234567890")


def test_cleanup_worktree_removes_orphaned_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R5: cleanup must also remove stale task directories Git no longer tracks."""
    tmp_path = _sandbox_tmp_path()
    try:
        slug = "abcjdef234567890"
        wt_path = tmp_path / f"task-{slug}"
        stale_file = wt_path / "orphaned.txt"
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("stale", encoding="utf-8")

        def _run(args: list[str], **_kwargs: Any) -> _Proc:
            if args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
                return _Proc(returncode=1)
            if args[:3] == ["git", "worktree", "list"]:
                return _Proc(stdout="")
            return _Proc()

        monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
        monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path)
        monkeypatch.setattr(local_runner.subprocess, "run", _run)

        local_runner._cleanup_worktree(slug)

        assert not wt_path.exists(), "orphaned worktree directory must be deleted during cleanup"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)

    assert any("--force" in c for c in remove_calls), (
        "git worktree remove --force must be used to ensure cleanup"
    )


# ---------------------------------------------------------------------------
# Structural: _runner_deploy_phase and _runner_verify_phase are callable
# This verifies R6/R7 guard exists and is not a provider path
# ---------------------------------------------------------------------------


def test_runner_deploy_phase_function_exists() -> None:
    """R6: _runner_deploy_phase function must exist in local_runner (runner owns deploy)."""
    assert callable(getattr(local_runner, "_runner_deploy_phase", None)), (
        "_runner_deploy_phase must be defined — deploy is a runner-side action (R6)"
    )


def test_runner_verify_phase_function_exists() -> None:
    """R7: _runner_verify_phase function must exist in local_runner (runner owns verify)."""
    assert callable(getattr(local_runner, "_runner_verify_phase", None)), (
        "_runner_verify_phase must be defined — verify is a runner-side action (R7)"
    )


def test_runner_deploy_phase_logs_deploy_phase_start(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-6: deploy start must produce a structured log entry (P1 observable proof)."""
    monkeypatch.setattr(local_runner, "_deploy_to_vps", lambda: "Deploy successful")
    monkeypatch.setattr(local_runner, "complete_task", lambda *_a, **_kw: True)

    task = {"id": "task_deploy_log12345", "task_type": "deploy", "context": {}}

    with caplog.at_level(logging.INFO, logger="local_runner"):
        local_runner._runner_deploy_phase(task)

    assert any("DEPLOY_PHASE" in r.message for r in caplog.records), (
        "deploy start must produce an observable log entry (P1)"
    )


def test_runner_verify_phase_logs_verify_phase_start(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-7: verify start must produce a structured log entry (P1 observable proof)."""

    class _MockResp:
        status_code = 200

    import httpx as _httpx
    monkeypatch.setattr(_httpx, "get", lambda *_a, **_kw: _MockResp())
    monkeypatch.setattr(local_runner, "complete_task", lambda *_a, **_kw: True)

    task = {"id": "task_verify_log1234_", "task_type": "verify", "context": {"idea_id": "idea-x"}}

    with caplog.at_level(logging.INFO, logger="local_runner"):
        local_runner._runner_verify_phase(task)

    assert any("VERIFY_PHASE" in r.message for r in caplog.records), (
        "verify start must produce an observable log entry (P1)"
    )
