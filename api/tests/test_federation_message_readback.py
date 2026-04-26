from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


BASE = "http://test"


def _node_id() -> str:
    return uuid4().hex[:16]


@pytest.mark.asyncio
async def test_federation_message_can_be_read_back_by_id() -> None:
    sender = _node_id()
    receiver = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        for node_id, hostname in ((sender, "sender.local"), (receiver, "receiver.local")):
            created = await client.post(
                "/api/federation/nodes",
                json={"node_id": node_id, "hostname": hostname, "os_type": "linux"},
            )
            assert created.status_code in {200, 201}, created.text

        sent = await client.post(
            f"/api/federation/nodes/{sender}/messages",
            json={
                "from_node": sender,
                "to_node": receiver,
                "type": "agent_voice",
                "text": "readback proof",
                "payload": {"agent": "codex"},
            },
        )
        assert sent.status_code == 201, sent.text
        msg_id = sent.json()["id"]

        fetched = await client.get(f"/api/federation/messages/{msg_id}")
        assert fetched.status_code == 200, fetched.text
        body = fetched.json()
        assert body["id"] == msg_id
        assert body["from_node"] == sender
        assert body["to_node"] == receiver
        assert body["type"] == "agent_voice"
        assert body["text"] == "readback proof"
        assert body["payload"] == {"agent": "codex"}


@pytest.mark.asyncio
async def test_federation_messages_include_self_only_when_requested() -> None:
    node_id = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        created = await client.post(
            "/api/federation/nodes",
            json={"node_id": node_id, "hostname": "loopback.local", "os_type": "linux"},
        )
        assert created.status_code in {200, 201}, created.text

        sent = await client.post(
            f"/api/federation/nodes/{node_id}/messages",
            json={
                "from_node": node_id,
                "to_node": node_id,
                "type": "agent_voice",
                "text": "loopback voice",
            },
        )
        assert sent.status_code == 201, sent.text
        msg_id = sent.json()["id"]

        normal = await client.get(
            f"/api/federation/nodes/{node_id}/messages",
            params={"unread_only": "false"},
        )
        assert normal.status_code == 200, normal.text
        assert msg_id not in {row["id"] for row in normal.json()["messages"]}

        loopback = await client.get(
            f"/api/federation/nodes/{node_id}/messages",
            params={"unread_only": "false", "include_self": "true", "limit": 20},
        )
        assert loopback.status_code == 200, loopback.text
        assert any(row["id"] == msg_id and row["text"] == "loopback voice" for row in loopback.json()["messages"])
