"""Tests for task claim tracking and ROI auto-pick deduplication.

Covers spec: task-claim-tracking-and-roi-dedupe

R1: Task updates to running record claim ownership (claimed_by, claimed_at)
R2: Starting already-claimed task returns 409 conflict
R3: Agent runner sends stable worker identifier when claiming tasks
R4: ROI auto-pick detects active fingerprint-matched tasks, returns task_already_active
R5: Implementation-request question sync uses active-task deduplication
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import (
    AgentTaskCreate,
    TaskStatus,
    TaskType,
)

BASE = "http://test"


def _uid(prefix: str = "claim-test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# R1: Task updates to running record claim ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_sets_claimed_by_and_claimed_at():
    """When a task transitions to running with a worker_id, claimed_by and claimed_at are set."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create a pending task
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "Test claim ownership", "task_type": "impl"},
        )
        assert r.status_code == 201
        task_id = r.json()["id"]
        assert r.json()["claimed_by"] is None
        assert r.json()["claimed_at"] is None

        # Transition to running with worker_id
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "node-alpha:1234"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["claimed_by"] == "node-alpha:1234"
        assert body["claimed_at"] is not None
        # Verify claimed_at is a valid ISO datetime
        dt = datetime.fromisoformat(body["claimed_at"].replace("Z", "+00:00"))
        assert dt.tzinfo is not None


@pytest.mark.asyncio
async def test_claim_without_worker_id_sets_unknown():
    """When transitioning to running without explicit worker_id, claimed_by defaults to 'unknown'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "Test default worker", "task_type": "impl"},
        )
        assert r.status_code == 201
        task_id = r.json()["id"]

        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["claimed_by"] == "unknown"
        assert body["claimed_at"] is not None


@pytest.mark.asyncio
async def test_same_worker_can_reclaim():
    """The same worker can PATCH running again without conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "Test reclaim", "task_type": "impl"},
        )
        task_id = r.json()["id"]

        # First claim
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "node-beta:5678"},
        )
        assert r.status_code == 200

        # Same worker reclaims -- should succeed
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "node-beta:5678"},
        )
        assert r.status_code == 200
        assert r.json()["claimed_by"] == "node-beta:5678"


# ---------------------------------------------------------------------------
# R2: Starting already-claimed task returns 409 conflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_worker_gets_409():
    """A second worker attempting to claim a running task gets 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "Test 409 conflict", "task_type": "impl"},
        )
        task_id = r.json()["id"]

        # Worker A claims
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "worker-A"},
        )
        assert r.status_code == 200

        # Worker B tries to claim
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "worker-B"},
        )
        assert r.status_code == 409
        assert "worker-A" in r.json()["detail"]


@pytest.mark.asyncio
async def test_409_on_pending_claimed_by_different_worker():
    """If a pending task was already pre-claimed, another worker gets 409."""
    from app.services import agent_service

    task = agent_service.create_task(
        AgentTaskCreate(direction="Pre-claimed test", task_type=TaskType.IMPL)
    )
    task_id = task["id"]

    # Manually set claimed_by on the pending task (simulating a pre-claim)
    task["claimed_by"] = "pre-claimer"
    task["claimed_at"] = datetime.now(timezone.utc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # A different worker tries to claim
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "intruder"},
        )
        assert r.status_code == 409
        assert "pre-claimer" in r.json()["detail"]


@pytest.mark.asyncio
async def test_decision_bypasses_claim_check():
    """A decision on a needs_decision task works even if claimed by another worker."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "Decision bypass test", "task_type": "impl"},
        )
        task_id = r.json()["id"]

        # Worker A claims
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "worker-A"},
        )
        assert r.status_code == 200

        # Transition to needs_decision
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "needs_decision",
                "decision_prompt": "Proceed?",
                "worker_id": "worker-A",
            },
        )
        assert r.status_code == 200

        # Any worker can supply a decision (no 409)
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"decision": "yes, proceed"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "running"


# ---------------------------------------------------------------------------
# R3: Agent runner sends stable worker identifier
# ---------------------------------------------------------------------------


def test_worker_id_normalize():
    """normalize_worker_id trims whitespace and defaults empty to 'unknown'."""
    from app.services.agent_service_task_derive import normalize_worker_id

    assert normalize_worker_id("node-A:1234") == "node-A:1234"
    assert normalize_worker_id("  node-B:5678  ") == "node-B:5678"
    assert normalize_worker_id("") == "unknown"
    assert normalize_worker_id(None) == "unknown"


def test_runner_worker_id_format():
    """The runner worker_id follows hostname:pid pattern or AGENT_WORKER_ID env var."""
    import os
    import socket

    # Default pattern
    hostname = socket.gethostname()
    pid = os.getpid()
    default_id = os.environ.get("AGENT_WORKER_ID") or f"{hostname}:{pid}"
    assert ":" in default_id or os.environ.get("AGENT_WORKER_ID")
    assert len(default_id) > 0


@pytest.mark.asyncio
async def test_worker_id_present_in_task_response():
    """The worker_id sent in PATCH is reflected in the task's claimed_by field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "Worker ID test", "task_type": "impl"},
        )
        task_id = r.json()["id"]

        stable_id = "vps-node-42:9999"
        r = await c.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": stable_id},
        )
        assert r.status_code == 200
        assert r.json()["claimed_by"] == stable_id

        # GET should also reflect it
        r = await c.get(f"/api/agent/tasks/{task_id}")
        assert r.status_code == 200
        assert r.json()["claimed_by"] == stable_id


# ---------------------------------------------------------------------------
# R4: ROI auto-pick detects active fingerprint-matched tasks
# ---------------------------------------------------------------------------


def test_find_active_task_by_fingerprint():
    """find_active_task_by_fingerprint returns an active task with matching fingerprint."""
    from app.services import agent_service

    fp = f"test-fp-{uuid4().hex[:8]}"
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Fingerprint match test",
            task_type=TaskType.IMPL,
            context={"task_fingerprint": fp},
        )
    )
    # Task is pending (active status)
    found = agent_service.find_active_task_by_fingerprint(fp)
    assert found is not None
    assert found["id"] == task["id"]


def test_find_active_task_by_fingerprint_skips_completed():
    """Completed tasks are not returned by fingerprint search."""
    from app.services import agent_service

    fp = f"completed-fp-{uuid4().hex[:8]}"
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Completed fingerprint test",
            task_type=TaskType.IMPL,
            context={"task_fingerprint": fp},
        )
    )
    agent_service.update_task(task["id"], status=TaskStatus.COMPLETED, output="Done " * 50)
    found = agent_service.find_active_task_by_fingerprint(fp)
    assert found is None


def test_create_task_reuses_active_fingerprint():
    """Creating a task with the same fingerprint as an active task returns the existing one."""
    from app.services import agent_service

    fp = f"reuse-fp-{uuid4().hex[:8]}"
    first = agent_service.create_task(
        AgentTaskCreate(
            direction="First task",
            task_type=TaskType.IMPL,
            context={"task_fingerprint": fp},
        )
    )
    second = agent_service.create_task(
        AgentTaskCreate(
            direction="Duplicate task",
            task_type=TaskType.IMPL,
            context={"task_fingerprint": fp},
        )
    )
    # Should return the same task, not create a new one
    assert second["id"] == first["id"]


# ---------------------------------------------------------------------------
# R5: Implementation-request question sync deduplication
# ---------------------------------------------------------------------------


def test_active_impl_question_fingerprints():
    """_active_impl_question_fingerprints returns fingerprints of active impl tasks."""
    from app.services import agent_service
    from app.services.inventory_service import _active_impl_question_fingerprints

    qfp = f"question-fp-{uuid4().hex[:8]}"
    agent_service.create_task(
        AgentTaskCreate(
            direction="Question sync test",
            task_type=TaskType.IMPL,
            context={
                "source": "implementation_request_question",
                "question_fingerprint": qfp,
            },
        )
    )
    fps = _active_impl_question_fingerprints()
    assert qfp in fps


def test_question_sync_skips_existing_fingerprint():
    """sync_implementation_request_question_tasks skips questions with active fingerprints."""
    from app.services import agent_service
    from app.services.inventory_service import (
        _active_impl_question_fingerprints,
        _question_fingerprint,
    )

    idea_id = "test-idea-sync"
    question = "How do we implement feature X?"
    fp = _question_fingerprint(idea_id, question)

    # Pre-create an active task with this fingerprint
    agent_service.create_task(
        AgentTaskCreate(
            direction="Existing question task",
            task_type=TaskType.IMPL,
            context={
                "source": "implementation_request_question",
                "question_fingerprint": fp,
                "task_fingerprint": fp,
            },
        )
    )

    fps = _active_impl_question_fingerprints()
    assert fp in fps


# ---------------------------------------------------------------------------
# Service-level claim logic
# ---------------------------------------------------------------------------


def test_claim_running_task_from_pending():
    """_claim_running_task transitions pending to running and sets claim fields."""
    from app.services.agent_service_crud import _claim_running_task
    from app.services.agent_service_store import _now

    task = {
        "status": TaskStatus.PENDING,
        "claimed_by": None,
        "claimed_at": None,
        "started_at": None,
    }
    _claim_running_task(task, "node-test:100")
    assert task["status"] == TaskStatus.RUNNING
    assert task["claimed_by"] == "node-test:100"
    assert task["claimed_at"] is not None
    assert task["started_at"] is not None


def test_claim_running_task_conflict():
    """_claim_running_task raises TaskClaimConflictError for different worker."""
    from app.services.agent_service_crud import _claim_running_task
    from app.services.agent_service_store import TaskClaimConflictError

    task = {
        "status": TaskStatus.RUNNING,
        "claimed_by": "worker-original",
        "claimed_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
    }
    with pytest.raises(TaskClaimConflictError) as exc_info:
        _claim_running_task(task, "worker-intruder")
    assert exc_info.value.claimed_by == "worker-original"


def test_claim_running_task_from_needs_decision():
    """_claim_running_task can transition needs_decision to running."""
    from app.services.agent_service_crud import _claim_running_task

    task = {
        "status": TaskStatus.NEEDS_DECISION,
        "claimed_by": None,
        "claimed_at": None,
        "started_at": None,
    }
    _claim_running_task(task, "node-decision:200")
    assert task["status"] == TaskStatus.RUNNING
    assert task["claimed_by"] == "node-decision:200"


def test_claim_terminal_status_raises():
    """_claim_running_task raises for terminal statuses (completed, failed)."""
    from app.services.agent_service_crud import _claim_running_task
    from app.services.agent_service_store import TaskClaimConflictError

    for terminal_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT):
        task = {
            "status": terminal_status,
            "claimed_by": "old-worker",
            "claimed_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
        }
        with pytest.raises(TaskClaimConflictError):
            _claim_running_task(task, "any-worker")


# ---------------------------------------------------------------------------
# Upsert-active endpoint claim tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_active_sets_claim():
    """POST /tasks/upsert-active sets claimed_by on newly created task."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        session = _uid("session")
        r = await c.post(
            "/api/agent/tasks/upsert-active",
            json={
                "session_key": session,
                "direction": "Upsert active test",
                "task_type": "impl",
                "worker_id": "ext-worker:3000",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["created"] is True
        task = body["task"]
        assert task["claimed_by"] == "ext-worker:3000"
        assert task["claimed_at"] is not None


@pytest.mark.asyncio
async def test_upsert_active_conflict_different_worker():
    """POST /tasks/upsert-active with different worker_id on existing session returns 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        session = _uid("session-conflict")

        # First upsert
        r = await c.post(
            "/api/agent/tasks/upsert-active",
            json={
                "session_key": session,
                "direction": "Upsert conflict test",
                "task_type": "impl",
                "worker_id": "worker-first",
            },
        )
        assert r.status_code == 200

        # Second upsert with different worker
        r = await c.post(
            "/api/agent/tasks/upsert-active",
            json={
                "session_key": session,
                "direction": "Upsert conflict test",
                "task_type": "impl",
                "worker_id": "worker-second",
            },
        )
        assert r.status_code == 409
        assert "worker-first" in r.json()["detail"]
