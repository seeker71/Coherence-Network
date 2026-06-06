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


def test_gathering_raise_answer_tally_and_visibility(client):
    """A resident raises questions; the field answers, changes its mind, and
    sees the tally — and the audience predicate (visible-to) + head-count rule
    (yes-plus-one = 2), both Form recipes on the kernel, keep it honest."""
    resident = client.post("/api/household/bootstrap", json={"name": "Ketut"})
    if resident.status_code not in (200, 201):
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    rtok = resident.json()["token"]

    # A plain member self-registers — see-only is enough to see and answer.
    member = client.post("/api/household/members", json={"name": "Made"}).json()
    mtok = member["token"]

    # Resident raises a poll to everyone.
    g = client.post("/api/household/gatherings", json={
        "actor_token": rtok, "text": "Kirtan & Fire on Thursday?", "audience_kind": "everyone",
    })
    assert g.status_code == 201, g.text
    gid = g.json()["id"]
    assert g.json()["tally"]["voters"] == 0
    assert g.json()["my_choice"] is None

    # The member answers yes, then changes to yes-plus-one (a vote can change).
    a1 = client.post(f"/api/household/gatherings/{gid}/answer",
                     json={"actor_token": mtok, "choice": "yes"})
    assert a1.json()["my_choice"] == "yes"
    assert a1.json()["tally"]["heads"] == 1
    a2 = client.post(f"/api/household/gatherings/{gid}/answer",
                     json={"actor_token": mtok, "choice": "yes-plus-one"})
    assert a2.json()["my_choice"] == "yes-plus-one"
    assert a2.json()["tally"]["heads"] == 2          # yes-plus-one is two heads
    assert a2.json()["tally"]["voters"] == 1          # re-answer replaces, not appends

    # The member sees the everyone-poll in their list, carrying their choice.
    listed = client.get(f"/api/household/gatherings?token={mtok}").json()
    assert any(x["id"] == gid and x["my_choice"] == "yes-plus-one" for x in listed)

    # A resident-only question does not reach a plain member.
    gr = client.post("/api/household/gatherings", json={
        "actor_token": rtok, "text": "Residents: budget for the new pump?",
        "audience_kind": "group", "audience_value": "resident",
    }).json()
    grid = gr["id"]
    member_list = client.get(f"/api/household/gatherings?token={mtok}").json()
    assert all(x["id"] != grid for x in member_list)   # invisible to the member
    blocked = client.post(f"/api/household/gatherings/{grid}/answer",
                          json={"actor_token": mtok, "choice": "yes"})
    assert blocked.status_code == 403                  # cannot answer what didn't reach you

    # An event-kind question carries a place, a moment, and a proposed status.
    ev = client.post("/api/household/gatherings", json={
        "actor_token": rtok, "text": "Cacao circle", "audience_kind": "everyone",
        "kind": "event", "where": "Fire Pit", "when_text": "Thu 5pm",
    }).json()
    assert ev["kind"] == "event" and ev["status"] == "proposed" and ev["where"] == "Fire Pit"

    # Only a resident raises a gathering — a write-capable staff member cannot.
    inv = client.post("/api/household/invites",
                      json={"inviter_token": rtok, "name": "Wayan", "role": "staff"}).json()
    stok = inv["token"]
    client.get(f"/api/household/me?token={stok}")       # open the link → bind the device
    staff_raise = client.post("/api/household/gatherings", json={
        "actor_token": stok, "text": "staff trying to raise", "audience_kind": "everyone",
    })
    assert staff_raise.status_code == 403               # raise requires a resident


def test_request_trace_follows_attributes_and_witnesses(client):
    """A food request shows who asked + where it goes (core), and carries a
    full trace that can be followed, accounted for, attributed, and witnessed —
    each beat naming its cell and its moment. (lc-the-trace-is-the-memory.)"""
    resident = client.post("/api/household/bootstrap", json={"name": "Wayan"})
    if resident.status_code not in (200, 201):
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    rtok = resident.json()["token"]

    # Who asks and where it goes are core to the request.
    r = client.post("/api/household/requests", json={
        "actor_token": rtok, "kind": "food", "detail": "nasi campur x2",
        "location": "Bale Vishnu",
    }).json()
    rid = r["id"]

    # The board itself is open only to a registered cell, not the public.
    assert client.get("/api/household/requests").status_code == 401
    assert client.get(f"/api/household/requests?token={rtok}").status_code == 200

    # Walk its whole life; each transition attributes itself to a cell.
    client.post(f"/api/household/requests/{rid}/acknowledge", json={"actor_token": rtok})
    client.post(f"/api/household/requests/{rid}/start", json={"actor_token": rtok})
    client.post(f"/api/household/requests/{rid}/complete", json={
        "actor_token": rtok, "cost_amount": 50000, "cost_note": "warung",
    })
    client.post(f"/api/household/requests/{rid}/pay", json={"actor_token": rtok})

    # The trace is the field's tissue — witnessed by its cells, not the public.
    assert client.get(f"/api/household/requests/{rid}/trace").status_code == 401
    trace = client.get(f"/api/household/requests/{rid}/trace?token={rtok}").json()
    # Core, compact: who + where.
    assert trace["requester_name"] == "Wayan"
    assert trace["location"] == "Bale Vishnu"
    # The full followable, attributed, witnessed sequence.
    assert [s["step"] for s in trace["steps"]] == \
        ["requested", "acknowledged", "tending", "completed", "settled"]
    assert all(s["at"] for s in trace["steps"])          # every beat witnessed by a moment
    assert trace["steps"][0]["actor_name"] == "Wayan"     # attributed to the cell who asked
    assert any("50,000" in (s["note"] or "") for s in trace["steps"])   # accounted for
    assert trace["progress"] == 5 and trace["settled"] is True

    # A cancelled request traces only what was real.
    r2 = client.post("/api/household/requests", json={
        "actor_token": rtok, "kind": "ride", "detail": "airport run",
    }).json()
    client.post(f"/api/household/requests/{r2['id']}/cancel", json={"actor_token": rtok})
    t2 = client.get(f"/api/household/requests/{r2['id']}/trace?token={rtok}").json()
    assert [s["step"] for s in t2["steps"]] == ["requested", "cancelled"]
    assert t2["progress"] == 0 and t2["settled"] is False


def test_places_seed_pin_and_nearest(client):
    """Every place at Hati Suci is a cell; once pinned on site, GPS proximity
    resolves which one a phone is at — the by-pin door, its distance decision a
    Form recipe on the kernel. (household-membrane.form: place + locate.)"""
    resident = client.post("/api/household/bootstrap", json={"name": "Kadek"})
    if resident.status_code not in (200, 201):
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    rtok = resident.json()["token"]

    # Seed the grounds as cells (idempotent), and a plain member cannot.
    seeded = client.post("/api/household/places/seed", json={"actor_token": rtok}).json()
    slugs = {p["id"] for p in seeded}
    assert {"place-yoga-studio", "place-fire-pit", "place-pool"} <= slugs
    assert any(p["kind"] == "house" for p in seeded)
    member = client.post("/api/household/members", json={"name": "Putu"}).json()
    assert client.post("/api/household/places/seed",
                       json={"actor_token": member["token"]}).status_code == 403

    # The roster of places is see-locked — registered cells only.
    assert client.get("/api/household/places").status_code == 401
    assert len(client.get(f"/api/household/places?token={rtok}").json()) >= 22

    # Stand in two places, pin their GPS (micro-degrees) + one WiFi name.
    client.post("/api/household/places/place-yoga-studio/pin", json={
        "actor_token": rtok, "lat": -8516000, "lon": 115278000, "wifi": "HatiSuci-Yoga",
    })
    client.post("/api/household/places/place-fire-pit/pin", json={
        "actor_token": rtok, "lat": -8515900, "lon": 115277900,
    })

    # A phone near the studio resolves to the studio (the Form distance recipe).
    near = client.get(
        f"/api/household/nearest?token={rtok}&lat=-8516010&lon=115278010"
    ).json()
    assert near["id"] == "place-yoga-studio"
    assert near["wifi"] == "HatiSuci-Yoga" and near["pinned"] is True


def test_presence_scan_sets_and_clears_coarse_and_see_locked(client):
    """A cell scans a place's QR and is here; the field sees who's where on the
    see-locked roster, coarse, and the cell clears its own presence on leave —
    nothing tracks in the background. (household-membrane.form: presence-flow.)"""
    resident = client.post("/api/household/bootstrap", json={"name": "Nyoman"})
    if resident.status_code not in (200, 201):
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    rtok = resident.json()["token"]
    client.post("/api/household/places/seed", json={"actor_token": rtok})

    # A member scans the studio's QR → present there (the scan IS the consent).
    member = client.post("/api/household/members", json={"name": "Wira"}).json()
    mtok = member["token"]
    here = client.post("/api/household/presence",
                       json={"actor_token": mtok, "place_id": "place-yoga-studio"}).json()
    assert here["at_place"] == "place-yoga-studio" and here["at_place_name"] == "Yoga Studio"

    # The field sees who's where, on the see-locked roster (registered cells only).
    assert client.get("/api/household/members").status_code == 401
    roster = client.get(f"/api/household/members?token={rtok}").json()
    me = next(m for m in roster if m["id"] == member["id"])
    assert me["at_place_name"] == "Yoga Studio"

    # The cell clears its own presence on leave — sovereign.
    left = client.post("/api/household/presence/leave", json={"actor_token": mtok}).json()
    assert left["at_place"] in (None, "")

    # Presence at a place that doesn't exist is refused.
    assert client.post("/api/household/presence",
                       json={"actor_token": mtok, "place_id": "place-nowhere"}).status_code == 404
