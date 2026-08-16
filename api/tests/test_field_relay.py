"""Field relay WS endpoint — open join, consent-gated, content-blind (breath 1 transport).

Mirrors the four-way-proven fr-route decision (form/form/form-stdlib/field-relay.fk, verdict 127):
DELIVER / QUEUE / DENY / DROP, plus the body-blindness law.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import field_relay


@pytest.fixture
def client(monkeypatch):
    field_relay._reset_for_tests()
    monkeypatch.setattr(field_relay, "_HEARTBEAT_SECONDS", 0.05)
    yield TestClient(app)
    field_relay._reset_for_tests()


def _receive_signal(websocket):
    for _ in range(20):
        frame = websocket.receive_json()
        if frame.get("type") != "heartbeat":
            return frame
    pytest.fail("relay returned heartbeats without the pending signal")


def test_relay_consent_gate_and_content_blindness(client):
    with client.websocket_connect("/api/field/relay/alice") as wa, \
         client.websocket_connect("/api/field/relay/bob") as wb:
        assert _receive_signal(wa)["type"] == "connected"
        assert _receive_signal(wb)["type"] == "connected"
        wa.send_json({"type": "hello", "interface": ["announce", "ping"]})
        assert _receive_signal(wa)["type"] == "ready"
        wb.send_json({"type": "hello", "interface": ["announce"]})  # bob does NOT offer ping
        assert _receive_signal(wb)["type"] == "ready"

        # DENY — bob has not offered "ping" (consent is the gate)
        wa.send_json({"type": "envelope", "to": "bob", "kind": "ping", "body": {"x": 1}})
        assert _receive_signal(wa)["decision"] == "deny"

        # DELIVER — bob offers "announce"; bob receives the body opaquely
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": {"hi": "there"}})
        got = _receive_signal(wb)
        assert got["type"] == "envelope" and got["from"] == "alice" and got["kind"] == "announce"
        assert got["body"] == {"hi": "there"}
        assert _receive_signal(wa)["decision"] == "deliver"

        # DROP — unknown recipient
        wa.send_json({"type": "envelope", "to": "carol", "kind": "announce", "body": 1})
        dropped = _receive_signal(wa)
        assert dropped.get("decision") == "drop", dropped

        # BODY-BLINDNESS — same metadata, different bodies, identical decision; both delivered intact
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": {"a": 1}})
        b1 = _receive_signal(wb)
        ack1 = _receive_signal(wa)
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": [9, 9, 9]})
        b2 = _receive_signal(wb)
        ack2 = _receive_signal(wa)
        assert ack1["decision"] == ack2["decision"] == "deliver"
        assert b1["body"] == {"a": 1} and b2["body"] == [9, 9, 9]

        # ping/pong keepalive
        wa.send_json({"type": "ping"})
        assert _receive_signal(wa)["type"] == "pong"


def test_relay_queues_for_known_but_offline_cell(client):
    # bob connects, announces an interface, then disconnects -> known but offline
    with client.websocket_connect("/api/field/relay/bob") as wb:
        assert _receive_signal(wb)["type"] == "connected"
        wb.send_json({"type": "hello", "interface": ["announce"]})
        assert _receive_signal(wb)["type"] == "ready"
    # bob is now offline (entry retained, connected=False)
    with client.websocket_connect("/api/field/relay/alice") as wa:
        assert _receive_signal(wa)["type"] == "connected"
        wa.send_json({"type": "hello", "interface": ["announce"]})
        assert _receive_signal(wa)["type"] == "ready"
        # consent ok (bob offers announce) but offline -> QUEUE, not DROP
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": 1})
        assert _receive_signal(wa)["decision"] == "queue"


def test_relay_keeps_pending_receive_alive_across_heartbeat(client, monkeypatch):
    monkeypatch.setattr(field_relay, "_HEARTBEAT_SECONDS", 0.05)
    with client.websocket_connect("/api/field/relay/alice") as wa:
        assert wa.receive_json()["type"] == "connected"
        wa.send_json({"type": "hello", "interface": ["announce"]})
        assert wa.receive_json()["type"] == "ready"
        assert wa.receive_json()["type"] == "heartbeat"

        wa.send_json(
            {"type": "envelope", "to": "unknown", "kind": "announce", "body": 1}
        )
        routed = wa.receive_json()
        assert routed.get("decision") == "drop", routed
