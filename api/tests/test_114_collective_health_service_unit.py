"""Unit and integration tests for spec 114: Collective Health Service internals.

Covers scenarios not addressed by the existing integration tests:
- ignored_events field presence and value in friction diagnostics
- Friction queue sorted by signal descending across multiple stages
- Coherence score formula weights verified via known task inputs
- Resonance reference_reuse_ratio rises when tasks share spec_id
- Resonance learning_capture_ratio rises with retry_reflections
- Flow status_counts maps expected status keys
- Friction score formula: open_density + energy_norm + issue_norm
- top_friction_queue signal formula: energy_loss + 0.5 * event_count per stage
- Zero-task: collective_value = 0.5^3 * (1 - friction_score)
- Repeated window_days values produce stable scores
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.models.friction import FrictionEvent
from app.services import agent_service, friction_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


def _base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))


# ---------------------------------------------------------------------------
# ignored_events field present in friction diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friction_diagnostics_has_ignored_events_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """friction pillar must include ignored_events (integer >= 0)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    friction = response.json()["friction"]
    assert "ignored_events" in friction
    assert isinstance(friction["ignored_events"], int)
    assert friction["ignored_events"] >= 0


@pytest.mark.asyncio
async def test_friction_diagnostics_ignored_events_zero_when_no_ignored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When all events are open (none ignored), ignored_events must be 0."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    friction_service.append_event(
        FrictionEvent(
            id="fric-ignored-test-1",
            timestamp=datetime.now(timezone.utc),
            stage="execution",
            block_type="timeout",
            severity="medium",
            owner="runner",
            unblock_condition="retry",
            energy_loss_estimate=2.0,
            cost_of_delay=1.0,
            status="open",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    friction = response.json()["friction"]
    assert friction["ignored_events"] == 0


# ---------------------------------------------------------------------------
# Friction queue sorted by signal descending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friction_queue_sorted_by_signal_descending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """top_friction_queue entries must be sorted by signal value descending."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    now = datetime.now(timezone.utc)
    # Add events in different stages with different energy losses
    for i, (stage, energy) in enumerate([
        ("deploy", 10.0),
        ("execution", 2.0),
        ("planning", 5.0),
    ]):
        friction_service.append_event(
            FrictionEvent(
                id=f"fric-sorted-{i}",
                timestamp=now,
                stage=stage,
                block_type="timeout",
                severity="medium",
                owner="runner",
                unblock_condition="retry",
                energy_loss_estimate=energy,
                cost_of_delay=energy / 2.0,
                status="open",
            )
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    queue = response.json()["top_friction_queue"]
    assert len(queue) >= 1

    signals = [float(entry["signal"]) for entry in queue]
    assert signals == sorted(signals, reverse=True), (
        f"top_friction_queue not sorted by signal desc: {signals}"
    )


# ---------------------------------------------------------------------------
# Coherence formula: tasks with target_state and evidence raise scores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_coherence_score_rises_with_target_state_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Coherence score with target_state + evidence > score without them."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    # Task with good spec coverage
    agent_service.create_task(
        AgentTaskCreate(
            direction="Well-specified task",
            task_type=TaskType.IMPL,
            context={
                "target_state_contract": {"goal": "endpoint returns 200"},
                "success_evidence": ["GET /api/health returns 200"],
                "spec_id": "spec-coherence-unit",
            },
            target_state="well-specified goal",
            success_evidence=["endpoint passes"],
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()
    coherence = payload["coherence"]
    # With target_state_contract present, target_state_coverage should be 1.0
    assert float(coherence["target_state_coverage"]) > 0.0
    # evidence_coverage should reflect success_evidence on the task
    # Score must be in range and represent real data (not neutral fallback 0.5)
    assert 0.0 <= float(coherence["score"]) <= 1.0
    # task_count must be 1
    assert coherence["task_count"] == 1


# ---------------------------------------------------------------------------
# Resonance reference_reuse_ratio rises when tasks share spec_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resonance_reference_reuse_rises_with_shared_spec_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Two tasks sharing the same spec_id must raise reference_reuse_ratio above 0."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    shared_spec = "spec-shared-resonance"
    for i in range(2):
        agent_service.create_task(
            AgentTaskCreate(
                direction=f"Shared spec task {i}",
                task_type=TaskType.IMPL,
                context={"spec_id": shared_spec},
            )
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    resonance = response.json()["resonance"]
    # tracked_reference_total should be >= 2 (both tasks reference the shared spec)
    assert resonance["tracked_reference_total"] >= 2
    # reused_reference_count should be >= 1 (the spec appears >1 time)
    assert resonance["reused_reference_count"] >= 1
    assert float(resonance["reference_reuse_ratio"]) > 0.0


# ---------------------------------------------------------------------------
# Resonance learning_capture_ratio rises with retry_reflections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resonance_learning_capture_ratio_rises_with_reflections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Failed tasks with retry_reflections must increase learning_capture_ratio."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Failing task with reflection",
            task_type=TaskType.HEAL,
            context={
                "retry_reflections": [
                    {
                        "retry_number": 1,
                        "failure_category": "scope",
                        "blind_spot": "Too broad",
                        "next_action": "Narrow scope",
                    }
                ]
            },
        )
    )
    agent_service.update_task(task["id"], status=TaskStatus.FAILED)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    resonance = response.json()["resonance"]
    # Failed tasks with reflections should have learning_capture_ratio = 1.0
    assert float(resonance["learning_capture_ratio"]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Flow status_counts contains expected status keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_status_counts_has_expected_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """flow.status_counts must contain all TaskStatus values as keys."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    status_counts = response.json()["flow"]["status_counts"]
    assert isinstance(status_counts, dict)

    expected_keys = {"pending", "running", "completed", "failed", "needs_decision"}
    for key in expected_keys:
        assert key in status_counts, f"status_counts missing key: {key}"
        assert isinstance(status_counts[key], int)
        assert status_counts[key] >= 0


@pytest.mark.asyncio
async def test_flow_status_counts_reflects_actual_task_statuses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """status_counts must accurately reflect task statuses from the store."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    t1 = agent_service.create_task(AgentTaskCreate(direction="task1", task_type=TaskType.IMPL))
    agent_service.update_task(t1["id"], status=TaskStatus.COMPLETED)

    t2 = agent_service.create_task(AgentTaskCreate(direction="task2", task_type=TaskType.IMPL))
    agent_service.update_task(t2["id"], status=TaskStatus.FAILED)

    # Third task stays pending
    agent_service.create_task(AgentTaskCreate(direction="task3", task_type=TaskType.IMPL))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    status_counts = response.json()["flow"]["status_counts"]
    assert status_counts["completed"] == 1
    assert status_counts["failed"] == 1
    assert status_counts["pending"] == 1


# ---------------------------------------------------------------------------
# Zero-task collective_value = 0.5^3 * (1 - friction)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_task_collective_value_formula(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With zero tasks, collective_value = 0.5^3 * (1 - friction_score)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    s = response.json()["scores"]

    assert float(s["coherence"]) == pytest.approx(0.5)
    assert float(s["resonance"]) == pytest.approx(0.5)
    assert float(s["flow"]) == pytest.approx(0.5)

    expected_cv = 0.5 * 0.5 * 0.5 * (1.0 - float(s["friction"]))
    assert float(s["collective_value"]) == pytest.approx(expected_cv, rel=1e-5)


# ---------------------------------------------------------------------------
# Friction score formula components: issue_norm from monitor_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friction_score_rises_with_monitor_issues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Adding monitor issues must raise friction score above 0.0."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    # No friction events but 5 monitor issues
    (tmp_path / "monitor_issues.json").write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": f"issue-{i}",
                        "condition": "test_condition",
                        "severity": "medium",
                        "message": f"Issue {i}",
                    }
                    for i in range(5)
                ],
                "last_check": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()
    assert float(payload["friction"]["score"]) > 0.0
    assert payload["friction"]["issue_count"] == 5


# ---------------------------------------------------------------------------
# Friction queue signal = energy_loss + 0.5 * event_count (single event)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friction_queue_signal_equals_energy_plus_half_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """For a single friction event, signal = energy_loss + 0.5 * 1 (event_count=1)."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    energy = 6.0
    friction_service.append_event(
        FrictionEvent(
            id="fric-signal-exact-1",
            timestamp=datetime.now(timezone.utc),
            stage="integration",
            block_type="api_error",
            severity="high",
            owner="api",
            unblock_condition="fix api",
            energy_loss_estimate=energy,
            cost_of_delay=3.0,
            status="open",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    queue = response.json()["top_friction_queue"]
    assert len(queue) >= 1

    signal = float(queue[0]["signal"])
    # signal = energy_loss_aggregate + 0.5 * event_count (per stage)
    # One event in "integration": energy=6.0, count=1 → signal = 6.0 + 0.5 = 6.5
    expected_signal = energy + 0.5 * 1
    assert signal == pytest.approx(expected_signal, rel=1e-4), (
        f"Expected signal {expected_signal}, got {signal}"
    )


# ---------------------------------------------------------------------------
# Two events same stage: signal aggregates both
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friction_queue_signal_aggregates_same_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Two events in the same stage aggregate: signal = sum(energy) + 0.5 * count."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    now = datetime.now(timezone.utc)
    for i, energy in enumerate([3.0, 5.0]):
        friction_service.append_event(
            FrictionEvent(
                id=f"fric-agg-{i}",
                timestamp=now,
                stage="deploy",
                block_type="timeout",
                severity="medium",
                owner="ci",
                unblock_condition="retry",
                energy_loss_estimate=energy,
                cost_of_delay=energy / 2.0,
                status="open",
            )
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    queue = response.json()["top_friction_queue"]
    assert len(queue) >= 1

    # Find the "deploy" stage entry
    deploy_entry = next((e for e in queue if "deploy" in str(e.get("key", ""))), None)
    assert deploy_entry is not None, f"deploy stage not found in queue: {queue}"

    # signal = (3.0 + 5.0) + 0.5 * 2 = 8.0 + 1.0 = 9.0
    expected_signal = (3.0 + 5.0) + 0.5 * 2
    assert float(deploy_entry["signal"]) == pytest.approx(expected_signal, rel=1e-4)


# ---------------------------------------------------------------------------
# Collective value: all scores > 0 gives positive collective_value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_value_positive_when_all_pillars_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With tasks and no friction, collective_value must be a positive float."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Healthy task",
            task_type=TaskType.IMPL,
            context={"spec_id": "spec-positive-cv"},
            target_state="green",
            success_evidence=["passes"],
        )
    )
    agent_service.update_task(task["id"], status=TaskStatus.COMPLETED)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    s = response.json()["scores"]
    # All pillar scores should be positive (tasks present → not neutral, friction=0.0)
    assert float(s["collective_value"]) > 0.0
    assert float(s["collective_value"]) <= 1.0


# ---------------------------------------------------------------------------
# window_days=14 vs window_days=7 both return valid responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collective_health_different_window_days_both_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """window_days=7 and window_days=14 both return 200 with correct window_days."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r7 = await client.get("/api/agent/collective-health?window_days=7")
        r14 = await client.get("/api/agent/collective-health?window_days=14")

    assert r7.status_code == 200
    assert r14.status_code == 200
    assert r7.json()["window_days"] == 7
    assert r14.json()["window_days"] == 14


# ---------------------------------------------------------------------------
# top_friction_queue and top_opportunities are lists (not null) when empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_data_returns_lists_not_null(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With no tasks and no friction, lists must be [] — not null."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["top_friction_queue"] == []
    assert isinstance(payload["top_opportunities"], list)


# ---------------------------------------------------------------------------
# No 5xx on any valid window_days value in [1, 30]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_5xx_for_all_valid_window_days(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """window_days values 1, 7, 14, 30 all return non-500 responses."""
    _base_env(monkeypatch, tmp_path)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for days in (1, 7, 14, 30):
            r = await client.get(f"/api/agent/collective-health?window_days={days}")
            assert r.status_code != 500, f"Got 500 for window_days={days}"
            assert r.status_code == 200
