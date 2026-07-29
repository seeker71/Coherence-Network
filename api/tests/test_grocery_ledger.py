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


def test_the_csv_door_names_every_column_the_sheet_gets():
    # The export and the Sheets mirror must not drift apart — leaving the app
    # has to hand back exactly what staying in it recorded.
    spend = grocery.SpendResponse(
        id="spend-1", amount_typed="123.5", amount_idr=123500,
        description="morning market", category="fish", place_name="Pasar Badung",
        spent_on="2026-07-29", by_id="m1", by_name="Wayan", created_at="2026-07-29T01:00:00Z",
    )
    assert set(grocery._sheet_row(spend)) == set(grocery._SHEET_COLUMNS)


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
