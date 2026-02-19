from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import TaskStatus
from app.routers.agent_telegram import format_task_alert


def _telegram_update(text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "text": text,
            "from": {"id": 1001, "is_bot": False, "first_name": "tester"},
            "chat": {"id": 2002, "type": "private"},
        },
    }


@pytest.mark.asyncio
async def test_telegram_railway_status_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.release_gate_service.evaluate_public_deploy_contract_report",
        lambda **kwargs: {
            "repository": kwargs.get("repository", "seeker71/Coherence-Network"),
            "branch": kwargs.get("branch", "main"),
            "expected_sha": "1234567890abcdef1234567890abcdef12345678",
            "result": "public_contract_passed",
            "failing_checks": [],
            "warnings": [],
            "reason": "",
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway status"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Railway status*" in sent["message"]
    assert "Checked:" in sent["message"]
    assert "public_contract_passed" in sent["message"]
    assert "`1234567890ab`" in sent["message"]
    assert "Next:" in sent["message"]
    assert "[main head](https://coherence-network-production.up.railway.app/api/gates/main-head)" in sent["message"]
    assert "[tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]


@pytest.mark.asyncio
async def test_telegram_railway_verify_command_creates_and_ticks_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.release_gate_service.create_public_deploy_verification_job",
        lambda **kwargs: {
            "job_id": "job_123",
            "status": "scheduled",
            "attempts": 0,
            "max_attempts": kwargs.get("max_attempts") or 8,
        },
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.tick_public_deploy_verification_job",
        lambda **kwargs: {
            "job_id": kwargs.get("job_id", "job_123"),
            "status": "retrying",
            "attempts": 1,
            "max_attempts": 8,
            "last_result": {"result": "blocked", "reason": "railway_health"},
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway verify"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Railway verify*" in sent["message"]
    assert "Checked:" in sent["message"]
    assert "`job_123`" in sent["message"]
    assert "`retrying`" in sent["message"]
    assert "blocked" in sent["message"]
    assert "/railway tick job_123" in sent["message"]
    assert "[main head](https://coherence-network-production.up.railway.app/api/gates/main-head)" in sent["message"]
    assert "[tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]


@pytest.mark.asyncio
async def test_telegram_railway_jobs_command_lists_recent_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.release_gate_service.list_public_deploy_verification_jobs",
        lambda: [
            {"job_id": "job_a", "status": "scheduled", "attempts": 0, "max_attempts": 8},
            {"job_id": "job_b", "status": "completed", "attempts": 1, "max_attempts": 8},
        ],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway jobs"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Railway jobs*" in sent["message"]
    assert "Checked:" in sent["message"]
    assert "`job_a` scheduled" in sent["message"]
    assert "`job_b` completed" in sent["message"]
    assert "[tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]
    assert "[telegram diagnostics](https://coherence-network-production.up.railway.app/api/agent/telegram/diagnostics)" in sent["message"]


@pytest.mark.asyncio
async def test_telegram_railway_tick_requires_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway tick"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "Usage: /railway tick {job_id}" in sent["message"]


@pytest.mark.asyncio
async def test_telegram_railway_head_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.release_gate_service.get_branch_head_sha",
        lambda repository, branch, github_token=None, timeout=10.0: "abcdef1234567890abcdef1234567890abcdef12",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway head"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Railway head*" in sent["message"]
    assert "`abcdef123456`" in sent["message"]
    assert "[main head](https://coherence-network-production.up.railway.app/api/gates/main-head)" in sent["message"]
    assert "[tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]


@pytest.mark.asyncio
async def test_telegram_railway_tick_due_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.release_gate_service.tick_public_deploy_verification_jobs",
        lambda **kwargs: {
            "ok": True,
            "jobs": [
                {
                    "job_id": "job_due_1",
                    "status": "retrying",
                    "attempts": 1,
                    "max_attempts": 8,
                    "last_result": {"result": "blocked"},
                },
                {
                    "job_id": "job_due_2",
                    "status": "completed",
                    "attempts": 2,
                    "max_attempts": 8,
                    "last_result": {"result": "public_contract_passed"},
                },
            ],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway tick due"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Railway tick due*" in sent["message"]
    assert "Checked:" in sent["message"]
    assert "`job_due_1` retrying" in sent["message"]
    assert "`job_due_2` completed" in sent["message"]
    assert "Next: `/railway jobs`" in sent["message"]
    assert "[tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]
    assert "[telegram diagnostics](https://coherence-network-production.up.railway.app/api/agent/telegram/diagnostics)" in sent["message"]


@pytest.mark.asyncio
async def test_telegram_railway_schedule_command_creates_job_without_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}
    tick_called = {"value": False}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.release_gate_service.create_public_deploy_verification_job",
        lambda **kwargs: {
            "job_id": "job_sched_1",
            "status": "scheduled",
            "attempts": 0,
            "max_attempts": kwargs.get("max_attempts") or 8,
        },
    )

    def _fail_if_ticked(**kwargs):
        tick_called["value"] = True
        return {"job_id": kwargs.get("job_id", ""), "status": "completed"}

    monkeypatch.setattr(
        "app.services.release_gate_service.tick_public_deploy_verification_job",
        _fail_if_ticked,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/railway schedule 5"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Railway schedule*" in sent["message"]
    assert "Checked:" in sent["message"]
    assert "`job_sched_1`" in sent["message"]
    assert "`scheduled`" in sent["message"]
    assert "`0/5`" in sent["message"]
    assert "Next: `/railway tick due`" in sent["message"]
    assert "[tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]
    assert "[telegram diagnostics](https://coherence-network-production.up.railway.app/api/agent/telegram/diagnostics)" in sent["message"]
    assert tick_called["value"] is False


@pytest.mark.asyncio
async def test_telegram_status_command_reports_checked_and_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.agent_service.get_review_summary",
        lambda: {
            "total": 3,
            "by_status": {"running": 1, "failed": 1, "needs_decision": 1},
            "needs_attention": [{"id": "task_a"}, {"id": "task_b"}],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/status"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "*Agent status*" in sent["message"]
    assert "Checked:" in sent["message"]
    assert "Total tasks: `3`" in sent["message"]
    assert "Attention: `2`" in sent["message"]
    assert "/attention" in sent["message"]
    assert "Web UI: [open tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]


def test_format_task_alert_includes_updated_and_action() -> None:
    task = {
        "id": "task_123",
        "status": "needs_decision",
        "direction": "Handle release blocker",
        "updated_at": "2026-02-19T17:00:00Z",
        "context": {},
    }
    message = format_task_alert(task)
    assert "Updated: `2026-02-19T17:00:00Z`" in message
    assert "Action: `/reply task_123 <decision>`" in message
    assert "[open task](https://coherence-web-production.up.railway.app/tasks?task_id=task_123)" in message
    assert "[all tasks](https://coherence-web-production.up.railway.app/tasks)" in message


@pytest.mark.asyncio
async def test_telegram_tasks_command_renders_status_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["chat_id"] = str(chat_id)
        sent["message"] = message
        sent["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr(
        "app.services.agent_service.list_tasks",
        lambda status=None, limit=10: (
            [{"id": "task_1", "status": TaskStatus.PENDING, "direction": "Build telemetry endpoint"}],
            1,
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/telegram/webhook",
            json=_telegram_update("/tasks"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["chat_id"] == "2002"
    assert "`pending`" in sent["message"]
    assert "TaskStatus.PENDING" not in sent["message"]
    assert "[open](https://coherence-web-production.up.railway.app/tasks?task_id=task_1)" in sent["message"]
    assert "Web UI: [open tasks](https://coherence-web-production.up.railway.app/tasks)" in sent["message"]
