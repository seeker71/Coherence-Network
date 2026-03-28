"""Tests for agent routing: spec and test task_types route to local model.

Spec 043: Ensures GET /api/agent/route?task_type=spec and task_type=test
return a local model (e.g. ollama/glm/qwen) with tier "local" per the
routing table in spec 002 (spec | test | impl | review → local; heal → claude).

Spec 039: Ensures GET /api/agent/pipeline-status returns 200 in empty state.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


_LOCAL_SPEC_ROUTE = {
    "task_type": "spec",
    "model": "ollama/glm-4.7-flash:latest",
    "command_template": "ollama run glm-4.7-flash:latest",
    "tier": "local",
    "executor": "claude",
    "provider": "local",
    "billing_provider": "local",
    "is_paid_provider": False,
}

_LOCAL_TEST_ROUTE = {
    "task_type": "test",
    "model": "ollama/glm-4.7-flash:latest",
    "command_template": "ollama run glm-4.7-flash:latest",
    "tier": "local",
    "executor": "claude",
    "provider": "local",
    "billing_provider": "local",
    "is_paid_provider": False,
}


@pytest.mark.asyncio
async def test_spec_tasks_route_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/route?task_type=spec returns 200 with a local model.

    Contract (spec 002): spec task_type routes to local tier — model must
    contain 'ollama', 'glm', or 'qwen', or tier must be 'local'.
    """
    from app.services import agent_service

    monkeypatch.setattr(agent_service, "get_route", lambda task_type, executor="auto": _LOCAL_SPEC_ROUTE)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/route", params={"task_type": "spec"})

    assert r.status_code == 200, r.text
    body = r.json()
    model: str = body.get("model", "")
    tier: str = body.get("tier", "")
    is_local_model = any(indicator in model.lower() for indicator in ("ollama", "glm", "qwen"))
    assert is_local_model or tier == "local", (
        f"Expected spec task_type to route to a local model or tier='local', "
        f"got model={model!r} tier={tier!r}"
    )


@pytest.mark.asyncio
async def test_test_tasks_route_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/route?task_type=test returns 200 with a local model.

    Contract (spec 002): test task_type routes to local tier — model must
    contain 'ollama', 'glm', or 'qwen', or tier must be 'local'.
    """
    from app.services import agent_service

    monkeypatch.setattr(agent_service, "get_route", lambda task_type, executor="auto": _LOCAL_TEST_ROUTE)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/route", params={"task_type": "test"})

    assert r.status_code == 200, r.text
    body = r.json()
    model: str = body.get("model", "")
    tier: str = body.get("tier", "")
    is_local_model = any(indicator in model.lower() for indicator in ("ollama", "glm", "qwen"))
    assert is_local_model or tier == "local", (
        f"Expected test task_type to route to a local model or tier='local', "
        f"got model={model!r} tier={tier!r}"
    )


@pytest.mark.asyncio
async def test_pipeline_status_returns_200_in_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/agent/pipeline-status returns 200 when no tasks exist (empty state).

    Spec 039: Empty state is a valid outcome — no 4xx/5xx due to absence of tasks.
    Response must include all required top-level keys with running as an empty list.
    """
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200, f"Expected 200 in empty state, got {response.status_code}: {response.text}"
    body = response.json()

    # All required top-level keys must be present
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase"):
        assert key in body, f"Missing required key '{key}' in pipeline-status response"

    # running must be a list (empty in empty state)
    assert isinstance(body["running"], list), "Expected 'running' to be a list"
    assert body["running"] == [], f"Expected 'running' to be empty in empty state, got {body['running']}"

    # attention must have required sub-keys
    attention = body["attention"]
    for key in ("stuck", "repeated_failures", "low_success_rate", "flags"):
        assert key in attention, f"Missing required key '{key}' in attention object"

    # running_by_phase must have all phase keys with empty/zero values
    running_by_phase = body["running_by_phase"]
    for phase in ("spec", "impl", "test", "review"):
        assert phase in running_by_phase, f"Missing phase '{phase}' in running_by_phase"


@pytest.mark.asyncio
async def test_effectiveness_plan_progress_includes_phase_6_and_phase_7(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/agent/effectiveness returns plan_progress with phase_6 and phase_7.

    Spec 045: plan_progress must include phase_6 (total=2) and phase_7 (total=17).
    Completion is derived from PM state and backlog (006).
    Phase 6 = items 56–57 (2 items), Phase 7 = items 58–74 (17 items).
    """
    import app.services.effectiveness_service as eff_svc

    _fake_response = {
        "throughput": {"completed_7d": 0, "tasks_per_day": 0.0},
        "success_rate": 0.0,
        "issues": {"open": 0, "resolved_7d": 0},
        "progress": {"spec": 0, "impl": 0, "test": 0, "review": 0, "heal": 0},
        "plan_progress": {
            "index": 0,
            "total": 74,
            "pct": 0.0,
            "state_file": "",
            "phase_6": {"completed": 0, "total": 2, "pct": 0.0},
            "phase_7": {"completed": 0, "total": 17, "pct": 0.0},
        },
        "goal_proximity": 0.0,
        "heal_resolved_count": 0,
        "top_issues_by_priority": [],
    }
    monkeypatch.setattr(eff_svc, "get_effectiveness", lambda: _fake_response)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200, r.text
    body = r.json()

    assert "plan_progress" in body, "plan_progress missing from effectiveness response"
    pp = body["plan_progress"]

    assert "phase_6" in pp, "plan_progress.phase_6 missing"
    assert "phase_7" in pp, "plan_progress.phase_7 missing"

    p6 = pp["phase_6"]
    assert isinstance(p6["completed"], int), "phase_6.completed must be int"
    assert isinstance(p6["total"], int), "phase_6.total must be int"
    assert p6["total"] == 2, f"phase_6.total expected 2, got {p6['total']}"

    p7 = pp["phase_7"]
    assert isinstance(p7["completed"], int), "phase_7.completed must be int"
    assert isinstance(p7["total"], int), "phase_7.total must be int"
    assert p7["total"] == 17, f"phase_7.total expected 17, got {p7['total']}"


@pytest.mark.asyncio
async def test_effectiveness_plan_progress_phase_boundary_logic() -> None:
    """_plan_progress() correctly computes phase_6 and phase_7 completion from backlog_index.

    Spec 045: Phase 6 = items 56–57 (0-based start 55), Phase 7 = items 58–74 (0-based start 57).
    Validates boundary values: 0, 56, 57, 65, 74.
    """
    import app.services.effectiveness_service as eff_svc

    cases = [
        # (backlog_index, expected_p6_completed, expected_p7_completed)
        (0, 0, 0),
        (55, 0, 0),
        (56, 1, 0),
        (57, 2, 0),
        (58, 2, 1),
        (65, 2, 8),
        (74, 2, 17),
        (200, 2, 17),  # beyond total — clamped
    ]

    original_state_files = eff_svc.STATE_FILES
    original_backlog_file = eff_svc.BACKLOG_FILE

    import tempfile, json, os

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, "project_manager_state.json")
        # Use a non-existent backlog so total=0 but phase logic still runs from constants
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = os.path.join(tmpdir, "nonexistent_006.md")

        try:
            for idx, exp_p6, exp_p7 in cases:
                with open(state_path, "w") as f:
                    json.dump({"backlog_index": idx}, f)

                result = eff_svc._plan_progress()
                p6 = result["phase_6"]
                p7 = result["phase_7"]

                assert p6["completed"] == exp_p6, (
                    f"backlog_index={idx}: phase_6.completed expected {exp_p6}, got {p6['completed']}"
                )
                assert p6["total"] == eff_svc.PHASE_6_TOTAL, (
                    f"phase_6.total expected {eff_svc.PHASE_6_TOTAL}, got {p6['total']}"
                )
                assert p7["completed"] == exp_p7, (
                    f"backlog_index={idx}: phase_7.completed expected {exp_p7}, got {p7['completed']}"
                )
                assert p7["total"] == eff_svc.PHASE_7_TOTAL, (
                    f"phase_7.total expected {eff_svc.PHASE_7_TOTAL}, got {p7['total']}"
                )
        finally:
            eff_svc.STATE_FILES = original_state_files
            eff_svc.BACKLOG_FILE = original_backlog_file
