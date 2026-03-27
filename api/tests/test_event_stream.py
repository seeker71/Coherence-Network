"""Cross-service event stream: WebSocket pub/sub + HTTP publish (ucore-event-streaming)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def test_event_stream_ws_connected(client: TestClient) -> None:
    with client.websocket_connect("/api/events/stream") as ws:
        raw = ws.receive_text()
        msg = json.loads(raw)
        assert msg["v"] == 1
        assert msg["schema"] == "coherence.event_stream.v1"
        assert msg["event_type"] == "connected"
        assert msg["data"]["schema"] == "coherence.event_stream.v1"


def test_event_stream_publish_delivers(client: TestClient) -> None:
    with client.websocket_connect("/api/events/stream") as ws:
        _ = ws.receive_text()
        res = client.post(
            "/api/events/publish",
            json={
                "event_type": "test_ping",
                "entity": "test",
                "entity_id": "e1",
                "data": {"hello": "world"},
            },
        )
        assert res.status_code == 201
        body = json.loads(ws.receive_text())
        assert body["event_type"] == "test_ping"
        assert body["entity"] == "test"
        assert body["entity_id"] == "e1"
        assert body["data"]["hello"] == "world"


def test_event_stream_filter_event_types(client: TestClient) -> None:
    with client.websocket_connect("/api/events/stream?event_types=keep_me") as ws:
        _ = ws.receive_text()
        client.post(
            "/api/events/publish",
            json={"event_type": "drop_me", "entity": "x", "data": {}},
        )
        client.post(
            "/api/events/publish",
            json={"event_type": "keep_me", "entity": "x", "data": {"n": 1}},
        )
        got = json.loads(ws.receive_text())
        assert got["event_type"] == "keep_me"
        assert got["data"]["n"] == 1
