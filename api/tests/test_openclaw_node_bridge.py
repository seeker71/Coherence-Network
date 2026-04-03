"""Openclaw WebSocket bridge: real-time federation messages (Spec 156 Phase 3 follow-up)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import config_loader

@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def test_openclaw_bridge_connected_envelope(client: TestClient) -> None:
    with client.websocket_connect("/api/federation/openclaw/nodes/node_ws_a/bridge") as ws:
        raw = ws.receive_text()
        msg = json.loads(raw)
        assert msg["v"] == 1
        assert msg["schema"] == "coherence.openclaw.bridge.v1"
        assert msg["event_type"] == "connected"
        assert msg["data"]["node_id"] == "node_ws_a"


def test_openclaw_bridge_delivers_posted_message(client: TestClient) -> None:
    with client.websocket_connect("/api/federation/openclaw/nodes/node_ws_recv/bridge") as ws:
        first = json.loads(ws.receive_text())
        assert first["event_type"] == "connected"

        post = client.post(
            "/api/federation/nodes/node_ws_send/messages",
            json={
                "from_node": "node_ws_send",
                "to_node": "node_ws_recv",
                "type": "text",
                "text": "qa-openclaw-bridge-1",
                "payload": {"k": 1},
            },
        )
        assert post.status_code == 201, post.text

        got = json.loads(ws.receive_text())
        assert got["event_type"] == "federation_message"
        assert got["data"]["text"] == "qa-openclaw-bridge-1"
        assert got["data"]["from_node"] == "node_ws_send"
        assert got["data"]["payload"] == {"k": 1}


def test_openclaw_bridge_ping_pong(client: TestClient) -> None:
    with client.websocket_connect("/api/federation/openclaw/nodes/node_ws_ping/bridge") as ws:
        _ = json.loads(ws.receive_text())
        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"
        assert pong["schema"] == "coherence.openclaw.bridge.v1"


def test_bridge_token_ok_config() -> None:
    from app.services import openclaw_node_bridge_service as bridge

    config_loader.set_config_value("federation", "bridge_token", None)
    assert bridge.bridge_token_ok(None) is True
    assert bridge.bridge_token_ok("wrong") is True

    config_loader.set_config_value("federation", "bridge_token", "secret-bridge")
    assert bridge.bridge_token_ok("secret-bridge") is True
    assert bridge.bridge_token_ok(None) is False
    assert bridge.bridge_token_ok("nope") is False
