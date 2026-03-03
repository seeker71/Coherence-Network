from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_runner_registry_service


@pytest.mark.asyncio
async def test_runner_registry_heartbeat_and_list(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "runner_registry.db"
    monkeypatch.setenv("AGENT_RUNNER_REGISTRY_DATABASE_URL", f"sqlite:///{db_path}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        heartbeat = await client.post(
            "/api/agent/runners/heartbeat",
            json={
                "runner_id": "runner-a",
                "status": "idle",
                "lease_seconds": 120,
                "host": "worker-host",
                "pid": 1001,
                "active_task_id": "",
            },
        )
        assert heartbeat.status_code == 200
        hb_payload = heartbeat.json()
        assert hb_payload["runner_id"] == "runner-a"
        assert hb_payload["online"] is True
        assert hb_payload["status"] == "idle"

        listed = await client.get("/api/agent/runners")
        assert listed.status_code == 200
        listed_payload = listed.json()
        assert listed_payload["total"] == 1
        assert listed_payload["runners"][0]["runner_id"] == "runner-a"

        running = await client.post(
            "/api/agent/runners/heartbeat",
            json={
                "runner_id": "runner-a",
                "status": "running",
                "lease_seconds": 120,
                "active_task_id": "task_1",
                "active_run_id": "run_1",
            },
        )
        assert running.status_code == 200
        running_payload = running.json()
        assert running_payload["status"] == "running"
        assert running_payload["active_task_id"] == "task_1"
        assert running_payload["active_run_id"] == "run_1"


@pytest.mark.asyncio
async def test_runner_registry_filters_stale_by_default(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "runner_registry_stale.db"
    monkeypatch.setenv("AGENT_RUNNER_REGISTRY_DATABASE_URL", f"sqlite:///{db_path}")

    base_now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    offset_seconds = {"value": 0}

    def _fake_now() -> datetime:
        return base_now + timedelta(seconds=offset_seconds["value"])

    monkeypatch.setattr(agent_runner_registry_service, "_now", _fake_now)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        heartbeat = await client.post(
            "/api/agent/runners/heartbeat",
            json={
                "runner_id": "runner-stale",
                "status": "idle",
                "lease_seconds": 10,
            },
        )
        assert heartbeat.status_code == 200

        offset_seconds["value"] = 120

        listed_default = await client.get("/api/agent/runners")
        assert listed_default.status_code == 200
        assert listed_default.json()["total"] == 0

        listed_with_stale = await client.get("/api/agent/runners?include_stale=true")
        assert listed_with_stale.status_code == 200
        payload = listed_with_stale.json()
        assert payload["total"] == 1
        assert payload["runners"][0]["runner_id"] == "runner-stale"
        assert payload["runners"][0]["online"] is False
