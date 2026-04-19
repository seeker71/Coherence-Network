"""Gatherings router — a presence carries the events where it happens.

An artist has ceremonies, a festival has a next gathering, a sanctuary
has an upcoming retreat. Anyone who knows about one can add it to a
presence page, no gate — the living edge of the identity surfaces here.

Storage: an ``event`` node (properties carry when/where/url/note/added_by)
plus a ``contributes-to`` edge from the identity to the event with
``{kind: "event"}``. The edge type is the same one the resolver uses
for albums, videos, books — every kind of thing a presence puts into
the world — which keeps the discography+gatherings lineage uniform and
the /people/[id] feed simple.

This endpoint pairs the two operations so the web doesn't have to
juggle node-then-edge (and so the edge-type validation on the public
graph router stays strict about Spec 169 canonical types; the service
layer is free to compose larger vocabulary edges internally).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import graph_service

router = APIRouter()


class GatheringCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    when: str | None = Field(None, max_length=120)
    where: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)
    added_by: str | None = Field(None, max_length=255)
    added_by_name: str | None = Field(None, max_length=120)


def _slugify(s: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]
    return slug or "gathering"


def _event_id(identity_id: str, title: str, when: str | None, added_by: str | None) -> str:
    seed = f"{identity_id}|{title}|{when or ''}|{added_by or ''}".lower()
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"event:{_slugify(title)}-{digest}"


@router.post(
    "/presences/{identity_id}/gatherings",
    status_code=201,
    summary="Add a gathering (event) to a presence page",
)
async def add_gathering(identity_id: str, body: GatheringCreate) -> dict[str, Any]:
    identity = graph_service.get_node(identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail=f"Presence '{identity_id}' not found")

    title = body.title.strip()
    node_id = _event_id(identity_id, title, body.when, body.added_by)
    existing = graph_service.get_node(node_id)
    if existing:
        event_node = existing
        created = False
    else:
        properties: dict[str, Any] = {
            "when": body.when.strip() if body.when else None,
            "where": body.where.strip() if body.where else None,
            "url": body.url.strip() if body.url else None,
            "note": body.note.strip() if body.note else None,
            "added_by": body.added_by or None,
            "added_by_name": body.added_by_name or None,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        properties = {k: v for k, v in properties.items() if v}
        event_node = graph_service.create_node(
            id=node_id,
            type="event",
            name=title,
            description=title,
            properties=properties,
        )

    edge_result = graph_service.create_edge_strict(
        from_id=identity_id,
        to_id=node_id,
        type="contributes-to",
        properties={"kind": "event"},
        strength=1.0,
        created_by=body.added_by or "gatherings_endpoint",
    )
    edge_existed = edge_result.get("error") == "edge_exists"

    return {
        "event": event_node,
        "created": created if not existing else False,
        "edge": edge_result if not edge_existed else None,
        "edge_existed": edge_existed,
    }
