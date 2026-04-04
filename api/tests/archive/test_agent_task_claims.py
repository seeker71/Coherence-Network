from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_task_start_tracks_claim_owner_and_blocks_other_workers() -> None:
    agent_service._store.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "Implement claim ownership tracking",
                "task_type": "impl",
            },
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        first_claim = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "bot-a"},
        )
        assert first_claim.status_code == 200
        first_payload = first_claim.json()
        assert first_payload["status"] == "running"
        assert first_payload["claimed_by"] == "bot-a"
        assert first_payload["claimed_at"] is not None

        conflicting_claim = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "bot-b"},
        )
        assert conflicting_claim.status_code == 409

        idempotent_claim = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "bot-a"},
        )
        assert idempotent_claim.status_code == 200
        assert idempotent_claim.json()["claimed_by"] == "bot-a"
