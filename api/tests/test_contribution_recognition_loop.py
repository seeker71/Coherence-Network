"""Spec 003 — Contribution Recognition Loop (agent–Telegram decision loop).

Acceptance: human `/reply`, `/attention`, PATCH progress/decision, diagnostics webhook path,
and runner-facing task list contract. See specs/003-agent-telegram-decision-loop.md.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service
from app.services import telegram_diagnostics


def _telegram_update_status(update_id: int = 90001) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 12345, "type": "private"},
            "date": 1640000000,
            "text": "/status",
        },
    }


async def _clear_tasks(client: AsyncClient) -> None:
    r = await client.delete("/api/agent/tasks?confirm=clear")
    assert r.status_code == 204, r.text


@pytest.mark.asyncio
async def test_reply_command_records_decision_and_updates_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Telegram `/reply {task_id} {decision}` records decision; needs_decision → running."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    agent_service.clear_store()
    agent_service._store_loaded = False

    sent: dict[str, str] = {}

    async def _fake_send_reply(chat_id: int | str, message: str, parse_mode: str = "Markdown") -> bool:
        sent["message"] = message
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _clear_tasks(client)
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Decision loop probe", "task_type": "impl"},
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]

        nd = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "needs_decision",
                "output": "Blocked: choose path. " + "x" * 200,
                "decision_prompt": "Reply yes or no",
                "worker_id": "manual-test",
            },
        )
        assert nd.status_code == 200, nd.text
        assert nd.json()["status"] == "needs_decision"

        wh = await client.post(
            "/api/agent/telegram/webhook",
            json={
                "update_id": 42,
                "message": {
                    "message_id": 2,
                    "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
                    "chat": {"id": 12345, "type": "private"},
                    "date": 1640000001,
                    "text": f"/reply {task_id} proceed-with-fix",
                },
            },
        )
        assert wh.status_code == 200, wh.text
        assert wh.json() == {"ok": True}
        assert "Decision recorded" in sent.get("message", "")

        got = await client.get(f"/api/agent/tasks/{task_id}")
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["status"] == "running"
        assert body["decision"] == "proceed-with-fix"


@pytest.mark.asyncio
async def test_attention_lists_only_needs_decision_and_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/agent/tasks/attention returns only needs_decision and failed tasks."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    agent_service.clear_store()
    agent_service._store_loaded = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _clear_tasks(client)

        r1 = await client.post(
            "/api/agent/tasks",
            json={"direction": "pending only", "task_type": "impl"},
        )
        r2 = await client.post(
            "/api/agent/tasks",
            json={"direction": "needs decision", "task_type": "impl"},
        )
        r3 = await client.post(
            "/api/agent/tasks",
            json={"direction": "failed task", "task_type": "impl"},
        )
        assert {r1.status_code, r2.status_code, r3.status_code} == {201}

        id_nd = r2.json()["id"]
        id_fail = r3.json()["id"]

        await client.patch(
            f"/api/agent/tasks/{id_nd}",
            json={
                "status": "needs_decision",
                "output": "Choose: " + "y" * 200,
                "worker_id": "manual-test",
            },
        )
        await client.patch(
            f"/api/agent/tasks/{id_fail}",
            json={
                "status": "failed",
                "output": "Failure output " + "z" * 200,
                "worker_id": "manual-test",
            },
        )

        att = await client.get("/api/agent/tasks/attention")
        assert att.status_code == 200, att.text
        payload = att.json()
        assert "tasks" in payload and "total" in payload
        ids = {t["id"] for t in payload["tasks"]}
        assert id_nd in ids and id_fail in ids
        assert r1.json()["id"] not in ids
        for t in payload["tasks"]:
            assert t["status"] in ("needs_decision", "failed")


@pytest.mark.asyncio
async def test_patch_accepts_progress_and_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATCH /api/agent/tasks/{id} accepts progress_pct, current_step, decision_prompt, decision."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    agent_service.clear_store()
    agent_service._store_loaded = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _clear_tasks(client)
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Progress patch test", "task_type": "test"},
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]

        await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={
                "status": "needs_decision",
                "output": "Need input. " + "p" * 200,
                "progress_pct": 60,
                "current_step": "Running tests",
                "decision_prompt": "Approve merge?",
                "worker_id": "manual-test",
            },
        )

        patch_dec = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"decision": "approved"},
        )
        assert patch_dec.status_code == 200, patch_dec.text
        body = patch_dec.json()
        assert body["status"] == "running"
        assert body["decision"] == "approved"
        assert body["progress_pct"] == 60
        assert body["current_step"] == "Running tests"
        assert body["decision_prompt"] == "Approve merge?"


@pytest.mark.asyncio
async def test_telegram_flow_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook records inbound update; diagnostics expose config, webhook_events, send_results."""
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    telegram_diagnostics.clear()

    async def _fake_send_reply(*_a, **_k) -> bool:
        return True

    monkeypatch.setattr("app.services.telegram_adapter.send_reply", _fake_send_reply)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        base = await client.get("/api/agent/telegram/diagnostics")
        assert base.status_code == 200
        n0 = len(base.json().get("webhook_events") or [])

        wh = await client.post("/api/agent/telegram/webhook", json=_telegram_update_status(90001))
        assert wh.status_code == 200
        assert wh.json() == {"ok": True}

        diag = await client.get("/api/agent/telegram/diagnostics")
        assert diag.status_code == 200
        d = diag.json()
        for key in ("config", "webhook_events", "send_results"):
            assert key in d, f"missing {key}"
        cfg = d["config"]
        for k in ("has_token", "token_prefix", "chat_ids", "allowed_user_ids"):
            assert k in cfg

        events = d["webhook_events"] or []
        assert len(events) >= n0 + 1
        found = next((e for e in events if (e.get("update") or {}).get("update_id") == 90001), None)
        assert found is not None
        assert found["update"]["message"]["text"] == "/status"


@pytest.mark.asyncio
async def test_agent_runner_pending_list_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runner polls GET /api/agent/tasks?status=pending — response includes tasks[].id and status."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    agent_service.clear_store()
    agent_service._store_loaded = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _clear_tasks(client)
        await client.post(
            "/api/agent/tasks",
            json={"direction": "Poll me", "task_type": "impl"},
        )
        pending = await client.get("/api/agent/tasks", params={"status": "pending", "limit": 10})
        assert pending.status_code == 200, pending.text
        data = pending.json()
        assert "tasks" in data and "total" in data
        assert data["total"] >= 1
        assert all(t.get("status") == "pending" for t in data["tasks"])
        assert all(t.get("id") for t in data["tasks"])
