from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import TaskType



def _assistant_update(text: str, *, user_id: int = 1001, chat_id: int = 2002) -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "text": text,
            "from": {"id": user_id, "is_bot": False, "first_name": "tester"},
            "chat": {"id": chat_id, "type": "private"},
        },
    }


@pytest.mark.asyncio
async def test_assistant_research_command_creates_spec_task_and_queues_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_PERSONAL_BOT_TOKEN", "assistant-token")
    monkeypatch.setenv("TELEGRAM_PERSONAL_ALLOWED_USER_IDS", "1001")
    monkeypatch.setenv("TELEGRAM_PERSONAL_AUTO_EXECUTE", "1")

    captured: dict[str, Any] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        captured["chat_id"] = str(chat_id)
        captured["message"] = message
        captured["parse_mode"] = parse_mode
        return True

    def _fake_create_task(data):
        captured["direction"] = data.direction
        captured["task_type"] = data.task_type
        captured["context"] = dict(data.context or {})
        return {
            "id": "task_assistant_1",
            "direction": data.direction,
            "task_type": data.task_type,
            "status": "pending",
            "model": "openclaw/openrouter/free",
            "command": "openclaw run ...",
            "context": data.context or {},
        }

    def _fake_execute_task(task_id: str, **kwargs):
        captured["executed_task_id"] = task_id
        captured["execute_kwargs"] = kwargs
        return {"ok": True, "status": "completed"}

    monkeypatch.setattr("app.services.telegram_personal_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr("app.services.agent_service.create_task", _fake_create_task)
    monkeypatch.setattr("app.services.agent_execution_service.execute_task", _fake_execute_task)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/assistant/telegram/webhook",
            json=_assistant_update("/research Compare LangGraph and AutoGen for multi-agent workflows"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["chat_id"] == "2002"
    assert captured["task_type"] == TaskType.SPEC
    assert captured["direction"] == "Compare LangGraph and AutoGen for multi-agent workflows"
    assert captured["context"]["source"] == "telegram_personal_assistant"
    assert captured["context"]["assistant_request_kind"] == "research"
    assert captured["context"]["telegram_user_id"] == "1001"
    assert captured["context"]["telegram_chat_id"] == "2002"
    assert captured["executed_task_id"] == "task_assistant_1"
    assert "Queued execution: `yes`" in captured["message"]


@pytest.mark.asyncio
async def test_assistant_plain_text_creates_impl_task(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PERSONAL_BOT_TOKEN", "assistant-token")
    monkeypatch.setenv("TELEGRAM_PERSONAL_AUTO_EXECUTE", "0")

    captured: dict[str, Any] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        captured["chat_id"] = str(chat_id)
        captured["message"] = message
        return True

    def _fake_create_task(data):
        captured["direction"] = data.direction
        captured["task_type"] = data.task_type
        captured["context"] = dict(data.context or {})
        return {
            "id": "task_assistant_2",
            "direction": data.direction,
            "task_type": data.task_type,
            "status": "pending",
            "model": "openclaw/openrouter/free",
            "command": "openclaw run ...",
            "context": data.context or {},
        }

    monkeypatch.setattr("app.services.telegram_personal_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr("app.services.agent_service.create_task", _fake_create_task)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/assistant/telegram/webhook",
            json=_assistant_update("Fix the deployment guide and summarize changes"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["chat_id"] == "2002"
    assert captured["task_type"] == TaskType.IMPL
    assert captured["direction"] == "Fix the deployment guide and summarize changes"
    assert captured["context"]["assistant_request_kind"] == "action"
    assert "task_assistant_2" in captured["message"]
    assert "Queued execution: `no`" in captured["message"]


@pytest.mark.asyncio
async def test_assistant_status_lists_recent_chat_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PERSONAL_BOT_TOKEN", "assistant-token")

    captured: dict[str, Any] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        captured["chat_id"] = str(chat_id)
        captured["message"] = message
        return True

    def _fake_list_tasks(status=None, task_type=None, limit=20, offset=0):
        return (
            [
                {
                    "id": "task_assistant_chat",
                    "status": "running",
                    "direction": "Research team process",
                    "context": {
                        "source": "telegram_personal_assistant",
                        "telegram_chat_id": "2002",
                    },
                },
                {
                    "id": "task_other_chat",
                    "status": "pending",
                    "direction": "Other chat request",
                    "context": {
                        "source": "telegram_personal_assistant",
                        "telegram_chat_id": "9999",
                    },
                },
                {
                    "id": "task_not_assistant",
                    "status": "failed",
                    "direction": "Internal task",
                    "context": {"source": "pipeline"},
                },
            ],
            3,
        )

    monkeypatch.setattr("app.services.telegram_personal_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr("app.services.agent_service.list_tasks", _fake_list_tasks)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/assistant/telegram/webhook",
            json=_assistant_update("/status"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["chat_id"] == "2002"
    assert "task_assistant_chat" in captured["message"]
    assert "task_other_chat" not in captured["message"]
    assert "task_not_assistant" not in captured["message"]


@pytest.mark.asyncio
async def test_assistant_rejects_disallowed_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PERSONAL_BOT_TOKEN", "assistant-token")
    monkeypatch.setenv("TELEGRAM_PERSONAL_ALLOWED_USER_IDS", "9999")

    sent = {"value": False}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["value"] = True
        return True

    monkeypatch.setattr("app.services.telegram_personal_adapter.send_reply", _fake_send_reply)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/assistant/telegram/webhook",
            json=_assistant_update("/do anything", user_id=1001),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent["value"] is False


@pytest.mark.asyncio
async def test_assistant_help_command_returns_help(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PERSONAL_BOT_TOKEN", "assistant-token")

    captured: dict[str, Any] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        captured["chat_id"] = str(chat_id)
        captured["message"] = message
        return True

    monkeypatch.setattr("app.services.telegram_personal_adapter.send_reply", _fake_send_reply)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/assistant/telegram/webhook",
            json=_assistant_update("/help"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["chat_id"] == "2002"
    assert "Commands:" in captured["message"]
    assert "/research <request>" in captured["message"]


@pytest.mark.asyncio
async def test_assistant_plain_help_returns_help_without_creating_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_PERSONAL_BOT_TOKEN", "assistant-token")

    captured: dict[str, Any] = {}
    create_called = {"value": False}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        captured["chat_id"] = str(chat_id)
        captured["message"] = message
        return True

    def _fake_create_task(data):
        create_called["value"] = True
        return {"id": "unexpected"}

    monkeypatch.setattr("app.services.telegram_personal_adapter.send_reply", _fake_send_reply)
    monkeypatch.setattr("app.services.agent_service.create_task", _fake_create_task)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/assistant/telegram/webhook",
            json=_assistant_update("help"),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert create_called["value"] is False
    assert "Commands:" in captured["message"]
