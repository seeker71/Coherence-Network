"""Grocery — the shopping ledger for a Light Hub manager.

One number, one tap. The manager stands in the market, types what they
spent, and the entry lands with the date, the place, and a description
already filled in. Everything else is the app's job, not theirs.

**The amount is typed in thousands** — the Indonesian *ribu* habit. `123.5`
means Rp 123.500. The conversion is exact integer arithmetic on the Form
kernel (``endpoint_grocery_amount.fk``); nothing here rounds a float, so
`0.25` is Rp 250 and not Rp 249.99999.

**The description arrives before they type it.** Shops are place cells —
the same ``household_place`` tissue that already holds the grounds, with
``kind="shop"`` and a ``default_description``. When the phone's GPS lands
near a pinned shop, that shop's description is the entry's description.
When no shop is near (or GPS is off), a category icon carries the meaning
— fruit, vegetable, fish, spice — and a free-text field takes anything the
icons don't hold.

**The ledger is not a lock.** The graph holds the entries; Google Sheets is
a mirror, fed by a webhook URL the hub owns (an Apps Script bound to their
own sheet — see ``docs/grocery-sheets-setup.md``). If the webhook is unset
or failing, entries still record and carry ``sheet_synced=false`` until a
resync. ``GET /grocery/export.csv`` is the always-available door out, so
leaving this app costs nothing.

Identity is the household's: a device token that resolves to a member with
write access. Seeing the ledger is open to any registered cell here.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.routers.household import (
    _PLACE_TYPE,
    _all_places,
    _member_by_token,
    _node_to_place,
    _now,
    _place_distance,
    _require_member,
    _require_writer,
    _s,
    PlaceResponse,
)
from app import config_loader
from app.services import config_service, graph_service
from app.services.form_kernel_bridge import serve_via_kernel

router = APIRouter()

_SPEND_TYPE = "grocery_spend"
_KIND_BUY = "buy"        # money out — a market run
_KIND_TOPUP = "topup"    # money in — the float topped back up
_SHOP_KIND = "shop"
_CURRENCY = "IDR"

# Bali is UTC+8 with no DST — "today" for the manager standing in the market,
# not today in UTC. An entry made at 07:30 local must not file as yesterday.
_HUB_TZ = timezone(timedelta(hours=8))

# Icons carry the meaning when no shop is near. The key is stored; the emoji
# and the labels are what the manager sees. Kept small on purpose — a long
# list is a form to fill in, and a form is the thing this app exists to avoid.
_CATEGORIES: list[tuple[str, str, str, str]] = [
    # (key, emoji, english, indonesian)
    ("fruit", "🍎", "Fruit", "Buah"),
    ("vegetable", "🥬", "Vegetables", "Sayur"),
    ("fish", "🐟", "Fish", "Ikan"),
    ("meat", "🍗", "Meat", "Daging"),
    ("egg_dairy", "🥚", "Eggs & dairy", "Telur & susu"),
    ("rice_staple", "🍚", "Rice & staples", "Beras & pokok"),
    ("spice", "🌶️", "Spices", "Bumbu"),
    ("drink", "🥤", "Drinks", "Minuman"),
    ("gas_fuel", "🔥", "Gas & fuel", "Gas & bahan bakar"),
    ("household", "🧼", "Household", "Rumah tangga"),
    ("other", "🧺", "Other", "Lainnya"),
]
_CATEGORY_KEYS = {c[0] for c in _CATEGORIES}
_CATEGORY_LABEL = {c[0]: c[2] for c in _CATEGORIES}

# How close counts as "at this shop". Micro-degree Manhattan distance, the
# same unit household places pin in. 1500 ≈ 150m at Bali's latitude — near
# enough that the manager is at the market, far enough that a phone's GPS
# drift under a warung roof still lands.
_NEAR_MICRODEG = 1500


def _today_local() -> str:
    return datetime.now(_HUB_TZ).date().isoformat()


# --------------------------------------------------------------------------
# The amount — typed in thousands, held in whole rupiah.
# --------------------------------------------------------------------------


def _split_typed_amount(typed: str) -> tuple[int, int, int]:
    """Parse `"123.5"` into (whole, frac, fraclen) — never a float.

    The manager's thumb produces `123.5`, `123,5`, `1.2` or `85`. We keep
    the decimal as digits, not as a binary fraction, so the kernel can do
    exact integer arithmetic on it.
    """
    raw = (typed or "").strip().replace(",", ".").replace(" ", "")
    if not raw:
        raise HTTPException(status_code=422, detail="type an amount first")
    neg = raw.startswith("-")
    if neg:
        raise HTTPException(status_code=422, detail="an amount is not negative")
    if raw.count(".") > 1:
        raise HTTPException(status_code=422, detail=f"{typed!r} is not a number")
    whole_s, _, frac_s = raw.partition(".")
    whole_s = whole_s or "0"
    if not whole_s.isdigit() or (frac_s and not frac_s.isdigit()):
        raise HTTPException(status_code=422, detail=f"{typed!r} is not a number")
    # Beyond 3 decimals a "thousands" figure is below one rupiah — the digits
    # past that point are noise, and truncating is honest about the unit.
    frac_s = frac_s[:3]
    if len(whole_s) > 12:
        raise HTTPException(status_code=422, detail="that amount is too large")
    return int(whole_s), int(frac_s or 0), len(frac_s)


def _to_rupiah(typed: str) -> tuple[int, str]:
    """Thousands → whole rupiah, on the Form kernel. `123.5` → `123500`."""
    whole, frac, fraclen = _split_typed_amount(typed)
    value, runtime = serve_via_kernel(
        "endpoint_grocery_amount.fk",
        bindings={"whole": whole, "frac": frac, "fraclen": fraclen},
        parse=int,
    )
    return int(value), runtime


# --------------------------------------------------------------------------
# Shops — place cells with a default description, near-matched by GPS.
# --------------------------------------------------------------------------


class ShopResponse(PlaceResponse):
    default_description: str = ""


class ShopBody(BaseModel):
    actor_token: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    default_description: str = Field(min_length=1, max_length=200)
    lat: int | None = None   # micro-degrees, as the phone's GPS gives
    lon: int | None = None


def _node_to_shop(node: dict) -> ShopResponse:
    base = _node_to_place(node)
    return ShopResponse(
        **base.model_dump(),
        default_description=_s(node.get("default_description")) or base.name,
    )


def _all_shops() -> list[dict]:
    return [n for n in _all_places() if n.get("kind") == _SHOP_KIND]


@router.get(
    "/grocery/shops",
    response_model=list[ShopResponse],
    summary="Every stored shop, with the description it fills in",
)
async def list_shops(token: str | None = Query(default=None)) -> list[ShopResponse]:
    _require_member(token)
    shops = sorted(_all_shops(), key=lambda n: (n.get("name", "") or ""))
    return [_node_to_shop(n) for n in shops]


@router.post(
    "/grocery/shops",
    response_model=ShopResponse,
    summary="Remember this shop — name, default description, and where it stands",
)
async def save_shop(body: ShopBody) -> ShopResponse:
    _require_writer(body.actor_token)
    shop_id = f"place-shop-{uuid.uuid4().hex[:10]}"
    # `name` is not duplicated into properties: Node.to_dict() merges
    # properties over the top-level columns, so a copy here would freeze
    # the name at creation and outlive any later rename via PATCH.
    props: dict[str, Any] = {
        "kind": _SHOP_KIND,
        "default_description": body.default_description,
        "created_at": _now(),
    }
    if body.lat is not None and body.lon is not None:
        props["lat"] = int(body.lat)
        props["lon"] = int(body.lon)
    graph_service.create_node(
        id=shop_id,
        type=_PLACE_TYPE,
        name=body.name,
        description=body.default_description,
        properties=props,
    )
    node = graph_service.get_node(shop_id) or {"id": shop_id, **props}
    return _node_to_shop(node)


class ShopEdit(BaseModel):
    actor_token: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    default_description: str | None = Field(default=None, min_length=1, max_length=200)


@router.patch(
    "/grocery/shops/{shop_id}",
    response_model=ShopResponse,
    summary="Rename a stored shop, or change what it fills in — never a new place",
)
async def edit_shop(shop_id: str, body: ShopEdit) -> ShopResponse:
    _require_writer(body.actor_token)
    if body.name is None and body.default_description is None:
        raise HTTPException(status_code=400, detail="nothing to change")
    node = graph_service.get_node(shop_id)
    if not node or node.get("kind") != _SHOP_KIND:
        raise HTTPException(status_code=404, detail=f"shop {shop_id!r} not found")
    # Spends already recorded keep the description they were written with —
    # editing a shop only changes what the NEXT visit fills in, never what a
    # past entry says. `name` and `default_description` default to each
    # other so the two rarely drift back apart.
    new_name = body.name or node.get("name") or ""
    new_desc = body.default_description or new_name
    updates: dict[str, Any] = {"properties": {"default_description": new_desc}}
    if body.name is not None:
        updates["name"] = body.name
        updates["description"] = new_desc
        # A shop saved before this endpoint existed may carry a copy of its
        # name inside properties too, which Node.to_dict() would otherwise
        # let win over the column just updated above. Clearing it here heals
        # that node the first time it is ever edited, no migration needed.
        updates["properties"]["name"] = body.name
    graph_service.update_node(shop_id, **updates)
    node = graph_service.get_node(shop_id) or node
    return _node_to_shop(node)


class ShopDeleteResponse(BaseModel):
    deleted: str


@router.delete(
    "/grocery/shops/{shop_id}",
    response_model=ShopDeleteResponse,
    summary="Forget a stored shop — past entries keep what they already said",
)
async def forget_shop(
    shop_id: str,
    actor_token: str = Query(..., description="the device token of the recorder or a resident"),
) -> ShopDeleteResponse:
    _require_writer(actor_token)
    node = graph_service.get_node(shop_id)
    if not node or node.get("kind") != _SHOP_KIND:
        raise HTTPException(status_code=404, detail=f"shop {shop_id!r} not found")
    graph_service.delete_node(shop_id)
    return ShopDeleteResponse(deleted=shop_id)


@router.get(
    "/grocery/shops/nearest",
    response_model=ShopResponse | None,
    summary="The shop the manager is standing at, or null when none is near",
)
async def nearest_shop(
    lat: int = Query(...),
    lon: int = Query(...),
    token: str | None = Query(default=None),
) -> ShopResponse | None:
    _require_member(token)
    pinned = [
        n for n in _all_shops()
        if isinstance(n.get("lat"), (int, float)) and isinstance(n.get("lon"), (int, float))
    ]
    if not pinned:
        return None
    best = min(pinned, key=lambda n: _place_distance(lat, lon, int(n["lat"]), int(n["lon"])))
    # Nearest is only an answer when it is actually near. Otherwise the
    # icons carry the description instead of a shop 4km away.
    if _place_distance(lat, lon, int(best["lat"]), int(best["lon"])) > _NEAR_MICRODEG:
        return None
    return _node_to_shop(best)


# --------------------------------------------------------------------------
# Spends — the ledger.
# --------------------------------------------------------------------------


class SpendCreate(BaseModel):
    actor_token: str = Field(min_length=1)
    amount: str = Field(min_length=1, max_length=20)  # typed in thousands: "123.5"
    category: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=200)      # the custom field
    place_id: str | None = None                                  # a shop, when one was near
    lat: int | None = None                                       # or raw GPS, to resolve one
    lon: int | None = None
    spent_on: str | None = Field(default=None, max_length=10)    # ISO date; today when absent


class SpendResponse(BaseModel):
    id: str
    amount_typed: str          # what the thumb typed — "123.5"
    amount_idr: int            # what it means — 123500
    currency: str = _CURRENCY
    description: str           # shop default, or category label, or the note
    category: str | None = None
    note: str | None = None
    place_id: str | None = None
    place_name: str | None = None
    spent_on: str
    kind: str = "buy"          # "buy" — money out; "topup" — money added to the float
    by_id: str
    by_name: str
    created_at: str
    sheet_synced: bool = False
    runtime: str = ""          # which kernel carrier computed the amount


    @property
    def signed_idr(self) -> int:
        """Money out is positive, money in is negative — one column, one SUM."""
        return -self.amount_idr if self.kind == _KIND_TOPUP else self.amount_idr


class CategoryOut(BaseModel):
    key: str
    emoji: str
    en: str
    id: str


def _node_to_spend(node: dict) -> SpendResponse:
    return SpendResponse(
        id=node.get("id", ""),
        amount_typed=_s(node.get("amount_typed")) or "",
        amount_idr=int(node.get("amount_idr") or 0),
        currency=_s(node.get("currency")) or _CURRENCY,
        description=_s(node.get("spend_description")) or "",
        category=_s(node.get("category")),
        note=_s(node.get("note")),
        place_id=_s(node.get("place_id")),
        place_name=_s(node.get("place_name")),
        spent_on=_s(node.get("spent_on")) or "",
        kind=_s(node.get("kind")) or _KIND_BUY,
        by_id=_s(node.get("by_id")) or "",
        by_name=_s(node.get("by_name")) or "",
        created_at=_s(node.get("created_at")) or "",
        sheet_synced=bool(node.get("sheet_synced")),
        runtime=_s(node.get("runtime")) or "",
    )


def _all_spends() -> list[dict]:
    try:
        response = graph_service.list_nodes(type=_SPEND_TYPE, limit=2000)
        nodes = response.get("items", []) if isinstance(response, dict) else (response or [])
    except Exception:
        nodes = []
    return [n for n in nodes if n.get("type") == _SPEND_TYPE]


def _resolve_description(
    *, note: str | None, category: str | None, shop: dict | None
) -> str:
    """What this entry says it was — in the order the manager meant it.

    A typed note is the most specific thing anyone said, so it wins. The
    shop's stored description comes next: standing in the fish market is
    itself a statement. The category icon is the floor.
    """
    if note and note.strip():
        return note.strip()
    if shop is not None:
        stored = _s(shop.get("default_description"))
        if stored:
            return stored
        name = _s(shop.get("name"))
        if name:
            return name
    if category and category in _CATEGORY_LABEL:
        return _CATEGORY_LABEL[category]
    return "Groceries"


@router.get(
    "/grocery/categories",
    response_model=list[CategoryOut],
    summary="The icon set that carries a description when no shop is near",
)
async def list_categories() -> list[CategoryOut]:
    return [CategoryOut(key=k, emoji=e, en=en, id=idn) for k, e, en, idn in _CATEGORIES]


@router.post(
    "/grocery/spend",
    response_model=SpendResponse,
    summary="Record what was spent — one number, everything else filled in",
)
async def record_spend(body: SpendCreate) -> SpendResponse:
    actor = _require_writer(body.actor_token)

    if body.category is not None and body.category not in _CATEGORY_KEYS:
        raise HTTPException(status_code=422, detail=f"unknown category {body.category!r}")

    amount_idr, runtime = _to_rupiah(body.amount)
    if amount_idr <= 0:
        raise HTTPException(status_code=422, detail="an amount of zero is not a spend")

    # The place: an explicit shop, else the nearest pinned shop to the GPS.
    shop: dict | None = None
    if body.place_id:
        node = graph_service.get_node(body.place_id)
        if not node or node.get("type") != _PLACE_TYPE:
            raise HTTPException(status_code=404, detail=f"place {body.place_id!r} not found")
        shop = node
    elif body.lat is not None and body.lon is not None:
        near = await nearest_shop(lat=body.lat, lon=body.lon, token=body.actor_token)
        if near is not None:
            shop = graph_service.get_node(near.id)

    spent_on = (body.spent_on or "").strip() or _today_local()
    try:
        datetime.strptime(spent_on, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{spent_on!r} is not a date (YYYY-MM-DD)")

    description = _resolve_description(
        note=body.note, category=body.category, shop=shop
    )
    spend_id = f"spend-{uuid.uuid4().hex[:12]}"
    props: dict[str, Any] = {
        "amount_typed": (body.amount or "").strip(),
        "amount_idr": amount_idr,
        "currency": _CURRENCY,
        "spend_description": description,
        "category": body.category,
        "note": (body.note or "").strip() or None,
        "place_id": shop.get("id") if shop else None,
        "place_name": (_s(shop.get("name")) if shop else None),
        "spent_on": spent_on,
        "kind": _KIND_BUY,
        "by_id": actor.get("id", ""),
        "by_name": actor.get("name", ""),
        "created_at": _now(),
        "runtime": runtime,
        "sheet_synced": False,
    }
    graph_service.create_node(
        id=spend_id,
        type=_SPEND_TYPE,
        name=f"{_CURRENCY} {amount_idr:,} — {description}",
        description=description,
        properties=props,
    )
    node = graph_service.get_node(spend_id) or {"id": spend_id, **props}
    spend = _node_to_spend(node)

    # The mirror. A dark sheet never costs the manager their entry.
    if _push_to_sheet(spend):
        graph_service.update_node(spend_id, properties={"sheet_synced": True})
        spend.sheet_synced = True
    return spend


@router.get(
    "/grocery/spend",
    response_model=list[SpendResponse],
    summary="The ledger — newest first, optionally a single day",
)
async def list_spends(
    token: str | None = Query(default=None),
    on: str | None = Query(default=None, description="ISO date; a single day"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[SpendResponse]:
    _require_member(token)
    rows = _all_spends()
    if on:
        rows = [n for n in rows if _s(n.get("spent_on")) == on]
    rows.sort(key=lambda n: (_s(n.get("created_at")) or ""), reverse=True)
    return [_node_to_spend(n) for n in rows[:limit]]


class TopUpCreate(BaseModel):
    actor_token: str = Field(min_length=1)
    amount: str = Field(min_length=1, max_length=20)   # thousands, same as a buy
    note: str | None = Field(default=None, max_length=200)
    spent_on: str | None = Field(default=None, max_length=10)


@router.post(
    "/grocery/topup",
    response_model=SpendResponse,
    summary="Money added to the float — the other direction of the same ledger",
)
async def record_topup(body: TopUpCreate) -> SpendResponse:
    """A top-up is the same shape as a buy, pointing the other way.

    Keeping both in one cell type means "remaining" is a single sum rather
    than two tables that have to be reconciled — the thing the hub was doing
    by hand with negative rows.
    """
    actor = _require_writer(body.actor_token)
    amount_idr, runtime = _to_rupiah(body.amount)
    if amount_idr <= 0:
        raise HTTPException(status_code=422, detail="a top-up of zero is not a top-up")

    spent_on = (body.spent_on or "").strip() or _today_local()
    try:
        datetime.strptime(spent_on, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{spent_on!r} is not a date (YYYY-MM-DD)")

    note = (body.note or "").strip()
    topup_id = f"topup-{uuid.uuid4().hex[:12]}"
    props: dict[str, Any] = {
        "amount_typed": (body.amount or "").strip(),
        "amount_idr": amount_idr,
        "currency": _CURRENCY,
        "spend_description": note or "top up",
        "category": None,
        "note": note or None,
        "place_id": None,
        "place_name": None,
        "spent_on": spent_on,
        "kind": _KIND_TOPUP,
        "by_id": actor.get("id", ""),
        "by_name": actor.get("name", ""),
        "created_at": _now(),
        "runtime": runtime,
        "sheet_synced": False,
    }
    graph_service.create_node(
        id=topup_id, type=_SPEND_TYPE,
        name=f"top up {_CURRENCY} {amount_idr:,}",
        description=props["spend_description"], properties=props,
    )
    node = graph_service.get_node(topup_id) or {"id": topup_id, **props}
    topup = _node_to_spend(node)
    if _push_to_sheet(topup):
        graph_service.update_node(topup_id, properties={"sheet_synced": True})
        topup.sheet_synced = True
    return topup


class DeleteResponse(BaseModel):
    deleted: str
    was_mirrored: bool   # did the sheet already get this row?


@router.delete(
    "/grocery/spend/{spend_id}",
    response_model=DeleteResponse,
    summary="Remove an entry — a wrong number should be fixable by the person who typed it",
)
async def delete_spend(
    spend_id: str,
    actor_token: str = Query(..., description="the device token of the recorder or a resident"),
) -> DeleteResponse:
    actor = _require_writer(actor_token)
    node = graph_service.get_node(spend_id)
    if not node or node.get("type") != _SPEND_TYPE:
        raise HTTPException(status_code=404, detail=f"entry {spend_id!r} not found")
    # Your own mistake is yours to undo; a resident can fix anyone's.
    if node.get("by_id") != actor.get("id") and actor.get("role") != "resident":
        raise HTTPException(
            status_code=403, detail="only the person who recorded it, or a resident, can remove it"
        )
    mirrored = bool(node.get("sheet_synced"))
    graph_service.delete_node(spend_id)
    # The sheet is the hub's own document; we never reach in and edit rows we
    # already handed over. Saying so plainly is the honest half of undo.
    return DeleteResponse(deleted=spend_id, was_mirrored=mirrored)


class TotalsResponse(BaseModel):
    on: str
    currency: str = _CURRENCY
    day_total_idr: int
    day_count: int
    month_total_idr: int
    month_count: int
    remaining_idr: int = 0     # topped up minus spent — what is left to shop with


@router.get(
    "/grocery/totals",
    response_model=TotalsResponse,
    summary="What today and this month have cost so far",
)
async def totals(
    token: str | None = Query(default=None),
    on: str | None = Query(default=None),
) -> TotalsResponse:
    _require_member(token)
    day = (on or "").strip() or _today_local()
    month = day[:7]
    rows = _all_spends()
    buys = [n for n in rows if (_s(n.get("kind")) or _KIND_BUY) != _KIND_TOPUP]
    day_rows = [n for n in buys if _s(n.get("spent_on")) == day]
    month_rows = [n for n in buys if (_s(n.get("spent_on")) or "").startswith(month)]
    # One sum over the whole ledger, signed — the same number the sheet's
    # remaining cell computes, so the two can never quietly disagree.
    remaining = -sum(_node_to_spend(n).signed_idr for n in rows)
    return TotalsResponse(
        on=day,
        day_total_idr=sum(int(n.get("amount_idr") or 0) for n in day_rows),
        day_count=len(day_rows),
        month_total_idr=sum(int(n.get("amount_idr") or 0) for n in month_rows),
        month_count=len(month_rows),
        remaining_idr=remaining,
    )


# --------------------------------------------------------------------------
# The mirror — Google Sheets by webhook, CSV as the door out.
# --------------------------------------------------------------------------

# The hub's ledger, restructured so the app can just append: `When | Amount
# | What`, one row per event, newest at the bottom, nothing ever moved.
#
# `Amount` is signed — a purchase is positive, a top-up is negative — which
# is the convention the sheet already used for its settlement rows, so the
# existing numbers keep their meaning. The balance sits on top, above the
# header, as a formula in a fixed cell (`=-SUM(...)`), where a person looks
# first and where appending can never disturb it.
#
# The column names are the whole contract: the sheet's own script finds its
# header row by name and matches these columns to it, so the balance block
# above the log can change shape without breaking the write.
#
# `What` is the column that matters. In the ledger as we found it, all eight
# purchases had it empty. Filling it is the whole point of this app.
_SHEET_COLUMNS = ["When", "Amount", "What"]

# The door out stays lossless — everything the graph holds, not just the
# four columns the sheet shows.
_CSV_COLUMNS = [
    "date", "amount_typed", "amount_idr", "currency",
    "description", "category", "place", "by", "recorded_at", "id",
]


def _sheet_row(spend: SpendResponse) -> dict[str, Any]:
    """One appendable row: when, how much (signed), what it was.

    `Amount` goes as a plain integer, never "Rp385,000" — the column carries
    its own currency format, and text would break the sums the sheet
    computes beside it. A top-up is negative, so the remaining formula is a
    single SUM over one column.
    """
    return {
        "When": spend.spent_on,   # ISO; the script hands the sheet a real date
        "Amount": spend.signed_idr,
        "What": spend.description,
    }


def _csv_row(spend: SpendResponse) -> dict[str, Any]:
    return {
        "date": spend.spent_on,
        "amount_typed": spend.amount_typed,
        "amount_idr": spend.amount_idr,
        "currency": spend.currency,
        "description": spend.description,
        "category": spend.category or "",
        "place": spend.place_name or "",
        "by": spend.by_name,
        "recorded_at": spend.created_at,
        "id": spend.id,
    }


def _sheet_webhook() -> tuple[str, str]:
    """The hub's sheet door, from the keystore — `(url, secret)`.

    The URL *is* the credential (anyone holding it can append a row), so it
    lives beside the other keys in ``~/.coherence-network/keys.json`` under
    ``grocery_sheet``, read through the one config carrier. Nothing here
    reads the environment.
    """
    return (
        config_service.get_key("grocery_sheet", "webhook_url").strip(),
        config_service.get_key("grocery_sheet", "secret").strip(),
    )


def _sheet_id() -> str:
    """The spreadsheet this hub mirrors into — a plain id, not a credential.

    The webhook is what grants writing; this only says *where* the ledger
    lands, so it sits in the editable config rather than the keystore and
    the app can hand a person a link to their own record.
    """
    override = config_service.get_editable_config().get("grocery_sheet_id", "")
    if str(override or "").strip():
        return str(override).strip()
    # Otherwise the hub's own sheet, which ships in api/config/settings.json so
    # a fresh deploy already points at the right ledger with nothing to set up.
    return str(config_loader.api_config("grocery", "sheet_id", "") or "").strip()


class SheetStatus(BaseModel):
    configured: bool          # is there a webhook to push through?
    sheet_url: str | None = None   # where the hub's own copy lives
    pending: int              # entries the sheet has not seen yet


@router.get(
    "/grocery/sheet",
    response_model=SheetStatus,
    summary="Where the mirror lands, and whether anything is waiting",
)
async def sheet_status(token: str | None = Query(default=None)) -> SheetStatus:
    _require_member(token)
    sheet_id = _sheet_id()
    return SheetStatus(
        configured=bool(_sheet_webhook()[0]),
        sheet_url=(
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else None
        ),
        pending=sum(1 for n in _all_spends() if not n.get("sheet_synced")),
    )


def _push_to_sheet(spend: SpendResponse) -> bool:
    """Append one row to the hub's own sheet. False when there's nowhere to push.

    The URL is an Apps Script Web App the hub deploys against their own
    spreadsheet — no service account, and the sheet stays theirs. Any failure
    is swallowed on purpose: the graph already holds the entry, and
    `sheet_synced=false` is the handle for a resync.
    """
    url, secret = _sheet_webhook()
    if not url:
        return False
    payload: dict[str, Any] = {"row": _sheet_row(spend), "columns": _SHEET_COLUMNS}
    if secret:
        payload["secret"] = secret
    try:
        response = httpx.post(url, json=payload, timeout=6.0, follow_redirects=True)
        return response.status_code < 400
    except Exception:
        return False


class ResyncBody(BaseModel):
    actor_token: str = Field(min_length=1)


class ResyncResponse(BaseModel):
    attempted: int
    synced: int
    configured: bool


@router.post(
    "/grocery/sheet/resync",
    response_model=ResyncResponse,
    summary="Push every entry the sheet hasn't seen yet",
)
async def resync_sheet(body: ResyncBody) -> ResyncResponse:
    _require_writer(body.actor_token)
    configured = bool(_sheet_webhook()[0])
    pending = [n for n in _all_spends() if not n.get("sheet_synced")]
    pending.sort(key=lambda n: (_s(n.get("created_at")) or ""))
    synced = 0
    if configured:
        for node in pending:
            spend = _node_to_spend(node)
            if _push_to_sheet(spend):
                graph_service.update_node(node["id"], properties={"sheet_synced": True})
                synced += 1
    return ResyncResponse(attempted=len(pending), synced=synced, configured=configured)


@router.get(
    "/grocery/export.csv",
    response_class=PlainTextResponse,
    summary="The whole ledger as CSV — the door out, always open",
)
async def export_csv(token: str | None = Query(default=None)) -> PlainTextResponse:
    _require_member(token)
    rows = sorted(_all_spends(), key=lambda n: (_s(n.get("spent_on")) or "", _s(n.get("created_at")) or ""))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS)
    writer.writeheader()
    for node in rows:
        writer.writerow(_csv_row(_node_to_spend(node)))
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="hati-grocery.csv"'},
    )
