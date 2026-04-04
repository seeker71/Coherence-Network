"""Tests for Node Remote Control — federation command messages (`cc cmd` API path).

Core requirement: a sender can POST a directed `command` message; the recipient
inbox returns it with `type`, `text`, and `payload` (command + args).

CLI reference: cli/lib/commands/nodes.mjs — sendCommand()
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


def test_directed_command_message_delivered_to_recipient(client):
    """POST type=command with payload → recipient GET sees command, args, and text."""
    # FederationNodeRegisterRequest.node_id is exactly 16 chars (spec 132).
    sender = "nrcsend01a1b2c3d"
    recipient = "nrcrecv02b2c3d4e"
    _register_node(client, sender, "sender.nrc.example")
    _register_node(client, recipient, "recv.nrc.example")

    body = {
        "from_node": sender,
        "to_node": recipient,
        "type": "command",
        "text": "status --verbose",
        "payload": {"command": "status", "args": ["--verbose"]},
    }
    post = client.post(f"/api/federation/nodes/{sender}/messages", json=body)
    assert post.status_code == 201, post.text
    created = post.json()
    assert created["type"] == "command"
    assert created["text"] == "status --verbose"
    assert created["payload"]["command"] == "status"
    assert created["payload"]["args"] == ["--verbose"]

    inbox = client.get(
        f"/api/federation/nodes/{recipient}/messages?unread_only=true&limit=20",
    )
    assert inbox.status_code == 200
    data = inbox.json()
    assert data["count"] >= 1
    cmd_msgs = [m for m in data["messages"] if m.get("type") == "command"]
    assert cmd_msgs, "expected at least one command message in inbox"
    last = cmd_msgs[0]
    assert last["text"] == "status --verbose"
    assert last["payload"].get("command") == "status"
    assert last["payload"].get("args") == ["--verbose"]
    assert last["from_node"] == sender
