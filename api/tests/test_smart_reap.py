"""Tests for Smart Reap — Spec 169.

Covers R1–R10 acceptance tests:
  test_runner_alive_extends_timeout
  test_runner_dead_reaps_with_diagnosis
  test_partial_output_creates_resume_task
  test_no_resume_below_20pct
  test_reap_history_endpoint_empty
  test_reap_history_endpoint_populated
  test_reap_diagnosis_endpoint_200
  test_reap_diagnosis_endpoint_404
  test_needs_human_attention_after_3_timeouts
  test_idempotent_double_reap
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.services.smart_reap_service import (
    REAP_HUMAN_ATTENTION_THRESHOLD,
    REAP_MAX_EXTENSIONS,
    REAP_RUNNER_LIVENESS_SECONDS,
    aggregate_reap_history,
    build_resume_direction,
    can_extend,
    capture_partial_output,
    estimate_partial_pct,
    get_extension_count,
    get_idea_timeout_count_from_tasks,
    is_runner_alive,
    smart_reap_task,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(
    task_id: str | None = None,
    task_type: str = "impl",
    idea_id: str = "idea_test",
    claimed_by: str | None = None,
    context: dict | None = None,
    age_minutes: float = 20.0,
    direction: str = "Do the thing",
) -> dict[str, Any]:
    tid = task_id or f"task_{uuid.uuid4().hex[:12]}"
    created = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).isoformat()
    ctx = {"idea_id": idea_id, "idea_name": "Test Idea", "provider": "claude", **(context or {})}
    return {
        "id": tid,
        "task_type": task_type,
        "claimed_by": claimed_by,
        "created_at": created,
        "updated_at": created,
        "direction": direction,
        "target_state": "Completed",
        "context": ctx,
    }


def _runner(runner_id: str, last_seen_seconds_ago: float = 10.0) -> dict[str, Any]:
    last_seen = (datetime.now(timezone.utc) - timedelta(seconds=last_seen_seconds_ago)).isoformat()
    return {"runner_id": runner_id, "last_seen_at": last_seen}


def _api_fn(calls: list | None = None):
    """Returns a mock api_fn that records calls and returns sensible defaults."""
    recorded = [] if calls is None else calls

    def fn(method: str, path: str, body: dict | None = None) -> dict | None:
        recorded.append({"method": method, "path": path, "body": body})
        if method == "POST" and "/tasks" in path and body:
            # Simulate created task
            return {"id": f"task_{uuid.uuid4().hex[:12]}"}
        if method == "PATCH" and "/tasks/" in path:
            return {"id": path.split("/")[-1], "status": "timed_out"}
        return {}

    fn.calls = recorded
    return fn


# ---------------------------------------------------------------------------
# Unit tests: is_runner_alive
# ---------------------------------------------------------------------------

def test_runner_alive_when_recently_seen():
    task = _task(claimed_by="runner-A")
    runners = [_runner("runner-A", last_seen_seconds_ago=30)]
    assert is_runner_alive(task, runners) is True


def test_runner_dead_when_not_seen_recently():
    task = _task(claimed_by="runner-A")
    runners = [_runner("runner-A", last_seen_seconds_ago=REAP_RUNNER_LIVENESS_SECONDS + 60)]
    assert is_runner_alive(task, runners) is False


def test_runner_dead_when_not_in_registry():
    task = _task(claimed_by="runner-missing")
    runners = [_runner("runner-other")]
    assert is_runner_alive(task, runners) is False


def test_runner_dead_when_claimed_by_none():
    task = _task(claimed_by=None)
    runners = [_runner("runner-A")]
    assert is_runner_alive(task, runners) is False


# ---------------------------------------------------------------------------
# Unit tests: can_extend
# ---------------------------------------------------------------------------

def test_can_extend_when_no_extensions_yet():
    task = _task(age_minutes=17, context={"reap_extensions": 0})
    assert can_extend(task, max_age_minutes=15) is True


def test_cannot_extend_at_max():
    task = _task(age_minutes=17, context={"reap_extensions": REAP_MAX_EXTENSIONS})
    assert can_extend(task, max_age_minutes=15) is False


def test_cannot_extend_beyond_3x_max_age():
    task = _task(age_minutes=50, context={"reap_extensions": 0})
    assert can_extend(task, max_age_minutes=15) is False  # 50 > 3*15=45


# ---------------------------------------------------------------------------
# Unit tests: capture_partial_output
# ---------------------------------------------------------------------------

def test_capture_partial_output_reads_log(tmp_path):
    log_dir = tmp_path
    task_id = "task_abc123"
    log_file = log_dir / f"task_{task_id}.log"
    content = "A" * 5000
    log_file.write_text(content)
    text, chars = capture_partial_output(task_id, log_dir)
    assert chars == 4096
    assert len(text) == 4096


def test_capture_partial_output_returns_empty_when_no_log(tmp_path):
    text, chars = capture_partial_output("task_nonexistent", tmp_path)
    assert text == ""
    assert chars == 0


# ---------------------------------------------------------------------------
# Unit tests: estimate_partial_pct
# ---------------------------------------------------------------------------

def test_estimate_partial_pct_impl():
    pct = estimate_partial_pct(1000, "impl")  # 1000/5000=20%
    assert pct == 20


def test_estimate_partial_pct_capped_at_100():
    pct = estimate_partial_pct(100_000, "spec")
    assert pct == 100


def test_estimate_partial_pct_zero():
    assert estimate_partial_pct(0, "impl") == 0


def test_estimate_partial_pct_uses_target_state():
    pct = estimate_partial_pct(500, "impl", target_state="x" * 2000)
    assert pct == 25


# ---------------------------------------------------------------------------
# Unit tests: build_resume_direction
# ---------------------------------------------------------------------------

def test_build_resume_direction_includes_partial():
    direction = build_resume_direction("Do the thing", "partial code here")
    assert "Previous attempt produced this partial work" in direction
    assert "partial code here" in direction
    assert "Do the thing" in direction


def test_build_resume_direction_truncates_partial():
    long_partial = "X" * 5000
    direction = build_resume_direction("orig", long_partial)
    assert "[truncated]" in direction
    assert len(direction) < 10000


# ---------------------------------------------------------------------------
# R1 — Runner alive → extend timeout
# ---------------------------------------------------------------------------

def test_runner_alive_extends_timeout():
    """R1+R2: alive runner causes extension, not reap."""
    calls = []
    fn = _api_fn(calls)
    t = _task(claimed_by="runner-A", context={"reap_extensions": 0})
    runners = [_runner("runner-A", last_seen_seconds_ago=10)]
    result = smart_reap_task(
        t,
        runners=runners,
        timed_out_tasks=[],
        log_dir=Path("/tmp/nonexistent"),
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "extended"
    # Should have patched context with reap_extensions=1
    patch_calls = [c for c in calls if c["method"] == "PATCH"]
    assert len(patch_calls) == 1
    assert patch_calls[0]["body"]["context"]["reap_extensions"] == 1


def test_runner_alive_max_extensions_then_reap():
    """R2: after max extensions, reap even if runner alive."""
    calls = []
    fn = _api_fn(calls)
    t = _task(claimed_by="runner-A", context={"reap_extensions": REAP_MAX_EXTENSIONS})
    runners = [_runner("runner-A", last_seen_seconds_ago=10)]
    result = smart_reap_task(
        t,
        runners=runners,
        timed_out_tasks=[],
        log_dir=Path("/tmp/nonexistent"),
        max_age_minutes=15,
        api_fn=fn,
    )
    # Max extensions reached → reap
    assert result["action"] == "reaped"


# ---------------------------------------------------------------------------
# R3+R4 — Dead runner → reap with diagnosis
# ---------------------------------------------------------------------------

def test_runner_dead_reaps_with_diagnosis(tmp_path):
    """R3+R4: dead runner triggers reap with structured diagnosis."""
    calls = []
    fn = _api_fn(calls)
    t = _task(claimed_by=None)

    result = smart_reap_task(
        t,
        runners=[],
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "reaped"
    diag = result["diagnosis"]
    assert diag is not None
    assert diag["runner_alive"] is False
    assert "error_class" in diag
    assert "reaped_at" in diag
    assert diag["extensions_granted"] == 0


def test_diagnosis_written_to_context(tmp_path):
    """R4: reap_diagnosis is written into task context on PATCH."""
    calls = []
    fn = _api_fn(calls)
    t = _task(claimed_by=None)

    smart_reap_task(
        t, runners=[], timed_out_tasks=[], log_dir=tmp_path, max_age_minutes=15, api_fn=fn
    )
    patch_calls = [c for c in calls if c["method"] == "PATCH" and "timed_out" in str(c.get("body", {}))]
    assert len(patch_calls) == 1
    ctx = patch_calls[0]["body"]["context"]
    assert "reap_diagnosis" in ctx
    assert ctx["reap_diagnosis"]["runner_alive"] is False


# ---------------------------------------------------------------------------
# R5 — Partial output >= 20% → resume task
# ---------------------------------------------------------------------------

def test_partial_output_creates_resume_task(tmp_path):
    """R5: >= 20% partial output creates a resume task."""
    task_id = "task_resume01"
    log_file = tmp_path / f"task_{task_id}.log"
    # 1100 chars / 5000 (impl baseline) = 22%
    log_file.write_text("A" * 1100)

    calls = []
    fn = _api_fn(calls)
    t = _task(task_id=task_id, claimed_by=None)

    result = smart_reap_task(
        t, runners=[], timed_out_tasks=[], log_dir=tmp_path, max_age_minutes=15, api_fn=fn
    )
    assert result["action"] == "reaped"
    diag = result["diagnosis"]
    assert diag["partial_output_pct"] >= 20
    assert diag["resume_task_id"] is not None
    # Verify POST /tasks was called for resume
    post_calls = [c for c in calls if c["method"] == "POST" and "/tasks" in c["path"]]
    assert len(post_calls) == 1
    assert "Previous attempt" in post_calls[0]["body"]["direction"]


def test_no_resume_below_20pct(tmp_path):
    """R5: < 20% partial output → no resume task."""
    task_id = "task_noresume"
    log_file = tmp_path / f"task_{task_id}.log"
    # 500 chars / 5000 = 10%
    log_file.write_text("B" * 500)

    calls = []
    fn = _api_fn(calls)
    t = _task(task_id=task_id, claimed_by=None)

    result = smart_reap_task(
        t, runners=[], timed_out_tasks=[], log_dir=tmp_path, max_age_minutes=15, api_fn=fn
    )
    assert result["action"] == "reaped"
    diag = result["diagnosis"]
    assert diag["partial_output_pct"] < 20
    assert diag["resume_task_id"] is None
    post_calls = [c for c in calls if c["method"] == "POST"]
    assert len(post_calls) == 0


# ---------------------------------------------------------------------------
# R6 — Reap history: needs_human_attention after 3 timeouts
# ---------------------------------------------------------------------------

def test_needs_human_attention_after_3_timeouts(tmp_path):
    """R6: 3rd timeout for same idea+type sets needs_human_attention."""
    idea_id = "idea_repeated"
    task_type = "impl"

    # 2 existing timed_out tasks for this idea
    existing = [
        _task(task_type=task_type, idea_id=idea_id, claimed_by=None),
        _task(task_type=task_type, idea_id=idea_id, claimed_by=None),
    ]

    calls = []
    fn = _api_fn(calls)
    t = _task(task_id="task_third", task_type=task_type, idea_id=idea_id, claimed_by=None)

    result = smart_reap_task(
        t, runners=[], timed_out_tasks=existing, log_dir=tmp_path, max_age_minutes=15, api_fn=fn
    )
    assert result["action"] == "reaped"
    diag = result["diagnosis"]

    # context should have reap_history with needs_human_attention=True
    patch_calls = [c for c in calls if c["method"] == "PATCH"]
    assert len(patch_calls) == 1
    ctx = patch_calls[0]["body"]["context"]
    assert ctx["reap_history"]["needs_human_attention"] is True
    assert ctx["reap_history"]["timeout_count"] == 3

    # No resume task created because needs_human_attention
    post_calls = [c for c in calls if c["method"] == "POST"]
    assert len(post_calls) == 0


# ---------------------------------------------------------------------------
# R10 — Idempotent double reap
# ---------------------------------------------------------------------------

def test_idempotent_double_reap(tmp_path):
    """R10: task that already has reap_diagnosis is skipped gracefully."""
    calls = []
    fn = _api_fn(calls)
    existing_diag = {
        "runner_alive": False,
        "provider": "claude",
        "error_class": "executor_crash",
        "partial_output_chars": 0,
        "partial_output_pct": 0,
        "extensions_granted": 0,
        "resume_task_id": None,
        "reaped_at": datetime.now(timezone.utc).isoformat(),
    }
    t = _task(claimed_by=None, context={"reap_diagnosis": existing_diag})

    result = smart_reap_task(
        t, runners=[], timed_out_tasks=[], log_dir=tmp_path, max_age_minutes=15, api_fn=fn
    )
    assert result["action"] == "skipped"
    # No API calls made
    assert len(calls) == 0


# ---------------------------------------------------------------------------
# aggregate_reap_history unit tests
# ---------------------------------------------------------------------------

def test_aggregate_reap_history_empty():
    result = aggregate_reap_history([])
    assert result == []


def test_aggregate_reap_history_groups_by_idea_and_type():
    reaped_at = datetime.now(timezone.utc).isoformat()
    tasks = [
        {
            "id": "t1",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_a",
                "idea_name": "Idea A",
                "reap_diagnosis": {"error_class": "executor_crash", "partial_output_pct": 10, "reaped_at": reaped_at},
            },
        },
        {
            "id": "t2",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_a",
                "idea_name": "Idea A",
                "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 5, "reaped_at": reaped_at},
            },
        },
        {
            "id": "t3",
            "task_type": "spec",
            "context": {
                "idea_id": "idea_b",
                "idea_name": "Idea B",
                "reap_diagnosis": {"error_class": "unknown", "partial_output_pct": 0, "reaped_at": reaped_at},
            },
        },
    ]
    result = aggregate_reap_history(tasks)
    assert len(result) == 2
    idea_a = next(r for r in result if r["idea_id"] == "idea_a")
    assert idea_a["timeout_count"] == 2
    assert idea_a["task_type"] == "impl"
    idea_b = next(r for r in result if r["idea_id"] == "idea_b")
    assert idea_b["timeout_count"] == 1


def test_aggregate_reap_history_needs_attention_flag():
    reaped_at = datetime.now(timezone.utc).isoformat()
    tasks = [
        {
            "id": f"t{i}",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_flag",
                "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at},
            },
        }
        for i in range(REAP_HUMAN_ATTENTION_THRESHOLD)
    ]
    result = aggregate_reap_history(tasks)
    assert result[0]["needs_human_attention"] is True


def test_aggregate_reap_history_idea_id_filter():
    reaped_at = datetime.now(timezone.utc).isoformat()
    tasks = [
        {
            "id": "t1",
            "task_type": "impl",
            "context": {"idea_id": "idea_x", "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at}},
        },
        {
            "id": "t2",
            "task_type": "impl",
            "context": {"idea_id": "idea_y", "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at}},
        },
    ]
    result = aggregate_reap_history(tasks, idea_id_filter="idea_x")
    assert len(result) == 1
    assert result[0]["idea_id"] == "idea_x"


# ---------------------------------------------------------------------------
# API endpoint tests (R7, R9)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reap_history_endpoint_empty():
    """R7: GET /api/agent/reap-history returns empty when no timed_out tasks."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    with patch.object(agent_service, "list_tasks", return_value=([], 0, 0)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/reap-history")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_reap_history_endpoint_populated():
    """R7: GET /api/agent/reap-history aggregates timed_out tasks."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    reaped_at = datetime.now(timezone.utc).isoformat()
    fake_tasks = [
        {
            "id": "t1",
            "task_type": "impl",
            "updated_at": reaped_at,
            "created_at": reaped_at,
            "context": {
                "idea_id": "idea_pop",
                "idea_name": "Populated Idea",
                "reap_diagnosis": {"error_class": "executor_crash", "partial_output_pct": 30, "reaped_at": reaped_at},
            },
        }
    ]
    with patch.object(agent_service, "list_tasks", return_value=(fake_tasks, 1, 0)):
        from httpx import ASGITransport, AsyncClient
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/reap-history")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["idea_id"] == "idea_pop")
    assert item["timeout_count"] == 1
    assert item["last_error_class"] == "executor_crash"


@pytest.mark.asyncio
async def test_reap_diagnosis_endpoint_200():
    """R9: GET /api/agent/tasks/{id}/reap-diagnosis returns 200 with diagnosis."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    reaped_at = datetime.now(timezone.utc).isoformat()
    fake_task = {
        "id": "task_diag01",
        "task_type": "impl",
        "status": "timed_out",
        "context": {
            "reap_diagnosis": {
                "runner_alive": False,
                "provider": "claude",
                "error_class": "executor_crash",
                "partial_output_chars": 1840,
                "partial_output_pct": 34,
                "extensions_granted": 1,
                "resume_task_id": "task_resume01",
                "reaped_at": reaped_at,
            }
        },
    }
    with patch.object(agent_service, "get_task", return_value=fake_task):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks/task_diag01/reap-diagnosis")

    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == "task_diag01"
    assert body["runner_alive"] is False
    assert body["error_class"] == "executor_crash"
    assert body["partial_output_pct"] == 34
    assert body["resume_task_id"] == "task_resume01"


@pytest.mark.asyncio
async def test_reap_diagnosis_endpoint_404():
    """R9: GET /api/agent/tasks/{id}/reap-diagnosis returns 404 for non-reaped task."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    # Task exists but has no reap_diagnosis
    fake_task = {"id": "task_clean01", "status": "completed", "context": {}}
    with patch.object(agent_service, "get_task", return_value=fake_task):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks/task_clean01/reap-diagnosis")

    assert r.status_code == 404
    assert "no reap diagnosis" in r.json()["detail"]


@pytest.mark.asyncio
async def test_reap_diagnosis_endpoint_404_task_not_found():
    """R9: returns 404 when task doesn't exist."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    with patch.object(agent_service, "get_task", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks/nonexistent_task/reap-diagnosis")

    assert r.status_code == 404
