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

import asyncio
import hashlib
from pathlib import Path
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import grocery
from app.services import unified_db
from app.services.form_kernel_bridge import run_kernel


_SHEET_SETUP = (
    Path(__file__).resolve().parents[2] / "docs" / "grocery-sheets-setup.md"
)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_RECONCILIATION_BML = (
    _REPO_ROOT
    / "api"
    / "app"
    / "form_recipes"
    / "endpoint_grocery_reconcile_selection.bml"
)
_RECONCILIATION_RECIPE = _RECONCILIATION_BML.with_suffix(".fk")


def _pending_grocery_node(node_id: str, description: str, created_at: str) -> dict:
    return {
        "id": node_id,
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": description,
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": created_at,
        "sheet_synced": False,
    }


def _configure_receipt_reserve_test(monkeypatch, legacy, current, reconciled):
    async def select_current(_rows, _now, *, deadline):
        assert deadline == grocery._SHEET_RESYNC_TOTAL_TIMEOUT
        return [current]

    async def reconcile(pending_nodes, _pending, **_kwargs):
        reconciled.extend(node["id"] for node in pending_nodes)
        legacy.update(sheet_synced=True, sheet_protocol=grocery._SHEET_PROTOCOL)
        return grocery._SheetSnapshot(2_000_000, frozenset(), frozenset())

    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy, current])
    monkeypatch.setattr(grocery, "_joined_current_sheet_retry_batch", select_current)
    monkeypatch.setattr(grocery, "_reconciled_sheet_snapshot", reconcile)
    monkeypatch.setattr(
        grocery,
        "_push_to_sheet_status",
        lambda _spend: pytest.fail("an append without receipt budget must not start"),
    )


@pytest.fixture
def client():
    return TestClient(app)


def test_reconciliation_policy_band_runs_on_production_form():
    recipe = _RECONCILIATION_RECIPE.read_text()
    band = (
        _REPO_ROOT
        / "api"
        / "tests"
        / "form"
        / "grocery-reconcile-selection-band.fk"
    ).read_text()
    band = band.replace(
        "; preludes: ../../api/app/form_recipes/"
        "endpoint_grocery_reconcile_selection.fk\n",
        "",
    )

    verdict, runtime = run_kernel(f"{recipe}\n{band}", parse=int, timeout=30)

    assert runtime == "fkwu"
    assert verdict == 255


def test_reconciliation_recipe_is_generated_from_current_bml_source():
    source_digest = hashlib.sha256(_RECONCILIATION_BML.read_bytes()).hexdigest()
    recipe = _RECONCILIATION_RECIPE.read_text()

    assert f"; BML-SHA256: {source_digest}" in recipe.splitlines()[:3]
    assert "(defn GroceryReconciliationPolicy" in recipe


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
    assert set(row) == set(grocery._SHEET_COLUMNS) == {
        "When", "Amount", "What", "Entry ID",
    }
    assert row["Amount"] == 477300 and isinstance(row["Amount"], int)
    assert row["When"] == "2026-07-29"
    # `What` is the column that was empty on every purchase in the real
    # ledger — the app exists to arrive with it already filled.
    assert row["What"] == "pasar pagi — sayur & ikan"
    assert row["Entry ID"] == "spend-1"

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


def test_every_grocery_row_comes_from_one_stable_snapshot(monkeypatch):
    rows = [
        {"id": f"spend-{i}", "type": grocery._SPEND_TYPE}
        for i in range(2001)
    ]
    calls: list[str] = []

    def snapshot(node_type):
        calls.append(node_type)
        return rows

    monkeypatch.setattr(grocery.graph_service, "list_nodes_by_type_snapshot", snapshot)
    assert len(grocery._all_spends()) == 2001
    assert calls == [grocery._SPEND_TYPE]


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
    assert grocery.graph_service.get_node_unfiltered(body["id"])["sheet_protocol"] == "entry-id-v1"

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
    monkeypatch.setattr(
        grocery,
        "_sheet_webhook",
        lambda: ("https://example.invalid/exec", "shared-secret"),
    )
    wired = client.get(f"/api/grocery/sheet?token={wtok}")
    assert wired.json()["configured"] is True
    assert wired.json()["sheet_url"] == "https://docs.google.com/spreadsheets/d/SHEETID123/edit"
    assert isinstance(wired.json()["pending"], int)


def test_the_sheet_balance_is_read_through_the_authenticated_bounded_carrier(monkeypatch):
    class _Response:
        status_code = 200
        def json(self):
            return {
                "ok": True,
                "remaining_idr": "Rp2,419,050",
                "acknowledged_ids": ["spend-1", "spend-legacy", "not-requested"],
                "cancelled_ids": ["spend-cancelled", "not-requested"],
            }

    seen: list[tuple[str, dict]] = []

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, json):
            seen.append((url, json))
            return _Response()

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "shared-secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())

    legacy = grocery.SpendResponse(
        id="spend-legacy", amount_typed="10", amount_idr=10_000,
        description="vegetables", spent_on="2026-09-10",
        by_id="m1", by_name="Wayan", created_at="2026-09-10T01:00:00Z",
    )

    snapshot = asyncio.run(
        grocery._read_sheet_snapshot(
            ["spend-1", "spend-cancelled", "spend-legacy"],
            legacy_entries=[legacy],
        )
    )
    assert snapshot == grocery._SheetSnapshot(
        2_419_050,
        frozenset({"spend-1", "spend-legacy"}),
        frozenset({"spend-cancelled"}),
    )
    assert seen == [("https://example.invalid/exec", {
        "action": "summary",
        "secret": "shared-secret",
        "pending_ids": ["spend-1", "spend-cancelled", "spend-legacy"],
        "legacy_entries": [{
            "entry_id": "spend-legacy",
            "row": {
                "When": "2026-09-10",
                "Amount": 10_000,
                "What": "vegetables",
                "Entry ID": "spend-legacy",
            },
            "columns": ["When", "Amount", "What", "Entry ID"],
        }],
    })]


def test_sheet_read_retries_one_transient_cold_start(monkeypatch):
    attempts = 0
    timeouts: list[float] = []

    class _Response:
        status_code = 200

        def json(self):
            return {
                "ok": True,
                "remaining_idr": 42,
                "acknowledged_ids": [],
                "cancelled_ids": [],
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise grocery.httpx.ReadTimeout("cold start")
            return _Response()

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    def client(**kwargs):
        timeouts.append(kwargs["timeout"])
        return _Client()

    monkeypatch.setattr(grocery.httpx, "AsyncClient", client)

    snapshot = asyncio.run(grocery._read_sheet_snapshot([]))
    assert snapshot == grocery._SheetSnapshot(42, frozenset(), frozenset())
    assert attempts == 2
    assert timeouts == [grocery._SHEET_READ_ATTEMPT_TIMEOUT] * 2
    assert sum(timeouts) < 15
    assert grocery._SHEET_READ_TOTAL_TIMEOUT < 15


def test_sheet_read_has_one_wall_clock_deadline(monkeypatch):
    attempts = 0

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            nonlocal attempts
            attempts += 1
            await asyncio.sleep(1)
            raise AssertionError("the total deadline should cancel this request")

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())
    monkeypatch.setattr(grocery, "_SHEET_READ_TOTAL_TIMEOUT", 0.01)

    assert asyncio.run(grocery._read_sheet_snapshot([])) is None
    assert attempts == 1


def test_totals_share_one_deadline_with_sheet_and_form(monkeypatch):
    observed_timeouts: list[float] = []
    ticks = iter([100.0, 100.0, 112.25])

    async def snapshot(_pending_ids):
        return grocery._SheetSnapshot(2_000_000, frozenset(), frozenset())

    def kernel(_recipe, *, bindings, parse, timeout):
        observed_timeouts.append(timeout)
        return [1, bindings["sheet_remaining"]], "fkwu"

    monkeypatch.setattr(grocery, "_require_member", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [])
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", snapshot)
    monkeypatch.setattr(grocery, "_monotonic", lambda: next(ticks))
    monkeypatch.setattr(grocery, "serve_via_kernel", kernel)

    result = asyncio.run(grocery.totals(token="member-token", on=None))

    assert result.remaining_source == "sheet"
    assert observed_timeouts == [pytest.approx(0.75)]


def test_totals_do_not_start_form_after_the_shared_deadline(monkeypatch):
    ticks = iter([100.0, 100.0, 113.01])

    async def snapshot(_pending_ids):
        return grocery._SheetSnapshot(2_000_000, frozenset(), frozenset())

    def kernel(*_args, **_kwargs):
        raise AssertionError("an expired totals request must not start Form")

    monkeypatch.setattr(grocery, "_require_member", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [])
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", snapshot)
    monkeypatch.setattr(grocery, "_monotonic", lambda: next(ticks))
    monkeypatch.setattr(grocery, "serve_via_kernel", kernel)

    result = asyncio.run(grocery.totals(token="member-token", on=None))

    assert result.remaining_idr is None
    assert result.remaining_source == "unavailable"


def test_sheet_read_fails_closed_without_the_shared_secret(monkeypatch):
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "")
    )
    assert asyncio.run(grocery._read_sheet_snapshot([])) is None


def test_totals_use_sheet_balance_plus_only_pending_graph_delta(client, monkeypatch):
    resident = client.post("/api/household/bootstrap", json={"name": "Sheet keeper"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]
    async def snapshot_without_entry(_pending_ids):
        return grocery._SheetSnapshot(2_000_000, frozenset(), frozenset())

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", snapshot_without_entry)

    spend = client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "100", "category": "vegetable"},
    )
    assert spend.status_code == 200, spend.text
    assert spend.json()["sheet_synced"] is False

    body = client.get(f"/api/grocery/totals?token={token}").json()
    assert body["remaining_idr"] == 1_900_000
    assert body["remaining_source"] == "sheet"


def test_totals_do_not_double_apply_an_entry_already_acknowledged_by_sheet(
    client, monkeypatch
):
    resident = client.post("/api/household/bootstrap", json={"name": "Sheet witness"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    spend = client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "100", "category": "vegetable"},
    )
    assert spend.status_code == 200, spend.text
    spend_id = spend.json()["id"]
    assert spend.json()["sheet_synced"] is False

    async def snapshot_with_entry(pending_ids):
        assert pending_ids == [spend_id]
        # The Sheet balance already includes this append even though a crash
        # left the graph flag false. Its acknowledgement makes the read exact.
        return grocery._SheetSnapshot(
            1_900_000, frozenset({spend_id}), frozenset()
        )

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", snapshot_with_entry)
    body = client.get(f"/api/grocery/totals?token={token}").json()
    assert body["remaining_idr"] == 1_900_000
    assert body["remaining_source"] == "sheet"


def test_totals_do_not_apply_an_entry_cancelled_after_the_database_snapshot(
    client, monkeypatch
):
    resident = client.post(
        "/api/household/bootstrap", json={"name": "Cancellation witness"}
    )
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    spend = client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "100", "category": "vegetable"},
    )
    assert spend.status_code == 200, spend.text
    spend_id = spend.json()["id"]

    async def snapshot_after_delete(pending_ids):
        assert pending_ids == [spend_id]
        # The graph snapshot preceded a completed delete. The same locked
        # Sheet receipt carries that cancellation, so the stale row is not
        # applied to the post-delete balance.
        return grocery._SheetSnapshot(
            2_000_000, frozenset(), frozenset({spend_id})
        )

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", snapshot_after_delete)
    body = client.get(f"/api/grocery/totals?token={token}").json()
    assert body["remaining_idr"] == 2_000_000
    assert body["remaining_source"] == "sheet"


def test_sheet_append_requires_an_idempotent_entry_acknowledgement(monkeypatch):
    spend = grocery.SpendResponse(
        id="spend-idempotent", amount_typed="10", amount_idr=10_000,
        description="vegetables", spent_on="2026-09-10",
        by_id="m1", by_name="Wayan", created_at="2026-09-10T01:00:00Z",
    )
    seen: list[dict] = []

    class _Response:
        status_code = 200
        def json(self):
            return {"ok": True, "entry_id": "spend-idempotent", "appended": False}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            seen.append(json)
            return _Response()

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "shared-secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())

    assert asyncio.run(grocery._push_to_sheet(spend)) is True
    assert seen[0]["action"] == "append"
    assert seen[0]["entry_id"] == spend.id
    assert seen[0]["row"]["Entry ID"] == spend.id
    assert seen[0]["secret"] == "shared-secret"


def test_sheet_append_does_not_acknowledge_a_cancelled_entry(monkeypatch):
    spend = grocery.SpendResponse(
        id="spend-cancelled", amount_typed="10", amount_idr=10_000,
        description="vegetables", spent_on="2026-09-10",
        by_id="m1", by_name="Wayan", created_at="2026-09-10T01:00:00Z",
    )

    class _Response:
        status_code = 200
        def json(self):
            return {
                "ok": True,
                "entry_id": spend.id,
                "appended": False,
                "cancelled": True,
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            return _Response()

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())
    assert asyncio.run(grocery._push_to_sheet_status(spend)) == "cancelled"


def test_sheet_append_has_one_wall_clock_deadline(monkeypatch):
    spend = grocery.SpendResponse(
        id="spend-write-timeout", amount_typed="10", amount_idr=10_000,
        description="vegetables", spent_on="2026-09-10",
        by_id="m1", by_name="Wayan", created_at="2026-09-10T01:00:00Z",
    )

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            await asyncio.sleep(1)
            raise AssertionError("the total deadline should cancel this request")

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())
    monkeypatch.setattr(grocery, "_SHEET_WRITE_TOTAL_TIMEOUT", 0.01)

    assert asyncio.run(grocery._push_to_sheet(spend)) is False


def test_sheet_delete_reconciliation_is_one_atomic_carrier_operation(monkeypatch):
    node = {
        "id": "spend-race",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "100",
        "amount_idr": 100_000,
        "spend_description": "vegetables",
        "spent_on": "2026-09-10",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-09-10T01:00:00Z",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    actor = {"id": "m1", "name": "Wayan"}
    seen: list[dict] = []

    class _Response:
        status_code = 200
        def json(self):
            return {
                "ok": True,
                "cancelled": True,
                "original_id": "spend-race",
                "original_present": True,
                "reversal_id": "reversal-spend-race",
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            seen.append(json)
            return _Response()

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())

    assert asyncio.run(grocery._reconcile_sheet_delete(node, actor)) is True
    assert len(seen) == 1
    assert seen[0]["action"] == "reconcile_delete"
    assert seen[0]["original_id"] == "spend-race"
    assert seen[0]["known_mirrored"] is False
    assert seen[0]["reversal"]["entry_id"] == "reversal-spend-race"
    assert seen[0]["reversal"]["row"]["Amount"] == -100_000


def test_sheet_delete_tags_a_synced_legacy_original_before_reversal(monkeypatch):
    node = {
        "id": "spend-legacy-synced",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "100",
        "amount_idr": 100_000,
        "spend_description": "vegetables",
        "spent_on": "2026-09-10",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-09-10T01:00:00Z",
        "sheet_synced": True,
    }
    seen: list[dict] = []

    class _Response:
        status_code = 200
        def json(self):
            return {
                "ok": True,
                "cancelled": True,
                "original_id": "spend-legacy-synced",
                "original_present": True,
                "reversal_id": "reversal-spend-legacy-synced",
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, json):
            seen.append(json)
            return _Response()

    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery.httpx, "AsyncClient", lambda **_kwargs: _Client())

    assert asyncio.run(grocery._reconcile_sheet_delete(node, {"id": "m1"})) is True
    assert seen[0]["legacy_original"]["entry_id"] == "spend-legacy-synced"
    assert seen[0]["legacy_original"]["row"]["What"] == "vegetables"


def test_legacy_unsynced_entry_is_reconciled_before_balance(monkeypatch):
    legacy = {
        "id": "spend-legacy-unknown",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "100",
        "amount_idr": 100_000,
        "spend_description": "legacy vegetables",
        "spent_on": "2026-09-10",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-09-10T01:00:00Z",
        "sheet_synced": False,
        # No sheet_protocol: a predecessor append may have landed without an ID.
    }
    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )

    async def must_not_push(_spend):
        raise AssertionError("legacy unknown entry must not be replayed")

    monkeypatch.setattr(grocery, "_push_to_sheet", must_not_push)
    assert asyncio.run(grocery._reconcile_sheet_delete(legacy, {"id": "m1"})) is None
    seen_updates: list[tuple[dict[str, dict], dict]] = []

    async def must_not_read_while_legacy_is_unresolved(_pending_ids):
        pytest.fail("a known legacy block must not wait on the Sheet")

    monkeypatch.setattr(
        grocery,
        "_require_member",
        lambda _token: {"id": "watcher", "write_access": False},
    )
    monkeypatch.setattr(
        grocery,
        "_read_sheet_snapshot",
        must_not_read_while_legacy_is_unresolved,
    )
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda updates, **kwargs: (
            seen_updates.append((updates, kwargs)) or set(updates)
        ),
    )
    totals = asyncio.run(grocery.totals(token="member-token", on=None))
    assert totals.remaining_idr is None
    assert totals.remaining_source == "unavailable"
    assert seen_updates == []
    assert "sheet_reconcile_attempted_at" not in legacy

    async def reconcile_legacy(pending_ids, *, legacy_entries):
        assert pending_ids == ["spend-legacy-unknown"]
        assert [entry.id for entry in legacy_entries] == ["spend-legacy-unknown"]
        return grocery._SheetSnapshot(
            2_000_000,
            frozenset({"spend-legacy-unknown"}),
            frozenset(),
        )

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", reconcile_legacy)
    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert result.attempted == 0
    assert result.synced == 0
    assert result.blocked_legacy == 0
    assert len(seen_updates) == 1
    updates, update_kwargs = seen_updates[0]
    assert set(updates) == {"spend-legacy-unknown"}
    assert update_kwargs["_include_private"] is True
    assert updates["spend-legacy-unknown"]["sheet_synced"] is True
    assert (
        updates["spend-legacy-unknown"]["sheet_protocol"]
        == grocery._SHEET_PROTOCOL
    )
    assert updates["spend-legacy-unknown"]["sheet_reconcile_attempted_at"]

    async def read_only_summary(pending_ids):
        assert pending_ids == []
        return grocery._SheetSnapshot(
            2_000_000,
            frozenset(),
            frozenset(),
        )

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", read_only_summary)
    totals = asyncio.run(grocery.totals(token="member-token", on=None))
    assert totals.remaining_idr == 2_000_000
    assert totals.remaining_source == "sheet"


def test_unavailable_sheet_does_not_persist_reconciliation_rotation(monkeypatch):
    legacy = {
        "id": "spend-legacy-unavailable",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "legacy",
        "spent_on": "2026-09-10",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-09-10T01:00:00Z",
        "sheet_synced": False,
    }

    async def unavailable(_pending_ids, *, legacy_entries):
        assert [entry.id for entry in legacy_entries] == [legacy["id"]]
        return None

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", unavailable)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda *_args, **_kwargs: pytest.fail("an unavailable carrier must not write"),
    )

    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert result.blocked_legacy == 1
    assert "sheet_reconcile_attempted_at" not in legacy


def test_legacy_resync_has_one_wall_clock_deadline(monkeypatch):
    legacy = {
        "id": "spend-legacy-total-deadline",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "legacy",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
    }

    selection_finished = threading.Event()

    def slow_selection(*_args, **_kwargs):
        grocery.time.sleep(0.05)
        selection_finished.set()
        return []

    async def must_not_read(*_args, **_kwargs):
        pytest.fail("the resync deadline must expire before Sheet I/O starts")

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_legacy_reconciliation_batch", slow_selection)
    monkeypatch.setattr(
        grocery, "_current_sheet_retry_batch", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", must_not_read)
    monkeypatch.setattr(grocery, "_SHEET_RESYNC_TOTAL_TIMEOUT", 0.01)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda *_args, **_kwargs: pytest.fail("timed-out resync must not persist"),
    )

    started = grocery.time.monotonic()
    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert grocery.time.monotonic() - started >= 0.04
    assert selection_finished.is_set()
    assert result.attempted == 0
    assert result.synced == 0
    assert result.blocked_legacy == 1


def test_legacy_selection_passes_its_remaining_deadline_to_form(monkeypatch):
    node = {"id": "spend-form-deadline", "sheet_synced": False}
    spend = grocery.SpendResponse(
        id=node["id"],
        amount_typed="1",
        amount_idr=1_000,
        description="rice",
        spent_on="2026-10-07",
        by_id="m1",
        by_name="Wayan",
        created_at="2026-10-07T01:00:00Z",
    )
    observed_timeout: list[float] = []

    def form_selection(_recipe, *, bindings, parse, timeout):
        assert bindings["entries_wire"]
        assert parse is grocery.json.loads
        observed_timeout.append(timeout)
        return [0], "fkwu"

    monkeypatch.setattr(grocery, "serve_via_kernel", form_selection)
    deadline = grocery.time.monotonic() + 0.5
    batch = grocery._legacy_reconciliation_batch(
        [node],
        [spend],
        all_nodes=[node],
        all_entries=[spend],
        deadline=deadline,
    )

    assert [entry.id for _node, entry in batch] == [spend.id]
    assert len(observed_timeout) == 1
    assert 0 < observed_timeout[0] <= 0.5
    with pytest.raises(asyncio.TimeoutError):
        grocery._legacy_reconciliation_batch(
            [node],
            [spend],
            all_nodes=[node],
            all_entries=[spend],
            deadline=grocery.time.monotonic() - 1,
        )


def test_current_retry_selection_runs_on_form_policy():
    rows = [
        {
            "id": "ready",
            "sheet_synced": False,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
        },
        {
            "id": "waiting",
            "sheet_synced": False,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
            "sheet_append_retry_after": "2026-10-07T02:00:00Z",
        },
        {
            "id": "elapsed",
            "sheet_synced": False,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
            "sheet_append_retry_after": "2026-10-07T00:00:00Z",
        },
        {
            "id": "cancelled",
            "sheet_synced": False,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
            "sheet_cancelled": True,
        },
        {"id": "legacy", "sheet_synced": False},
        {
            "id": "yielding",
            "sheet_synced": False,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
            "sheet_append_yield_legacy": True,
        },
    ]

    selected = grocery._current_sheet_retry_batch(
        rows,
        "2026-10-07T01:00:00Z",
        deadline=grocery.time.monotonic() + 10,
    )

    assert [row["id"] for row in selected] == ["ready", "elapsed"]

    selected_after_legacy = grocery._current_sheet_retry_batch(
        [rows[-1]],
        "2026-10-07T01:00:00Z",
        deadline=grocery.time.monotonic() + 10,
    )

    assert [row["id"] for row in selected_after_legacy] == ["yielding"]


def test_successful_legacy_snapshot_returns_the_next_turn_to_current(monkeypatch):
    current = {
        "id": "current-yielded-to-legacy",
        "sheet_synced": False,
        "sheet_protocol": grocery._SHEET_PROTOCOL,
        "sheet_append_yield_legacy": True,
    }
    observed: list[dict[str, dict]] = []

    def persist(updates, **_kwargs):
        observed.append(updates)
        return set(updates)

    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        persist,
    )

    persisted = grocery._persist_sheet_receipts(
        [current],
        [],
        grocery._SheetSnapshot(2_000_000, frozenset(), frozenset()),
    )

    assert persisted == {
        current["id"]: {"sheet_append_yield_legacy": False}
    }
    assert observed == [persisted]


def test_cancelled_sheet_receipt_precedes_acknowledgement(monkeypatch):
    current = {
        "id": "current-cancelled-after-delete",
        "sheet_synced": False,
        "sheet_protocol": grocery._SHEET_PROTOCOL,
        "sheet_append_yield_legacy": True,
    }
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda updates, **_kwargs: set(updates),
    )
    entry_id = current["id"]

    persisted = grocery._persist_sheet_receipts(
        [current],
        [],
        grocery._SheetSnapshot(
            2_000_000,
            frozenset({entry_id}),
            frozenset({entry_id}),
        ),
    )

    assert persisted == {
        entry_id: {
            "sheet_cancelled": True,
            "sheet_append_yield_legacy": False,
        }
    }


def test_current_retry_selection_worker_is_joined_on_cancellation(monkeypatch):
    finished = threading.Event()

    def slow_selection(*_args, **_kwargs):
        grocery.time.sleep(0.05)
        finished.set()
        return []

    async def cancel_selection():
        selection = asyncio.create_task(
            grocery._joined_current_sheet_retry_batch(
                [],
                "2026-10-07T01:00:00Z",
                deadline=grocery.time.monotonic() + 1,
            )
        )
        await asyncio.sleep(0.005)
        selection.cancel()
        with pytest.raises(asyncio.CancelledError):
            await selection

    monkeypatch.setattr(grocery, "_current_sheet_retry_batch", slow_selection)

    asyncio.run(cancel_selection())

    assert finished.is_set()


def test_current_retry_selection_deadline_includes_executor_queue(monkeypatch):
    async def queued_without_starting(_function, *_args, **_kwargs):
        await asyncio.Future()

    monkeypatch.setattr(grocery.asyncio, "to_thread", queued_without_starting)
    started = grocery.time.monotonic()

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(
            grocery._joined_current_sheet_retry_batch(
                [],
                "2026-10-07T01:00:00Z",
                deadline=grocery.time.monotonic() + 0.01,
            )
        )

    assert grocery.time.monotonic() - started < 0.1


def test_current_receipt_deadline_cancels_queued_worker(monkeypatch):
    async def queued_without_starting(_function, *_args, **_kwargs):
        await asyncio.Future()

    monkeypatch.setattr(grocery.asyncio, "to_thread", queued_without_starting)
    started = grocery.time.monotonic()

    persisted = asyncio.run(
        grocery._persist_current_sheet_append_status(
            {"id": "queued-current-receipt"},
            "unavailable",
            deadline=grocery.time.monotonic() + 0.01,
        )
    )

    assert persisted is False
    assert grocery.time.monotonic() - started < 0.1


def test_legacy_selection_deadline_includes_executor_queue(monkeypatch):
    async def queued_without_starting(_function, *_args, **_kwargs):
        await asyncio.Future()

    monkeypatch.setattr(grocery.asyncio, "to_thread", queued_without_starting)
    started = grocery.time.monotonic()

    snapshot = asyncio.run(
        grocery._reconciled_sheet_snapshot(
            [],
            [],
            all_nodes=[],
            all_entries=[],
            deadline=grocery.time.monotonic() + 0.01,
        )
    )

    assert snapshot is None
    assert grocery.time.monotonic() - started < 0.1


def test_legacy_resync_waits_for_receipt_transaction_after_deadline(monkeypatch):
    legacy = {
        "id": "spend-legacy-receipt-deadline",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "legacy",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
    }
    transaction_finished = threading.Event()
    observed_deadline: list[float] = []
    observed_remaining: list[float] = []

    def select_one(pending_nodes, pending, **_kwargs):
        return [(pending_nodes[0], pending[0])]

    async def acknowledge(pending_ids, *, legacy_entries):
        assert pending_ids == [legacy["id"]]
        assert [entry.id for entry in legacy_entries] == [legacy["id"]]
        return grocery._SheetSnapshot(
            2_000_000,
            frozenset({legacy["id"]}),
            frozenset(),
        )

    def slow_receipt_write(updates, **kwargs):
        observed_deadline.append(kwargs["_deadline"])
        observed_remaining.append(kwargs["_deadline"] - grocery.time.monotonic())
        grocery.time.sleep(0.05)
        transaction_finished.set()
        return set(updates)

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_legacy_reconciliation_batch", select_one)
    monkeypatch.setattr(
        grocery, "_current_sheet_retry_batch", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", acknowledge)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        slow_receipt_write,
    )
    monkeypatch.setattr(grocery, "_SHEET_RESYNC_TOTAL_TIMEOUT", 0.01)

    started = grocery.time.monotonic()
    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert grocery.time.monotonic() - started >= 0.04
    assert transaction_finished.is_set()
    assert len(observed_deadline) == 1
    assert observed_deadline[0] > started
    assert observed_remaining[0] <= grocery._SHEET_RESYNC_TOTAL_TIMEOUT
    assert result.blocked_legacy == 1


def test_graph_transaction_deadline_expires_before_the_next_operation():
    with pytest.raises(
        grocery.graph_service.TransactionDeadlineExceeded,
        match="deadline exhausted",
    ):
        grocery.graph_service._apply_transaction_deadline(
            None,
            grocery.graph_service.time.monotonic() - 1,
        )


def test_graph_batch_preserves_an_expired_caller_deadline():
    deadline = grocery.graph_service.time.monotonic() + 0.01
    grocery.time.sleep(0.02)

    with pytest.raises(
        unified_db.SQLAlchemyTimeoutError,
        match="deadline exhausted before connect",
    ):
        grocery.graph_service.update_node_properties_batch(
            {"queued-receipt": {"sheet_synced": True}},
            _include_private=True,
            _deadline=deadline,
        )


def test_deadline_postgres_connect_is_direct_and_bounded(monkeypatch):
    captured: dict = {}
    sentinel = object()

    def fake_create_engine(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return sentinel

    monkeypatch.setattr(unified_db, "create_engine", fake_create_engine)
    deadline = unified_db.time.monotonic() + 2.9

    result = unified_db._create_deadline_engine(
        "postgresql+psycopg://user@example.invalid/database",
        deadline,
    )

    assert result is sentinel
    assert captured["pool_pre_ping"] is False
    assert captured["poolclass"] is unified_db.NullPool
    assert captured["connect_args"]["connect_timeout"] == 2
    with pytest.raises(
        unified_db.SQLAlchemyTimeoutError,
        match="no bounded PostgreSQL connect window",
    ):
        unified_db._create_deadline_engine(
            "postgresql+psycopg://user@example.invalid/database",
            unified_db.time.monotonic() + 1.9,
        )


def test_deadline_sqlite_connect_carries_the_absolute_budget(monkeypatch):
    captured: dict = {}
    sentinel = object()

    def fake_create_engine(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return sentinel

    monkeypatch.setattr(unified_db, "_create_engine", fake_create_engine)
    deadline = unified_db.time.monotonic() + 0.2

    result = unified_db._create_deadline_engine(
        "sqlite+pysqlite:////tmp/coherence-deadline-test.db",
        deadline,
    )

    assert result is sentinel
    assert captured["isolated"] is True
    assert 0 < captured["sqlite_timeout_seconds"] <= 0.2
    assert captured["sqlite_deadline"] == deadline


def test_deadline_sqlite_connection_initialization_does_not_outlive_lock(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "locked-receipts.db"
    lock = sqlite3.connect(database_path)
    lock.execute("CREATE TABLE receipts (value INTEGER NOT NULL)")
    lock.commit()
    lock.execute("BEGIN EXCLUSIVE")
    lock.execute("INSERT INTO receipts VALUES (1)")
    monkeypatch.setattr(
        unified_db,
        "database_url",
        lambda: f"sqlite+pysqlite:///{database_path}",
    )

    started = unified_db.time.monotonic()
    try:
        with pytest.raises((unified_db.OperationalError, sqlite3.OperationalError)):
            with unified_db.deadline_session(started + 0.2) as receipt_session:
                receipt_session.execute(
                    unified_db.text("INSERT INTO receipts VALUES (2)")
                )
    finally:
        lock.rollback()
        lock.close()

    assert unified_db.time.monotonic() - started < 1.0


def test_cursor_deadline_shrinks_before_each_statement(monkeypatch):
    class Cursor:
        def __init__(self):
            self.calls: list[tuple[str, tuple[str, str]]] = []

        def execute(self, statement, parameters):
            self.calls.append((statement, parameters))

    cursor = Cursor()
    clock = iter([100.0, 100.4, 101.1])
    monkeypatch.setattr(unified_db.time, "monotonic", lambda: next(clock))

    unified_db._apply_cursor_deadline(cursor, "postgresql", 101.0)
    unified_db._apply_cursor_deadline(cursor, "postgresql", 101.0)
    with pytest.raises(unified_db.SQLAlchemyTimeoutError, match="deadline exhausted"):
        unified_db._apply_cursor_deadline(cursor, "postgresql", 101.0)

    first_ms = int(cursor.calls[0][1][0][:-2])
    second_ms = int(cursor.calls[1][1][0][:-2])
    assert 0 < second_ms < first_ms <= 1_000


def test_connection_deadline_cancels_the_active_operation():
    cancelled = threading.Event()

    class DriverConnection:
        def cancel(self):
            cancelled.set()

    class ConnectionFairy:
        driver_connection = DriverConnection()

    class Connection:
        connection = ConnectionFairy()

    timer = unified_db._arm_connection_deadline(
        Connection(),
        unified_db.time.monotonic() + 0.01,
    )
    try:
        assert cancelled.wait(0.2)
    finally:
        timer.cancel()


def test_connection_deadline_closes_when_driver_cancel_fails():
    closed = threading.Event()

    class DriverConnection:
        def cancel(self):
            raise RuntimeError("cancel carrier unavailable")

        def close(self):
            closed.set()

    class ConnectionFairy:
        driver_connection = DriverConnection()

    class Connection:
        connection = ConnectionFairy()

    timer = unified_db._arm_connection_deadline(
        Connection(),
        unified_db.time.monotonic() + 0.01,
    )
    try:
        assert closed.wait(0.2)
    finally:
        timer.cancel()


def test_connection_deadline_closes_when_driver_cancel_stalls():
    closed = threading.Event()
    release_cancel = threading.Event()

    class DriverConnection:
        def cancel(self):
            release_cancel.wait(1)

        def close(self):
            closed.set()
            release_cancel.set()

    class ConnectionFairy:
        driver_connection = DriverConnection()

    class Connection:
        connection = ConnectionFairy()

    timer = unified_db._arm_connection_deadline(
        Connection(),
        unified_db.time.monotonic() + 0.01,
    )
    try:
        assert closed.wait(0.3)
    finally:
        release_cancel.set()
        timer.cancel()


def test_deadline_batch_rechecks_each_orm_flush_statement(monkeypatch):
    node_ids = ["deadline-flush-one", "deadline-flush-two"]
    for node_id in node_ids:
        grocery.graph_service.create_node(
            id=node_id,
            type="concept",
            name=node_id,
        )
    observed: list[tuple[str, float]] = []
    apply_cursor_deadline = unified_db._apply_cursor_deadline

    def observe(cursor, dialect_name, deadline):
        observed.append((dialect_name, deadline))
        apply_cursor_deadline(cursor, dialect_name, deadline)

    monkeypatch.setattr(unified_db, "_apply_cursor_deadline", observe)
    deadline = unified_db.time.monotonic() + 2
    persisted = grocery.graph_service.update_node_properties_batch(
        {node_id: {"deadline_probe": True} for node_id in node_ids},
        _deadline=deadline,
    )

    assert persisted == set(node_ids)
    assert len(observed) >= 4
    assert all(dialect == "sqlite" for dialect, _deadline in observed)
    assert all(seen_deadline == deadline for _dialect, seen_deadline in observed)


def test_current_protocol_resync_skips_the_legacy_summary_preflight(monkeypatch):
    current = {
        "id": "spend-current-unsynced",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "current",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    pushed: list[str] = []

    async def must_not_preflight(*_args, **_kwargs):
        pytest.fail("current-protocol resync must not spend the summary deadline")

    async def append_current(spend):
        pushed.append(spend.id)
        return "synced"

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [current])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_reconciled_sheet_snapshot", must_not_preflight)
    monkeypatch.setattr(grocery, "_push_to_sheet_status", append_current)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda updates, **_kwargs: set(updates),
    )

    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert result.attempted == 1
    assert result.synced == 1
    assert result.blocked_legacy == 0
    assert pushed == [current["id"]]


def test_unconfigured_resync_returns_without_starting_form(monkeypatch):
    current = {
        "id": "spend-current-unconfigured",
        "sheet_synced": False,
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    legacy = {"id": "spend-legacy-unconfigured", "sheet_synced": False}

    async def must_not_select(*_args, **_kwargs):
        pytest.fail("an unconfigured Sheet must return before Form selection")

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [current, legacy])
    monkeypatch.setattr(grocery, "_sheet_webhook", lambda: ("", ""))
    monkeypatch.setattr(grocery, "_joined_current_sheet_retry_batch", must_not_select)

    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert result.configured is False
    assert result.attempted == 1
    assert result.synced == 0
    assert result.blocked_legacy == 1


def test_current_retry_selection_excludes_synced_history(monkeypatch):
    synced_history = [
        {
            "id": f"spend-synced-{index}",
            "sheet_synced": True,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
        }
        for index in range(500)
    ]
    current = {
        "id": "spend-current-after-history",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "current",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    observed: list[list[str]] = []

    async def select(pending_rows, _now, *, deadline):
        assert deadline > grocery.time.monotonic()
        observed.append([row["id"] for row in pending_rows])
        return pending_rows

    async def append(_spend):
        return "synced"

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [*synced_history, current])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_joined_current_sheet_retry_batch", select)
    monkeypatch.setattr(grocery, "_push_to_sheet_status", append)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda updates, **_kwargs: set(updates),
    )

    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert observed == [[current["id"]]]
    assert result.attempted == 1
    assert result.synced == 1


def test_current_resync_stops_before_the_proxy_budget_is_exhausted(monkeypatch):
    rows = [
        {
            "id": f"spend-current-{index}",
            "type": grocery._SPEND_TYPE,
            "amount_typed": "1",
            "amount_idr": 1_000,
            "spend_description": f"current {index}",
            "spent_on": "2026-10-07",
            "kind": "buy",
            "by_id": "m1",
            "by_name": "Wayan",
            "created_at": f"2026-10-07T0{index}:00:00Z",
            "sheet_synced": False,
            "sheet_protocol": grocery._SHEET_PROTOCOL,
        }
        for index in range(1, 4)
    ]
    pushed: list[str] = []
    clock = iter([0.0, 0.0, 0.1, 0.1, 7.0])

    async def append_current(spend):
        pushed.append(spend.id)
        return "synced"

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: rows)
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_push_to_sheet_status", append_current)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda updates, **_kwargs: set(updates),
    )
    monkeypatch.setattr(
        grocery, "_current_sheet_retry_batch", lambda selected, *_args, **_kwargs: selected
    )
    monkeypatch.setattr(grocery, "_monotonic", lambda: next(clock))

    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert result.attempted == 1
    assert result.synced == 1
    assert pushed == [rows[0]["id"]]


def test_current_resync_reserves_receipt_budget_and_advances_legacy(monkeypatch):
    legacy = _pending_grocery_node(
        "spend-legacy-receipt-reserve",
        "legacy reserve",
        "2026-10-07T01:00:00Z",
    )
    current = {
        **legacy,
        "id": "spend-current-receipt-reserve",
        "spend_description": "current reserve",
        "created_at": "2026-10-07T02:00:00Z",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    reconciled: list[str] = []

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    _configure_receipt_reserve_test(monkeypatch, legacy, current, reconciled)
    clock = iter([0.0, 4.1])
    monkeypatch.setattr(grocery, "_monotonic", lambda: next(clock))

    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )

    assert result.attempted == 0
    assert result.synced == 0
    assert result.blocked_legacy == 0
    assert reconciled == [legacy["id"], current["id"]]


def test_current_resync_bounds_and_joins_receipt_write(monkeypatch):
    current = {
        "id": "spend-current-slow-receipt",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "slow receipt",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    completed = threading.Event()
    received_deadlines: list[float] = []
    received_remaining: list[float] = []

    async def append_current(_spend):
        return "synced"

    def slow_receipt(updates, **kwargs):
        assert set(updates) == {current["id"]}
        received_deadlines.append(kwargs["_deadline"])
        received_remaining.append(kwargs["_deadline"] - grocery.time.monotonic())
        grocery.time.sleep(0.05)
        completed.set()
        return set(updates)

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [current])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_push_to_sheet_status", append_current)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        slow_receipt,
    )
    monkeypatch.setattr(
        grocery, "_current_sheet_retry_batch", lambda selected, *_args, **_kwargs: selected
    )
    monkeypatch.setattr(grocery, "_SHEET_WRITE_TOTAL_TIMEOUT", 0.005)
    monkeypatch.setattr(grocery, "_SHEET_RECEIPT_MIN_TIMEOUT", 0.001)
    monkeypatch.setattr(grocery, "_SHEET_RESYNC_TOTAL_TIMEOUT", 0.01)

    started = grocery.time.monotonic()
    result = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    elapsed = grocery.time.monotonic() - started

    assert result.attempted == 1
    assert result.synced == 0
    assert completed.is_set()
    assert elapsed >= 0.04
    assert len(received_deadlines) == 1
    assert received_deadlines[0] > started
    assert received_remaining[0] <= grocery._SHEET_RESYNC_TOTAL_TIMEOUT


def test_mixed_resync_advances_current_before_legacy(monkeypatch):
    legacy = {
        "id": "spend-legacy-mixed",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "legacy",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
    }
    current = {
        **legacy,
        "id": "spend-current-mixed",
        "spend_description": "current",
        "created_at": "2026-10-07T02:00:00Z",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    pushed: list[str] = []

    async def reconcile(pending_ids, *, legacy_entries):
        assert pending_ids == [legacy["id"]]
        assert [entry.id for entry in legacy_entries] == [legacy["id"]]
        return grocery._SheetSnapshot(
            2_000_000,
            frozenset({legacy["id"]}),
            frozenset(),
        )

    async def append_current(spend):
        pushed.append(spend.id)
        return "synced"

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy, current])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", reconcile)
    monkeypatch.setattr(grocery, "_push_to_sheet_status", append_current)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda updates, **_kwargs: set(updates),
    )

    append = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert append.attempted == 1
    assert append.synced == 1
    assert append.blocked_legacy == 1
    assert pushed == [current["id"]]

    migration = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert migration.attempted == 0
    assert migration.synced == 0
    assert migration.blocked_legacy == 0
    assert pushed == [current["id"]]


def test_cancelled_current_row_does_not_starve_legacy_reconciliation(monkeypatch):
    legacy = {
        "id": "spend-legacy-after-cancel",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "legacy",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
    }
    current = {
        **legacy,
        "id": "spend-current-cancelled",
        "spend_description": "cancelled current",
        "created_at": "2026-10-07T02:00:00Z",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    reconciled: list[str] = []

    async def cancelled(_spend):
        return "cancelled"

    async def reconcile(pending_nodes, _pending, **_kwargs):
        reconciled.extend(node["id"] for node in pending_nodes)
        legacy["sheet_synced"] = True
        legacy["sheet_protocol"] = grocery._SHEET_PROTOCOL
        return grocery._SheetSnapshot(2_000_000, frozenset(), frozenset())

    def persist_marker(updates, **_kwargs):
        assert set(updates) == {current["id"]}
        return set(updates)

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy, current])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_push_to_sheet_status", cancelled)
    monkeypatch.setattr(grocery, "_reconciled_sheet_snapshot", reconcile)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        persist_marker,
    )

    first = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert first.attempted == 1
    assert first.synced == 0
    assert first.blocked_legacy == 1
    assert current["sheet_cancelled"] is True
    assert reconciled == []

    second = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert second.attempted == 0
    assert second.synced == 0
    assert second.blocked_legacy == 0
    assert reconciled == [legacy["id"]]


def test_unavailable_current_row_defers_to_legacy_reconciliation(monkeypatch):
    legacy = {
        "id": "spend-legacy-after-current-failure",
        "type": grocery._SPEND_TYPE,
        "amount_typed": "1",
        "amount_idr": 1_000,
        "spend_description": "legacy",
        "spent_on": "2026-10-07",
        "kind": "buy",
        "by_id": "m1",
        "by_name": "Wayan",
        "created_at": "2026-10-07T01:00:00Z",
        "sheet_synced": False,
    }
    current = {
        **legacy,
        "id": "spend-current-unavailable",
        "spend_description": "unavailable current",
        "created_at": "2026-10-07T02:00:00Z",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    reconciled: list[str] = []

    async def unavailable(_spend):
        return "unavailable"

    async def reconcile(pending_nodes, _pending, **_kwargs):
        reconciled.extend(node["id"] for node in pending_nodes)
        legacy["sheet_synced"] = True
        legacy["sheet_protocol"] = grocery._SHEET_PROTOCOL
        return grocery._SheetSnapshot(2_000_000, frozenset(), frozenset())

    def persist_retry(updates, **_kwargs):
        assert set(updates) == {current["id"]}
        return set(updates)

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: [legacy, current])
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_push_to_sheet_status", unavailable)
    monkeypatch.setattr(grocery, "_reconciled_sheet_snapshot", reconcile)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        persist_retry,
    )

    first = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert first.attempted == 1
    assert first.synced == 0
    assert first.blocked_legacy == 1
    assert current["sheet_append_retry_after"] > grocery._now()
    assert current["sheet_append_yield_legacy"] is True
    assert reconciled == []

    # Even when a manually spaced retry arrives after the time window, the
    # persisted yield signal lets legacy work advance before this row retries.
    current["sheet_append_retry_after"] = "2026-10-07T00:00:00+00:00"
    second = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert second.attempted == 0
    assert second.synced == 0
    assert second.blocked_legacy == 0
    assert legacy["id"] in reconciled


def test_legacy_reconciliation_advances_in_bounded_batches(monkeypatch):
    legacy = [
        {
            "id": f"spend-legacy-{index:03d}",
            "type": grocery._SPEND_TYPE,
            "amount_typed": "1",
            "amount_idr": 1_000,
            "spend_description": f"legacy {index}",
            "spent_on": "2026-09-10",
            "kind": "buy",
            "by_id": "m1",
            "by_name": "Wayan",
            "created_at": f"2026-09-10T01:{index % 60:02d}:00Z",
            "sheet_synced": False,
        }
        for index in range(101)
    ]
    updates: list[str] = []
    batches: list[list[str]] = []

    async def reconcile_batch(pending_ids, *, legacy_entries):
        assert len(pending_ids) == 101
        assert len(legacy_entries) == 100
        batch = [entry.id for entry in legacy_entries]
        batches.append(batch)
        return grocery._SheetSnapshot(
            2_000_000,
            (
                frozenset()
                if len(batches) == 1
                else frozenset({"spend-legacy-100"})
            ),
            frozenset(),
        )

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(grocery, "_all_spends", lambda: legacy)
    monkeypatch.setattr(
        grocery, "_sheet_webhook", lambda: ("https://example.invalid/exec", "secret")
    )
    monkeypatch.setattr(grocery, "_read_sheet_snapshot", reconcile_batch)
    monkeypatch.setattr(
        grocery.graph_service,
        "update_node_properties_batch",
        lambda batch, **_kwargs: (updates.extend(batch) or set(batch)),
    )

    first = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert first.blocked_legacy == 101
    assert "spend-legacy-100" not in batches[0]
    assert all(not node.get("sheet_synced") for node in legacy)

    second = asyncio.run(
        grocery.resync_sheet(grocery.ResyncBody(actor_token="resident-token"))
    )
    assert second.blocked_legacy == 100
    assert "spend-legacy-100" in batches[1]
    assert legacy[100]["sheet_synced"] is True
    assert len(updates) == 200


def test_legacy_reconciliation_excludes_all_duplicate_graph_signatures():
    nodes = [
        {
            "id": "spend-duplicate-a",
            "sheet_synced": False,
        },
        {
            "id": "spend-duplicate-b",
            "sheet_synced": False,
        },
        {
            "id": "spend-unique",
            "sheet_synced": False,
        },
    ]
    spends = [
        grocery.SpendResponse(
            id="spend-duplicate-a", amount_typed="10", amount_idr=10_000,
            description="vegetables", spent_on="2026-09-10",
            by_id="m1", by_name="Wayan", created_at="2026-09-10T01:00:00Z",
        ),
        grocery.SpendResponse(
            id="spend-duplicate-b", amount_typed="10", amount_idr=10_000,
            description=" vegetables ", spent_on="2026-09-10",
            by_id="m1", by_name="Wayan", created_at="2026-09-10T02:00:00Z",
        ),
        grocery.SpendResponse(
            id="spend-unique", amount_typed="20", amount_idr=20_000,
            description="fruit", spent_on="2026-09-10",
            by_id="m1", by_name="Wayan", created_at="2026-09-10T03:00:00Z",
        ),
    ]
    synced_pre_protocol_duplicate = grocery.SpendResponse(
        id="spend-synced-duplicate", amount_typed="10", amount_idr=10_000,
        description="vegetables", spent_on="2026-09-10",
        by_id="m1", by_name="Wayan", created_at="2026-09-09T01:00:00Z",
    )
    all_nodes = [
        {"id": "spend-synced-duplicate", "sheet_synced": True},
        *nodes,
    ]

    batch = grocery._legacy_reconciliation_batch(
        nodes,
        spends,
        all_nodes=all_nodes,
        all_entries=[synced_pre_protocol_duplicate, *spends],
    )
    assert [spend.id for _node, spend in batch] == ["spend-unique"]


def test_legacy_policy_wire_excludes_synced_history(monkeypatch):
    pending_node = {"id": "spend-pending-only", "sheet_synced": False}
    pending = grocery.SpendResponse(
        id=pending_node["id"], amount_typed="20", amount_idr=20_000,
        description="fruit", spent_on="2026-09-10",
        by_id="m1", by_name="Wayan", created_at="2026-09-10T03:00:00Z",
    )
    synced_nodes = [
        {"id": f"spend-synced-{index}", "sheet_synced": True}
        for index in range(2_000)
    ]
    synced_spends = [
        pending.model_copy(update={"id": node["id"], "description": node["id"]})
        for node in synced_nodes
    ]

    def select(_recipe, *, bindings, **_kwargs):
        assert bindings["entries_wire"].count(";") == 0
        assert "spend-pending-only" in bindings["entries_wire"]
        return [0], "fkwu"

    monkeypatch.setattr(grocery, "serve_via_kernel", select)
    batch = grocery._legacy_reconciliation_batch(
        [pending_node],
        [pending],
        all_nodes=[*synced_nodes, pending_node],
        all_entries=[*synced_spends, pending],
    )

    assert [spend.id for _node, spend in batch] == [pending.id]


def test_legacy_reconciliation_rejects_misaligned_carrier_rows():
    spend = grocery.SpendResponse(
        id="spend-misaligned", amount_typed="1", amount_idr=1_000,
        description="rice", spent_on="2026-10-07",
        by_id="m1", by_name="Wayan", created_at="2026-10-07T01:00:00Z",
    )

    with pytest.raises(RuntimeError, match="pending.*misaligned"):
        grocery._legacy_reconciliation_batch(
            [], [spend], all_nodes=[], all_entries=[]
        )


def test_large_legacy_backlog_keeps_only_the_next_hundred_candidates():
    nodes = [
        {"id": f"spend-large-{index:04d}", "sheet_synced": False}
        for index in range(2_001)
    ]
    spends = [
        grocery.SpendResponse(
            id=node["id"], amount_typed="1", amount_idr=1_000,
            description=f"item {index}", spent_on="2026-10-07",
            by_id="m1", by_name="Wayan", created_at="2026-10-07T01:00:00Z",
        )
        for index, node in enumerate(nodes)
    ]

    batch = grocery._legacy_reconciliation_batch(
        nodes,
        spends,
        all_nodes=nodes,
        all_entries=spends,
    )

    assert [spend.id for _node, spend in batch] == [
        f"spend-large-{index:04d}" for index in range(100)
    ]


def test_a_wrong_number_can_be_taken_back(client, monkeypatch):
    async def not_appended(_spend):
        return False

    async def reconcile_without_entry(_node, _actor):
        return False

    monkeypatch.setattr(grocery, "_push_to_sheet", not_appended)
    monkeypatch.setattr(grocery, "_reconcile_sheet_delete", reconcile_without_entry)
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
    assert gone.json()["was_mirrored"] is False

    remaining = client.get(f"/api/grocery/spend?token={token}").json()
    assert all(r["id"] != spend_id for r in remaining)

    # Gone means gone.
    assert client.delete(f"/api/grocery/spend/{spend_id}?actor_token={token}").status_code == 404


def test_delete_shares_one_deadline_with_the_database_commit(monkeypatch):
    node = {
        "id": "spend-bounded-delete",
        "type": grocery._SPEND_TYPE,
        "by_id": "m1",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }
    observed: list[tuple[str, bool, float]] = []

    async def reconciled(_node, _actor):
        return True

    def bounded_delete(node_id, *, _include_private, _deadline):
        observed.append((node_id, _include_private, _deadline))
        return True

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(
        grocery.graph_service, "get_node_unfiltered", lambda _node_id: node
    )
    monkeypatch.setattr(grocery, "_reconcile_sheet_delete", reconciled)
    monkeypatch.setattr(grocery.graph_service, "delete_node", bounded_delete)
    monkeypatch.setattr(grocery, "_monotonic", lambda: 100.0)

    result = asyncio.run(
        grocery.delete_spend("spend-bounded-delete", actor_token="writer-token")
    )

    assert result.was_mirrored is True
    assert observed == [
        ("spend-bounded-delete", True, 100.0 + grocery._GROCERY_REQUEST_TOTAL_TIMEOUT)
    ]


def test_delete_returns_success_when_commit_wins_the_timeout_boundary(monkeypatch):
    node = {
        "id": "spend-boundary-delete",
        "type": grocery._SPEND_TYPE,
        "by_id": "m1",
        "sheet_protocol": grocery._SHEET_PROTOCOL,
    }

    async def reconciled(_node, _actor):
        return True

    def committed(*_args, **_kwargs):
        return True

    async def boundary_timeout(_future, *, timeout):
        assert timeout == grocery._GROCERY_REQUEST_TOTAL_TIMEOUT
        raise asyncio.TimeoutError

    monkeypatch.setattr(grocery, "_require_writer", lambda _token: {"id": "m1"})
    monkeypatch.setattr(
        grocery.graph_service, "get_node_unfiltered", lambda _node_id: node
    )
    monkeypatch.setattr(grocery, "_reconcile_sheet_delete", reconciled)
    monkeypatch.setattr(grocery.graph_service, "delete_node", committed)
    monkeypatch.setattr(grocery, "_monotonic", lambda: 100.0)
    monkeypatch.setattr(grocery.asyncio, "wait_for", boundary_timeout)

    result = asyncio.run(
        grocery.delete_spend("spend-boundary-delete", actor_token="writer-token")
    )

    assert result.deleted == "spend-boundary-delete"


def test_delete_preserves_the_entry_while_sheet_state_is_unavailable(
    client, monkeypatch
):
    async def not_appended(_spend):
        return False

    async def unavailable(_node, _actor):
        return None

    monkeypatch.setattr(grocery, "_push_to_sheet", not_appended)
    monkeypatch.setattr(grocery, "_reconcile_sheet_delete", unavailable)
    resident = client.post("/api/household/bootstrap", json={"name": "Retry keeper"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]
    spend_id = client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "42", "category": "vegetable"},
    ).json()["id"]

    deleted = client.delete(f"/api/grocery/spend/{spend_id}?actor_token={token}")
    assert deleted.status_code == 503
    assert grocery.graph_service.get_node_unfiltered(spend_id) is not None


def _grocery_privacy_graph(client, monkeypatch) -> tuple[str, str, str, str]:
    async def not_appended(_spend):
        return False

    monkeypatch.setattr(grocery, "_push_to_sheet", not_appended)
    resident = client.post("/api/household/bootstrap", json={"name": "Boundary keeper"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]
    spend_id = client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "42", "category": "vegetable"},
    ).json()["id"]
    public_id = "contributor:grocery-boundary-public"
    other_id = "asset:grocery-boundary-other"
    grocery.graph_service.create_node(
        id=public_id, type="contributor", name="Public boundary witness"
    )
    grocery.graph_service.create_node(
        id=other_id, type="asset", name="Other boundary witness"
    )
    first_edge = grocery.graph_service.create_edge(
        from_id=public_id,
        to_id=spend_id,
        type="depends-on",
        _include_private=True,
    )
    grocery.graph_service.create_edge(
        from_id=spend_id,
        to_id=other_id,
        type="depends-on",
        _include_private=True,
    )
    return spend_id, public_id, other_id, first_edge["id"]


def test_generic_graph_access_cannot_bypass_grocery_privacy_or_reconciliation(
    client, monkeypatch
):
    spend_id, public_id, other_id, edge_id = _grocery_privacy_graph(
        client, monkeypatch
    )

    patched = client.patch(
        f"/api/graph/nodes/{spend_id}",
        json={"properties": {"sheet_synced": True}},
    )
    deleted = client.delete(f"/api/graph/nodes/{spend_id}")
    listed = client.get("/api/graph/nodes?type=grocery_spend")
    fetched = client.get(f"/api/graph/nodes/{spend_id}")
    revisions = client.get(f"/api/graph/nodes/{spend_id}/revisions")
    generic = client.get("/api/graph/nodes?limit=500")
    edges = client.get(f"/api/graph/nodes/{spend_id}/edges")
    neighbors = client.get(f"/api/graph/nodes/{spend_id}/neighbors")
    subgraph = client.get(f"/api/graph/nodes/{spend_id}/subgraph")
    private_path = client.get(
        f"/api/graph/path?from_id={spend_id}&to_id={other_id}&max_depth=2"
    )
    count = client.get("/api/graph/nodes/count?type=grocery_spend")
    stats = client.get("/api/graph/stats")
    proof = client.get("/api/graph/proof")
    profile = client.get(f"/api/profile/{spend_id}")
    verify = client.get(f"/api/profile/{spend_id}/verify?hash=not-a-real-hash")
    sign = client.post(f"/api/profile/{spend_id}/sign")
    resonant = client.get(f"/api/profile/{spend_id}/resonant")
    resonance = client.post("/api/resonance", json={"a": spend_id, "b": other_id})
    zoom = client.get(f"/api/graph/zoom/{spend_id}")
    edge_create = client.post(
        "/api/edges",
        json={"from_id": spend_id, "to_id": other_id, "type": "depends-on"},
    )
    duplicate_create = client.post(
        "/api/graph/nodes",
        json={
            "id": spend_id,
            "type": "concept",
            "name": "Attempted duplicate",
        },
    )
    meeting_capture = client.post(
        "/api/meetings/captures",
        json={
            "meeting_id": spend_id,
            "title": "Attempted private overwrite",
            "participants": [
                {"id": public_id, "name": "Boundary witness", "kind": "person"}
            ],
            "concept_resonances": [
                {
                    "participant_id": public_id,
                    "concept_id": "concept-grocery-private-guard",
                    "concept_part_id": "guard",
                    "resonance": "boundary",
                    "strength": 1.0,
                }
            ],
        },
    )
    private_concept_capture = client.post(
        "/api/meetings/captures",
        json={
            "meeting_id": "meeting:grocery-private-concept-guard",
            "title": "Attempted private concept edge",
            "participants": [
                {"id": public_id, "name": "Boundary witness", "kind": "person"}
            ],
            "concept_resonances": [
                {
                    "participant_id": public_id,
                    "concept_id": spend_id,
                    "concept_part_id": "guard",
                    "resonance": "boundary",
                    "strength": 1.0,
                }
            ],
        },
    )
    private_participant_capture = client.post(
        "/api/meetings/captures",
        json={
            "meeting_id": "meeting:grocery-private-participant-guard",
            "title": "Attempted private participant overwrite",
            "participants": [
                {"id": spend_id, "name": "Attempted rename", "kind": "person"}
            ],
            "concept_resonances": [
                {
                    "participant_id": spend_id,
                    "concept_id": "concept-grocery-private-guard",
                    "concept_part_id": "guard",
                    "resonance": "boundary",
                    "strength": 1.0,
                }
            ],
        },
    )
    forged_meeting_id = "meeting:grocery-private-read-guard"
    grocery.graph_service.create_node(
        id=forged_meeting_id,
        type="event",
        name="Forged public meeting",
        properties={
            "meeting_capture": True,
            "participants": [
                {"id": spend_id, "name": "Forged participant", "kind": "person"}
            ],
            "concept_resonances": [
                {
                    "participant_id": spend_id,
                    "concept_id": spend_id,
                    "concept_part_id": "forged",
                    "concept_part_node_id": spend_id,
                    "concept_part_label": "Forged part",
                    "resonance": "forged",
                    "strength": 1.0,
                }
            ],
        },
    )
    forged_recall = client.get(
        "/api/meetings/resonance", params={"meeting_id": forged_meeting_id}
    )
    edge_patch = client.patch(f"/api/edges/{edge_id}", json={"strength": 0.4})
    edge_delete = client.delete(f"/api/edges/{edge_id}")
    graph_edge_delete = client.delete(f"/api/graph/edges/{edge_id}")
    assert patched.status_code == 403
    assert deleted.status_code == 403
    assert listed.status_code == 403
    assert fetched.status_code == 403
    assert revisions.status_code == 403
    assert edges.status_code == 403
    assert neighbors.status_code == 403
    assert subgraph.status_code == 403
    assert private_path.status_code == 403
    assert count.status_code == 403
    assert profile.status_code == 403
    assert verify.status_code == 403
    assert sign.status_code == 403
    assert resonant.status_code == 403
    assert resonance.status_code == 403
    assert zoom.status_code == 404
    assert edge_create.status_code == 404
    assert duplicate_create.status_code == 422
    assert duplicate_create.json() == {
        "detail": "node id is owned by a dedicated private service"
    }
    assert meeting_capture.status_code == 400
    assert meeting_capture.json() == {
        "detail": "node id is owned by a dedicated private service"
    }
    assert private_concept_capture.status_code == 400
    assert private_concept_capture.json() == {
        "detail": "edge endpoint is owned by a dedicated private service"
    }
    assert private_participant_capture.status_code == 400
    assert private_participant_capture.json() == {
        "detail": "node id is owned by a dedicated private service"
    }
    assert forged_recall.status_code == 200
    assert forged_recall.json()["items"] == []
    assert edge_patch.status_code == 404
    assert edge_delete.status_code == 404
    assert graph_edge_delete.status_code == 404
    assert grocery.graph_service.get_edge_by_id(edge_id) is None
    assert grocery.graph_service.get_edge_by_id(
        edge_id, exclude_node_types=None
    ) is not None
    assert spend_id not in {node["id"] for node in generic.json()["items"]}
    assert "grocery_spend" not in stats.json()["nodes_by_type"]
    assert "grocery_spend" not in proof.json()["nodes_by_type"]
    assert grocery.graph_service.get_node(spend_id) is None
    assert grocery.graph_service.get_node_unfiltered(spend_id) is not None
    with pytest.raises(ValueError, match="dedicated private service"):
        grocery.graph_service.create_node(
            id="grocery-private-generic-create-denied",
            type="grocery_spend",
            name="Denied generic private create",
        )
    assert grocery.graph_service.update_node(
        spend_id, properties={"sheet_synced": True}
    ) is None
    assert grocery.graph_service.update_node_properties_batch(
        {spend_id: {"batch_probe": "blocked"}}
    ) == set()
    assert grocery.graph_service.update_node_properties_batch(
        {
            spend_id: {"batch_probe": "private"},
            public_id: {"batch_probe": "public"},
        },
        _include_private=True,
        _source="grocery-batch-test",
        _timeout_seconds=0.1,
    ) == {spend_id, public_id}
    assert (
        grocery.graph_service.get_node_unfiltered(spend_id)["batch_probe"]
        == "private"
    )
    assert grocery.graph_service.get_node(public_id)["batch_probe"] == "public"
    assert grocery.graph_service.delete_node(spend_id) is False
    with pytest.raises(ValueError, match="dedicated private service"):
        grocery.graph_service.create_edge(
            from_id=spend_id,
            to_id=other_id,
            type="depends-on",
        )


def test_generic_graph_traversals_prune_private_grocery_cells(client, monkeypatch):
    spend_id, public_id, other_id, edge_id = _grocery_privacy_graph(
        client, monkeypatch
    )
    concept_id = "concept-grocery-boundary-public"
    grocery.graph_service.create_node(
        id=concept_id, type="concept", name="Public concept boundary witness"
    )
    grocery.graph_service.create_edge(
        from_id=concept_id,
        to_id=spend_id,
        type="depends-on",
        _include_private=True,
    )
    grocery.graph_service.create_edge(
        from_id=public_id,
        to_id=spend_id,
        type="contribution",
        properties={"contribution_id": "00000000-0000-0000-0000-000000000042"},
        _include_private=True,
    )

    public_edges = client.get(f"/api/graph/nodes/{public_id}/edges")
    public_neighbors = client.get(f"/api/graph/nodes/{public_id}/neighbors")
    public_subgraph = client.get(f"/api/graph/nodes/{public_id}/subgraph?depth=2")
    path = client.get(
        f"/api/graph/path?from_id={public_id}&to_id={other_id}&max_depth=2"
    )
    flow = client.get("/api/flow/render")
    edges = client.get("/api/edges?limit=500")
    edge = client.get(f"/api/edges/{edge_id}")
    public_entity_edges = client.get(f"/api/entities/{public_id}/edges")
    public_entity_neighbors = client.get(f"/api/entities/{public_id}/neighbors")
    public_profile = client.get(f"/api/profile/{public_id}")
    public_zoom = client.get(f"/api/graph/zoom/{public_id}?depth=2")
    concept_edges = client.get(f"/api/concepts/{concept_id}/edges")
    contributions = client.get("/api/contributions")
    inventory_flow = client.get("/api/inventory/flow?contribution_limit=100")

    assert public_edges.json() == []
    assert public_neighbors.json() == []
    assert spend_id not in {node["id"] for node in public_subgraph.json()["nodes"]}
    assert all(
        spend_id not in (edge["from_id"], edge["to_id"])
        for edge in public_subgraph.json()["edges"]
    )
    assert path.json()["path"] is None
    assert spend_id not in {node["id"] for node in flow.json()["nodes"]}
    assert all(
        spend_id not in (item["from_id"], item["to_id"])
        for item in edges.json()["items"]
    )
    assert edge.status_code == 404
    assert public_entity_edges.json()["items"] == []
    assert public_entity_neighbors.json()["neighbors"] == []
    assert public_profile.status_code == 200
    assert public_zoom.status_code == 200
    assert spend_id not in public_zoom.text
    assert concept_edges.status_code == 200
    assert concept_edges.json() == []
    assert contributions.status_code == 200
    assert spend_id not in contributions.text
    assert grocery.graph_service.get_edge_by_property(
        edge_type="contribution",
        property_name="contribution_id",
        property_value="00000000-0000-0000-0000-000000000042",
    ) is None
    assert inventory_flow.status_code == 200
    assert spend_id not in inventory_flow.text
    assert spend_id not in {
        item["dimension"] for item in public_profile.json()["top"]
    }


def test_a_mirrored_deletion_is_reconciled_by_one_idempotent_reversal(
    client, monkeypatch
):
    reconciled: list[tuple[str, str]] = []
    allow_delete = False

    async def fake_push(spend):
        # Simulate the append/flag crash seam: the Sheet received this row,
        # but the app never committed sheet_synced=True.
        return False

    async def fake_reconcile(node, actor):
        reversal = grocery._reversal_spend(node, actor)
        reconciled.append((node["id"], reversal.id))
        return True if allow_delete else None

    monkeypatch.setattr(grocery, "_push_to_sheet", fake_push)
    monkeypatch.setattr(grocery, "_reconcile_sheet_delete", fake_reconcile)
    resident = client.post("/api/household/bootstrap", json={"name": "Undo keeper"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    created = client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "100", "category": "vegetable"},
    )
    assert created.status_code == 200, created.text
    spend_id = created.json()["id"]
    assert created.json()["sheet_synced"] is False

    # A carrier failure preserves the visible row. There is no tombstone and
    # no chance to strand the already-started Sheet append.
    deleted = client.delete(
        f"/api/grocery/spend/{spend_id}?actor_token={token}"
    )
    assert deleted.status_code == 503, deleted.text
    assert grocery.graph_service.get_node_unfiltered(spend_id) is not None

    # Retrying carries exactly the same deterministic IDs through one atomic
    # carrier operation and only then physically removes the graph row.
    allow_delete = True
    deleted = client.delete(f"/api/grocery/spend/{spend_id}?actor_token={token}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["was_mirrored"] is True
    reversal_id = f"reversal-{spend_id}"
    assert reconciled == [
        (spend_id, reversal_id),
        (spend_id, reversal_id),
    ]

    # Gone means physically gone: unauthenticated generic graph reads cannot
    # expose a supposedly private tombstone.
    visible = client.get(f"/api/grocery/spend?token={token}").json()
    assert all(row["id"] != spend_id for row in visible)
    assert grocery.graph_service.get_node_unfiltered(spend_id) is None


def test_someone_else_s_entry_is_not_yours_to_delete(client, monkeypatch):
    async def not_appended(_spend):
        return False

    async def reconcile_without_entry(_node, _actor):
        return False

    monkeypatch.setattr(grocery, "_push_to_sheet", not_appended)
    monkeypatch.setattr(grocery, "_reconcile_sheet_delete", reconcile_without_entry)
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


def test_topping_up_the_float_and_what_is_left(client, monkeypatch):
    async def empty_sheet_snapshot(_pending_ids):
        return grocery._SheetSnapshot(0, frozenset(), frozenset())

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", empty_sheet_snapshot)
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


def test_remaining_balance_is_unavailable_when_sheet_baseline_is_unknown(
    client, monkeypatch
):
    resident = client.post("/api/household/bootstrap", json={"name": "Sisa witness"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]

    client.post(
        "/api/grocery/spend",
        json={"actor_token": token, "amount": "100", "category": "vegetable"},
    )

    async def unavailable(_pending_ids):
        return None

    monkeypatch.setattr(grocery, "_read_sheet_snapshot", unavailable)
    totals = client.get(f"/api/grocery/totals?token={token}")
    assert totals.status_code == 200, totals.text
    assert totals.json()["remaining_idr"] is None
    assert totals.json()["remaining_source"] == "unavailable"


def test_a_top_up_of_zero_is_refused(client):
    resident = client.post("/api/household/bootstrap", json={"name": "Wayan2"})
    if resident.status_code == 409:
        pytest.skip("a resident already exists in this graph; bootstrap-dependent flow skipped")
    token = resident.json()["token"]
    assert client.post("/api/grocery/topup", json={"actor_token": token, "amount": "0"}).status_code == 422


def test_sheet_carrier_binds_to_the_restructured_tab_identity():
    carrier = _SHEET_SETUP.read_text(encoding="utf-8")

    assert 'const LEDGER_SHEET_ID_PROPERTY = "GROCERY_LEDGER_SHEET_ID";' in carrier
    assert "String(sheet.getSheetId())" in carrier
    assert "const sheet = ledgerSheet(ss);" in carrier
    assert "if (candidates.length !== 1)" in carrier
    assert "getName() !== STATE_SHEET_NAME;\n    })[0]" not in carrier
    assert "function reconcileLegacy(ss, sheet, hrow, entries)" in carrier
    assert 'if (body.action === "reconcile_legacy")' in carrier
    assert "if (matches.length === 1)" in carrier
    assert "signatureCounts.get(wantedSignature) !== 1" in carrier
    assert "if (pass === 1 && existingWhat)" not in carrier
    assert "const acknowledgedSet = new Set(rows.map(function (row)" in carrier
    assert "if (acknowledgedSet.has(entryId))" in carrier
    assert "acknowledgedSet.add(entryId);" in carrier
    assert "setValues(idValues);" in carrier
    assert "setValue(entryId);" not in carrier
    assert "const legacyOriginal = body.legacy_original || null;" in carrier
    assert "legacy original could not be uniquely tagged" in carrier
    assert "const historicalDeletionSignatures = new Set();" in carrier
    assert "acknowledgedSet.has(originalId)" in carrier
    assert "historicalDeletionSignatures.has(historicalDeletion)" in carrier
