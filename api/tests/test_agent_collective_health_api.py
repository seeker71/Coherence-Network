from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.models.friction import FrictionEvent
from app.services import agent_service, friction_service, metrics_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


@pytest.mark.asyncio
async def test_collective_health_endpoint_returns_scores_and_components(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))

    _reset_agent_store()

    task1 = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement coherence scoring",
            task_type=TaskType.IMPL,
            context={
                "task_card": {
                    "goal": "Implement collective health endpoint",
                    "files_allowed": ["api/app/services/collective_health_service.py"],
                    "done_when": ["endpoint returns 200"],
                    "commands": ["cd api && pytest -q tests/test_agent_collective_health_api.py"],
                    "constraints": ["no placeholder data"],
                },
                "spec_id": "114-collective-health",
            },
            target_state="collective health endpoint returns coherence/resonance/flow/friction",
            success_evidence=["GET /api/agent/collective-health returns 200"],
        )
    )
    agent_service.update_task(task1["id"], status=TaskStatus.COMPLETED, worker_id="openai-codex")

    task2 = agent_service.create_task(
        AgentTaskCreate(
            direction="Investigate flow bottleneck",
            task_type=TaskType.HEAL,
            context={"spec_id": "114-collective-health", "retry_reflections": [{"retry_number": 1}]},
        )
    )
    agent_service.update_task(
        task2["id"],
        status=TaskStatus.FAILED,
        context={
            "retry_reflections": [
                {
                    "retry_number": 1,
                    "failure_category": "timeout",
                    "blind_spot": "Scope too wide",
                    "next_action": "Reduce scope",
                }
            ]
        },
        worker_id="openai-codex",
    )

    metrics_service.record_task(task1["id"], "impl", "openai-codex", 40.0, "completed")
    metrics_service.record_task(task2["id"], "heal", "openai-codex", 220.0, "failed")

    friction_service.append_event(
        FrictionEvent(
            id="fric-collective-1",
            timestamp=datetime.now(timezone.utc),
            stage="execution",
            block_type="timeout",
            severity="high",
            owner="runner",
            unblock_condition="reduce scope and retry",
            energy_loss_estimate=4.0,
            cost_of_delay=2.0,
            status="open",
            task_id=task2["id"],
        )
    )

    (tmp_path / "monitor_issues.json").write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "issue-collective-1",
                        "condition": "no_task_running",
                        "severity": "medium",
                        "message": "pending queue has no runner",
                    }
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
    assert payload["window_days"] == 7

    scores = payload["scores"]
    for key in ("coherence", "resonance", "flow", "friction", "collective_value"):
        assert isinstance(scores[key], (int, float))
        assert 0.0 <= float(scores[key]) <= 1.0

    expected_collective_value = round(
        float(scores["coherence"])
        * float(scores["resonance"])
        * float(scores["flow"])
        * (1.0 - float(scores["friction"])),
        4,
    )
    assert float(scores["collective_value"]) == pytest.approx(expected_collective_value, rel=1e-6)

    assert payload["coherence"]["task_count"] >= 2
    assert payload["friction"]["open_events"] >= 1
    assert isinstance(payload["top_friction_queue"], list)
    assert isinstance(payload["top_opportunities"], list)


@pytest.mark.asyncio
async def test_collective_health_friction_queue_surfaces_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("METRICS_FILE_PATH", str(tmp_path / "metrics.jsonl"))
    monkeypatch.setenv("MONITOR_ISSUES_PATH", str(tmp_path / "monitor_issues.json"))

    _reset_agent_store()

    now = datetime.now(timezone.utc)
    friction_service.append_event(
        FrictionEvent(
            id="fric-collective-queue-1",
            timestamp=now,
            stage="deploy",
            block_type="checks_failed",
            severity="high",
            owner="ci",
            unblock_condition="fix failing checks",
            energy_loss_estimate=8.0,
            cost_of_delay=4.0,
            status="open",
        )
    )

    (tmp_path / "monitor_issues.json").write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "issue-collective-queue-1",
                        "condition": "github_actions_high_failure_rate",
                        "severity": "high",
                        "message": "High GH actions failure rate",
                        "suggested_action": "Triage latest failed run",
                    }
                ],
                "last_check": now.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/collective-health")

    assert response.status_code == 200
    payload = response.json()
    queue = payload["top_friction_queue"]
    assert len(queue) >= 1
    assert "key" in queue[0]
    assert "severity" in queue[0]
    assert float(queue[0]["signal"]) >= 0.0
