"""Field relay WS endpoint — open join, consent-gated, content-blind (breath 1 transport).

Mirrors the four-way-proven fr-route decision (form/form-stdlib/field-relay.fk, verdict 127):
DELIVER / QUEUE / DENY / DROP, plus the body-blindness law.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import field_relay


@pytest.fixture
def client():
    field_relay._reset_for_tests()
    yield TestClient(app)
    field_relay._reset_for_tests()


def test_relay_consent_gate_and_content_blindness(client):
    with client.websocket_connect("/api/field/relay/alice") as wa, \
         client.websocket_connect("/api/field/relay/bob") as wb:
        assert wa.receive_json()["type"] == "connected"
        assert wb.receive_json()["type"] == "connected"
        wa.send_json({"type": "hello", "interface": ["announce", "ping"]})
        assert wa.receive_json()["type"] == "ready"
        wb.send_json({"type": "hello", "interface": ["announce"]})  # bob does NOT offer ping
        assert wb.receive_json()["type"] == "ready"

        # DENY — bob has not offered "ping" (consent is the gate)
        wa.send_json({"type": "envelope", "to": "bob", "kind": "ping", "body": {"x": 1}})
        assert wa.receive_json()["decision"] == "deny"

        # DELIVER — bob offers "announce"; bob receives the body opaquely
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": {"hi": "there"}})
        got = wb.receive_json()
        assert got["type"] == "envelope" and got["from"] == "alice" and got["kind"] == "announce"
        assert got["body"] == {"hi": "there"}
        assert wa.receive_json()["decision"] == "deliver"

        # DROP — unknown recipient
        wa.send_json({"type": "envelope", "to": "carol", "kind": "announce", "body": 1})
        assert wa.receive_json()["decision"] == "drop"

        # BODY-BLINDNESS — same metadata, different bodies, identical decision; both delivered intact
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": {"a": 1}})
        b1 = wb.receive_json()
        ack1 = wa.receive_json()
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": [9, 9, 9]})
        b2 = wb.receive_json()
        ack2 = wa.receive_json()
        assert ack1["decision"] == ack2["decision"] == "deliver"
        assert b1["body"] == {"a": 1} and b2["body"] == [9, 9, 9]

        # ping/pong keepalive
        wa.send_json({"type": "ping"})
        assert wa.receive_json()["type"] == "pong"


def test_relay_queues_for_known_but_offline_cell(client):
    # bob connects, announces an interface, then disconnects -> known but offline
    with client.websocket_connect("/api/field/relay/bob") as wb:
        assert wb.receive_json()["type"] == "connected"
        wb.send_json({"type": "hello", "interface": ["announce"]})
        assert wb.receive_json()["type"] == "ready"
    # bob is now offline (entry retained, connected=False)
    with client.websocket_connect("/api/field/relay/alice") as wa:
        assert wa.receive_json()["type"] == "connected"
        wa.send_json({"type": "hello", "interface": ["announce"]})
        assert wa.receive_json()["type"] == "ready"
        # consent ok (bob offers announce) but offline -> QUEUE, not DROP
        wa.send_json({"type": "envelope", "to": "bob", "kind": "announce", "body": 1})
        assert wa.receive_json()["decision"] == "queue"
