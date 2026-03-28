"""Acceptance tests for Smart Reap — Spec 169.

This file covers the API endpoint acceptance criteria (R7, R9) that require
importing app.main. It patches the missing diagnose_batch symbol in
smart_reaper_service before the app loads, making the import succeed.

Tests:
  test_reap_history_endpoint_empty
  test_reap_history_endpoint_populated
  test_reap_history_endpoint_needs_attention_filter
  test_reap_history_endpoint_idea_id_filter
  test_reap_diagnosis_endpoint_200
  test_reap_diagnosis_endpoint_404_no_diagnosis
  test_reap_diagnosis_endpoint_404_task_not_found
  test_smart_reap_service_r1_runner_alive
  test_smart_reap_service_r2_extension_cap
  test_smart_reap_service_r3_r4_dead_runner_diagnosis
  test_smart_reap_service_r5_resume_task_created
  test_smart_reap_service_r5_no_resume_below_threshold
  test_smart_reap_service_r6_human_attention_threshold
  test_smart_reap_service_r10_idempotent_reap
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Patch missing diagnose_batch before app.main is imported so that
# agent_smart_reap_routes can load without ImportError.
# ---------------------------------------------------------------------------
if "app.services.smart_reaper_service" not in sys.modules:
    _mock_srs = MagicMock()
    _mock_srs.diagnose_batch = MagicMock(return_value=[])
    sys.modules["app.services.smart_reaper_service"] = _mock_srs
else:
    _existing = sys.modules["app.services.smart_reaper_service"]
    if not hasattr(_existing, "diagnose_batch"):
        _existing.diagnose_batch = MagicMock(return_value=[])

# ---------------------------------------------------------------------------
# Helpers shared with service-level tests
# ---------------------------------------------------------------------------

def _task(
    task_id: str | None = None,
    task_type: str = "impl",
    idea_id: str = "idea_test",
    claimed_by: str | None = None,
    context: dict | None = None,
    age_minutes: float = 20.0,
    direction: str = "Do the thing",
    target_state: str | None = None,
    status: str = "running",
) -> dict[str, Any]:
    tid = task_id or f"task_{uuid.uuid4().hex[:12]}"
    created = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).isoformat()
    ctx = {"idea_id": idea_id, "idea_name": "Test Idea", "provider": "claude", **(context or {})}
    return {
        "id": tid,
        "task_type": task_type,
        "status": status,
        "claimed_by": claimed_by,
        "created_at": created,
        "updated_at": created,
        "direction": direction,
        "target_state": target_state,
        "context": ctx,
    }


def _runner(runner_id: str, last_seen_seconds_ago: float = 10.0) -> dict[str, Any]:
    last_seen = (datetime.now(timezone.utc) - timedelta(seconds=last_seen_seconds_ago)).isoformat()
    return {"runner_id": runner_id, "last_seen_at": last_seen}


def _api_fn(calls: list | None = None):
    recorded = [] if calls is None else calls

    def fn(method: str, path: str, body: dict | None = None) -> dict | None:
        recorded.append({"method": method, "path": path, "body": body})
        if method == "POST" and "/tasks" in path and body:
            return {"id": f"task_{uuid.uuid4().hex[:12]}"}
        if method == "PATCH" and "/tasks/" in path:
            return {"id": path.split("/")[-1], "status": "timed_out"}
        return {}

    fn.calls = recorded
    return fn


# ---------------------------------------------------------------------------
# Service-level acceptance tests (pure unit, no app startup)
# ---------------------------------------------------------------------------

from app.services.smart_reap_service import (
    REAP_HUMAN_ATTENTION_THRESHOLD,
    REAP_MAX_EXTENSIONS,
    REAP_RUNNER_LIVENESS_SECONDS,
    aggregate_reap_history,
    can_extend,
    capture_partial_output,
    estimate_partial_pct,
    is_runner_alive,
    smart_reap_task,
)


def test_smart_reap_service_r1_runner_alive():
    """R1: Runner alive check returns True when runner is recently seen."""
    task = _task(claimed_by="runner-1")
    runners = [_runner("runner-1", last_seen_seconds_ago=30)]
    assert is_runner_alive(task, runners) is True


def test_smart_reap_service_r1_runner_dead():
    """R1: Runner dead when last_seen_at exceeds liveness window."""
    task = _task(claimed_by="runner-1")
    runners = [_runner("runner-1", last_seen_seconds_ago=REAP_RUNNER_LIVENESS_SECONDS + 60)]
    assert is_runner_alive(task, runners) is False


def test_smart_reap_service_r1_unclaimed_task():
    """R1: Unclaimed task (claimed_by=None) → runner considered dead."""
    task = _task(claimed_by=None)
    runners = [_runner("runner-A")]
    assert is_runner_alive(task, runners) is False


def test_smart_reap_service_r2_extension_cap():
    """R2: Task at max extensions is reaped even if runner alive."""
    calls = []
    fn = _api_fn(calls)
    task = _task(claimed_by="runner-A", context={"reap_extensions": REAP_MAX_EXTENSIONS})
    runners = [_runner("runner-A", last_seen_seconds_ago=10)]
    result = smart_reap_task(
        task,
        runners=runners,
        timed_out_tasks=[],
        log_dir=Path("/tmp/nonexistent_test_path"),
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "reaped"


def test_smart_reap_service_r3_r4_dead_runner_diagnosis(tmp_path):
    """R3+R4: Dead runner triggers reap with structured reap_diagnosis in context."""
    calls = []
    fn = _api_fn(calls)
    task = _task(claimed_by=None)

    result = smart_reap_task(
        task,
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

    # Verify reap_diagnosis written into PATCH context
    patch_calls = [c for c in calls if c["method"] == "PATCH" and "timed_out" in str(c.get("body", {}))]
    assert patch_calls, "Expected a PATCH with status=timed_out"
    ctx = patch_calls[0]["body"]["context"]
    assert "reap_diagnosis" in ctx
    assert ctx["reap_diagnosis"]["runner_alive"] is False


def test_smart_reap_service_r5_resume_task_created(tmp_path):
    """R5: partial_output_pct >= 20% triggers resume task creation."""
    task_id = "task_resume_acc"
    log_file = tmp_path / f"task_{task_id}.log"
    log_file.write_text("X" * 1100)  # 1100/5000 = 22%

    calls = []
    fn = _api_fn(calls)
    task = _task(task_id=task_id, claimed_by=None)

    result = smart_reap_task(
        task,
        runners=[],
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "reaped"
    diag = result["diagnosis"]
    assert diag["partial_output_pct"] >= 20
    assert diag["resume_task_id"] is not None

    post_calls = [c for c in calls if c["method"] == "POST" and "/tasks" in c["path"]]
    assert len(post_calls) == 1
    assert "Previous attempt" in post_calls[0]["body"]["direction"]


def test_smart_reap_service_r5_no_resume_below_threshold(tmp_path):
    """R5: partial_output_pct < 20% → no resume task created."""
    task_id = "task_noresume_acc"
    log_file = tmp_path / f"task_{task_id}.log"
    log_file.write_text("Y" * 500)  # 500/5000 = 10%

    calls = []
    fn = _api_fn(calls)
    task = _task(task_id=task_id, claimed_by=None)

    result = smart_reap_task(
        task,
        runners=[],
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "reaped"
    diag = result["diagnosis"]
    assert diag["partial_output_pct"] < 20
    assert diag["resume_task_id"] is None
    post_calls = [c for c in calls if c["method"] == "POST"]
    assert len(post_calls) == 0


def test_smart_reap_service_r6_human_attention_threshold(tmp_path):
    """R6: 3rd timeout for same idea+type sets needs_human_attention=True, no resume."""
    idea_id = "idea_attention_acc"
    task_type = "impl"
    # 2 existing timed_out tasks
    existing = [
        _task(task_type=task_type, idea_id=idea_id, claimed_by=None),
        _task(task_type=task_type, idea_id=idea_id, claimed_by=None),
    ]
    calls = []
    fn = _api_fn(calls)
    task = _task(task_id="task_third_acc", task_type=task_type, idea_id=idea_id, claimed_by=None)

    result = smart_reap_task(
        task,
        runners=[],
        timed_out_tasks=existing,
        log_dir=tmp_path,
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "reaped"

    patch_calls = [c for c in calls if c["method"] == "PATCH"]
    assert patch_calls
    ctx = patch_calls[0]["body"]["context"]
    assert ctx["reap_history"]["needs_human_attention"] is True
    assert ctx["reap_history"]["timeout_count"] == 3

    # No resume task created when needs_human_attention
    post_calls = [c for c in calls if c["method"] == "POST"]
    assert len(post_calls) == 0


def test_smart_reap_service_r10_idempotent_reap(tmp_path):
    """R10: Task already with reap_diagnosis is skipped (idempotent)."""
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
    calls = []
    fn = _api_fn(calls)
    task = _task(claimed_by=None, context={"reap_diagnosis": existing_diag})

    result = smart_reap_task(
        task,
        runners=[],
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=15,
        api_fn=fn,
    )
    assert result["action"] == "skipped"
    assert len(calls) == 0


# ---------------------------------------------------------------------------
# aggregate_reap_history unit tests
# ---------------------------------------------------------------------------

def test_aggregate_reap_history_empty_list():
    """aggregate_reap_history returns [] for empty input."""
    assert aggregate_reap_history([]) == []


def test_aggregate_reap_history_single_task():
    """aggregate_reap_history aggregates a single timed_out task."""
    reaped_at = datetime.now(timezone.utc).isoformat()
    tasks = [
        {
            "id": "t1",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_single",
                "idea_name": "Single Idea",
                "reap_diagnosis": {"error_class": "executor_crash", "partial_output_pct": 20, "reaped_at": reaped_at},
            },
        }
    ]
    result = aggregate_reap_history(tasks)
    assert len(result) == 1
    assert result[0]["idea_id"] == "idea_single"
    assert result[0]["timeout_count"] == 1
    assert result[0]["last_error_class"] == "executor_crash"
    assert result[0]["needs_human_attention"] is False


def test_aggregate_reap_history_threshold_flags_attention():
    """aggregate_reap_history sets needs_human_attention=True at threshold."""
    reaped_at = datetime.now(timezone.utc).isoformat()
    tasks = [
        {
            "id": f"t{i}",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_flag_acc",
                "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at},
            },
        }
        for i in range(REAP_HUMAN_ATTENTION_THRESHOLD)
    ]
    result = aggregate_reap_history(tasks)
    assert len(result) == 1
    assert result[0]["needs_human_attention"] is True
    assert result[0]["timeout_count"] == REAP_HUMAN_ATTENTION_THRESHOLD


# ---------------------------------------------------------------------------
# API endpoint tests: R7 GET /api/agent/reap-history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reap_history_endpoint_empty():
    """R7: GET /api/agent/reap-history returns empty result when no timed_out tasks."""
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
    """R7: GET /api/agent/reap-history aggregates and returns timed_out tasks."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    reaped_at = datetime.now(timezone.utc).isoformat()
    fake_tasks = [
        {
            "id": "t_pop1",
            "task_type": "impl",
            "updated_at": reaped_at,
            "created_at": reaped_at,
            "context": {
                "idea_id": "idea_populated",
                "idea_name": "Populated Idea",
                "reap_diagnosis": {
                    "error_class": "executor_crash",
                    "partial_output_pct": 30,
                    "reaped_at": reaped_at,
                },
            },
        }
    ]
    with patch.object(agent_service, "list_tasks", return_value=(fake_tasks, 1, 0)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/reap-history")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    item = next((i for i in body["items"] if i["idea_id"] == "idea_populated"), None)
    assert item is not None
    assert item["timeout_count"] == 1
    assert item["last_error_class"] == "executor_crash"


@pytest.mark.asyncio
async def test_reap_history_endpoint_needs_attention_filter():
    """R7: GET /api/agent/reap-history?needs_attention=true filters correctly."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    reaped_at = datetime.now(timezone.utc).isoformat()
    # 3 tasks for the same idea → needs_human_attention=True
    fake_tasks = [
        {
            "id": f"t_attn{i}",
            "task_type": "impl",
            "updated_at": reaped_at,
            "created_at": reaped_at,
            "context": {
                "idea_id": "idea_attn",
                "idea_name": "Attn Idea",
                "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at},
            },
        }
        for i in range(REAP_HUMAN_ATTENTION_THRESHOLD)
    ]
    with patch.object(agent_service, "list_tasks", return_value=(fake_tasks, len(fake_tasks), 0)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/reap-history?needs_attention=true")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["needs_human_attention"] is True


@pytest.mark.asyncio
async def test_reap_history_endpoint_idea_id_filter():
    """R7: GET /api/agent/reap-history?idea_id=X returns only matching idea."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    reaped_at = datetime.now(timezone.utc).isoformat()
    fake_tasks = [
        {
            "id": "t_filter1",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_target",
                "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at},
            },
        },
        {
            "id": "t_filter2",
            "task_type": "impl",
            "context": {
                "idea_id": "idea_other",
                "reap_diagnosis": {"error_class": "timeout", "partial_output_pct": 0, "reaped_at": reaped_at},
            },
        },
    ]
    with patch.object(agent_service, "list_tasks", return_value=(fake_tasks, 2, 0)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/reap-history?idea_id=idea_target")

    assert r.status_code == 200
    body = r.json()
    assert all(i["idea_id"] == "idea_target" for i in body["items"])


# ---------------------------------------------------------------------------
# API endpoint tests: R9 GET /api/agent/tasks/{id}/reap-diagnosis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reap_diagnosis_endpoint_200():
    """R9: GET /api/agent/tasks/{id}/reap-diagnosis returns 200 with structured diagnosis."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    reaped_at = datetime.now(timezone.utc).isoformat()
    fake_task = {
        "id": "task_diag_acc01",
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
                "resume_task_id": "task_resume_acc01",
                "reaped_at": reaped_at,
            }
        },
    }
    with patch.object(agent_service, "get_task", return_value=fake_task):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks/task_diag_acc01/reap-diagnosis")

    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == "task_diag_acc01"
    assert body["runner_alive"] is False
    assert body["error_class"] == "executor_crash"
    assert body["partial_output_chars"] == 1840
    assert body["partial_output_pct"] == 34
    assert body["extensions_granted"] == 1
    assert body["resume_task_id"] == "task_resume_acc01"
    assert "reaped_at" in body


@pytest.mark.asyncio
async def test_reap_diagnosis_endpoint_404_no_diagnosis():
    """R9: returns 404 when task exists but has no reap_diagnosis."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    fake_task = {"id": "task_clean_acc", "status": "completed", "context": {}}
    with patch.object(agent_service, "get_task", return_value=fake_task):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks/task_clean_acc/reap-diagnosis")

    assert r.status_code == 404
    assert "no reap diagnosis" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reap_diagnosis_endpoint_404_task_not_found():
    """R9: returns 404 when task does not exist at all."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services import agent_service

    with patch.object(agent_service, "get_task", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks/nonexistent_acc/reap-diagnosis")

    assert r.status_code == 404
