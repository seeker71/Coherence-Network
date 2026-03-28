"""Tests for Smart Reap Diagnose Resume: ``_reap_stale_tasks`` in ``local_runner``.

Acceptance coverage (implementation in ``api/scripts/local_runner.py``):

- List running tasks; skip when none or when age ≤ threshold (``created_at``).
- Reap stale runs: PATCH ``timed_out`` with diagnosis, ``error_category=stale_task_reaped``.
- Optional diagnosis enrichment from tail of ``logs/task_{id}.log`` when it mentions error/timeout.
- If worktree ``.worktrees/task-{id[:16]}`` exists: capture ``.task-checkpoint.md`` and ``git diff HEAD`` patch under ``api/task_patches/``.
- If ``idea_id`` and ``retry_count < _MAX_RETRIES_PER_IDEA_PHASE``: POST retry task with resume context.
- If ``idea_id`` and max retries exceeded: POST friction ``repeated_timeout``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest

from scripts import local_runner


def _old_created_iso(minutes_ago: int = 20) -> str:
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return t.isoformat().replace("+00:00", "Z")


def test_reap_returns_zero_when_no_running_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_runner, "api", lambda *_a, **_k: None)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 0


def test_reap_returns_zero_when_running_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_runner, "api", lambda *_a, **_k: [])
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 0


def test_reap_skips_tasks_younger_than_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    task = {
        "id": "task_fresh_12345678",
        "task_type": "impl",
        "created_at": fresh,
        "context": {"idea_id": "idea-1"},
    }

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [task]
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 0


def test_reap_skips_task_without_created_at(monkeypatch: pytest.MonkeyPatch) -> None:
    task = {"id": "task_no_created_12345", "task_type": "impl", "context": {}}

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [task]
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 0


def test_reap_times_out_stale_task_with_diagnosis_and_category(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    repo = tmp_path / "repo"
    (repo / "api" / "task_patches").mkdir(parents=True)
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "wt")

    task_id = "task_reap_basic_xx"
    task = {
        "id": task_id,
        "task_type": "test",
        "created_at": _old_created_iso(25),
        "direction": "Run tests",
        "context": {},
    }
    patches: list[dict[str, Any]] = []

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [task]
        if method == "PATCH" and task_id in path:
            patches.append(body or {})
            return {"id": task_id, "status": "timed_out"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 1
    assert len(patches) == 1
    assert patches[0]["status"] == "timed_out"
    assert patches[0]["error_category"] == "stale_task_reaped"
    assert "Stuck running" in (patches[0].get("output") or "")
    assert "Stuck running" in (patches[0].get("error_summary") or "")


def test_reap_enriches_diagnosis_from_task_log_when_error_keyword_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(local_runner, "_LOG_DIR", log_dir)
    repo = tmp_path / "repo"
    (repo / "api" / "task_patches").mkdir(parents=True)
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "wt")

    task_id = "task_log_diag_xx_01"
    (log_dir / f"task_{task_id}.log").write_text("x" * 400 + " ERROR: something broke\n", encoding="utf-8")

    task = {
        "id": task_id,
        "task_type": "impl",
        "created_at": _old_created_iso(30),
        "context": {},
    }
    patches: list[dict[str, Any]] = []

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [task]
        if method == "PATCH" and task_id in path:
            patches.append(body or {})
            return {"id": task_id, "status": "timed_out"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 1
    assert "Partial log:" in (patches[0].get("error_summary") or "")


def test_reap_creates_retry_with_checkpoint_and_resume_patch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(local_runner, "_LOG_DIR", log_dir)
    repo = tmp_path / "repo"
    patch_dir = repo / "api" / "task_patches"
    patch_dir.mkdir(parents=True)
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)

    # slug = task_id[:16] → first 16 chars must match worktree folder name segment
    task_id = "task_smart_reap_cp_01"
    slug16 = task_id[:16]
    assert slug16 == "task_smart_reap"
    wt_root = tmp_path / "worktrees" / f"task-{slug16}"
    wt_root.mkdir(parents=True)
    (wt_root / ".task-checkpoint.md").write_text("## Progress\n- step A done\n", encoding="utf-8")
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "worktrees")

    diff_text = "diff --git a/foo b/foo\n+hello\n"
    monkeypatch.setattr(
        local_runner.subprocess,
        "run",
        lambda *_a, **_k: CompletedProcess([], 0, stdout=diff_text, stderr=""),
    )

    task = {
        "id": task_id,
        "task_type": "impl",
        "created_at": _old_created_iso(40),
        "direction": "Implement feature X",
        "target_state": "Impl done",
        "context": {
            "idea_id": "idea-reap-1",
            "idea_name": "Feature X",
            "provider": "codex",
            "retry_count": 0,
        },
    }
    posts: list[dict[str, Any]] = []

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [task]
        if method == "PATCH" and task_id in path:
            return {"id": task_id, "status": "timed_out"}
        if method == "POST" and path == "/api/agent/tasks":
            posts.append(body or {})
            return {"id": "task_retry_new_01"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 1

    assert len(posts) == 1
    ctx = posts[0].get("context") or {}
    assert ctx.get("retry_count") == 1
    assert ctx.get("retried_from") == task_id
    assert ctx.get("failed_provider") == "codex"
    assert ctx.get("seed_source") == "reaper_retry"
    assert "step A done" in (ctx.get("checkpoint_summary") or "")
    resume_patch = ctx.get("resume_patch_path") or ""
    assert "task_patches" in resume_patch
    assert Path(resume_patch).name == f"task_{task_id}.patch"
    assert Path(resume_patch).read_text(encoding="utf-8") == diff_text


def test_reap_posts_friction_when_max_retries_reached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / "api" / "task_patches").mkdir(parents=True)
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "wt")

    task_id = "task_max_retry_xx_01"
    task = {
        "id": task_id,
        "task_type": "impl",
        "created_at": _old_created_iso(60),
        "context": {
            "idea_id": "idea-mx-1",
            "idea_name": "Heavy task",
            "provider": "openrouter",
            "retry_count": 2,
        },
    }
    frictions: list[dict[str, Any]] = []

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return [task]
        if method == "PATCH" and task_id in path:
            return {"id": task_id, "status": "timed_out"}
        if method == "POST" and path == "/api/friction/events":
            frictions.append(body or {})
            return {"id": "fr-1"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 1
    assert len(frictions) == 1
    assert frictions[0].get("block_type") == "repeated_timeout"
    assert frictions[0].get("severity") == "high"
    assert frictions[0].get("owner") == "reaper"


def test_reap_accepts_tasks_wrapped_in_dict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    repo = tmp_path / "repo"
    (repo / "api" / "task_patches").mkdir(parents=True)
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", tmp_path / "wt")

    task_id = "task_wrapped_resp_01"
    task = {
        "id": task_id,
        "task_type": "spec",
        "created_at": _old_created_iso(22),
        "context": {},
    }

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if method == "GET" and "running" in path:
            return {"tasks": [task]}
        if method == "PATCH" and task_id in path:
            return {"id": task_id, "status": "timed_out"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(local_runner, "api", _api)
    assert local_runner._reap_stale_tasks(max_age_minutes=15) == 1
