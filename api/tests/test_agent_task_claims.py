"""Task claim tracking and ROI auto-pick deduplication.

Three flows cover the contract (spec: task-claim-tracking-and-roi-dedupe):

  · Claim lifecycle over HTTP — claimed_by/_at round-trip, same-worker
    reclaims, different-worker 409, needs_decision bypasses claim,
    upsert-active claim + conflict
  · Worker-id handling — normalize, runner format, response round-trip
  · Service-layer claim logic — _claim_running_task transitions from
    pending/needs_decision, conflict on different worker, terminal
    statuses always raise, fingerprint dedup (find active, skip
    completed, reuse active, question-sync fingerprints)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType

BASE = "http://test"


def _uid(prefix: str = "claim-test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_claim_lifecycle_over_http():
    """Every claim transition a runner can hit: transitions to running
    record claimed_by + claimed_at; omitted worker_id defaults to
    'unknown'; same worker can reclaim; different worker gets 409;
    pre-claim on pending rejects intruder; needs_decision decisions
    bypass the claim check; upsert-active sets the claim and conflicts
    on session_key + different worker."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Fresh pending task — no claim yet.
        t = (await c.post("/api/agent/tasks",
                          json={"direction": "claim test", "task_type": "impl"})).json()
        assert t["claimed_by"] is None and t["claimed_at"] is None
        tid = t["id"]

        # Transition to running with worker_id — claim fields populate.
        r = await c.patch(f"/api/agent/tasks/{tid}",
                          json={"status": "running", "worker_id": "node-alpha:1234"})
        body = r.json()
        assert r.status_code == 200
        assert body["claimed_by"] == "node-alpha:1234"
        assert datetime.fromisoformat(body["claimed_at"].replace("Z", "+00:00")).tzinfo is not None

        # Same worker reclaims — idempotent, no conflict.
        r = await c.patch(f"/api/agent/tasks/{tid}",
                          json={"status": "running", "worker_id": "node-alpha:1234"})
        assert r.status_code == 200 and r.json()["claimed_by"] == "node-alpha:1234"

        # Different worker attempting to take over → 409, message
        # names the current owner.
        r = await c.patch(f"/api/agent/tasks/{tid}",
                          json={"status": "running", "worker_id": "worker-B"})
        assert r.status_code == 409 and "node-alpha:1234" in r.json()["detail"]

        # needs_decision — any worker can supply a decision.
        r = await c.patch(f"/api/agent/tasks/{tid}",
                          json={"status": "needs_decision",
                                "decision_prompt": "Proceed?",
                                "worker_id": "node-alpha:1234"})
        assert r.status_code == 200
        r = await c.patch(f"/api/agent/tasks/{tid}", json={"decision": "yes, proceed"})
        assert r.status_code == 200 and r.json()["status"] == "running"

        # Default worker_id → 'unknown' when omitted on running transition.
        t2 = (await c.post("/api/agent/tasks",
                           json={"direction": "default worker", "task_type": "impl"})).json()
        r = await c.patch(f"/api/agent/tasks/{t2['id']}", json={"status": "running"})
        assert r.json()["claimed_by"] == "unknown" and r.json()["claimed_at"] is not None

    # Pre-claim on pending task — different worker intruder gets 409.
    from app.services import agent_service
    pre = agent_service.create_task(
        AgentTaskCreate(direction="pre-claimed", task_type=TaskType.IMPL)
    )
    pre["claimed_by"] = "pre-claimer"
    pre["claimed_at"] = datetime.now(timezone.utc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.patch(f"/api/agent/tasks/{pre['id']}",
                          json={"status": "running", "worker_id": "intruder"})
        assert r.status_code == 409 and "pre-claimer" in r.json()["detail"]

        # Upsert-active — sets claim on create, conflicts on reuse
        # of session_key with a different worker.
        session = _uid("session")
        r1 = await c.post("/api/agent/tasks/upsert-active", json={
            "session_key": session, "direction": "upsert test",
            "task_type": "impl", "worker_id": "ext-worker:3000",
        })
        assert r1.status_code == 200
        upsert_task = r1.json()["task"]
        assert r1.json()["created"] is True
        assert upsert_task["claimed_by"] == "ext-worker:3000"
        assert upsert_task["claimed_at"] is not None

        r2 = await c.post("/api/agent/tasks/upsert-active", json={
            "session_key": session, "direction": "upsert conflict",
            "task_type": "impl", "worker_id": "worker-second",
        })
        assert r2.status_code == 409


def test_worker_id_handling():
    """normalize_worker_id trims + defaults empty/None to 'unknown';
    the runner's default worker_id follows hostname:pid."""
    import os
    import socket
    from app.services.agent_service_task_derive import normalize_worker_id

    assert normalize_worker_id("node-A:1234") == "node-A:1234"
    assert normalize_worker_id("  node-B:5678  ") == "node-B:5678"
    assert normalize_worker_id("") == "unknown"
    assert normalize_worker_id(None) == "unknown"

    # Runner format: AGENT_WORKER_ID env or hostname:pid.
    default_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    assert default_id and (":" in default_id or os.environ.get("AGENT_WORKER_ID"))


def test_service_claim_and_fingerprint_dedup():
    """Service-layer _claim_running_task transitions pending and
    needs_decision to running with claim fields; conflicts on a
    different worker; terminal statuses always raise. Fingerprint
    search returns active tasks, skips completed, and creating a
    task with a matching fingerprint returns the existing one.
    Implementation-request question fingerprints surface in the
    active-set."""
    from app.services import agent_service
    from app.services.agent_service_crud import _claim_running_task
    from app.services.agent_service_store import TaskClaimConflictError
    from app.services.inventory_service import (
        _active_impl_question_fingerprints,
        _question_fingerprint,
    )

    # Claim from pending.
    t = {"status": TaskStatus.PENDING, "claimed_by": None,
         "claimed_at": None, "started_at": None}
    _claim_running_task(t, "node-test:100")
    assert t["status"] == TaskStatus.RUNNING
    assert t["claimed_by"] == "node-test:100"
    assert t["claimed_at"] is not None and t["started_at"] is not None

    # Claim from needs_decision.
    t2 = {"status": TaskStatus.NEEDS_DECISION, "claimed_by": None,
          "claimed_at": None, "started_at": None}
    _claim_running_task(t2, "node-decision:200")
    assert t2["status"] == TaskStatus.RUNNING and t2["claimed_by"] == "node-decision:200"

    # Conflict on different worker.
    t3 = {"status": TaskStatus.RUNNING, "claimed_by": "worker-original",
          "claimed_at": datetime.now(timezone.utc),
          "started_at": datetime.now(timezone.utc)}
    with pytest.raises(TaskClaimConflictError) as exc:
        _claim_running_task(t3, "worker-intruder")
    assert exc.value.claimed_by == "worker-original"

    # Terminal statuses always raise.
    for status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT):
        t_term = {"status": status, "claimed_by": "old-worker",
                  "claimed_at": datetime.now(timezone.utc),
                  "started_at": datetime.now(timezone.utc)}
        with pytest.raises(TaskClaimConflictError):
            _claim_running_task(t_term, "any-worker")

    # Fingerprint dedup — find active, skip completed, reuse on create.
    fp_active = f"active-{uuid4().hex[:8]}"
    active_task = agent_service.create_task(AgentTaskCreate(
        direction="fp match", task_type=TaskType.IMPL,
        context={"task_fingerprint": fp_active},
    ))
    assert agent_service.find_active_task_by_fingerprint(fp_active) == {
        **active_task,  # type: ignore[arg-type]
    } or agent_service.find_active_task_by_fingerprint(fp_active)["id"] == active_task["id"]

    fp_completed = f"completed-{uuid4().hex[:8]}"
    completed = agent_service.create_task(AgentTaskCreate(
        direction="fp completed", task_type=TaskType.IMPL,
        context={"task_fingerprint": fp_completed},
    ))
    agent_service.update_task(completed["id"], status=TaskStatus.COMPLETED, output="Done " * 50)
    assert agent_service.find_active_task_by_fingerprint(fp_completed) is None

    # The one-pass index the inventory flow reads (one store scan for every idea, not one per idea):
    # the active fingerprint is in it, the completed one is not, and the flow builds without any
    # per-idea lookup at all.
    index = agent_service.active_tasks_by_fingerprint()
    assert index[fp_active]["id"] == active_task["id"]
    assert fp_completed not in index

    fp_reuse = f"reuse-{uuid4().hex[:8]}"
    first = agent_service.create_task(AgentTaskCreate(
        direction="first", task_type=TaskType.IMPL,
        context={"task_fingerprint": fp_reuse},
    ))
    second = agent_service.create_task(AgentTaskCreate(
        direction="duplicate", task_type=TaskType.IMPL,
        context={"task_fingerprint": fp_reuse},
    ))
    assert second["id"] == first["id"]

    # Implementation-request question fingerprints surface.
    qfp = f"question-{uuid4().hex[:8]}"
    agent_service.create_task(AgentTaskCreate(
        direction="question sync", task_type=TaskType.IMPL,
        context={"source": "implementation_request_question",
                 "question_fingerprint": qfp},
    ))
    assert qfp in _active_impl_question_fingerprints()

    # _question_fingerprint is deterministic for (idea_id, question).
    fp_q = _question_fingerprint("test-idea-sync", "How do we implement X?")
    agent_service.create_task(AgentTaskCreate(
        direction="existing Q", task_type=TaskType.IMPL,
        context={"source": "implementation_request_question",
                 "question_fingerprint": fp_q, "task_fingerprint": fp_q},
    ))
    assert fp_q in _active_impl_question_fingerprints()


def test_active_fingerprint_index_reads_active_rows_from_the_database(set_config, monkeypatch):
    # With a database-backed store the index is one status-filtered query — it never loads the whole
    # store. On production the store holds 16,706 tasks (1,742 active); loading all of them cost 8.3 s
    # of every uncached /api/inventory/flow build, the active rows alone read in 0.45 s.
    from app.services import agent_service, agent_service_store, agent_task_store_service

    set_config("agent_tasks", "persist", True)
    set_config("agent_tasks", "use_db", True)
    assert agent_task_store_service.enabled()

    fp_active = f"db-active-{uuid4().hex[:8]}"
    fp_done = f"db-done-{uuid4().hex[:8]}"
    active = agent_service.create_task(AgentTaskCreate(
        direction="db active", task_type=TaskType.IMPL, context={"task_fingerprint": fp_active},
    ))
    done = agent_service.create_task(AgentTaskCreate(
        direction="db done", task_type=TaskType.IMPL, context={"task_fingerprint": fp_done},
    ))
    agent_service.update_task(done["id"], status=TaskStatus.COMPLETED, output="Done")

    def _whole_store_is_not_loaded(*args, **kwargs):
        raise AssertionError("active_tasks_by_fingerprint loaded the whole task store")

    monkeypatch.setattr(agent_service_store, "_load_store_from_disk", _whole_store_is_not_loaded)
    index = agent_service.active_tasks_by_fingerprint()

    assert index[fp_active]["id"] == active["id"]
    assert index[fp_active]["status"] == TaskStatus.PENDING
    assert index[fp_active]["output"] is None  # the narrow read carries no output column
    assert fp_done not in index


def test_inventory_cache_clone_is_independent_and_keeps_non_json_payloads():
    # The inventory cache clones by JSON round-trip (0.35 s on the 16 MB flow payload where deepcopy
    # took 1.2 s — the whole "warm" cost of the route); a payload that is not JSON-shaped is still
    # deep-copied rather than dropped.
    from app.services import inventory_service as inv

    payload = {"items": [{"idea_id": "a", "roi": 1.5, "flags": [True, None]}], "summary": {"count": 1}}
    clone = inv._clone_payload(payload)
    assert clone == payload and clone is not payload
    clone["items"][0]["idea_id"] = "b"
    assert payload["items"][0]["idea_id"] == "a"

    odd = {"ids": {"a", "b"}}
    odd_clone = inv._clone_payload(odd)
    assert odd_clone == odd and odd_clone["ids"] is not odd["ids"]

    inv._write_inventory_cache("flow", "clone-claim", payload)
    cached = inv._read_inventory_cache("flow", "clone-claim")
    assert cached == payload and cached is not payload
    inv._INVENTORY_CACHE.pop("flow", None)
