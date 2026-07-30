"""Flow test for the grocery ledger (api/app/routers/grocery.py).

Two lanes. The first is the amount — the manager types thousands and the
ledger must hold whole rupiah, exactly, with no float anywhere in the path;
that lane is pure parsing and runs everywhere. The second is the flow: a
resident records a spend, a stored shop fills the description in by GPS
proximity, and the ledger totals what the day cost — that lane computes the
amount on the Form kernel, so it runs where the kernel is built (the same
place the household board's tests run).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import grocery


@pytest.fixture
def client():
    return TestClient(app)


# --------------------------------------------------------------------------
# The amount, before it reaches the kernel: digits stay digits.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("123.5", (123, 5, 1)),     # the manager's example: Rp 123.500
        ("123,5", (123, 5, 1)),     # an Indonesian keyboard's decimal comma
        ("85", (85, 0, 0)),         # Rp 85.000
        ("0.25", (0, 25, 2)),       # Rp 250 — below one thousand
        ("12.05", (12, 5, 2)),      # the leading zero is load-bearing: Rp 12.050
        (" 7.5 ", (7, 5, 1)),       # thumbs add whitespace
        ("12.3456", (12, 345, 3)),  # past one rupiah, the digits are noise
    ],
)
def test_typed_amount_splits_into_exact_digits(typed, expected):
    assert grocery._split_typed_amount(typed) == expected


@pytest.mark.parametrize("bad", ["", "  ", "abc", "1.2.3", "-5", "12x"])
def test_a_non_amount_is_refused_rather_than_guessed(bad):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        grocery._split_typed_amount(bad)
    assert exc.value.status_code == 422


def test_description_prefers_what_was_actually_said():
    shop = {"name": "Pasar Badung", "default_description": "morning market"}
    # A typed note is the most specific thing anyone said.
    assert grocery._resolve_description(note="ikan tuna", category="fish", shop=shop) == "ikan tuna"
    # Standing in the market is itself a statement.
    assert grocery._resolve_description(note=None, category="fish", shop=shop) == "morning market"
    # With no shop near, the icon carries it.
    assert grocery._resolve_description(note=None, category="fish", shop=None) == "Fish"
    # And with nothing at all, the entry still says what it is.
    assert grocery._resolve_description(note=None, category=None, shop=None) == "Groceries"


def test_the_mirror_appends_a_signed_row():
    # The restructured ledger is an append-only `When | Amount | What` log.
    # Amount is signed so "remaining" is one SUM in a fixed cell rather than
    # a row that every new entry has to be squeezed above.
    buy = grocery.SpendResponse(
        id="spend-1", amount_typed="477.3", amount_idr=477300,
        description="pasar pagi — sayur & ikan", category="fish",
        place_name="Pasar Badung", spent_on="2026-07-29",
        by_id="m1", by_name="Wayan", created_at="2026-07-29T01:00:00Z",
    )
    row = grocery._sheet_row(buy)
    assert set(row) == set(grocery._SHEET_COLUMNS) == {"When", "Amount", "What"}
    assert row["Amount"] == 477300 and isinstance(row["Amount"], int)
    assert row["When"] == "2026-07-29"
    # `What` is the column that was empty on every purchase in the real
    # ledger — the app exists to arrive with it already filled.
    assert row["What"] == "pasar pagi — sayur & ikan"

    # Money coming in points the other way, in the same column.
    topup = grocery.SpendResponse(
        id="topup-1", amount_typed="4000", amount_idr=4_000_000,
        description="top up", spent_on="2026-07-29", kind="topup",
        by_id="m1", by_name="Wayan", created_at="2026-07-29T01:00:00Z",
    )
    assert grocery._sheet_row(topup)["Amount"] == -4_000_000


def test_the_csv_door_stays_lossless():
    # The sheet shows four columns; the export must still carry everything
    # the ledger knows, or leaving the app would cost the hub its detail.
    spend = grocery.SpendResponse(
        id="spend-1", amount_typed="123.5", amount_idr=123500,
        description="morning market", category="fish", place_name="Pasar Badung",
        spent_on="2026-07-29", by_id="m1", by_name="Wayan", created_at="2026-07-29T01:00:00Z",
    )
    assert set(grocery._csv_row(spend)) == set(grocery._CSV_COLUMNS)
    assert len(grocery._CSV_COLUMNS) > len(grocery._SHEET_COLUMNS)


# --------------------------------------------------------------------------
# The flow — needs the Form kernel, like the household board's tests.
# --------------------------------------------------------------------------


def test_a_spend_records_with_the_shop_filling_in_the_description(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Komang"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    assert resident.status_code == 201, resident.text
    token = resident.json()["token"]

    # A shop is remembered where it stands, with the description it carries.
    shop = client.post("/api/grocery/shops", json={
        "actor_token": token,
        "name": "Pasar Badung",
        "default_description": "pasar pagi — sayur & ikan",
        "lat": -8_650_000, "lon": 115_216_000,
    })
    assert shop.status_code == 200, shop.text
    shop_id = shop.json()["id"]
    assert shop.json()["default_description"] == "pasar pagi — sayur & ikan"

    # Standing at it, the nearest door finds it.
    near = client.get(
        f"/api/grocery/shops/nearest?lat=-8650100&lon=115216050&token={token}"
    )
    assert near.status_code == 200, near.text
    assert near.json() and near.json()["id"] == shop_id

    # Four kilometres away it is not "near", so the icons carry the meaning.
    far = client.get(f"/api/grocery/shops/nearest?lat=-8700000&lon=115216000&token={token}")
    assert far.status_code == 200 and far.json() is None

    # The manager types one number; the rest is already filled in.
    spend = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "123.5", "lat": -8_650_100, "lon": 115_216_050,
    })
    assert spend.status_code == 200, spend.text
    body = spend.json()
    assert body["amount_idr"] == 123_500          # the whole point
    assert body["amount_typed"] == "123.5"
    assert body["currency"] == "IDR"
    assert body["place_id"] == shop_id
    assert body["description"] == "pasar pagi — sayur & ikan"
    assert body["spent_on"] == grocery._today_local()
    assert body["by_name"] == "Komang"

    # Away from any shop, an icon plus a custom note still says what it was.
    other = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "0.25", "category": "spice", "note": "cabe rawit",
    })
    assert other.status_code == 200, other.text
    assert other.json()["amount_idr"] == 250
    assert other.json()["description"] == "cabe rawit"

    # And the day totals what it cost.
    totals = client.get(f"/api/grocery/totals?token={token}")
    assert totals.status_code == 200
    assert totals.json()["day_total_idr"] >= 123_750
    assert totals.json()["day_count"] >= 2


def test_a_stored_shop_is_renamed_without_touching_past_entries(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Wayan"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    shop = client.post("/api/grocery/shops", json={
        "actor_token": token, "name": "Toko Lama", "default_description": "Toko Lama",
    })
    shop_id = shop.json()["id"]

    # An entry recorded before the rename keeps what it already said.
    before = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "50", "place_id": shop_id,
    })
    assert before.json()["description"] == "Toko Lama"

    edit = client.patch(f"/api/grocery/shops/{shop_id}", json={
        "actor_token": token, "name": "Toko Baru",
    })
    assert edit.status_code == 200, edit.text
    assert edit.json()["name"] == "Toko Baru"
    # default_description follows the new name when only name was given.
    assert edit.json()["default_description"] == "Toko Baru"

    # A later entry at the same place fills in the new name.
    after = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "60", "place_id": shop_id,
    })
    assert after.json()["description"] == "Toko Baru"

    # The earlier entry's own record is untouched.
    same_day = client.get(f"/api/grocery/spend?token={token}&on={grocery._today_local()}")
    earlier = [s for s in same_day.json() if s["id"] == before.json()["id"]][0]
    assert earlier["description"] == "Toko Lama"


def test_a_rename_survives_on_every_device_not_just_the_one_that_made_it(client):
    """origin_suggestion is server state, not localStorage - the whole point.

    A household has more than one phone. If "already used" lived only in the
    browser that did the renaming, the OTHER phone would still offer the
    starting suggestion as a ghost duplicate after a rename. Reading the shop
    back through a second, independent client call is the real test: the
    graph itself, not any one device, has to carry the answer.
    """
    resident = client.post("/api/household/bootstrap", json={"name": "Sri"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    created = client.post("/api/grocery/shops", json={
        "actor_token": token, "name": "Bali Buda", "default_description": "Bali Buda",
        "origin_suggestion": "Bali Buda",
    })
    assert created.json()["origin_suggestion"] == "Bali Buda"
    shop_id = created.json()["id"]

    client.patch(f"/api/grocery/shops/{shop_id}", json={
        "actor_token": token, "name": "Bali Buda Ubud",
    })

    # A fresh, independent read - standing in for Ita's phone reading the
    # same household state Urs's phone just changed.
    from_elsewhere = client.get(f"/api/grocery/shops?token={token}")
    shop = [s for s in from_elsewhere.json() if s["id"] == shop_id][0]
    assert shop["name"] == "Bali Buda Ubud"
    assert shop["origin_suggestion"] == "Bali Buda"


def test_a_rename_heals_a_shop_saved_before_origin_suggestion_existed(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Ketut"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    # No origin_suggestion sent - as every shop created before this field
    # existed looks today.
    legacy = client.post("/api/grocery/shops", json={
        "actor_token": token, "name": "Pasar", "default_description": "Pasar",
    })
    assert legacy.json()["origin_suggestion"] is None
    shop_id = legacy.json()["id"]

    healed = client.patch(f"/api/grocery/shops/{shop_id}", json={
        "actor_token": token, "name": "Pasar Ubud", "origin_suggestion": "Pasar",
    })
    assert healed.json()["origin_suggestion"] == "Pasar"

    # A second rename must not let a caller overwrite an origin already set.
    again = client.patch(f"/api/grocery/shops/{shop_id}", json={
        "actor_token": token, "name": "Pasar Ubud Pusat", "origin_suggestion": "Something Else",
    })
    assert again.json()["origin_suggestion"] == "Pasar"


def test_editing_a_shop_needs_write_access_and_something_to_change(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Kadek"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]
    shop = client.post("/api/grocery/shops", json={
        "actor_token": token, "name": "Warung", "default_description": "Warung",
    })
    shop_id = shop.json()["id"]

    member = client.post("/api/household/members", json={"name": "Rina"})
    read_only_token = member.json()["token"]
    refused = client.patch(f"/api/grocery/shops/{shop_id}", json={
        "actor_token": read_only_token, "name": "Warung Baru",
    })
    assert refused.status_code == 403

    empty = client.patch(f"/api/grocery/shops/{shop_id}", json={"actor_token": token})
    assert empty.status_code == 400

    missing = client.patch("/api/grocery/shops/place-shop-doesnotexist", json={
        "actor_token": token, "name": "Anything",
    })
    assert missing.status_code == 404


def test_forgetting_a_shop_keeps_what_past_entries_already_said(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Made"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    shop = client.post("/api/grocery/shops", json={
        "actor_token": token, "name": "Toko Sementara", "default_description": "Toko Sementara",
    })
    shop_id = shop.json()["id"]
    spend = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "40", "place_id": shop_id,
    })
    assert spend.json()["description"] == "Toko Sementara"

    gone = client.delete(f"/api/grocery/shops/{shop_id}?actor_token={token}")
    assert gone.status_code == 200, gone.text
    assert gone.json()["deleted"] == shop_id

    # The past entry's own text is unaffected by the shop no longer existing.
    same_day = client.get(f"/api/grocery/spend?token={token}&on={grocery._today_local()}")
    earlier = [s for s in same_day.json() if s["id"] == spend.json()["id"]][0]
    assert earlier["description"] == "Toko Sementara"

    # It no longer appears in the stored list, and a second delete is honest
    # about there being nothing left to forget.
    shops = client.get(f"/api/grocery/shops?token={token}")
    assert shop_id not in [s["id"] for s in shops.json()]
    twice = client.delete(f"/api/grocery/shops/{shop_id}?actor_token={token}")
    assert twice.status_code == 404


def test_zero_is_not_a_spend_and_an_unknown_category_is_refused(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Nyoman"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    zero = client.post("/api/grocery/spend", json={"actor_token": token, "amount": "0"})
    assert zero.status_code == 422

    bad = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "10", "category": "yacht",
    })
    assert bad.status_code == 422


def test_writing_the_ledger_needs_a_vouched_hand(client):
    watcher = client.post("/api/household/members", json={"name": "Ayu"})
    assert watcher.status_code in (200, 201), watcher.text
    wtok = watcher.json()["token"]
    assert watcher.json()["write_access"] is False

    denied = client.post("/api/grocery/spend", json={"actor_token": wtok, "amount": "10"})
    assert denied.status_code == 403

    # Seeing stays open to any registered cell here.
    assert client.get(f"/api/grocery/spend?token={wtok}").status_code == 200


def test_the_sheet_door_reports_where_the_mirror_lands(client, monkeypatch):
    from app.routers import grocery

    # No sheet configured: the ledger still answers, it just has nowhere to
    # point — an unconfigured mirror is a state, not an error.
    monkeypatch.setattr(grocery, "_sheet_id", lambda: "")
    monkeypatch.setattr(grocery, "_sheet_webhook", lambda: ("", ""))
    watcher = client.post("/api/household/members", json={"name": "Kadek"})
    wtok = watcher.json()["token"]
    bare = client.get(f"/api/grocery/sheet?token={wtok}")
    assert bare.status_code == 200, bare.text
    assert bare.json()["configured"] is False
    assert bare.json()["sheet_url"] is None

    # Configured: the id becomes a link a person can actually open.
    monkeypatch.setattr(grocery, "_sheet_id", lambda: "SHEETID123")
    monkeypatch.setattr(grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", ""))
    wired = client.get(f"/api/grocery/sheet?token={wtok}")
    assert wired.json()["configured"] is True
    assert wired.json()["sheet_url"] == "https://docs.google.com/spreadsheets/d/SHEETID123/edit"
    assert isinstance(wired.json()["pending"], int)


def test_a_wrong_number_can_be_taken_back(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Putu"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    # A fat-fingered 4770 instead of 477 must not be permanent.
    spend = client.post("/api/grocery/spend", json={
        "actor_token": token, "amount": "4770", "category": "vegetable",
    })
    assert spend.status_code == 200, spend.text
    spend_id = spend.json()["id"]

    gone = client.delete(f"/api/grocery/spend/{spend_id}?actor_token={token}")
    assert gone.status_code == 200, gone.text
    assert gone.json()["deleted"] == spend_id
    # Whether the sheet already saw it is said plainly — we never edit the
    # hub's own document behind their back.
    assert isinstance(gone.json()["was_mirrored"], bool)

    remaining = client.get(f"/api/grocery/spend?token={token}").json()
    assert all(r["id"] != spend_id for r in remaining)

    # Gone means gone.
    assert client.delete(f"/api/grocery/spend/{spend_id}?actor_token={token}").status_code == 404


def test_someone_else_s_entry_is_not_yours_to_delete(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Gede"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    rtok = resident.json()["token"]
    mine = client.post("/api/grocery/spend", json={"actor_token": rtok, "amount": "12"}).json()["id"]

    staff = client.post("/api/household/invites", json={
        "inviter_token": rtok, "name": "Made", "role": "staff",
    })
    stok = staff.json()["token"]
    client.get(f"/api/household/me?token={stok}")   # activate the invite

    denied = client.delete(f"/api/grocery/spend/{mine}?actor_token={stok}")
    assert denied.status_code == 403
    # ...but a resident can fix anyone's mistake.
    assert client.delete(f"/api/grocery/spend/{mine}?actor_token={rtok}").status_code == 200


def test_topping_up_the_float_and_what_is_left(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Ketut"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    before = client.get(f"/api/grocery/totals?token={token}").json()["remaining_idr"]

    # The hub's real shape: money in, then market runs against it.
    top = client.post("/api/grocery/topup", json={"actor_token": token, "amount": "4000"})
    assert top.status_code == 200, top.text
    assert top.json()["amount_idr"] == 4_000_000
    assert top.json()["kind"] == "topup"

    client.post("/api/grocery/spend", json={"actor_token": token, "amount": "385"})
    client.post("/api/grocery/spend", json={"actor_token": token, "amount": "477.3"})

    after = client.get(f"/api/grocery/totals?token={token}").json()
    # 4,000,000 in, 862,300 out — the number a manager asks for before shopping.
    assert after["remaining_idr"] - before == 4_000_000 - 385_000 - 477_300

    # A top-up is money moved, not groceries: it must not inflate the day's spend.
    assert after["day_total_idr"] >= 862_300
    day_rows = client.get(f"/api/grocery/spend?token={token}&on={grocery._today_local()}").json()
    assert any(r["kind"] == "topup" for r in day_rows)   # still visible in the ledger


def test_a_top_up_of_zero_is_refused(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Wayan2"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]
    assert client.post("/api/grocery/topup", json={"actor_token": token, "amount": "0"}).status_code == 422
