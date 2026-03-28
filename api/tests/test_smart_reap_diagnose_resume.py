"""Tests for Smart Reap Diagnose Resume: _reap_stale_tasks in local_runner.

Acceptance (implementation docstring + body):
- Stale running tasks (age > threshold) are marked timed_out with diagnosis and error_category.
- Optional task log tail enriches diagnosis when error/timeout keywords appear.
- With idea_id and retries remaining, a retry task is POSTed with reaper_retry context,
  including checkpoint_summary and resume_patch_path when the worktree provides them.
- When max retries for the idea+phase are exceeded, a friction event is recorded instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts import local_runner


def _iso_z(mins_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=mins_ago)
    return dt.isoformat().replace("+00:00", "Z")


def test_reap_skips_tasks_younger_than_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, Any]] = []

    def fake_api(method: str, path: str, body: dict | None = None) -> Any:
        calls.append((method, path, body))
        if method == "GET" and "running" in path:
            return [
                {
                    "id": "youngtask1234567",
                    "task_type": "test",
                    "created_at": _iso_z(5),
                    "context": {"idea_id": "i1", "retry_count": 0},
                }
            ]
        return None

    monkeypatch.setattr(local_runner, "api", fake_api)
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)

    n = local_runner._reap_stale_tasks(max_age_minutes=15)

    assert n == 0
    assert len(calls) == 1
    assert calls[0][0] == "GET"


def test_reap_marks_stale_timed_out_with_category_and_diagnosis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tid = "0123456789abcdefretry01"
    old_created = _iso_z(30)
    patch_calls: list[dict] = []

    def fake_api(method: str, path: str, body: dict | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [
                {
                    "id": tid,
                    "task_type": "impl",
                    "direction": "Implement feature X",
                    "created_at": old_created,
                    "target_state": "Impl done",
                    "context": {
                        "idea_id": "idea-99",
                        "idea_name": "Feature X",
                        "provider": "codex",
                        "retry_count": 0,
                    },
                }
            ]
        if method == "PATCH" and tid in path:
            patch_calls.append(body or {})
            return {"id": tid, "status": "timed_out"}
        if method == "POST" and path.endswith("/api/agent/tasks"):
            return {"id": "newretrytaskid00"}
        return None

    monkeypatch.setattr(local_runner, "api", fake_api)
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "nowt")

    n = local_runner._reap_stale_tasks(max_age_minutes=15)

    assert n == 1
    assert len(patch_calls) == 1
    b = patch_calls[0]
    assert b["status"] == "timed_out"
    assert b["error_category"] == "stale_task_reaped"
    assert "Reaped:" in (b["output"] or "")
    assert "Stuck running" in (b["error_summary"] or "")
    assert "threshold 15m" in (b["error_summary"] or "")


def test_reap_diagnosis_appends_log_snippet_when_error_in_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tid = "abcdef0123456789"
    old_created = _iso_z(20)
    log_file = tmp_path / f"task_{tid}.log"
    log_file.write_text("x" * 600 + " ERROR: something failed\n", encoding="utf-8")

    patch_body: dict | None = None

    def fake_api(method: str, path: str, body: dict | None = None) -> Any:
        nonlocal patch_body
        if method == "GET" and "running" in path:
            return [
                {
                    "id": tid,
                    "task_type": "test",
                    "created_at": old_created,
                    "context": {"idea_id": "i2", "retry_count": 0, "provider": "openrouter"},
                }
            ]
        if method == "PATCH":
            patch_body = body
            return {"id": tid}
        if method == "POST" and "/api/agent/tasks" in path:
            return {"id": "retry22222222222"}
        return None

    monkeypatch.setattr(local_runner, "api", fake_api)
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "empty_wt")

    local_runner._reap_stale_tasks(max_age_minutes=10)

    assert patch_body is not None
    es = patch_body.get("error_summary") or ""
    assert "Partial log:" in es


def test_reap_retry_includes_checkpoint_resume_patch_and_reaper_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tid = "fedcba9876543210"
    slug = tid[:16]
    old_created = _iso_z(100)
    repo = tmp_path / "repo"
    wt_base = tmp_path / "worktrees"
    wt = wt_base / f"task-{slug}"
    wt.mkdir(parents=True)
    (wt / ".task-checkpoint.md").write_text("## Progress\n- step 1 done\n", encoding="utf-8")

    post_body: dict | None = None

    def fake_api(method: str, path: str, body: dict | None = None) -> Any:
        nonlocal post_body
        if method == "GET" and "running" in path:
            return [
                {
                    "id": tid,
                    "task_type": "test",
                    "direction": "Write tests",
                    "created_at": old_created,
                    "context": {
                        "idea_id": "idea-z",
                        "idea_name": "Zeta",
                        "provider": "codex",
                        "retry_count": 0,
                    },
                }
            ]
        if method == "PATCH":
            return {"id": tid}
        if method == "POST" and "/api/agent/tasks" in path:
            post_body = body
            return {"id": "newtaskid0000001"}
        return None

    def fake_run(cmd: list[str], **kwargs: Any) -> Any:
        class _R:
            stdout = "diff --git a/x b/x\n+line\n"
            returncode = 0

        return _R()

    monkeypatch.setattr(local_runner, "api", fake_api)
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", wt_base)
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)
    monkeypatch.setattr(local_runner.subprocess, "run", fake_run)

    local_runner._reap_stale_tasks(max_age_minutes=15)

    assert post_body is not None
    ctx = post_body.get("context") or {}
    assert ctx.get("seed_source") == "reaper_retry"
    assert ctx.get("retried_from") == tid
    assert ctx.get("retry_count") == 1
    assert ctx.get("failed_provider") == "codex"
    assert "Progress" in (ctx.get("checkpoint_summary") or "")
    rpp = ctx.get("resume_patch_path") or ""
    assert rpp.endswith(f"task_{tid}.patch")
    patch_path = Path(rpp)
    assert patch_path.exists()
    assert "diff --git" in patch_path.read_text(encoding="utf-8")


def test_reap_max_retries_posts_friction_not_new_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tid = "maxretrytaskid00"
    old_created = _iso_z(45)
    task_posts: list[dict] = []
    friction_posts: list[dict] = []

    def fake_api(method: str, path: str, body: dict | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [
                {
                    "id": tid,
                    "task_type": "spec",
                    "created_at": old_created,
                    "context": {
                        "idea_id": "idea-maxed",
                        "idea_name": "Maxed Idea",
                        "provider": "gemini",
                        "retry_count": 2,
                    },
                }
            ]
        if method == "PATCH":
            return {"id": tid}
        if method == "POST" and path.endswith("/api/agent/tasks"):
            task_posts.append(body or {})
            return {"id": "should-not-happen"}
        if method == "POST" and "friction" in path:
            friction_posts.append(body or {})
            return {"id": "friction-1"}
        return None

    monkeypatch.setattr(local_runner, "api", fake_api)
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "nw")

    local_runner._reap_stale_tasks(max_age_minutes=15)

    assert task_posts == []
    assert len(friction_posts) == 1
    f = friction_posts[0]
    assert f.get("block_type") == "repeated_timeout"
    assert f.get("owner") == "reaper"
    assert "gemini" in (f.get("notes") or "")


def test_reap_without_idea_id_only_patches_no_retry_or_friction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tid = "noideatask123456"
    old_created = _iso_z(60)
    extra: list[tuple[str, str]] = []

    def fake_api(method: str, path: str, body: dict | None = None) -> Any:
        extra.append((method, path))
        if method == "GET" and "running" in path:
            return [
                {
                    "id": tid,
                    "task_type": "impl",
                    "created_at": old_created,
                    "context": {"retry_count": 0, "provider": "codex"},
                }
            ]
        if method == "PATCH":
            return {"id": tid}
        return None

    monkeypatch.setattr(local_runner, "api", fake_api)
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "x")

    n = local_runner._reap_stale_tasks(max_age_minutes=15)

    assert n == 1
    posts = [x for x in extra if x[0] == "POST"]
    assert posts == []
