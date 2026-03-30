from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_run_state_claim_update_get_with_lease_owner_enforced(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "run_state.db"
    monkeypatch.setenv("AGENT_RUN_STATE_DATABASE_URL", f"sqlite:///{db_path}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        claim_a = await client.post(
            "/api/agent/run-state/claim",
            json={
                "task_id": "task_lease_1",
                "run_id": "run_a",
                "worker_id": "worker-a",
                "lease_seconds": 120,
                "attempt": 1,
                "branch": "codex/task_lease_1",
            },
        )
        assert claim_a.status_code == 200
        claim_a_payload = claim_a.json()
        assert claim_a_payload["claimed"] is True

        claim_b = await client.post(
            "/api/agent/run-state/claim",
            json={
                "task_id": "task_lease_1",
                "run_id": "run_b",
                "worker_id": "worker-b",
                "lease_seconds": 120,
                "attempt": 1,
                "branch": "codex/task_lease_1",
            },
        )
        assert claim_b.status_code == 200
        claim_b_payload = claim_b.json()
        assert claim_b_payload["claimed"] is False
        assert claim_b_payload["detail"] == "lease_owned_by_other_worker"

        update_owner = await client.post(
            "/api/agent/run-state/update",
            json={
                "task_id": "task_lease_1",
                "run_id": "run_a",
                "worker_id": "worker-a",
                "patch": {"status": "completed", "next_action": "done"},
                "require_owner": True,
            },
        )
        assert update_owner.status_code == 200
        update_owner_payload = update_owner.json()
        assert update_owner_payload["claimed"] is True
        assert update_owner_payload["status"] == "completed"

        state = await client.get("/api/agent/run-state/task_lease_1")
        assert state.status_code == 200
        state_payload = state.json()
        assert state_payload["status"] == "completed"
        assert state_payload["worker_id"] == "worker-a"
