"""Acceptance tests for Node Remote Control (`cc cmd`) behavior.

Derived from spec verification criteria in `specs/156-openclaw-bidirectional-messaging.md`:
- command payload visibility/preservation
- malformed POST validation errors (422)
- invalid inbox bounds validation errors (422)
- unread/read fetch behavior
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def _register_node(client: TestClient, node_id: str, hostname: str) -> None:
    response = client.post(
        "/api/federation/nodes",
        json={
            "node_id": node_id,
            "hostname": hostname,
            "os_type": "linux",
            "providers": ["openai"],
            "capabilities": {},
        },
    )
    assert response.status_code == 201, response.text


def _post_command(
    client: TestClient,
    sender: str,
    recipient: str,
    text: str,
    payload: dict,
):
    return client.post(
        f"/api/federation/nodes/{sender}/messages",
        json={
            "from_node": sender,
            "to_node": recipient,
            "type": "command",
            "text": text,
            "payload": payload,
        },
    )


def test_command_payload_round_trips_and_unread_cycle(client: TestClient):
    sender = "nrca0001a1b2c3d4"
    recipient = "nrca0002b2c3d4e5"
    _register_node(client, sender, "sender.nrc.example")
    _register_node(client, recipient, "recipient.nrc.example")

    payload = {"command": "checkpoint", "args": ["--full"], "trace_id": "trace-156"}
    created = _post_command(
        client=client,
        sender=sender,
        recipient=recipient,
        text="checkpoint --full",
        payload=payload,
    )
    assert created.status_code == 201, created.text

    inbox_first = client.get(
        f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20",
    )
    assert inbox_first.status_code == 200, inbox_first.text
    first_data = inbox_first.json()
    assert first_data["count"] >= 1
    commands = [m for m in first_data["messages"] if m.get("type") == "command"]
    assert commands, "expected command message in first unread fetch"

    message = commands[0]
    assert message["from_node"] == sender
    assert message["text"] == "checkpoint --full"
    assert message["payload"] == payload

    inbox_second = client.get(
        f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20",
    )
    assert inbox_second.status_code == 200, inbox_second.text
    assert inbox_second.json()["count"] == 0


def test_unknown_command_is_visible_without_inbox_failure(client: TestClient):
    sender = "nrca0003c3d4e5f6"
    recipient = "nrca0004d4e5f6g7"
    _register_node(client, sender, "unknown-sender.nrc.example")
    _register_node(client, recipient, "unknown-recv.nrc.example")

    created = _post_command(
        client=client,
        sender=sender,
        recipient=recipient,
        text="do-magic --alpha",
        payload={"command": "do-magic", "args": ["--alpha"]},
    )
    assert created.status_code == 201, created.text

    inbox = client.get(f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20")
    assert inbox.status_code == 200, inbox.text
    data = inbox.json()
    assert data["count"] >= 1
    command_messages = [m for m in data["messages"] if m.get("type") == "command"]
    assert command_messages, "expected command message for unknown command payload"
    assert command_messages[0]["payload"].get("command") == "do-magic"


def test_command_post_missing_from_node_returns_422_with_field_error(client: TestClient):
    sender = "nrca0005e5f6g7h8"
    recipient = "nrca0006f6g7h8i9"
    _register_node(client, sender, "missing-from-sender.example")
    _register_node(client, recipient, "missing-from-recipient.example")

    response = client.post(
        f"/api/federation/nodes/{sender}/messages",
        json={
            "to_node": recipient,
            "type": "command",
            "text": "checkpoint",
            "payload": {"command": "checkpoint"},
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert isinstance(detail, list) and detail, "expected FastAPI validation detail list"
    assert any(
        err.get("loc") == ["body", "from_node"]
        or err.get("loc") == ("body", "from_node")
        for err in detail
    )


def test_command_inbox_limit_above_max_returns_422(client: TestClient):
    response = client.get("/api/federation/nodes/nrca0007g7h8i9j0/messages?unread_only=true&limit=999")
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert isinstance(detail, list) and detail, "expected validation detail for invalid limit"
    assert any(
        err.get("loc") == ["query", "limit"]
        or err.get("loc") == ("query", "limit")
        for err in detail
    )
