from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_runner_registry_service, agent_service


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


@pytest.mark.asyncio
async def test_runner_idle_heartbeat_reaps_orphaned_running_tasks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "runner_registry_orphan.db"
    monkeypatch.setenv("AGENT_RUNNER_REGISTRY_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_ORPHAN_RUNNING_SEC", "60")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    agent_service._store.clear()

    sent_messages: list[str] = []

    async def _fake_send_alert(message: str, parse_mode: str = "Markdown") -> bool:
        sent_messages.append(message)
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_alert", _fake_send_alert)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "orphan recovery probe", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        started = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "runner-a"},
        )
        assert started.status_code == 200
        sent_messages.clear()

        # Simulate an orphaned running task older than threshold.
        task = agent_service.get_task(task_id)
        assert task is not None
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=3700)
        task["started_at"] = stale_time
        task["claimed_at"] = stale_time
        task["updated_at"] = stale_time

        heartbeat = await client.post(
            "/api/agent/runners/heartbeat",
            json={
                "runner_id": "runner-a",
                "status": "idle",
                "lease_seconds": 120,
                "active_task_id": "",
            },
        )
        assert heartbeat.status_code == 200

        refreshed = await client.get(f"/api/agent/tasks/{task_id}")
        assert refreshed.status_code == 200
        payload = refreshed.json()
        assert payload["status"] == "failed"
        assert "auto-recovered" in str(payload.get("output") or "")

    assert len(sent_messages) == 1
    assert task_id in sent_messages[0]


@pytest.mark.asyncio
async def test_task_failed_alert_emits_once_per_status_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    sent_messages: list[str] = []

    async def _fake_send_alert(message: str, parse_mode: str = "Markdown") -> bool:
        sent_messages.append(message)
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_alert", _fake_send_alert)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "suppress duplicate failed alert", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "runner-a"},
        )
        assert running.status_code == 200

        first_failed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "first failure"},
        )
        assert first_failed.status_code == 200

        duplicate_failed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "same failure, updated context"},
        )
        assert duplicate_failed.status_code == 200

    assert len(sent_messages) == 1
    assert task_id in sent_messages[0]


@pytest.mark.asyncio
async def test_task_needs_decision_alert_emits_once_per_status_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    sent_messages: list[str] = []

    async def _fake_send_alert(message: str, parse_mode: str = "Markdown") -> bool:
        sent_messages.append(message)
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_alert", _fake_send_alert)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "suppress duplicate needs decision alert", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        to_needs_decision = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "needs_decision", "decision_prompt": "Approve deploy?"},
        )
        assert to_needs_decision.status_code == 200

        same_status_update = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "needs_decision", "decision_prompt": "Approve deploy to staging?"},
        )
        assert same_status_update.status_code == 200

    assert len(sent_messages) == 1
    assert task_id in sent_messages[0]
