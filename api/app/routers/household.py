"""Household — the resident-service nervous system for a Light Hub.

Residents signal a need (food, laundry, a ride, a repair, a room readied);
staff see it, acknowledge it, and complete it — everyone watching the same
open board. Outside-resource costs ride along and get marked settled.

Identity is light and WhatsApp-shaped. A member is a name + a phone + a
**device token** that remembers them. There are three doors in:

  • bootstrap — the founding resident (only when no resident exists yet),
  • invite    — a resident vouches someone in by name + role; the invite
                link carries a token, shared over WhatsApp, that auto-
                registers and binds the person the moment they tap it,
  • watch     — anyone can self-register see-only and watch the board.

Seeing is open to any registered cell. **Writing** (asking, tending,
settling) requires a token that resolves to a member with write access —
which residents and staff hold by construction, and a plain member holds
once a resident vouches them. The token is the lock; the invite is the
vouch. Backed by the same living graph that holds offerings and contributors.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import graph_service
from app.services.form_kernel_bridge import serve_via_kernel

router = APIRouter()


MemberRole = Literal["resident", "staff", "member"]
RequestKind = Literal[
    "food", "laundry", "cleaning", "ride", "repair", "room", "supplies", "other"
]
RequestStatus = Literal["open", "acknowledged", "in_progress", "completed", "cancelled"]

_MEMBER_TYPE = "household_member"
_REQUEST_TYPE = "service_request"
# Roles that carry write access by construction. A plain "member" is
# see-only until a resident vouches them.
_WRITE_ROLES = {"resident", "staff"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_token() -> str:
    # 32 url-safe chars (~192 bits). The device credential and the invite
    # link payload are the same token: opaque, unguessable, shared 1:1.
    return secrets.token_urlsafe(24)


# --------------------------------------------------------------------------
# Members — light identity: a name, a phone, a device token, a role.
# --------------------------------------------------------------------------


class MemberPublic(BaseModel):
    """What everyone may see about a member — never the token or phone."""
    id: str
    name: str
    role: str
    write_access: bool
    status: str
    invited_by_name: str | None = None
    created_at: str


class MemberPrivate(MemberPublic):
    """Returned only to the member themselves (carries the credential)."""
    token: str
    phone: str | None = None


class RegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    locale: str = Field(default="en", max_length=8)


class BootstrapBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class InviteBody(BaseModel):
    inviter_token: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)  # optional — role-only invites carry no typed name
    role: MemberRole = "member"
    phone: str | None = Field(default=None, max_length=40)


def _member_public(node: dict) -> MemberPublic:
    return MemberPublic(
        id=node.get("id", ""),
        name=node.get("name", ""),
        role=node.get("role", "member"),
        write_access=bool(node.get("write_access")),
        status=node.get("status", "active"),
        invited_by_name=(node.get("invited_by_name") or None),
        created_at=node.get("created_at", "") or node.get("observed_at", ""),
    )


def _member_private(node: dict) -> MemberPrivate:
    pub = _member_public(node).model_dump()
    return MemberPrivate(**pub, token=node.get("token", ""), phone=(node.get("phone") or None))


def _all_members() -> list[dict]:
    try:
        response = graph_service.list_nodes(type=_MEMBER_TYPE, limit=1000)
        nodes = response.get("items", []) if isinstance(response, dict) else (response or [])
    except Exception:
        nodes = []
    return [n for n in nodes if n.get("type") == _MEMBER_TYPE]


def _resident_exists() -> bool:
    return any(m.get("role") == "resident" for m in _all_members())


def _member_by_token(token: str | None) -> dict | None:
    if not token:
        return None
    for m in _all_members():
        if m.get("token") and m.get("token") == token:
            return m
    return None


def _is_placeholder_name_k(name: str) -> int:
    """Value-identical fallback for endpoint_placeholder_name.fk."""
    if len(name) == 0:
        return 1
    if len(name) < 4:
        return 0
    return 1 if name[0:4] == "New " else 0


def _is_placeholder_name(name: str) -> bool:
    """A role-only invite carries 'New {role}' until the newcomer claims it
    with their own name on first open — the self-name half of `bind`. The
    decision runs on the Form kernel (endpoint_placeholder_name.fk),
    Python the value-identical fallback."""
    val, _runtime = serve_via_kernel(
        "endpoint_placeholder_name.fk",
        bindings={"name": name},
        fallback=lambda: _is_placeholder_name_k(name),
        parse=int,
    )
    return bool(val)


def _create_member(name: str, role: str, *, write_access: bool, status: str,
                   phone: str | None, locale: str = "en",
                   invited_by: str = "", invited_by_name: str = "") -> dict:
    member_id = f"member-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    created_at = _now()
    properties: dict[str, Any] = {
        "role": role,
        "locale": locale or "en",
        "phone": phone or "",
        "token": _new_token(),
        "write_access": bool(write_access),
        "status": status,
        "invited_by": invited_by,
        "invited_by_name": invited_by_name,
        "created_at": created_at,
    }
    return graph_service.create_node(
        id=member_id,
        type=_MEMBER_TYPE,
        name=name,
        description=f"{role} of the household",
        properties=properties,
    )


@router.post(
    "/household/bootstrap",
    response_model=MemberPrivate,
    status_code=201,
    summary="Create the founding resident (only when no resident exists yet)",
)
async def bootstrap_resident(body: BootstrapBody) -> MemberPrivate:
    if _resident_exists():
        raise HTTPException(status_code=409, detail="a resident already exists; ask them for an invite")
    node = _create_member(body.name, "resident", write_access=True, status="active", phone=body.phone)
    return _member_private(node)


@router.post(
    "/household/members",
    response_model=MemberPrivate,
    status_code=201,
    summary="Self-register to watch the board (see-only until a resident vouches you)",
)
async def register_member(body: RegisterBody) -> MemberPrivate:
    node = _create_member(body.name, "member", write_access=False, status="active",
                          phone=body.phone, locale=body.locale)
    return _member_private(node)


@router.post(
    "/household/invites",
    response_model=MemberPrivate,
    status_code=201,
    summary="A resident vouches someone in by name + role; the returned token is the invite-link payload",
)
async def create_invite(body: InviteBody) -> MemberPrivate:
    inviter = _member_by_token(body.inviter_token)
    if not inviter or inviter.get("role") != "resident":
        raise HTTPException(status_code=403, detail="only a resident can invite")
    role = body.role
    write_access = role in _WRITE_ROLES
    # Role-only invite: when no name is typed, the cell carries a placeholder
    # until the newcomer claims it with their own name on first scan/open.
    invite_name = (body.name or "").strip() or f"New {role}"
    node = _create_member(
        invite_name, role, write_access=write_access, status="invited",
        phone=body.phone, invited_by=inviter.get("id", ""),
        invited_by_name=inviter.get("name", ""),
    )
    # The token is returned to the inviter, who shares the join link
    # (built client-side as {origin}/hati-suci?token=…) over WhatsApp.
    return _member_private(node)


@router.get(
    "/household/me",
    response_model=MemberPrivate,
    summary="Resolve your identity by device token (activates an invite on first open)",
)
async def whoami(
    token: str = Query(min_length=1),
    name: str | None = Query(default=None),
) -> MemberPrivate:
    node = _member_by_token(token)
    if not node:
        raise HTTPException(status_code=404, detail="unknown token")
    # bind: activate an invited cell, and let the newcomer claim their own
    # name (only over a placeholder — never clobber a real one).
    kwargs: dict[str, Any] = {}
    if node.get("status") == "invited":
        kwargs["properties"] = {"status": "active"}
    claimed = (name or "").strip()
    if claimed and _is_placeholder_name(node.get("name", "")):
        kwargs["name"] = claimed[:80]
    if kwargs:
        node = graph_service.update_node(node["id"], **kwargs) or node
    return _member_private(node)


@router.get(
    "/household/members",
    response_model=list[MemberPublic],
    summary="Everyone in the household — public view, no tokens or phones",
)
def _is_active_k(status: str) -> int:
    """Value-identical fallback for endpoint_member_active.fk."""
    return 1 if status == "active" else 0


def _is_active(status: str) -> bool:
    """The see-lock decision (Form: see open-to active-member) — on the kernel
    (endpoint_member_active.fk), Python the value-identical fallback."""
    val, _runtime = serve_via_kernel(
        "endpoint_member_active.fk",
        bindings={"status": status},
        fallback=lambda: _is_active_k(status),
        parse=int,
    )
    return bool(val)


async def list_members(role: str | None = Query(default=None)) -> list[MemberPublic]:
    # The roster is the people actually here (Form: `see open-to active-member`).
    # Pending invites stay off it until the newcomer opens their link.
    members = [m for m in _all_members() if _is_active(m.get("status", ""))]
    if role:
        members = [m for m in members if m.get("role") == role]
    members.sort(key=lambda n: n.get("created_at", ""))
    return [_member_public(m) for m in members]


def _require_writer(token: str | None) -> dict:
    member = _member_by_token(token)
    if not member:
        raise HTTPException(status_code=401, detail="register or open your invite link first")
    if not member.get("write_access"):
        raise HTTPException(status_code=403, detail="a resident needs to grant you write access first")
    return member


class GrantBody(BaseModel):
    actor_token: str = Field(min_length=1)


@router.post(
    "/household/members/{member_id}/grant-write",
    response_model=MemberPublic,
    summary="A resident grants a member full write access (the vouch)",
)
async def grant_write(member_id: str, body: GrantBody) -> MemberPublic:
    actor = _member_by_token(body.actor_token)
    if not actor or actor.get("role") != "resident":
        raise HTTPException(status_code=403, detail="only a resident can grant write access")
    node = graph_service.get_node(member_id)
    if not node or node.get("type") != _MEMBER_TYPE:
        raise HTTPException(status_code=404, detail="member not found")
    node = graph_service.update_node(member_id, properties={"write_access": True}) or node
    return _member_public(node)


# --------------------------------------------------------------------------
# Requests — the open board. Added → acknowledged → in_progress → completed.
# Seeing is open; every mutation requires a write-capable device token.
# --------------------------------------------------------------------------


# A market line: a language-free item id, an amount in the pasar's own
# proportion (kg / ikat / sisir / ons / …), and a snapshot of the label +
# unit so the board can re-render in EACH viewer's tongue. The substrate
# shape lives in docs/coherence-substrate/household-membrane.form (market).
class RequestItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    qty: float = Field(gt=0)
    unit: str | None = Field(default=None, max_length=24)
    label: str | None = Field(default=None, max_length=120)


class RequestCreate(BaseModel):
    actor_token: str = Field(min_length=1)
    kind: RequestKind
    detail: str = Field(min_length=1, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    when_text: str | None = Field(default=None, max_length=200)
    items: list[RequestItem] = Field(default_factory=list)


class ActorBody(BaseModel):
    actor_token: str = Field(min_length=1)


class CompleteBody(ActorBody):
    cost_amount: float | None = Field(default=None, ge=0)
    cost_currency: str = Field(default="IDR", max_length=8)
    cost_note: str | None = Field(default=None, max_length=400)


class RequestResponse(BaseModel):
    id: str
    kind: str
    detail: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    location: str | None = None
    when_text: str | None = None
    status: str
    requester_id: str
    requester_name: str
    acknowledged_by_name: str | None = None
    completed_by_name: str | None = None
    cost_amount: float | None = None
    cost_currency: str = "IDR"
    cost_note: str | None = None
    cost_status: str = "none"
    paid_by_name: str | None = None
    created_at: str
    updated_at: str


def _s(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


def _decode_items(node: dict) -> list[dict[str, Any]]:
    raw = node.get("items_json")
    if not isinstance(raw, str) or not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [i for i in parsed if isinstance(i, dict)] if isinstance(parsed, list) else []


def _node_to_request(node: dict) -> RequestResponse:
    raw_cost = node.get("cost_amount")
    cost_amount = float(raw_cost) if isinstance(raw_cost, (int, float)) else None
    return RequestResponse(
        id=node.get("id", ""),
        kind=node.get("kind", "other"),
        detail=node.get("detail", "") or node.get("description", ""),
        items=_decode_items(node),
        location=_s(node.get("location")),
        when_text=_s(node.get("when_text")),
        status=node.get("status", "open"),
        requester_id=node.get("requester_id", ""),
        requester_name=node.get("requester_name", "") or "",
        acknowledged_by_name=_s(node.get("acknowledged_by_name")),
        completed_by_name=_s(node.get("completed_by_name")),
        cost_amount=cost_amount,
        cost_currency=node.get("cost_currency", "IDR") or "IDR",
        cost_note=_s(node.get("cost_note")),
        cost_status=node.get("cost_status", "none") or "none",
        paid_by_name=_s(node.get("paid_by_name")),
        created_at=node.get("created_at", "") or node.get("observed_at", ""),
        updated_at=node.get("updated_at", "") or node.get("created_at", ""),
    )


def _load_request(request_id: str) -> dict:
    node = graph_service.get_node(request_id)
    if not node or node.get("type") != _REQUEST_TYPE:
        raise HTTPException(status_code=404, detail=f"request {request_id!r} not found")
    return node


def _apply(request_id: str, updates: dict[str, Any]) -> RequestResponse:
    updates["updated_at"] = _now()
    node = graph_service.update_node(request_id, properties=updates)
    if node is None:
        raise HTTPException(status_code=404, detail=f"request {request_id!r} not found")
    return _node_to_request(node)


# ── The request lifecycle, as a Form recipe ───────────────────────────
# advance(status, verb) — the membrane's state machine — runs on the Form
# kernel (endpoint_household_advance.fk) with a value-identical Python
# fallback. This is the first household rule to leave the Python if-tree and
# execute as Form; the carrier here only encodes/decodes and does the I/O.
# (household-membrane.form, recipes: acknowledge / tend / complete.)
_STATUS_CODE = {"open": 0, "acknowledged": 1, "in_progress": 2, "completed": 3, "cancelled": 4}
_CODE_STATUS = {v: k for k, v in _STATUS_CODE.items()}
_VERB_CODE = {"acknowledge": 0, "start": 1, "complete": 2, "cancel": 3}


def _advance_py(status: int, verb: int) -> int:
    """Value-identical fallback for endpoint_household_advance.fk."""
    if verb == 0:
        return 1 if status == 0 else -1
    if verb == 1:
        return 2 if status < 2 else -1
    if verb == 2:
        return 3 if status < 3 else -1
    if verb == 3:
        return 4 if status < 3 else -1
    return -1


def _advance_status(current: str, verb: str) -> str:
    """Next lifecycle status, computed by the Form recipe on the kernel."""
    s = _STATUS_CODE.get(current, 0)
    v = _VERB_CODE[verb]
    code, _runtime = serve_via_kernel(
        "endpoint_household_advance.fk",
        bindings={"status": s, "verb": v},
        fallback=lambda: _advance_py(s, v),
        parse=int,
    )
    nxt = _CODE_STATUS.get(int(code))
    if nxt is None:
        raise HTTPException(status_code=409, detail=f"cannot {verb} a {current} request")
    return nxt


@router.post(
    "/household/requests",
    response_model=RequestResponse,
    status_code=201,
    summary="Ask the field for something (write access required)",
)
async def create_request(body: RequestCreate) -> RequestResponse:
    actor = _require_writer(body.actor_token)
    request_id = f"request-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    created_at = _now()
    properties: dict[str, Any] = {
        "kind": body.kind,
        "detail": body.detail,
        "location": body.location or "",
        "when_text": body.when_text or "",
        "status": "open",
        "requester_id": actor.get("id", ""),
        "requester_name": actor.get("name", ""),
        "cost_status": "none",
        "cost_currency": "IDR",
        "created_at": created_at,
        "updated_at": created_at,
    }
    if body.items:
        properties["items_json"] = json.dumps(
            [i.model_dump(exclude_none=True) for i in body.items]
        )
    node = graph_service.create_node(
        id=request_id, type=_REQUEST_TYPE, name=body.detail[:120],
        description=body.detail, properties=properties,
    )
    return _node_to_request(node)


@router.get(
    "/household/requests",
    response_model=list[RequestResponse],
    summary="The open board — every request, what's done and what's waiting",
)
async def list_requests(
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[RequestResponse]:
    try:
        response = graph_service.list_nodes(type=_REQUEST_TYPE, limit=500)
        nodes = response.get("items", []) if isinstance(response, dict) else (response or [])
    except Exception:
        nodes = []
    requests = [n for n in nodes if n.get("type") == _REQUEST_TYPE]
    if status:
        requests = [n for n in requests if n.get("status") == status]
    requests.sort(key=lambda n: n.get("created_at", ""), reverse=True)
    return [_node_to_request(n) for n in requests[:limit]]


@router.get(
    "/household/requests/{request_id}",
    response_model=RequestResponse,
    summary="A single request in full",
)
async def get_request(request_id: str) -> RequestResponse:
    return _node_to_request(_load_request(request_id))


@router.post(
    "/household/requests/{request_id}/acknowledge",
    response_model=RequestResponse,
    summary="A staff member sees it and takes it on",
)
async def acknowledge_request(request_id: str, body: ActorBody) -> RequestResponse:
    actor = _require_writer(body.actor_token)
    node = _load_request(request_id)
    return _apply(request_id, {
        "status": _advance_status(node.get("status", "open"), "acknowledge"),
        "acknowledged_by": actor.get("id", ""),
        "acknowledged_by_name": actor.get("name", ""),
        "acknowledged_at": _now(),
    })


@router.post(
    "/household/requests/{request_id}/start",
    response_model=RequestResponse,
    summary="Work on it has begun",
)
async def start_request(request_id: str, body: ActorBody) -> RequestResponse:
    actor = _require_writer(body.actor_token)
    node = _load_request(request_id)
    updates: dict[str, Any] = {"status": _advance_status(node.get("status", "open"), "start"), "started_at": _now()}
    if not _s(node.get("acknowledged_by")):
        updates["acknowledged_by"] = actor.get("id", "")
        updates["acknowledged_by_name"] = actor.get("name", "")
        updates["acknowledged_at"] = _now()
    return _apply(request_id, updates)


@router.post(
    "/household/requests/{request_id}/complete",
    response_model=RequestResponse,
    summary="It's done — optionally recording the cost of any outside resources",
)
async def complete_request(request_id: str, body: CompleteBody) -> RequestResponse:
    actor = _require_writer(body.actor_token)
    node = _load_request(request_id)
    updates: dict[str, Any] = {
        "status": _advance_status(node.get("status", "open"), "complete"),
        "completed_by": actor.get("id", ""),
        "completed_by_name": actor.get("name", ""),
        "completed_at": _now(),
    }
    if body.cost_amount and body.cost_amount > 0:
        updates["cost_amount"] = float(body.cost_amount)
        updates["cost_currency"] = body.cost_currency or "IDR"
        updates["cost_note"] = body.cost_note or ""
        updates["cost_status"] = "recorded"
    return _apply(request_id, updates)


@router.post(
    "/household/requests/{request_id}/cancel",
    response_model=RequestResponse,
    summary="No longer needed",
)
async def cancel_request(request_id: str, body: ActorBody) -> RequestResponse:
    _require_writer(body.actor_token)
    node = _load_request(request_id)
    return _apply(request_id, {"status": _advance_status(node.get("status", "open"), "cancel"), "cancelled_at": _now()})


@router.post(
    "/household/requests/{request_id}/pay",
    response_model=RequestResponse,
    summary="Mark the outside-resource cost as settled",
)
async def pay_request(request_id: str, body: ActorBody) -> RequestResponse:
    actor = _require_writer(body.actor_token)
    node = _load_request(request_id)
    if node.get("cost_status") not in ("recorded", "paid"):
        raise HTTPException(status_code=400, detail="this request has no recorded cost to settle")
    return _apply(request_id, {
        "cost_status": "paid",
        "paid_by": actor.get("id", ""),
        "paid_by_name": actor.get("name", ""),
        "paid_at": _now(),
    })


# --------------------------------------------------------------------------
# Gatherings & votes — a resident raises a question to an audience; everyone
# it reaches answers (and may change their answer at any time); the field sees
# every answer with its name and the live tally. An event-kind question also
# carries a place, a moment, and a status. (household-membrane.form: gathering.)
#
# Two decisions run on the Form kernel, value-identical Python the fallback:
# who a question is VISIBLE to (the audience predicate) and how many HEADS one
# answer is worth (yes-plus-one = 2). The carrier does only I/O and the fold.
# --------------------------------------------------------------------------
_GATHERING_TYPE = "household_gathering"
_GROUPS = {"staff", "resident", "friend"}


def _gathering_visible_k(akind: str, aval: str, author: str, viewer: str, vrole: str) -> int:
    """Value-identical fallback for endpoint_gathering_visible.fk."""
    if viewer == author:
        return 1
    if akind == "everyone":
        return 1
    if akind == "person":
        return 1 if viewer == aval else 0
    if akind == "group":
        if aval == "friend":
            return 1
        return 1 if aval == vrole else 0
    return 0


def _gathering_visible(akind: str, aval: str, author: str, viewer: str, vrole: str) -> bool:
    """The audience predicate (household-membrane.form: visible-to) — on the
    Form kernel (endpoint_gathering_visible.fk), Python the value-identical
    fallback. A cell sees a question when it authored it, when it's for
    everyone, when it's named (person), or when its group matches (friend =
    any member; resident/staff = role)."""
    akind, aval, author, viewer, vrole = (str(x or "") for x in (akind, aval, author, viewer, vrole))
    val, _runtime = serve_via_kernel(
        "endpoint_gathering_visible.fk",
        bindings={"akind": akind, "aval": aval, "author": author, "viewer": viewer, "vrole": vrole},
        fallback=lambda: _gathering_visible_k(akind, aval, author, viewer, vrole),
        parse=int,
    )
    return bool(val)


def _head_value_k(choice: str) -> int:
    """Value-identical fallback for endpoint_gathering_head_value.fk."""
    if choice == "yes-plus-one":
        return 2
    if choice == "yes":
        return 1
    return 0


def _head_value(choice: str) -> int:
    """How many heads one answer is worth (yes-plus-one = 2) — on the Form
    kernel (endpoint_gathering_head_value.fk), Python the value-identical
    fallback. (household-membrane.form: tally.)"""
    val, _runtime = serve_via_kernel(
        "endpoint_gathering_head_value.fk",
        bindings={"choice": choice},
        fallback=lambda: _head_value_k(choice),
        parse=int,
    )
    return int(val)


class GatheringCreate(BaseModel):
    actor_token: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=400)
    audience_kind: Literal["person", "group", "everyone"] = "everyone"
    audience_value: str = Field(default="", max_length=120)   # member id | group name | ""
    kind: Literal["poll", "event"] = "poll"
    where: str | None = Field(default=None, max_length=120)   # event place (a cell name)
    when_text: str | None = Field(default=None, max_length=120)  # the event's moment, human text


class AnswerBody(BaseModel):
    actor_token: str = Field(min_length=1)
    choice: Literal["interested", "yes", "no", "yes-plus-one"]


class Tally(BaseModel):
    interested: int = 0
    yes: int = 0
    no: int = 0
    yes_plus_one: int = 0
    heads: int = 0                  # who is actually coming: yes + 2·yes-plus-one
    voters: int = 0


class VoteOut(BaseModel):
    voter_name: str
    choice: str


class GatheringResponse(BaseModel):
    id: str
    text: str
    author_id: str
    author_name: str
    audience_kind: str
    audience_value: str
    kind: str
    status: str | None = None       # event: proposed | confirmed | delayed
    where: str | None = None
    when_text: str | None = None
    raised_at: str
    my_choice: str | None = None    # the viewer's current answer
    tally: Tally
    votes: list[VoteOut]            # every answer with its name — open to all here


def _responses(node: dict) -> list[dict]:
    raw = node.get("responses_json")
    if not raw:
        return []
    try:
        items = json.loads(raw)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _tally_of(responses: list[dict]) -> Tally:
    counts = {"interested": 0, "yes": 0, "no": 0, "yes-plus-one": 0}
    heads = 0
    for r in responses:
        c = r.get("choice", "")
        if c in counts:
            counts[c] += 1
        heads += _head_value(c)
    return Tally(
        interested=counts["interested"], yes=counts["yes"], no=counts["no"],
        yes_plus_one=counts["yes-plus-one"], heads=heads, voters=len(responses),
    )


def _node_to_gathering(node: dict, viewer_id: str) -> GatheringResponse:
    responses = _responses(node)
    mine = next((r.get("choice") for r in responses if r.get("voter_id") == viewer_id), None)
    return GatheringResponse(
        id=node.get("id", ""),
        text=node.get("text", "") or node.get("description", ""),
        author_id=str(node.get("author_id") or ""),
        author_name=str(node.get("author_name") or ""),
        audience_kind=node.get("audience_kind", "everyone"),
        audience_value=str(node.get("audience_value") or ""),
        kind=node.get("kind", "poll"),
        status=(node.get("status") or None),
        where=(node.get("where") or None),
        when_text=(node.get("when_text") or None),
        raised_at=node.get("created_at", "") or node.get("observed_at", ""),
        my_choice=mine,
        tally=_tally_of(responses),
        votes=[VoteOut(voter_name=str(r.get("voter_name") or ""), choice=str(r.get("choice") or "")) for r in responses],
    )


def _load_gathering(gathering_id: str) -> dict:
    node = graph_service.get_node(gathering_id)
    if not node or node.get("type") != _GATHERING_TYPE:
        raise HTTPException(status_code=404, detail=f"gathering {gathering_id!r} not found")
    return node


@router.post(
    "/household/gatherings",
    response_model=GatheringResponse,
    status_code=201,
    summary="Raise a question or event to an audience (residents)",
)
async def create_gathering(body: GatheringCreate) -> GatheringResponse:
    actor = _require_writer(body.actor_token)
    if actor.get("role") != "resident":
        raise HTTPException(status_code=403, detail="only a resident raises a gathering")
    if body.audience_kind == "group" and body.audience_value not in _GROUPS:
        raise HTTPException(status_code=400, detail="group must be staff, resident, or friend")
    gid = f"gathering-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    created = _now()
    properties: dict[str, Any] = {
        "text": body.text,
        "author_id": actor.get("id", ""),
        "author_name": actor.get("name", ""),
        "audience_kind": body.audience_kind,
        "audience_value": body.audience_value or "",
        "kind": body.kind,
        "responses_json": "[]",
        "created_at": created,
        "updated_at": created,
    }
    if body.kind == "event":
        properties["status"] = "proposed"
        properties["where"] = body.where or ""
        properties["when_text"] = body.when_text or ""
    node = graph_service.create_node(
        id=gid, type=_GATHERING_TYPE, name=body.text[:120],
        description=body.text, properties=properties,
    )
    return _node_to_gathering(node, actor.get("id", ""))


@router.get(
    "/household/gatherings",
    response_model=list[GatheringResponse],
    summary="Questions and events visible to you, each with its live tally",
)
async def list_gatherings(token: str = Query(..., min_length=1)) -> list[GatheringResponse]:
    viewer = _member_by_token(token)
    if not viewer:
        raise HTTPException(status_code=401, detail="register or open your invite link first")
    vid = viewer.get("id", "")
    vrole = viewer.get("role", "member")
    try:
        response = graph_service.list_nodes(type=_GATHERING_TYPE, limit=500)
        nodes = response.get("items", []) if isinstance(response, dict) else (response or [])
    except Exception:
        nodes = []
    out: list[GatheringResponse] = []
    for n in nodes:
        if n.get("type") != _GATHERING_TYPE:
            continue
        if not _gathering_visible(
            n.get("audience_kind", "everyone"), _s(n.get("audience_value")),
            _s(n.get("author_id")), vid, vrole,
        ):
            continue
        out.append(_node_to_gathering(n, vid))
    out.sort(key=lambda g: g.raised_at, reverse=True)
    return out


@router.post(
    "/household/gatherings/{gathering_id}/answer",
    response_model=GatheringResponse,
    summary="Answer — or change your answer to — a question that reached you",
)
async def answer_gathering(gathering_id: str, body: AnswerBody) -> GatheringResponse:
    viewer = _member_by_token(body.actor_token)
    if not viewer:
        raise HTTPException(status_code=401, detail="register or open your invite link first")
    node = _load_gathering(gathering_id)
    vid = viewer.get("id", "")
    if not _gathering_visible(
        node.get("audience_kind", "everyone"), _s(node.get("audience_value")),
        _s(node.get("author_id")), vid, viewer.get("role", "member"),
    ):
        raise HTTPException(status_code=403, detail="this question did not reach you")
    responses = [r for r in _responses(node) if r.get("voter_id") != vid]
    responses.append({
        "voter_id": vid,
        "voter_name": viewer.get("name", ""),
        "choice": body.choice,
        "changed_at": _now(),
    })
    updated = graph_service.update_node(
        gathering_id,
        properties={"responses_json": json.dumps(responses), "updated_at": _now()},
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"gathering {gathering_id!r} not found")
    return _node_to_gathering(updated, vid)


# --------------------------------------------------------------------------
# Friend events — read from the shared Google Calendar(s), the external
# substrate. The calendar IS the store; we fetch its iCal feed, parse the
# upcoming events, and show them. No parallel event store of our own.
# (household-membrane.form: calendar-port.) Recurrence expansion is the
# next breath; v1 shows the one-off events friends actually post.
# --------------------------------------------------------------------------
_EVENT_WINDOW_DAYS = 120


class EventResponse(BaseModel):
    title: str
    start: str                      # ISO 8601 UTC
    end: str | None = None
    all_day: bool = False
    location: str | None = None
    description: str | None = None
    source: str | None = None       # which calendar it came from


def _calendar_urls() -> list[str]:
    """The shared Google Calendar iCal feeds — config over env, empty until set."""
    raw = os.environ.get("HATI_SUCI_CALENDAR_ICS", "")
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    try:
        cfg = os.path.expanduser("~/.coherence-network/config.json")
        if os.path.exists(cfg):
            with open(cfg) as f:
                extra = (json.load(f) or {}).get("hati_suci_calendars") or []
            urls += [str(u).strip() for u in extra if str(u).strip()]
    except Exception:
        pass
    # de-dupe, preserve order
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def _ical_unfold(text: str) -> list[str]:
    """RFC 5545 line unfolding — continuation lines begin with space/tab."""
    out: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _ical_unescape(v: str) -> str:
    return (v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def _ical_is_allday_k(value: str, params: str) -> int:
    """Value-identical fallback for endpoint_ical_allday.fk."""
    return 1 if ("VALUE=DATE" in params or (len(value) == 8 and "T" not in value)) else 0


def _ical_is_allday(value: str, params: str) -> bool:
    """The all-day vs timed-event DECISION — on the Form kernel
    (endpoint_ical_allday.fk), Python the value-identical fallback. The
    date-param recipe the iCal field recipe promised would follow."""
    val, _runtime = serve_via_kernel(
        "endpoint_ical_allday.fk",
        bindings={"value": value, "params": params},
        fallback=lambda: _ical_is_allday_k(value, params),
        parse=int,
    )
    return bool(val)


def _parse_ical_dt(value: str, params: str) -> tuple[datetime | None, bool]:
    """An iCal date/datetime → aware UTC datetime + all_day. Handles trailing Z
    (UTC), floating/TZID (read as UTC — enough to sort and show the day), and
    VALUE=DATE all-day. The all-day choice runs on the Form kernel; strptime
    stays carrier (parsing an external format's date into a value)."""
    v = value.strip()
    all_day = _ical_is_allday(v, params)
    try:
        if all_day:
            return datetime.strptime(v[:8], "%Y%m%d").replace(tzinfo=timezone.utc), True
        return datetime.strptime(v[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc), False
    except ValueError:
        return None, False


def _ical_field_py(line: str, name: str) -> str:
    """Value-identical fallback for endpoint_ical_field.fk — given one
    unfolded iCal line and a field name, the value if the line carries that
    field (handling the NAME[;params]:value shape), else ''."""
    colon = line.find(":")
    semi = line.find(";")
    if colon < 0:
        end = -1
    elif semi < 0 or semi >= colon:
        end = colon
    else:
        end = semi
    if end < 0 or line[:end] != name:
        return ""
    return line[colon + 1:]


def _ical_field(line: str, name: str) -> str:
    """The per-line iCal parsing DECISION + extraction — on the Form kernel
    (endpoint_ical_field.fk), Python the value-identical fallback. The
    first piece of the parser to leave the if-tree and execute as Form; the
    date-param + whole-text recipes follow."""
    val, _runtime = serve_via_kernel(
        "endpoint_ical_field.fk",
        bindings={"line": line, "name": name},
        fallback=lambda: _ical_field_py(line, name),
        parse=str,
    )
    return val


def _parse_ical_events(text: str, source: str) -> list[dict]:
    events: list[dict] = []
    cur: dict | None = None
    for line in _ical_unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {"source": source}
        elif line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            # text fields: the parse DECISION + extraction run as a Form recipe
            title = _ical_field(line, "SUMMARY")
            location = _ical_field(line, "LOCATION")
            description = _ical_field(line, "DESCRIPTION")
            if title:
                cur["title"] = _ical_unescape(title)
            elif location:
                cur["location"] = _ical_unescape(location)
            elif description:
                cur["description"] = _ical_unescape(description)
            else:
                # date / recurrence keep their param-handling in Python — the
                # next recipe to migrate (the param + date logic)
                key, val = line.split(":", 1)
                name = key.split(";", 1)[0].upper()
                if name == "DTSTART":
                    dt, ad = _parse_ical_dt(val, key)
                    if dt:
                        cur["start"], cur["all_day"] = dt, ad
                elif name == "DTEND":
                    dt, _ = _parse_ical_dt(val, key)
                    if dt:
                        cur["end"] = dt
                elif name == "RRULE":
                    cur["recurring"] = True
    return events


@router.get(
    "/household/events",
    response_model=list[EventResponse],
    summary="Upcoming friend events, read from the shared Google Calendar(s)",
)
async def list_events(limit: int = Query(default=50, ge=1, le=200)) -> list[EventResponse]:
    urls = _calendar_urls()
    if not urls:
        return []
    now = datetime.now(timezone.utc)
    floor, horizon = now - timedelta(hours=12), now + timedelta(days=_EVENT_WINDOW_DAYS)
    out: list[EventResponse] = []
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        for url in urls:
            try:
                r = await client.get(url)
                if r.status_code != 200:
                    continue
                for ev in _parse_ical_events(r.text, url):
                    start = ev.get("start")
                    # v1: one-off upcoming events; recurrence expansion is the next breath
                    if start and not ev.get("recurring") and floor <= start <= horizon:
                        out.append(EventResponse(
                            title=ev.get("title", "(untitled)"),
                            start=start.isoformat(),
                            end=ev["end"].isoformat() if ev.get("end") else None,
                            all_day=bool(ev.get("all_day")),
                            location=ev.get("location"),
                            description=(ev.get("description") or "")[:500] or None,
                            source=ev.get("source"),
                        ))
            except Exception:
                continue
    out.sort(key=lambda e: e.start)
    return out[:limit]
