"""Gatherings router — a presence carries the events where it happens.

An artist has ceremonies, a festival has a next gathering, a sanctuary
has an upcoming retreat. Anyone who knows about one can add it to a
presence page, no gate — the living edge of the identity surfaces here.

A gathering is rarely a single person's alone. Ceremony music is
co-led; a workshop has a hosting collective; a retreat has a land
that holds it. So a gathering stitches into several presences at
once: every co-host, the hosting collective, and the primary
identity whose page the visitor used to add the gathering. Each
gets a ``contributes-to`` edge to the event node with a ``role``
so the page can display *why* that presence connects to the event.

Storage:
  · event node — type="event", properties {when, where, url, note,
    added_by, added_by_name, added_at}
  · edges — contributes-to from every host (primary, co-led, hosting
    community) to the event, each carrying {kind: "event", role:
    "primary" | "co-leading" | "hosting"}

Co-host / host names that aren't yet presence nodes are created on
the fly via the inspired-by resolver so URL inputs become rich
identities (with portrait, presences, discography) and plain names
get a minimal contributor/community node held open for them to
claim later. The same pattern the inspired-by gesture already uses.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import graph_service, inspired_by_service


router = APIRouter()


class GatheringCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    when: str | None = Field(None, max_length=120)
    where: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)
    added_by: str | None = Field(None, max_length=255)
    added_by_name: str | None = Field(None, max_length=120)
    # Names or URLs for humans co-leading the gathering alongside the
    # primary identity. Each resolves to its own presence node (via the
    # inspired-by resolver). Plain text like "Robin" creates a minimal
    # contributor placeholder; a URL builds a rich identity.
    co_led_with: list[str] = Field(default_factory=list, max_length=8)
    # One name or URL for the collective / community hosting the
    # gathering (e.g. Boulder Ecstatic Dance). Resolves to a community
    # or contributor node depending on what the URL inference returns.
    hosted_by: str | None = Field(None, max_length=200)


def _slugify(s: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]
    return slug or "gathering"


def _event_id(identity_id: str, title: str, when: str | None, added_by: str | None) -> str:
    seed = f"{identity_id}|{title}|{when or ''}|{added_by or ''}".lower()
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"event:{_slugify(title)}-{digest}"


def _placeholder_person_id(name: str) -> str:
    """Mint a stable node id for a named-only person. Used when the
    input isn't a URL and the resolver can't discover them online —
    the page still holds space for them, and they can be claimed."""
    digest = hashlib.sha256(name.lower().strip().encode("utf-8")).hexdigest()[:12]
    return f"contributor:{_slugify(name)}-{digest}"


def _looks_like_url(text: str) -> bool:
    """Conservative URL detector — no whitespace, has a dot, has a host."""
    t = text.strip()
    if not t or " " in t or "\n" in t:
        return False
    parsed = urlparse(t if "://" in t else f"https://{t}")
    return bool(parsed.netloc) and "." in parsed.netloc


def _resolve_host(name_or_url: str) -> dict[str, Any] | None:
    """Resolve a free-text input into a presence node for a gathering.

    URLs go through the full resolver — fetch the page, parse OG and
    JSON-LD, mint a rich identity with presences and creations.

    Plain names do NOT search the web. A single first name ("Robin",
    "Aly") on a search engine returns wildlife articles or bank login
    pages — random strangers bound into the graph with full confidence.
    That's worse than saying nothing: it poisons the organism with
    false identity, and any visitor who clicks the chip lands on an
    unrelated site. So bare names mint a local-only placeholder node
    with the typed name and a claim flag — no canonical_url, no
    speculative image, no pretend-presence. The gathering still
    threads through that name; when the real person arrives (or
    someone who knows pastes their URL), the placeholder can be
    merged or replaced.
    """
    text = (name_or_url or "").strip()
    if not text:
        return None

    if _looks_like_url(text):
        resolved = inspired_by_service.resolve(text)
        if resolved is not None:
            identity_node, _created, _creations = inspired_by_service.ensure_identity(resolved)
            return identity_node
        # URL fetch failed — treat as placeholder so the link isn't lost.

    placeholder_id = _placeholder_person_id(text)
    existing = graph_service.get_node(placeholder_id)
    if existing:
        return existing
    return graph_service.create_node(
        id=placeholder_id,
        type="contributor",
        name=text,
        description=f"Held open for {text} — awaiting a URL or a claim.",
        properties={
            "claimed": False,
            "contributor_type": "HUMAN",
            "author_display_name": text,
            # No canonical_url on purpose. The /people/[id] page will
            # render the warm garden view for placeholders rather than
            # the presence page, which keeps unverified names visibly
            # held-open rather than passing as full identities.
        },
    )


def _link_host(event_id: str, host_node: dict[str, Any], role: str, created_by: str) -> None:
    graph_service.create_edge_strict(
        from_id=host_node["id"],
        to_id=event_id,
        type="contributes-to",
        properties={"kind": "event", "role": role},
        strength=1.0,
        created_by=created_by,
    )


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
        created = True

    created_by = body.added_by or "gatherings_endpoint"

    # Primary host — the identity whose page this was added from.
    _link_host(node_id, identity, role="primary", created_by=created_by)

    # The visitor who placed this gathering in the graph gets their
    # own contributes-to edge to the event with role="added-by". That
    # way their /people/[id] footprint carries what they've surfaced
    # — and when they later step in and name themselves, the thread
    # back to this gathering is already real.
    if body.added_by:
        added_by_node = graph_service.get_node(body.added_by)
        if added_by_node and body.added_by != identity_id:
            _link_host(node_id, added_by_node, role="added-by", created_by=created_by)

    # Co-leaders — each a real presence, linked with role: "co-leading".
    co_hosts: list[dict[str, Any]] = []
    for raw in body.co_led_with:
        host = _resolve_host(raw)
        if not host or host["id"] == identity_id:
            continue
        _link_host(node_id, host, role="co-leading", created_by=created_by)
        co_hosts.append(host)

    # Hosting collective — resolved and linked with role: "hosting".
    hosting_collective: dict[str, Any] | None = None
    if body.hosted_by:
        hosting_collective = _resolve_host(body.hosted_by)
        if hosting_collective and hosting_collective["id"] != identity_id:
            _link_host(node_id, hosting_collective, role="hosting", created_by=created_by)

    return {
        "event": event_node,
        "created": created,
        "co_hosts": co_hosts,
        "hosting_collective": hosting_collective,
    }
