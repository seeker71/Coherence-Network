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

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import graph_service

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
async def whoami(token: str = Query(min_length=1)) -> MemberPrivate:
    node = _member_by_token(token)
    if not node:
        raise HTTPException(status_code=404, detail="unknown token")
    if node.get("status") == "invited":
        node = graph_service.update_node(node["id"], properties={"status": "active"}) or node
    return _member_private(node)


@router.get(
    "/household/members",
    response_model=list[MemberPublic],
    summary="Everyone in the household — public view, no tokens or phones",
)
async def list_members(role: str | None = Query(default=None)) -> list[MemberPublic]:
    members = _all_members()
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


class RequestCreate(BaseModel):
    actor_token: str = Field(min_length=1)
    kind: RequestKind
    detail: str = Field(min_length=1, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    when_text: str | None = Field(default=None, max_length=200)


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


def _node_to_request(node: dict) -> RequestResponse:
    raw_cost = node.get("cost_amount")
    cost_amount = float(raw_cost) if isinstance(raw_cost, (int, float)) else None
    return RequestResponse(
        id=node.get("id", ""),
        kind=node.get("kind", "other"),
        detail=node.get("detail", "") or node.get("description", ""),
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
    _load_request(request_id)
    return _apply(request_id, {
        "status": "acknowledged",
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
    updates: dict[str, Any] = {"status": "in_progress", "started_at": _now()}
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
    _load_request(request_id)
    updates: dict[str, Any] = {
        "status": "completed",
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
    _load_request(request_id)
    return _apply(request_id, {"status": "cancelled", "cancelled_at": _now()})


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
