"""Flow test for the household resident-service board (api/app/routers/household.py).

The whole nervous system in one strange-minimal flow: a founding resident
bootstraps, vouches a staff member in by invite (the link's token auto-binds
on /me), the staff member tends a request through to a settled cost — and the
two locks that keep it honest: a see-only member cannot write until a resident
grants it, and an invite can only come from a resident.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_invite_carries_role_and_write_flows_through(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Giles"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    assert resident.status_code == 201, resident.text
    rtok = resident.json()["token"]
    assert resident.json()["role"] == "resident"
    assert resident.json()["write_access"] is True

    # Resident invites a staff member; the invite returns the link token.
    inv = client.post("/api/household/invites", json={
        "inviter_token": rtok, "name": "Wayan", "role": "staff",
    })
    assert inv.status_code == 201, inv.text
    stok = inv.json()["token"]
    assert inv.json()["role"] == "staff"
    assert inv.json()["status"] == "invited"

    # Opening the link (GET /me) activates the invite and binds the device.
    me = client.get(f"/api/household/me?token={stok}")
    assert me.status_code == 200
    assert me.json()["status"] == "active"
    assert me.json()["write_access"] is True

    # Staff asks + tends a request through, recording + settling a cost.
    rid = client.post("/api/household/requests", json={
        "actor_token": stok, "kind": "laundry", "detail": "linen for the lumbung",
    }).json()["id"]
    assert client.post(f"/api/household/requests/{rid}/acknowledge", json={"actor_token": stok}).json()["status"] == "acknowledged"
    done = client.post(f"/api/household/requests/{rid}/complete", json={
        "actor_token": stok, "cost_amount": 25000, "cost_note": "detergent",
    }).json()
    assert done["status"] == "completed" and done["cost_status"] == "recorded"
    assert client.post(f"/api/household/requests/{rid}/pay", json={"actor_token": stok}).json()["cost_status"] == "paid"


def test_see_only_member_cannot_write_until_vouched(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Ita"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; vouch flow skipped")
    rtok = resident.json()["token"]

    # A self-registered member is see-only.
    member = client.post("/api/household/members", json={"name": "Komang"}).json()
    mtok = member["token"]
    assert member["write_access"] is False

    # Writing is locked (403) until a resident vouches.
    blocked = client.post("/api/household/requests", json={
        "actor_token": mtok, "kind": "food", "detail": "lunch for two",
    })
    assert blocked.status_code == 403

    # Resident grants write; now the same member can ask.
    grant = client.post(f"/api/household/members/{member['id']}/grant-write", json={"actor_token": rtok})
    assert grant.status_code == 200 and grant.json()["write_access"] is True
    ok = client.post("/api/household/requests", json={
        "actor_token": mtok, "kind": "food", "detail": "lunch for two",
    })
    assert ok.status_code == 201


def test_only_a_resident_can_invite(client):
    # A bare self-registered member's token cannot create invites.
    member = client.post("/api/household/members", json={"name": "Drifter"}).json()
    res = client.post("/api/household/invites", json={
        "inviter_token": member["token"], "name": "Someone", "role": "staff",
    })
    assert res.status_code == 403

    # An unknown token cannot write.
    assert client.post("/api/household/requests", json={
        "actor_token": "not-a-real-token", "kind": "other", "detail": "x",
    }).status_code == 401
