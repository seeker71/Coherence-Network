"""Offerings — services and belongings woven into the network.

When a contributor brings a service (a craft, a presence, a daily
practice) or a belonging (a space, a tool, a thing they steward) into
the network, the offering becomes a node in the same living graph that
holds concepts, ideas, specs, and contributors.

The body keeps memory of what is offered, by whom, where, and on what
terms. The contributor keeps sovereignty over what they bring; the
network simply witnesses it and lets it be findable by resonance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.services import graph_service

router = APIRouter()


OfferingKind = Literal["service", "belonging", "space", "skill"]
ExchangeMode = Literal["gift", "exchange", "subscription", "by-resonance"]


class OfferingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: OfferingKind = Field(description="What kind of offering this is")
    description: str = Field(min_length=10, max_length=5000)
    location: str | None = Field(default=None, max_length=200, description="City / region / coordinates / 'wherever the body is'")
    exchange: ExchangeMode = Field(default="by-resonance")
    terms: str | None = Field(default=None, max_length=2000, description="Free text about how the offering moves — pricing, availability, limits")
    contact_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr
    image_urls: list[str] = Field(default_factory=list, max_length=10)
    contributor_id: str | None = Field(default=None, description="Existing contributor ID if known")


class OfferingResponse(BaseModel):
    id: str
    title: str
    kind: str
    description: str
    location: str | None = None
    exchange: str
    terms: str | None = None
    contact_name: str
    contact_email: str
    image_urls: list[str] = Field(default_factory=list)
    contributor_id: str | None = None
    created_at: str


_OFFERING_MARKER = "offering_kind"


def _node_to_offering(node: dict) -> OfferingResponse:
    return OfferingResponse(
        id=node.get("id", ""),
        title=node.get("name", "") or node.get("title", ""),
        kind=node.get(_OFFERING_MARKER, ""),
        description=node.get("description", ""),
        location=node.get("location"),
        exchange=node.get("exchange", "by-resonance"),
        terms=node.get("terms"),
        contact_name=node.get("contact_name", ""),
        contact_email=node.get("contact_email", ""),
        image_urls=list(node.get("image_urls") or []),
        contributor_id=node.get("contributor_id"),
        created_at=node.get("created_at", "") or node.get("observed_at", ""),
    )


def _is_offering(node: dict) -> bool:
    return node.get("type") == "offering" and bool(node.get(_OFFERING_MARKER))


@router.post(
    "/offerings",
    response_model=OfferingResponse,
    status_code=201,
    summary="Bring a service or belonging into the body",
    description=(
        "Anyone can register an offering — a service they provide (a craft, a "
        "presence, a practice) or a belonging they steward (a space, a tool, "
        "land, a thing). The offering becomes a node in the living graph; "
        "the contributor keeps full sovereignty over what they bring."
    ),
)
async def create_offering(body: OfferingCreate) -> OfferingResponse:
    offering_id = (
        f"offering-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    )
    created_at = datetime.now(timezone.utc).isoformat()

    properties: dict[str, Any] = {
        _OFFERING_MARKER: body.kind,
        "title": body.title,
        "description": body.description,
        "location": body.location or "",
        "exchange": body.exchange,
        "terms": body.terms or "",
        "contact_name": body.contact_name,
        "contact_email": body.contact_email,
        "image_urls": list(body.image_urls or []),
        "contributor_id": body.contributor_id or "",
        "created_at": created_at,
    }

    node = graph_service.create_node(
        id=offering_id,
        type="offering",
        name=body.title,
        description=body.description,
        properties=properties,
    )

    if body.contributor_id:
        try:
            graph_service.create_edge(
                from_id=body.contributor_id,
                to_id=offering_id,
                type="offers",
                properties={"created_at": created_at},
            )
        except Exception:
            # A missing contributor edge is a soft signal, not a failure.
            pass

    return _node_to_offering(node)


@router.get(
    "/offerings",
    response_model=list[OfferingResponse],
    summary="List offerings the body is currently holding",
)
async def list_offerings(
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[OfferingResponse]:
    try:
        response = graph_service.list_nodes(type="offering", limit=200)
        nodes = (
            response.get("items", [])
            if isinstance(response, dict)
            else (response or [])
        )
    except Exception:
        nodes = []

    offerings = [n for n in nodes if _is_offering(n)]
    if kind:
        offerings = [n for n in offerings if n.get(_OFFERING_MARKER) == kind]

    offerings.sort(key=lambda n: n.get("created_at", ""), reverse=True)
    return [_node_to_offering(n) for n in offerings[:limit]]


@router.get(
    "/offerings/{offering_id}",
    response_model=OfferingResponse,
    summary="A single offering in full",
)
async def get_offering(offering_id: str) -> OfferingResponse:
    node = graph_service.get_node(offering_id)
    if not node or not _is_offering(node):
        raise HTTPException(status_code=404, detail=f"offering {offering_id!r} not found")
    return _node_to_offering(node)
