"""Tests for pipeline data-flow guarantees in local_runner.

Contract (see api/scripts/local_runner.py parallel worker + worktree helpers):

1. Git fetch runs before worktree creation so the base ref is not stale.
2. Post-provider execution captures git diff (cached), not stdout alone.
3. Merge to main ends with push to origin main so code is on the remote.
4. Branch push failure leaves pushed=False so merge/deploy gates apply.
5. Failed branch push keeps the worktree (only copy) until recovery.
6. Deploy phase runs on the runner (_runner_deploy_phase / SSH path), not sandboxed provider.
7. Verify phase uses HTTP checks against production API, not provider hallucination.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import local_runner


class _CP:
    """subprocess.CompletedProcess stand-in."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_create_worktree_fetches_origin_before_add(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fix (1): stale base is prevented by fetching remotes before worktree add."""
    calls: list[list[str]] = []

    def _run(args: list[str], **_kwargs: Any) -> _CP:
        calls.append(list(args))
        if args[:3] == ["git", "fetch", "origin"]:
            return _CP(0)
        if args[:3] == ["git", "worktree", "add"]:
            wt = Path(args[-1])
            wt.mkdir(parents=True, exist_ok=True)
            return _CP(0)
        return _CP(1, stderr="unexpected")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / ".worktrees")

    tid = "task_fetch_order_12345678"
    wt = local_runner._create_worktree(tid)
    assert wt is not None
    assert len(calls) >= 2
    assert calls[0][:3] == ["git", "fetch", "origin"]
    assert any(c[:3] == ["git", "worktree", "add"] for c in calls)


def test_capture_worktree_diff_returns_cached_patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fix (2): diff is read from git, not inferred from provider stdout."""
    diff_body = "diff --git a/x.py b/x.py\n+ok\n"

    def _run(args: list[str], **_kwargs: Any) -> _CP:
        if args[:2] == ["git", "add"]:
            return _CP(0)
        if args == ["git", "diff", "--cached", "--stat"]:
            return _CP(0, stdout=" x.py | 1 +\n")
        if args == ["git", "diff", "--cached"]:
            return _CP(0, stdout=diff_body)
        return _CP(1, stderr="bad args")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    out = local_runner._capture_worktree_diff("task_diff_abcd12345678", tmp_path)
    assert diff_body[:20] in out
    assert "ok" in out


def test_run_task_in_worktree_returns_diff_after_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fix (2): _run_task_in_worktree pairs run_one success with captured diff."""
    repo_before = local_runner._REPO_DIR
    monkeypatch.setattr(local_runner, "run_one", lambda *_a, **_k: True)
    monkeypatch.setattr(local_runner, "_capture_worktree_diff", lambda _tid, _wt: "+added line\n")

    task = {"id": "task_pair_123456789012", "task_type": "impl", "direction": "x"}
    ok, diff = local_runner._run_task_in_worktree(task, tmp_path)
    assert ok is True
    assert "+added line" in diff
    assert local_runner._REPO_DIR == repo_before


def test_merge_branch_to_main_pushes_origin_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fix (3): merge concludes with git push origin main (not a local-only merge)."""
    pushes: list[list[str]] = []

    def _run(args: list[str], **_kwargs: Any) -> _CP:
        if args[:2] == ["git", "fetch"]:
            return _CP(0)
        if args[:3] == ["git", "rev-parse", "--verify"] and any("origin/task/" in str(a) for a in args[3:]):
            return _CP(0, stdout="deadbeef\n")
        if args[:2] == ["git", "checkout"]:
            return _CP(0)
        if args[:2] == ["git", "merge"] and "--abort" not in args:
            return _CP(0)
        if args[:4] == ["git", "push", "origin", "main"]:
            pushes.append(args)
            return _CP(0)
        if args[:3] == ["git", "push", "origin"] and len(args) > 3 and args[3] == "--delete":
            return _CP(0)
        if args[:2] == ["git", "merge"] and "--abort" in args:
            return _CP(0)
        return _CP(0)

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner, "_REPO_DIR", tmp_path)

    ok = local_runner._merge_branch_to_main("task_merge_push_12345678")
    assert ok is True
    assert any(p for p in pushes if p[:4] == ["git", "push", "origin", "main"])


def test_push_branch_to_origin_failure_blocks_push_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fix (4): failed origin push returns False so worker gates treat phase as not landed."""

    def _run(args: list[str], **_kwargs: Any) -> _CP:
        if args[:2] == ["git", "push"]:
            return _CP(1, stderr="permission denied")
        if args[:3] == ["git", "remote", "get-url"]:
            return _CP(0, stdout="https://github.com/example/repo.git")
        return _CP(0)

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(local_runner.os.path, "isdir", lambda _p: False)

    ok = local_runner._push_branch_to_origin("task_push_fail_12345678", tmp_path)
    assert ok is False


def test_worktree_cleanup_predicate_keeps_copy_on_push_failure() -> None:
    """Fix (5): mirror worker finally — keep worktree when push failed but run reported ok."""

    def should_remove_worktree(wt: bool, pushed: bool, ok: bool) -> bool:
        # api/scripts/local_runner.py _worker_loop finally (~4584)
        return bool(wt and (pushed or not ok))

    assert should_remove_worktree(True, False, True) is False
    assert should_remove_worktree(True, True, True) is True
    assert should_remove_worktree(True, False, False) is True


def test_runner_deploy_phase_uses_runner_deploy_not_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix (6): deploy phase completes via _deploy_to_vps-style path, not LLM provider."""
    hits: dict[str, int] = {"deploy": 0, "execute": 0}

    def _deploy() -> str:
        hits["deploy"] += 1
        return "Deploy successful: abc -> def"

    def _exec(*_a: Any, **_k: Any) -> None:
        hits["execute"] += 1
        raise AssertionError("provider execute must not run for deploy phase")

    monkeypatch.setattr(local_runner, "_deploy_to_vps", _deploy)
    monkeypatch.setattr(local_runner, "execute_with_provider", _exec)
    completions: list[dict[str, Any]] = []

    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda tid, out, succ, ctx=None: completions.append({"id": tid, "out": out, "ok": succ}) or True,
    )

    task = {"id": "task_deploy_runner_1", "context": {}}
    ok = local_runner._runner_deploy_phase(task)
    assert ok is True
    assert hits["deploy"] == 1
    assert hits["execute"] == 0
    assert completions[0]["ok"] is True
    assert "successful" in completions[0]["out"].lower() or "Deploy passed" in completions[0]["out"]


def test_runner_verify_phase_uses_http_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix (7): verify uses httpx GET to real endpoints, not chat completion."""

    class _Resp:
        def __init__(self, code: int) -> None:
            self.status_code = code

    def _get(url: str, **_kwargs: Any) -> _Resp:
        return _Resp(200)

    monkeypatch.setattr(local_runner, "rc", lambda *_a, **_k: "https://api.example.test")
    # _runner_verify_phase does `import httpx` inside the loop; patch the module object.
    monkeypatch.setattr(httpx, "get", _get)
    completions: list[dict[str, Any]] = []

    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda tid, out, succ, ctx=None: completions.append({"out": out, "ok": succ}) or True,
    )

    task = {"id": "task_verify_runner_1", "context": {"idea_id": "idea-x"}}
    ok = local_runner._runner_verify_phase(task)
    assert ok is True
    assert completions[0]["ok"] is True
    assert "PASS:" in completions[0]["out"] or "passed" in completions[0]["out"].lower()
