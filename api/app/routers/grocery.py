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

**The ledger is not a lock.** The graph holds app entries; Google Sheets is
the hub-owned historical balance baseline and outbound mirror (see
``docs/grocery-sheets-setup.md``). An authenticated Apps Script carrier returns
only the fixed summary plus acknowledgements and cancellations for entry IDs
the app already knows, so the household log never becomes a public download.
If the Sheet is dark, the graph ledger keeps answering while the historical
balance says it is unavailable. ``GET /grocery/export.csv`` remains the open
door out.

Identity is the household's: a device token that resolves to a member with
write access. Seeing the ledger is open to any registered cell here.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.routers.household import (
    _PLACE_TYPE,
    _all_places,
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
_SHEET_PROTOCOL = "entry-id-v1"
_SHEET_READ_ATTEMPT_TIMEOUT = 6.5
_SHEET_READ_TOTAL_TIMEOUT = 13.0
_SHEET_WRITE_ATTEMPT_TIMEOUT = 6.0
_SHEET_WRITE_TOTAL_TIMEOUT = 6.5
# libpq enforces a two-second connect-timeout floor. Keep another half-second
# for handoff/flush overhead so a Sheet attempt always leaves a viable durable
# receipt window inside the shared proxy deadline.
_SHEET_RECEIPT_MIN_TIMEOUT = 2.5
_SHEET_RESYNC_TOTAL_TIMEOUT = 13.0
_GROCERY_REQUEST_TOTAL_TIMEOUT = 13.0
_SHEET_APPEND_RETRY_DELAY_SECONDS = 30


def _monotonic() -> float:
    return time.monotonic()


def _current_sheet_attempt_fits(deadline: float) -> bool:
    required = _SHEET_WRITE_TOTAL_TIMEOUT + _SHEET_RECEIPT_MIN_TIMEOUT
    return deadline - _monotonic() >= required


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
    # Which starting suggestion (if any) this shop was first created from —
    # stamped once at creation, untouched by any later rename. The web layer
    # reads this across every device to know a suggestion has been used, so
    # renaming "Bali Buda" away doesn't resurrect it as a ghost duplicate on
    # a household member's *other* phone, where a per-device flag never was.
    origin_suggestion: str | None = None


class ShopBody(BaseModel):
    actor_token: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    default_description: str = Field(min_length=1, max_length=200)
    lat: int | None = None   # micro-degrees, as the phone's GPS gives
    lon: int | None = None
    origin_suggestion: str | None = Field(default=None, max_length=80)


def _node_to_shop(node: dict) -> ShopResponse:
    base = _node_to_place(node)
    return ShopResponse(
        **base.model_dump(),
        default_description=_s(node.get("default_description")) or base.name,
        origin_suggestion=_s(node.get("origin_suggestion")) or None,
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
    if body.origin_suggestion:
        props["origin_suggestion"] = body.origin_suggestion
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
    # Set only when the client knows the shop's PRE-rename name matched a
    # starting suggestion — heals a shop saved before origin_suggestion
    # existed, so a legacy rename doesn't resurrect a ghost either.
    origin_suggestion: str | None = Field(default=None, max_length=80)


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
    if body.origin_suggestion and not node.get("origin_suggestion"):
        updates["properties"]["origin_suggestion"] = body.origin_suggestion
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
    return [
        node
        for node in graph_service.list_nodes_by_type_snapshot(_SPEND_TYPE)
        if not node.get("sheet_cancelled")
    ]


def _reversal_spend(node: dict, actor: dict) -> SpendResponse:
    """The stable compensating Sheet event for one reconciled deletion."""
    original = _node_to_spend(node)
    reversal_kind = _KIND_BUY if original.kind == _KIND_TOPUP else _KIND_TOPUP
    return SpendResponse(
        id=f"reversal-{original.id}",
        amount_typed=original.amount_typed,
        amount_idr=original.amount_idr,
        description=f"undo: {original.description}",
        spent_on=_today_local(),
        kind=reversal_kind,
        by_id=_s(actor.get("id")) or original.by_id,
        by_name=_s(actor.get("name")) or original.by_name,
        created_at=_now(),
        runtime=original.runtime,
        sheet_synced=False,
    )


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
        "sheet_protocol": _SHEET_PROTOCOL,
    }
    graph_service.create_node(
        id=spend_id,
        type=_SPEND_TYPE,
        name=f"{_CURRENCY} {amount_idr:,} — {description}",
        description=description,
        properties=props,
        _include_private=True,
    )
    node = graph_service.get_node_unfiltered(spend_id) or {"id": spend_id, **props}
    spend = _node_to_spend(node)

    # The mirror. A dark sheet never costs the manager their entry.
    if await _push_to_sheet(spend):
        graph_service.update_node(
            spend_id,
            _include_private=True,
            properties={"sheet_synced": True},
        )
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
        "sheet_protocol": _SHEET_PROTOCOL,
    }
    graph_service.create_node(
        id=topup_id, type=_SPEND_TYPE,
        name=f"top up {_CURRENCY} {amount_idr:,}",
        description=props["spend_description"], properties=props,
        _include_private=True,
    )
    node = graph_service.get_node_unfiltered(topup_id) or {"id": topup_id, **props}
    topup = _node_to_spend(node)
    if await _push_to_sheet(topup):
        graph_service.update_node(
            topup_id,
            _include_private=True,
            properties={"sheet_synced": True},
        )
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
    deadline = _monotonic() + _GROCERY_REQUEST_TOTAL_TIMEOUT
    node = graph_service.get_node_unfiltered(spend_id)
    if not node or node.get("type") != _SPEND_TYPE:
        raise HTTPException(status_code=404, detail=f"entry {spend_id!r} not found")
    # Your own mistake is yours to undo; a resident can fix anyone's.
    if node.get("by_id") != actor.get("id") and actor.get("role") != "resident":
        raise HTTPException(
            status_code=403, detail="only the person who recorded it, or a resident, can remove it"
        )
    # One Apps Script lock covers cancellation, original-ID observation, and
    # any compensating append. If an append is already in flight it lands
    # first and is reversed; if deletion gets the lock first, its durable
    # private cancellation marker prevents that append from landing later.
    mirrored = await _reconcile_sheet_delete(node, actor)
    if mirrored is None:
        raise HTTPException(
            status_code=503,
            detail="Sheet reconciliation is unavailable; the entry was preserved",
        )
    remaining = deadline - _monotonic()
    if remaining <= 0:
        raise HTTPException(
            status_code=503,
            detail="The reconciled entry could not be removed; retry is safe",
        )
    deletion = asyncio.create_task(
        asyncio.to_thread(
            graph_service.delete_node,
            spend_id,
            _include_private=True,
            _deadline=deadline,
        )
    )
    try:
        deleted = await asyncio.wait_for(asyncio.shield(deletion), timeout=remaining)
    except asyncio.TimeoutError:
        try:
            deleted = await deletion
        except Exception:
            deleted = False
    except (graph_service.TransactionDeadlineExceeded, SQLAlchemyError):
        deleted = False
    except asyncio.CancelledError:
        try:
            await deletion
        except Exception:
            pass
        raise
    if not deleted:
        raise HTTPException(
            status_code=503,
            detail="The reconciled entry could not be removed; retry is safe",
        )
    return DeleteResponse(deleted=spend_id, was_mirrored=mirrored)


class TotalsResponse(BaseModel):
    on: str
    currency: str = _CURRENCY
    day_total_idr: int
    day_count: int
    month_total_idr: int
    month_count: int
    remaining_idr: int | None = None
    remaining_source: Literal["sheet", "unavailable"] = "unavailable"


def _remaining_balance(
    *,
    sheet_remaining: int | None,
    pending_signed: list[int],
    deadline: float | None = None,
) -> int | None:
    """Choose and reconcile the balance on the Form kernel."""
    kernel_timeout = 10.0
    if deadline is not None:
        kernel_timeout = deadline - _monotonic()
        if kernel_timeout <= 0:
            return None
        kernel_timeout = min(10.0, kernel_timeout)
    try:
        value, _runtime = serve_via_kernel(
            "endpoint_grocery_remaining.fk",
            bindings={
                "sheet_available": sheet_remaining is not None,
                "sheet_remaining": sheet_remaining or 0,
                "pending_signed": pending_signed,
            },
            parse=json.loads,
            timeout=kernel_timeout,
        )
    except RuntimeError:
        if deadline is not None and deadline <= _monotonic():
            return None
        raise
    if (
        not isinstance(value, list)
        or len(value) != 2
        or value[0] != 1
        or isinstance(value[1], bool)
        or not isinstance(value[1], int)
    ):
        return None
    return value[1]


def _legacy_sheet_signature(spend: SpendResponse) -> tuple[str, int, str]:
    """Mirror the Apps Script signature normalization at the carrier boundary."""
    return (
        spend.spent_on.strip()[:10],
        spend.signed_idr,
        spend.description.strip(),
    )


def _legacy_reconciliation_batch(
    pending_nodes: list[dict],
    pending: list[SpendResponse],
    *,
    all_nodes: list[dict],
    all_entries: list[SpendResponse],
    deadline: float | None = None,
) -> list[tuple[dict, SpendResponse]]:
    if deadline is not None and deadline <= _monotonic():
        raise asyncio.TimeoutError
    if len(pending_nodes) != len(pending):
        raise RuntimeError("pending grocery reconciliation rows are misaligned")
    if len(all_nodes) != len(all_entries):
        raise RuntimeError("grocery reconciliation ledger rows are misaligned")
    pending_by_position = {
        position: (node, spend)
        for position, (node, spend) in enumerate(zip(pending_nodes, pending))
    }
    signature_counts = Counter(
        _legacy_sheet_signature(spend)
        for node, spend in zip(all_nodes, all_entries)
        if _s(node.get("sheet_protocol")) != _SHEET_PROTOCOL
    )
    policy_rows = [
        [
            position,
            spend.id,
            1,
            _s(node.get("sheet_protocol")) or "",
            signature_counts[_legacy_sheet_signature(spend)],
            _s(node.get("sheet_reconcile_attempted_at")) or "",
            _s(node.get("sheet_append_retry_after")) or "",
            1 if node.get("sheet_cancelled") else 0,
            1 if node.get("sheet_append_yield_legacy") else 0,
        ]
        for position, (node, spend) in enumerate(zip(pending_nodes, pending))
    ]
    if any(
        "|" in str(value) or ";" in str(value)
        for row in policy_rows
        for value in row
    ):
        raise RuntimeError("grocery reconciliation policy field contains a delimiter")
    entries_wire = ";".join(
        "|".join(str(value) for value in row) for row in policy_rows
    )
    kernel_timeout = 10.0
    if deadline is not None:
        kernel_timeout = deadline - _monotonic()
        if kernel_timeout <= 0:
            raise asyncio.TimeoutError
        kernel_timeout = min(10.0, kernel_timeout)
    try:
        selected_positions, _runtime = serve_via_kernel(
            "endpoint_grocery_reconcile_selection.fk",
            bindings={
                "entries_wire": entries_wire,
                "selection_mode": "legacy",
                "now": "",
            },
            parse=json.loads,
            timeout=kernel_timeout,
        )
    except RuntimeError as exc:
        if deadline is not None and deadline <= _monotonic():
            raise asyncio.TimeoutError from exc
        raise
    if (
        not isinstance(selected_positions, list)
        or any(
            not isinstance(position, int) or isinstance(position, bool)
            for position in selected_positions
        )
        or len(selected_positions) != len(set(selected_positions))
        or any(position not in pending_by_position for position in selected_positions)
    ):
        raise RuntimeError("Form returned an invalid grocery reconciliation selection")
    return [pending_by_position[position] for position in selected_positions]


def _persist_sheet_receipts(
    pending_nodes: list[dict],
    legacy_batch: list[tuple[dict, SpendResponse]],
    snapshot: _SheetSnapshot | None,
    *,
    deadline: float | None = None,
) -> dict[str, dict[str, Any]]:
    if snapshot is None:
        return {}
    attempted_at = _now()
    updates: dict[str, dict[str, Any]] = {}
    for _node, spend in legacy_batch:
        properties: dict[str, Any] = {
            "sheet_reconcile_attempted_at": attempted_at,
        }
        properties.update(_sheet_receipt_properties(spend.id, snapshot))
        updates[spend.id] = properties

    legacy_batch_ids = {spend.id for _node, spend in legacy_batch}
    for node in pending_nodes:
        entry_id = _s(node.get("id"))
        if (
            _s(node.get("sheet_protocol")) == _SHEET_PROTOCOL
            and node.get("sheet_append_yield_legacy")
        ):
            updates.setdefault(entry_id, {})["sheet_append_yield_legacy"] = False
        receipt_properties = _sheet_receipt_properties(entry_id, snapshot)
        if entry_id in legacy_batch_ids or not receipt_properties:
            continue
        updates.setdefault(entry_id, {}).update(receipt_properties)

    persisted = graph_service.update_node_properties_batch(
        updates,
        _include_private=True,
        _source="grocery-sheet-reconciliation",
        _deadline=deadline,
    )
    return {entry_id: updates[entry_id] for entry_id in persisted}


def _sheet_receipt_properties(
    entry_id: str,
    snapshot: _SheetSnapshot,
) -> dict[str, Any]:
    """Cancellation is the terminal Sheet receipt, even when the row exists."""
    if entry_id in snapshot.cancelled_ids:
        return {"sheet_cancelled": True, "sheet_append_yield_legacy": False}
    if entry_id in snapshot.acknowledged_ids:
        return {"sheet_synced": True, "sheet_protocol": _SHEET_PROTOCOL}
    return {}


def _has_unresolved_legacy(pending_nodes: list[dict]) -> bool:
    return any(
        not node.get("sheet_cancelled")
        and not node.get("sheet_synced")
        and _s(node.get("sheet_protocol")) != _SHEET_PROTOCOL
        for node in pending_nodes
    )


def _blocked_legacy_count(pending_nodes: list[dict]) -> int:
    return sum(
        1
        for node in pending_nodes
        if not node.get("sheet_cancelled")
        and not node.get("sheet_synced")
        and _s(node.get("sheet_protocol")) != _SHEET_PROTOCOL
    )


def _current_sheet_retry_batch(
    rows: list[dict],
    now: str,
    *,
    deadline: float,
) -> list[dict]:
    """Let Form choose current-protocol rows whose retry window is open."""
    if deadline <= _monotonic():
        raise asyncio.TimeoutError
    policy_rows = [
        [
            position,
            _s(node.get("id")),
            0 if node.get("sheet_synced") else 1,
            _s(node.get("sheet_protocol")) or "",
            0,
            "",
            _s(node.get("sheet_append_retry_after")) or "",
            1 if node.get("sheet_cancelled") else 0,
            1 if node.get("sheet_append_yield_legacy") else 0,
        ]
        for position, node in enumerate(rows)
    ]
    if any(
        "|" in str(value) or ";" in str(value)
        for row in policy_rows
        for value in row
    ):
        raise RuntimeError("grocery current-retry policy field contains a delimiter")
    entries_wire = ";".join(
        "|".join(str(value) for value in row) for row in policy_rows
    )
    kernel_timeout = deadline - _monotonic()
    if kernel_timeout <= 0:
        raise asyncio.TimeoutError
    try:
        selected_positions, _runtime = serve_via_kernel(
            "endpoint_grocery_reconcile_selection.fk",
            bindings={
                "entries_wire": entries_wire,
                "selection_mode": "current-retry",
                "now": now,
            },
            parse=json.loads,
            timeout=min(10.0, kernel_timeout),
        )
    except RuntimeError as exc:
        if deadline <= _monotonic():
            raise asyncio.TimeoutError from exc
        raise
    if (
        not isinstance(selected_positions, list)
        or any(
            not isinstance(position, int) or isinstance(position, bool)
            for position in selected_positions
        )
        or len(selected_positions) != len(set(selected_positions))
        or any(position < 0 or position >= len(rows) for position in selected_positions)
    ):
        raise RuntimeError("Form returned an invalid current retry selection")
    return [rows[position] for position in selected_positions]


async def _joined_current_sheet_retry_batch(
    rows: list[dict],
    now: str,
    *,
    deadline: float,
) -> list[dict]:
    """Run current retry policy off-loop within its queue-inclusive deadline."""
    return await _run_joined_deadline(
        lambda: _current_sheet_retry_batch(rows, now, deadline=deadline),
        deadline=deadline,
    )


async def _run_joined_deadline(
    function: Callable[[], Any],
    *,
    deadline: float,
) -> Any:
    """Bound executor queue + runtime, skipping queued work and joining started work."""
    state_lock = threading.Lock()
    state = {"started": False, "skip": False}

    def run() -> Any:
        with state_lock:
            if state["skip"]:
                raise asyncio.TimeoutError
            state["started"] = True
        return function()

    remaining = deadline - _monotonic()
    if remaining <= 0:
        raise asyncio.TimeoutError
    selection = asyncio.create_task(asyncio.to_thread(run))
    try:
        return await asyncio.wait_for(asyncio.shield(selection), timeout=remaining)
    except asyncio.TimeoutError:
        with state_lock:
            queued = not state["started"]
            if queued:
                state["skip"] = True
        if queued:
            selection.cancel()
        try:
            await selection
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception:
            pass
        raise
    except asyncio.CancelledError:
        with state_lock:
            queued = not state["started"]
            if queued:
                state["skip"] = True
        if queued:
            selection.cancel()
        try:
            await selection
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        raise


async def _reconciled_sheet_snapshot(
    pending_nodes: list[dict],
    pending: list[SpendResponse],
    *,
    all_nodes: list[dict],
    all_entries: list[SpendResponse],
    deadline: float | None = None,
) -> _SheetSnapshot | None:
    if deadline is None:
        deadline = _monotonic() + _SHEET_RESYNC_TOTAL_TIMEOUT

    async def reconcile_within_deadline() -> _SheetSnapshot | None:
        legacy_batch = await _run_joined_deadline(
            lambda: _legacy_reconciliation_batch(
                pending_nodes,
                pending,
                all_nodes=all_nodes,
                all_entries=all_entries,
                deadline=deadline,
            ),
            deadline=deadline,
        )
        pending_ids = [spend.id for spend in pending]
        snapshot = (
            await _read_sheet_snapshot(
                pending_ids,
                legacy_entries=[spend for _node, spend in legacy_batch],
            )
            if legacy_batch
            else await _read_sheet_snapshot(pending_ids)
        )
        persistence = asyncio.create_task(
            asyncio.to_thread(
                _persist_sheet_receipts,
                pending_nodes,
                legacy_batch,
                snapshot,
                deadline=deadline,
            )
        )
        try:
            persisted_updates = await asyncio.shield(persistence)
        except (graph_service.TransactionDeadlineExceeded, SQLAlchemyError):
            return None
        except asyncio.CancelledError:
            # Cancelling to_thread only cancels its awaiter. The database-side
            # timeout above bounds the transaction; wait for its commit or
            # rollback so retries cannot accumulate background writers.
            try:
                await persistence
            except Exception:
                pass
            raise
        pending_by_id = {_s(node.get("id")): node for node in pending_nodes}
        for entry_id, properties in persisted_updates.items():
            pending_by_id[entry_id].update(properties)
        return None if _has_unresolved_legacy(pending_nodes) else snapshot

    remaining = deadline - _monotonic()
    if remaining <= 0:
        return None
    try:
        return await asyncio.wait_for(
            reconcile_within_deadline(),
            timeout=remaining,
        )
    except asyncio.TimeoutError:
        return None


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
    deadline = _monotonic() + _GROCERY_REQUEST_TOTAL_TIMEOUT
    day = (on or "").strip() or _today_local()
    month = day[:7]
    rows = _all_spends()
    buys = [n for n in rows if (_s(n.get("kind")) or _KIND_BUY) != _KIND_TOPUP]
    day_rows = [n for n in buys if _s(n.get("spent_on")) == day]
    month_rows = [n for n in buys if (_s(n.get("spent_on")) or "").startswith(month)]
    # The Sheet carries history from before the app existed. Its authenticated
    # carrier returns only Sisa plus acknowledgements for IDs already present
    # in this graph. That acknowledgement closes the append/flag crash seam:
    # an entry present in the Sheet is never applied twice merely because its
    # local sheet_synced flag was not committed before a crash.
    pending_nodes = [n for n in rows if not n.get("sheet_synced")]
    pending = [_node_to_spend(n) for n in pending_nodes]
    # GET remains a read for every member, including see-only watchers. A
    # writer explicitly advances predecessor-row reconciliation through the
    # resync endpoint; until then, an unproven legacy row keeps Sisa unavailable.
    if _has_unresolved_legacy(pending_nodes):
        balance_snapshot = None
    else:
        remaining = deadline - _monotonic()
        if remaining <= 0:
            balance_snapshot = None
        else:
            try:
                balance_snapshot = await asyncio.wait_for(
                    _read_sheet_snapshot([spend.id for spend in pending]),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                balance_snapshot = None
    pending_signed = [
        spend.signed_idr
        for spend in pending
        if balance_snapshot is None
        or (
            spend.id not in balance_snapshot.acknowledged_ids
            and spend.id not in balance_snapshot.cancelled_ids
        )
    ]
    remaining = _remaining_balance(
        sheet_remaining=(
            balance_snapshot.remaining_idr if balance_snapshot is not None else None
        ),
        pending_signed=pending_signed,
        deadline=deadline,
    )
    remaining_source: Literal["sheet", "unavailable"] = (
        "sheet" if remaining is not None else "unavailable"
    )
    return TotalsResponse(
        on=day,
        day_total_idr=sum(int(n.get("amount_idr") or 0) for n in day_rows),
        day_count=len(day_rows),
        month_total_idr=sum(int(n.get("amount_idr") or 0) for n in month_rows),
        month_count=len(month_rows),
        remaining_idr=remaining,
        remaining_source=remaining_source,
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
_SHEET_COLUMNS = ["When", "Amount", "What", "Entry ID"]

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
        "Entry ID": spend.id,
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

    Both values are scoped credentials and live in
    ``~/.coherence-network/keys.json`` under ``grocery_sheet``, read through
    the one config carrier. Nothing here reads the environment.
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


def _parse_sheet_idr(value: object) -> int | None:
    """Read one whole-rupiah formatted Sheet value without using a float."""
    if isinstance(value, bool):
        return None
    compact = re.sub(r"[^0-9,.-]", "", str(value or ""))
    if not compact:
        return None
    if re.fullmatch(r"-?\d{1,3}(?:[,.]\d{3})+", compact):
        compact = compact.replace(",", "").replace(".", "")
    if not re.fullmatch(r"-?\d+", compact):
        return None
    return int(compact)


@dataclass(frozen=True)
class _SheetSnapshot:
    remaining_idr: int
    acknowledged_ids: frozenset[str]
    cancelled_ids: frozenset[str]


async def _request_sheet_snapshot(
    url: str,
    body: dict[str, Any],
    requested: set[str],
) -> _SheetSnapshot | None:
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(
                timeout=_SHEET_READ_ATTEMPT_TIMEOUT,
                follow_redirects=True,
            ) as client:
                response = await client.post(url, json=body)
            if response.status_code >= 500 and attempt == 0:
                continue
            if response.status_code >= 400:
                return None
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                return None
            remaining = _parse_sheet_idr(payload.get("remaining_idr"))
            raw_acknowledged = payload.get("acknowledged_ids")
            raw_cancelled = payload.get("cancelled_ids")
            if (
                remaining is None
                or not isinstance(raw_acknowledged, list)
                or not isinstance(raw_cancelled, list)
            ):
                return None
            acknowledged = frozenset(
                entry_id
                for entry_id in raw_acknowledged
                if isinstance(entry_id, str) and entry_id in requested
            )
            cancelled = frozenset(
                entry_id
                for entry_id in raw_cancelled
                if isinstance(entry_id, str) and entry_id in requested
            )
            return _SheetSnapshot(remaining, acknowledged, cancelled)
        except httpx.HTTPError:
            if attempt == 0:
                continue
            return None
        except (TypeError, ValueError):
            return None
    return None


async def _read_sheet_snapshot(
    pending_ids: list[str],
    *,
    legacy_entries: list[SpendResponse] | None = None,
) -> _SheetSnapshot | None:
    """Read a private, bounded balance snapshot through Apps Script.

    The shared secret authenticates the request. The carrier returns only
    ``Sisa`` and the subsets of caller-supplied entry IDs already acknowledged
    or cancelled; it never exposes the household ledger. Any failure returns
    ``None`` so the Form policy can report that the historical balance is
    unavailable.
    """
    url, secret = _sheet_webhook()
    if not url or not secret:
        return None
    requested = {entry_id for entry_id in pending_ids if entry_id}
    legacy = list(legacy_entries or [])
    body: dict[str, Any] = {
        "action": "summary",
        "secret": secret,
        "pending_ids": sorted(requested),
    }
    if legacy:
        body["legacy_entries"] = [
            {
                "entry_id": spend.id,
                "row": _sheet_row(spend),
                "columns": _SHEET_COLUMNS,
            }
            for spend in legacy
        ]

    # Apps Script cold starts can outlive a four-second request. Summary and
    # legacy reconciliation are entry-ID idempotent, so one retry is safe. The
    # outer wall-clock deadline includes redirects and every HTTP phase, keeping
    # the whole operation inside the grocery proxy's 15-second ceiling.
    try:
        return await asyncio.wait_for(
            _request_sheet_snapshot(url, body, requested),
            timeout=_SHEET_READ_TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return None


class SheetStatus(BaseModel):
    configured: bool          # is there a webhook to push through?
    sheet_url: str | None = None   # where the hub's own copy lives
    pending: int              # entries the sheet has not seen yet
    blocked_legacy: int = 0   # pre-Entry-ID rows whose presence is unknowable


@router.get(
    "/grocery/sheet",
    response_model=SheetStatus,
    summary="Where the mirror lands, and whether anything is waiting",
)
async def sheet_status(token: str | None = Query(default=None)) -> SheetStatus:
    _require_member(token)
    sheet_id = _sheet_id()
    webhook_url, secret = _sheet_webhook()
    unsynced = [n for n in _all_spends() if not n.get("sheet_synced")]
    return SheetStatus(
        configured=bool(webhook_url and secret),
        sheet_url=(
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else None
        ),
        pending=len(unsynced),
        blocked_legacy=sum(
            1 for n in unsynced if _s(n.get("sheet_protocol")) != _SHEET_PROTOCOL
        ),
    )


async def _push_to_sheet_status(
    spend: SpendResponse,
) -> Literal["synced", "cancelled", "unavailable"]:
    """Append one row and distinguish acknowledgement from cancellation.

    The URL is an Apps Script Web App the hub deploys against their own
    spreadsheet. A shared secret authenticates it and ``entry_id`` makes
    retries idempotent. Any failure becomes ``unavailable`` on purpose: the
    graph already holds the entry, and ``sheet_synced=false`` is the retry handle.
    """
    url, secret = _sheet_webhook()
    if not url or not secret:
        return "unavailable"
    payload: dict[str, Any] = {
        "action": "append",
        "entry_id": spend.id,
        "row": _sheet_row(spend),
        "columns": _SHEET_COLUMNS,
        "secret": secret,
    }
    try:
        async with httpx.AsyncClient(
            timeout=_SHEET_WRITE_ATTEMPT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await asyncio.wait_for(
                client.post(url, json=payload),
                timeout=_SHEET_WRITE_TOTAL_TIMEOUT,
            )
        if response.status_code >= 400:
            return "unavailable"
        result = response.json()
        if (
            not isinstance(result, dict)
            or result.get("ok") is not True
            or result.get("entry_id") != spend.id
        ):
            return "unavailable"
        return "cancelled" if result.get("cancelled") is True else "synced"
    except (asyncio.TimeoutError, httpx.HTTPError, TypeError, ValueError):
        return "unavailable"


async def _push_to_sheet(spend: SpendResponse) -> bool:
    """Compatibility wrapper for callers that only need acknowledgement."""
    return await _push_to_sheet_status(spend) == "synced"


def _persist_sheet_append_status(
    node: dict,
    append_status: Literal["synced", "cancelled", "unavailable"],
    *,
    deadline: float,
) -> bool:
    """Carry one append outcome into durable graph retry state."""
    if append_status == "synced":
        properties: dict[str, Any] = {
            "sheet_synced": True,
            "sheet_append_yield_legacy": False,
        }
    elif append_status == "cancelled":
        properties = {
            "sheet_cancelled": True,
            "sheet_append_yield_legacy": False,
        }
    else:
        retry_after = (
            datetime.now(timezone.utc)
            + timedelta(seconds=_SHEET_APPEND_RETRY_DELAY_SECONDS)
        ).isoformat()
        properties = {
            "sheet_append_retry_after": retry_after,
            "sheet_append_yield_legacy": True,
        }
    persisted = graph_service.update_node_properties_batch(
        {node["id"]: properties},
        _include_private=True,
        _source="grocery-sheet-resync",
        _deadline=deadline,
    )
    if node["id"] not in persisted:
        return False
    node.update(properties)
    return append_status == "synced"


async def _persist_current_sheet_append_status(
    node: dict,
    append_status: Literal["synced", "cancelled", "unavailable"],
    *,
    deadline: float,
) -> bool:
    """Bound executor queue and receipt write so no database worker escapes."""
    try:
        return await _run_joined_deadline(
            lambda: _persist_sheet_append_status(
                node,
                append_status,
                deadline=deadline,
            ),
            deadline=deadline,
        )
    except asyncio.TimeoutError:
        return False
    except (graph_service.TransactionDeadlineExceeded, SQLAlchemyError):
        return False


async def _reconcile_sheet_delete(node: dict, actor: dict) -> bool | None:
    """Atomically cancel an entry and reverse it if the Sheet already has it.

    ``None`` means the private carrier could not prove completion. The caller
    must retain the graph row so retrying remains safe.
    """
    if not node.get("sheet_synced") and _s(node.get("sheet_protocol")) != _SHEET_PROTOCOL:
        # A predecessor carrier appended without Entry IDs. For these rows a
        # false local flag cannot distinguish "never sent" from "sent, then
        # crashed before flagging". Preserve the row until a one-time migration
        # identifies it; neither deletion nor resync may guess.
        return None
    url, secret = _sheet_webhook()
    if not url or not secret:
        return None
    original = _node_to_spend(node)
    reversal = _reversal_spend(node, actor)
    payload: dict[str, Any] = {
        "action": "reconcile_delete",
        "original_id": original.id,
        "known_mirrored": bool(node.get("sheet_synced")),
        "reversal": {
            "entry_id": reversal.id,
            "row": _sheet_row(reversal),
            "columns": _SHEET_COLUMNS,
        },
        "secret": secret,
    }
    if (
        node.get("sheet_synced")
        and _s(node.get("sheet_protocol")) != _SHEET_PROTOCOL
    ):
        # A predecessor row can be proven present while still lacking an Entry
        # ID. The carrier must tag that exact row before reversal so deleting
        # this graph node cannot make its signature available to a duplicate.
        payload["legacy_original"] = {
            "entry_id": original.id,
            "row": _sheet_row(original),
            "columns": _SHEET_COLUMNS,
        }
    try:
        async with httpx.AsyncClient(
            timeout=_SHEET_WRITE_ATTEMPT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await asyncio.wait_for(
                client.post(url, json=payload),
                timeout=_SHEET_WRITE_TOTAL_TIMEOUT,
            )
        if response.status_code >= 400:
            return None
        result = response.json()
        if (
            not isinstance(result, dict)
            or result.get("ok") is not True
            or result.get("cancelled") is not True
            or result.get("original_id") != original.id
            or result.get("reversal_id") != reversal.id
            or not isinstance(result.get("original_present"), bool)
        ):
            return None
        return bool(result["original_present"])
    except (asyncio.TimeoutError, httpx.HTTPError, TypeError, ValueError):
        return None


class ResyncBody(BaseModel):
    actor_token: str = Field(min_length=1)


class ResyncResponse(BaseModel):
    attempted: int
    synced: int
    configured: bool
    blocked_legacy: int = 0


@router.post(
    "/grocery/sheet/resync",
    response_model=ResyncResponse,
    summary="Push every entry the sheet hasn't seen yet",
)
async def resync_sheet(body: ResyncBody) -> ResyncResponse:
    _require_writer(body.actor_token)
    webhook_url, secret = _sheet_webhook()
    configured = bool(webhook_url and secret)
    rows = _all_spends()
    all_pending = [
        n
        for n in rows
        if not n.get("sheet_synced") and not n.get("sheet_cancelled")
    ]
    had_unresolved_legacy = _has_unresolved_legacy(all_pending)
    blocked_legacy = _blocked_legacy_count(all_pending)
    if not configured:
        return ResyncResponse(
            attempted=sum(
                1
                for node in all_pending
                if _s(node.get("sheet_protocol")) == _SHEET_PROTOCOL
            ),
            synced=0,
            configured=False,
            blocked_legacy=blocked_legacy,
        )
    now = _now()
    deadline = _monotonic() + _SHEET_RESYNC_TOTAL_TIMEOUT
    try:
        pending = await _joined_current_sheet_retry_batch(
            all_pending,
            now,
            deadline=deadline,
        )
    except (asyncio.TimeoutError, RuntimeError):
        return ResyncResponse(
            attempted=0,
            synced=0,
            configured=configured,
            blocked_legacy=blocked_legacy,
        )
    legacy_turn = had_unresolved_legacy and (
        not pending or not _current_sheet_attempt_fits(deadline)
    )
    if configured and legacy_turn:
        await _reconciled_sheet_snapshot(
            all_pending,
            [_node_to_spend(n) for n in all_pending],
            all_nodes=rows,
            all_entries=[_node_to_spend(n) for n in rows],
            deadline=deadline,
        )
        # Keep the request within the same-origin proxy deadline: a legacy
        # summary can consume nearly all of its thirteen-second budget, so
        # current-protocol appends belong to the next idempotent resync call.
        return ResyncResponse(
            attempted=0,
            synced=0,
            configured=True,
            blocked_legacy=_blocked_legacy_count(all_pending),
        )
    pending.sort(key=lambda n: (_s(n.get("created_at")) or ""))
    synced = 0
    attempted = len(pending) if not configured else 0
    if configured:
        for node in pending:
            if not _current_sheet_attempt_fits(deadline):
                break
            attempted += 1
            spend = _node_to_spend(node)
            append_status = await _push_to_sheet_status(spend)
            if await _persist_current_sheet_append_status(
                node,
                append_status,
                deadline=deadline,
            ):
                synced += 1
    return ResyncResponse(
        attempted=attempted,
        synced=synced,
        configured=configured,
        blocked_legacy=blocked_legacy,
    )


@router.get(
    "/grocery/export.csv",
    response_class=PlainTextResponse,
    summary="The whole ledger as CSV — the door out, always open",
)
async def export_csv(token: str | None = Query(default=None)) -> PlainTextResponse:
    _require_member(token)
    rows = sorted(
        _all_spends(),
        key=lambda n: (_s(n.get("spent_on")) or "", _s(n.get("created_at")) or ""),
    )
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
