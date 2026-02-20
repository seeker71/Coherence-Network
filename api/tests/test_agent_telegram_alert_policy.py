from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_runner_updates_send_hourly_summary_not_every_patch(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_service._store.clear()
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    monkeypatch.setenv("TELEGRAM_RUNNER_SUMMARY_MIN_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv(
        "TELEGRAM_RUNNER_SUMMARY_STATE_FILE",
        str(tmp_path / "telegram_runner_summary_state.json"),
    )

    sent_messages: list[str] = []

    async def _fake_send_alert(message: str, parse_mode: str = "Markdown") -> bool:
        sent_messages.append(message)
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_alert", _fake_send_alert)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "runner summary throttle test", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        first = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "running",
                "worker_id": "runner-a",
                "current_step": "phase 1",
                "progress_pct": 10,
            },
        )
        assert first.status_code == 200

        second = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "running",
                "worker_id": "runner-a",
                "current_step": "phase 2",
                "progress_pct": 40,
            },
        )
        assert second.status_code == 200

    assert len(sent_messages) == 1
    assert "hourly pipeline summary" in sent_messages[0].lower()


@pytest.mark.asyncio
async def test_failed_status_from_runner_sends_failed_alert_not_runner_summary(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_service._store.clear()
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    monkeypatch.setenv("TELEGRAM_RUNNER_SUMMARY_MIN_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv(
        "TELEGRAM_RUNNER_SUMMARY_STATE_FILE",
        str(tmp_path / "telegram_runner_summary_state.json"),
    )

    sent_messages: list[str] = []

    async def _fake_send_alert(message: str, parse_mode: str = "Markdown") -> bool:
        sent_messages.append(message)
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_alert", _fake_send_alert)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "failed alert precedence test", "task_type": "impl"},
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        started = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "running",
                "worker_id": "runner-a",
                "current_step": "phase 1",
                "progress_pct": 25,
            },
        )
        assert started.status_code == 200

        failed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "failed",
                "worker_id": "runner-a",
                "output": "pytest failed in CI",
            },
        )
        assert failed.status_code == 200

    assert len(sent_messages) == 2
    assert "*failed*" in sent_messages[-1].lower()
    assert f"/task {task_id}" in sent_messages[-1]
