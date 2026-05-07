"""External agent encounter record tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_external_agent_encounter_records_trace_without_task() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post(
            "/api/agent/external-encounters",
            json={
                "external_agent": "Grok",
                "directed_by": "Urs via Codex Playwright browser session",
                "returned_trace_url": "https://grok.com/share/example",
                "returned_trace_summary": (
                    "Grok inspected invitation/status and named the task-engine response-link gap."
                ),
                "metadata": {
                    "conversation_url": "https://grok.com/c/example",
                    "task_engine_blocker": "POST /api/agent/tasks timed out",
                },
            },
        )

        assert created.status_code == 201, created.text
        body = created.json()
        assert body["external_agent"] == "grok"
        assert body["evidence_status"] == "trace_recorded_task_unlinked"
        assert body["trace_completeness"] == {
            "has_returned_trace": True,
            "has_response_task": False,
            "has_route_snapshot": False,
        }
        assert body["response_task_snapshot"] is None
        assert body["metadata"]["task_engine_blocker"] == "POST /api/agent/tasks timed out"

        listed = await client.get("/api/agent/external-encounters", params={"external_agent": "grok"})
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        assert any(row["id"] == body["id"] for row in rows)


@pytest.mark.asyncio
async def test_external_agent_encounter_links_response_task_route_snapshot() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        task = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "Respond to a returned Grok public encounter trace.",
                "task_type": "reflect",
                "context": {
                    "source": "test-external-agent-encounter",
                    "external_agent": "grok",
                    "model_override": "openai/gpt-4o-mini",
                },
            },
        )
        assert task.status_code == 201, task.text
        task_body = task.json()

        created = await client.post(
            "/api/agent/external-encounters",
            json={
                "external_agent": "grok",
                "directed_by": "Urs via Codex",
                "returned_trace_url": "https://grok.com/share/linked",
                "returned_trace_summary": "Grok returned a trace that should be linked to a task.",
            },
        )
        assert created.status_code == 201, created.text
        encounter_id = created.json()["id"]

        linked = await client.patch(
            f"/api/agent/external-encounters/{encounter_id}/response-task",
            json={"response_task_id": task_body["id"]},
        )

    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["response_task_id"] == task_body["id"]
    assert body["evidence_status"] == "trace_recorded_task_linked"
    assert body["trace_completeness"]["has_route_snapshot"] is True
    snapshot = body["response_task_snapshot"]
    assert snapshot["task_id"] == task_body["id"]
    assert snapshot["task_type"] == "reflect"
    assert snapshot["provider"]
    assert snapshot["route_model"]
    assert snapshot["status"] == "pending"
