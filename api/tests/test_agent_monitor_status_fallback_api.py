from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_monitor_issues_returns_fresh_file_payload_without_derivation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setattr("app.routers.agent._agent_logs_dir", lambda: str(tmp_path))
    _reset_agent_store()

    expected = {
        "issues": [
            {
                "id": "abc123",
                "condition": "custom_condition",
                "severity": "medium",
                "priority": 1,
                "message": "Custom issue from monitor",
                "suggested_action": "Custom action",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "resolved_at": None,
            }
        ],
        "last_check": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }
    (tmp_path / "monitor_issues.json").write_text(json.dumps(expected), encoding="utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/monitor-issues")
        assert response.status_code == 200
        payload = response.json()

    assert payload == expected


@pytest.mark.asyncio
async def test_monitor_issues_derives_orphan_running_when_monitor_file_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("PIPELINE_ORPHAN_RUNNING_SECONDS", "60")
    monkeypatch.setattr("app.routers.agent._agent_logs_dir", lambda: str(tmp_path))
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Simulate stale running task", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex"},
        )
        assert running.status_code == 200

        # Force stale running duration without sleeping in test.
        agent_service._store[task_id]["started_at"] = datetime.now(timezone.utc) - timedelta(seconds=180)

        response = await client.get("/api/agent/monitor-issues")
        assert response.status_code == 200
        payload = response.json()

    assert payload["source"] == "derived_pipeline_status"
    assert payload["fallback_reason"] == "missing_monitor_issues_file"
    assert payload.get("last_check")
    conditions = {row.get("condition") for row in payload["issues"]}
    assert "orphan_running" in conditions


@pytest.mark.asyncio
async def test_status_report_falls_back_to_derived_live_report_when_file_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("PIPELINE_ORPHAN_RUNNING_SECONDS", "60")
    monkeypatch.setattr("app.routers.agent._agent_logs_dir", lambda: str(tmp_path))
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Status report fallback from live state", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex"},
        )
        assert running.status_code == 200
        agent_service._store[task_id]["started_at"] = datetime.now(timezone.utc) - timedelta(seconds=180)

        response = await client.get("/api/agent/status-report")
        assert response.status_code == 200
        payload = response.json()

    assert payload["source"] == "derived_pipeline_status"
    assert payload["fallback_reason"] == "missing_status_report_file"
    assert payload.get("generated_at")
    assert payload["overall"]["status"] == "needs_attention"
    assert payload["layer_3_attention"]["status"] == "needs_attention"
    assert "orphan_running" in payload["overall"]["needs_attention"]

