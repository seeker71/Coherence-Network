"""Acceptance tests for Node Remote Control command messaging.

Spec reference:
- specs/156-openclaw-bidirectional-messaging.md (Phase 1 verification items 3, 4, 5, 6)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def _register_node(client: TestClient, node_id: str, hostname: str) -> None:
    resp = client.post(
        "/api/federation/nodes",
        json={
            "node_id": node_id,
            "hostname": hostname,
            "os_type": "linux",
            "providers": ["openai"],
            "capabilities": {},
        },
    )
    assert resp.status_code == 201, resp.text


def test_command_message_payload_is_visible_in_recipient_inbox(client):
    """Directed command payload is preserved and readable via inbox polling."""
    sender = "nrcsend000000000"
    recipient = "nrcrecv000000000"
    _register_node(client, sender, "sender.nrc.example")
    _register_node(client, recipient, "recipient.nrc.example")

    post = client.post(
        f"/api/federation/nodes/{sender}/messages",
        json={
            "from_node": sender,
            "to_node": recipient,
            "type": "command",
            "text": "checkpoint now",
            "payload": {"command": "checkpoint", "args": ["now"]},
        },
    )
    assert post.status_code == 201, post.text

    inbox = client.get(f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20")
    assert inbox.status_code == 200
    data = inbox.json()
    assert data["count"] >= 1

    command_msgs = [m for m in data["messages"] if m.get("type") == "command"]
    assert command_msgs, "expected command message in recipient inbox"
    latest = command_msgs[0]
    assert latest["from_node"] == sender
    assert latest["to_node"] == recipient
    assert latest["text"] == "checkpoint now"
    assert latest["payload"]["command"] == "checkpoint"
    assert latest["payload"]["args"] == ["now"]


def test_unread_only_excludes_command_after_first_read(client):
    """Unread-only polling returns command once, then excludes it after read-marking."""
    sender = "nrcsend111111111"
    recipient = "nrcrecv111111111"
    _register_node(client, sender, "sender2.nrc.example")
    _register_node(client, recipient, "recipient2.nrc.example")

    post = client.post(
        f"/api/federation/nodes/{sender}/messages",
        json={
            "from_node": sender,
            "to_node": recipient,
            "type": "command",
            "text": "status --verbose",
            "payload": {"command": "status", "args": ["--verbose"]},
        },
    )
    assert post.status_code == 201, post.text

    first = client.get(f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20")
    assert first.status_code == 200
    first_data = first.json()
    first_texts = [m["text"] for m in first_data["messages"]]
    assert "status --verbose" in first_texts

    second = client.get(f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20")
    assert second.status_code == 200
    second_data = second.json()
    second_texts = [m["text"] for m in second_data["messages"]]
    assert "status --verbose" not in second_texts


def test_command_post_missing_required_from_node_returns_422(client):
    """Malformed command payload is rejected with FastAPI validation details."""
    sender = "nrcsend222222222"
    recipient = "nrcrecv222222222"
    _register_node(client, sender, "sender3.nrc.example")
    _register_node(client, recipient, "recipient3.nrc.example")

    bad_post = client.post(
        f"/api/federation/nodes/{sender}/messages",
        json={
            "to_node": recipient,
            "type": "command",
            "text": "checkpoint",
            "payload": {"command": "checkpoint"},
        },
    )
    assert bad_post.status_code == 422
    detail = bad_post.json().get("detail", [])
    assert isinstance(detail, list) and detail, "422 response must include detail list"
    assert any("from_node" in str(item.get("loc", "")) for item in detail)


def test_inbox_invalid_limit_returns_422_with_query_error_shape(client):
    """Out-of-bounds inbox limit returns deterministic query validation error."""
    recipient = "nrcrecv333333333"
    _register_node(client, recipient, "recipient4.nrc.example")

    resp = client.get(f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=999")
    assert resp.status_code == 422
    detail = resp.json().get("detail", [])
    assert isinstance(detail, list) and detail, "422 response must include detail list"
    assert any("limit" in str(item.get("loc", "")) for item in detail)
