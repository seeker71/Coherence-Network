"""Flow test for the household resident-service board (api/app/routers/household.py).

One strange-minimal flow that exercises the whole nervous system: a resident
asks, a staff member sees it and carries it through, an outside-resource cost
rides along and gets settled — and the two guards that keep it honest (a
request needs a real member; a settle needs a recorded cost).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _member(client, name, role):
    res = client.post("/api/household/members", json={"name": name, "role": role})
    assert res.status_code == 201, res.text
    return res.json()


def test_request_moves_from_ask_to_done_with_settled_cost(client):
    resident = _member(client, "Ayu", "resident")
    staff = _member(client, "Wayan", "staff")

    # The ask
    res = client.post("/api/household/requests", json={
        "requester_id": resident["id"],
        "kind": "laundry",
        "detail": "two sets of bed linen for the lumbung",
        "location": "Lumbung house",
        "when_text": "before sunset",
    })
    assert res.status_code == 201, res.text
    req = res.json()
    assert req["status"] == "open"
    assert req["requester_name"] == "Ayu"
    rid = req["id"]

    # It shows on the open board everyone sees
    board = client.get("/api/household/requests").json()
    assert any(r["id"] == rid for r in board)

    # Staff sees it and carries it through
    ack = client.post(f"/api/household/requests/{rid}/acknowledge", json={"actor_id": staff["id"]}).json()
    assert ack["status"] == "acknowledged"
    assert ack["acknowledged_by_name"] == "Wayan"

    started = client.post(f"/api/household/requests/{rid}/start", json={"actor_id": staff["id"]}).json()
    assert started["status"] == "in_progress"

    # Done — with an outside-resource cost recorded
    done = client.post(f"/api/household/requests/{rid}/complete", json={
        "actor_id": staff["id"],
        "cost_amount": 25000,
        "cost_note": "detergent",
    }).json()
    assert done["status"] == "completed"
    assert done["completed_by_name"] == "Wayan"
    assert done["cost_amount"] == 25000
    assert done["cost_status"] == "recorded"

    # The small money that moved is settled — and visible
    paid = client.post(f"/api/household/requests/{rid}/pay", json={"actor_id": staff["id"]}).json()
    assert paid["cost_status"] == "paid"
    assert paid["paid_by_name"] == "Wayan"


def test_request_needs_a_real_member(client):
    res = client.post("/api/household/requests", json={
        "requester_id": "member-does-not-exist",
        "kind": "food",
        "detail": "lunch for two",
    })
    assert res.status_code == 400


def test_settle_needs_a_recorded_cost(client):
    resident = _member(client, "Komang", "resident")
    staff = _member(client, "Made", "staff")
    rid = client.post("/api/household/requests", json={
        "requester_id": resident["id"],
        "kind": "ride",
        "detail": "scooter to the market",
    }).json()["id"]
    # Completed with no outside cost → nothing to settle
    client.post(f"/api/household/requests/{rid}/complete", json={"actor_id": staff["id"]})
    res = client.post(f"/api/household/requests/{rid}/pay", json={"actor_id": staff["id"]})
    assert res.status_code == 400
