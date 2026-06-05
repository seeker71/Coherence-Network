"""Household — the resident-service nervous system for a Light Hub.

Residents signal a need (food, laundry, a ride, a repair, a room readied);
the staff see the request, acknowledge it, and complete it — everyone
watching the same open board, no secrets. When a request needs something
bought outside (detergent, a part, groceries), the cost rides along on the
request and can be marked settled, so the small money that has to move
stays as visible as the care.

This is the first physical surface of the network's living economy: the
resonance board (lc-offering) and the visible membrane (lc-economy) made
operational for a real residence. Identity is light on purpose — a member
is a name + a role (resident or staff) + a language — so registering is as
easy as walking in. Backed by the same living graph that holds concepts,
offerings, and contributors.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import graph_service

router = APIRouter()


MemberRole = Literal["resident", "staff"]
RequestKind = Literal[
    "food", "laundry", "cleaning", "ride", "repair", "room", "supplies", "other"
]
RequestStatus = Literal["open", "acknowledged", "in_progress", "completed", "cancelled"]
CostStatus = Literal["none", "recorded", "paid"]

_MEMBER_TYPE = "household_member"
_REQUEST_TYPE = "service_request"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Members — light identity: a name, a role, a language. No password, no gate.
# --------------------------------------------------------------------------


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: MemberRole
    locale: str = Field(default="en", max_length=8, description="UI language: en, id, …")


class MemberResponse(BaseModel):
    id: str
    name: str
    role: str
    locale: str
    created_at: str


def _node_to_member(node: dict) -> MemberResponse:
    return MemberResponse(
        id=node.get("id", ""),
        name=node.get("name", "") or node.get("member_name", ""),
        role=node.get("role", "resident"),
        locale=node.get("locale", "en") or "en",
        created_at=node.get("created_at", "") or node.get("observed_at", ""),
    )


def _get_member(member_id: str) -> dict | None:
    node = graph_service.get_node(member_id)
    if node and node.get("type") == _MEMBER_TYPE:
        return node
    return None


def _member_name(member_id: str | None) -> str:
    if not member_id:
        return ""
    node = _get_member(member_id)
    return node.get("name", "") if node else ""


@router.post(
    "/household/members",
    response_model=MemberResponse,
    status_code=201,
    summary="Register a resident or staff member (light identity)",
)
async def create_member(body: MemberCreate) -> MemberResponse:
    member_id = f"member-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    created_at = _now()
    properties: dict[str, Any] = {
        "role": body.role,
        "locale": body.locale or "en",
        "created_at": created_at,
    }
    node = graph_service.create_node(
        id=member_id,
        type=_MEMBER_TYPE,
        name=body.name,
        description=f"{body.role} of the household",
        properties=properties,
    )
    return _node_to_member(node)


@router.get(
    "/household/members",
    response_model=list[MemberResponse],
    summary="Everyone in the household — residents and staff",
)
async def list_members(role: str | None = Query(default=None)) -> list[MemberResponse]:
    try:
        response = graph_service.list_nodes(type=_MEMBER_TYPE, limit=500)
        nodes = response.get("items", []) if isinstance(response, dict) else (response or [])
    except Exception:
        nodes = []
    members = [n for n in nodes if n.get("type") == _MEMBER_TYPE]
    if role:
        members = [n for n in members if n.get("role") == role]
    members.sort(key=lambda n: n.get("created_at", ""))
    return [_node_to_member(n) for n in members]


# --------------------------------------------------------------------------
# Requests — the open board. Added → acknowledged → in_progress → completed.
# --------------------------------------------------------------------------


class RequestCreate(BaseModel):
    requester_id: str = Field(min_length=1)
    kind: RequestKind
    detail: str = Field(min_length=1, max_length=2000, description="What is needed")
    location: str | None = Field(default=None, max_length=200, description="Where (which house, the garden, …)")
    when_text: str | None = Field(default=None, max_length=200, description="When it's needed, in plain words")


class ActorBody(BaseModel):
    actor_id: str = Field(min_length=1, description="The member performing this action")


class CompleteBody(ActorBody):
    cost_amount: float | None = Field(default=None, ge=0, description="Cost of any outside resources")
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
    acknowledged_by: str | None = None
    acknowledged_by_name: str | None = None
    acknowledged_at: str | None = None
    started_at: str | None = None
    completed_by: str | None = None
    completed_by_name: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None
    cost_amount: float | None = None
    cost_currency: str = "IDR"
    cost_note: str | None = None
    cost_status: str = "none"
    paid_by: str | None = None
    paid_by_name: str | None = None
    paid_at: str | None = None
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
        acknowledged_by=_s(node.get("acknowledged_by")),
        acknowledged_by_name=_s(node.get("acknowledged_by_name")),
        acknowledged_at=_s(node.get("acknowledged_at")),
        started_at=_s(node.get("started_at")),
        completed_by=_s(node.get("completed_by")),
        completed_by_name=_s(node.get("completed_by_name")),
        completed_at=_s(node.get("completed_at")),
        cancelled_at=_s(node.get("cancelled_at")),
        cost_amount=cost_amount,
        cost_currency=node.get("cost_currency", "IDR") or "IDR",
        cost_note=_s(node.get("cost_note")),
        cost_status=node.get("cost_status", "none") or "none",
        paid_by=_s(node.get("paid_by")),
        paid_by_name=_s(node.get("paid_by_name")),
        paid_at=_s(node.get("paid_at")),
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
    summary="Ask the field for something (food, laundry, a ride, a repair…)",
)
async def create_request(body: RequestCreate) -> RequestResponse:
    requester = _get_member(body.requester_id)
    if not requester:
        raise HTTPException(status_code=400, detail=f"member {body.requester_id!r} not found")
    request_id = f"request-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    created_at = _now()
    properties: dict[str, Any] = {
        "kind": body.kind,
        "detail": body.detail,
        "location": body.location or "",
        "when_text": body.when_text or "",
        "status": "open",
        "requester_id": body.requester_id,
        "requester_name": requester.get("name", ""),
        "cost_status": "none",
        "cost_currency": "IDR",
        "created_at": created_at,
        "updated_at": created_at,
    }
    node = graph_service.create_node(
        id=request_id,
        type=_REQUEST_TYPE,
        name=body.detail[:120],
        description=body.detail,
        properties=properties,
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
    _load_request(request_id)
    return _apply(request_id, {
        "status": "acknowledged",
        "acknowledged_by": body.actor_id,
        "acknowledged_by_name": _member_name(body.actor_id),
        "acknowledged_at": _now(),
    })


@router.post(
    "/household/requests/{request_id}/start",
    response_model=RequestResponse,
    summary="Work on it has begun",
)
async def start_request(request_id: str, body: ActorBody) -> RequestResponse:
    node = _load_request(request_id)
    updates: dict[str, Any] = {"status": "in_progress", "started_at": _now()}
    if not _s(node.get("acknowledged_by")):
        updates["acknowledged_by"] = body.actor_id
        updates["acknowledged_by_name"] = _member_name(body.actor_id)
        updates["acknowledged_at"] = _now()
    return _apply(request_id, updates)


@router.post(
    "/household/requests/{request_id}/complete",
    response_model=RequestResponse,
    summary="It's done — optionally recording the cost of any outside resources",
)
async def complete_request(request_id: str, body: CompleteBody) -> RequestResponse:
    _load_request(request_id)
    updates: dict[str, Any] = {
        "status": "completed",
        "completed_by": body.actor_id,
        "completed_by_name": _member_name(body.actor_id),
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
    _load_request(request_id)
    return _apply(request_id, {"status": "cancelled", "cancelled_at": _now()})


@router.post(
    "/household/requests/{request_id}/pay",
    response_model=RequestResponse,
    summary="Mark the outside-resource cost as settled",
)
async def pay_request(request_id: str, body: ActorBody) -> RequestResponse:
    node = _load_request(request_id)
    if node.get("cost_status") not in ("recorded", "paid"):
        raise HTTPException(status_code=400, detail="this request has no recorded cost to settle")
    return _apply(request_id, {
        "cost_status": "paid",
        "paid_by": body.actor_id,
        "paid_by_name": _member_name(body.actor_id),
        "paid_at": _now(),
    })
