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


# ---------------------------------------------------------------------------
# Meeting-context — "I was met at this gathering"
#
# Where hosting a gathering is the identity's offering, meeting-at is the
# inverse: the gathering is where someone was *found*. The first humans
# arriving to this network are meeting us at retreats, workshops, land-based
# ceremonies. Encoding the meeting-context lets the body remember the
# threshold a person crossed to get here — and lets the person themselves
# see that context reflected back. The teaching that happened in that room
# often explains why their first reads landed where they did.
# ---------------------------------------------------------------------------


class HostInput(BaseModel):
    """A teacher or presence who held the gathering.

    Name is required — pulling OG titles from websites gives strings like
    'The Official Website of Dr Joe Dispenza' instead of a person's name.
    The caller knows who they met; we respect that by taking the name
    directly. URL is optional and becomes canonical_url on the node —
    clicking links the reader to the person's own presence on the web.
    """
    name: str = Field(..., min_length=1, max_length=120, description="Human name as it should appear, e.g. 'Dr Joe Dispenza'")
    url: str | None = Field(None, max_length=500, description="Canonical URL — the teacher's own site — used for the outbound link")


class MetAtCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Name of the gathering, e.g. 'Joe Dispenza April 2026 Retreat'")
    when: str | None = Field(None, max_length=120, description="Free-text date/range — 'April 2026', '2026-04-18 to 2026-04-25'")
    where: str | None = Field(None, max_length=200, description="Free-text location — 'Aurora, Colorado'")
    url: str | None = Field(None, max_length=500, description="Canonical URL for the gathering, if any")
    teaching_note: str | None = Field(None, max_length=500, description="What was being taught or held — shapes why this meeting mattered")
    hosts: list[HostInput] = Field(
        default_factory=list,
        max_length=8,
        description="Teachers who held the gathering. Each has name + optional URL.",
    )
    resonates_with: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Concept ids (e.g. lc-sensing) whose frequency the gathering's teaching carries",
    )
    added_by: str | None = Field(None, max_length=255, description="Who recorded the meeting (usually the one who was present)")


def _event_id_for_meeting(title: str, when: str | None, where: str | None) -> str:
    """Stable id for a gathering, independent of who attended. Two people
    met at the same retreat should resolve to the same event node so the
    cohort emerges naturally from the graph."""
    seed = f"{title}|{when or ''}|{where or ''}".lower()
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"event:{_slugify(title)}-{digest}"


@router.post(
    "/contributors/{contributor_id}/met-at",
    status_code=201,
    summary="Record that a contributor was met at a gathering",
    description=(
        "Creates (or finds) an event node for the gathering and links the "
        "contributor to it with role='attended'. If `resonates_with` is "
        "provided, the event picks up `resonates-with` edges to those "
        "concepts, making visible *why* the gathering's teaching explains "
        "the person's field-trail."
    ),
)
async def contributor_met_at(contributor_id: str, body: MetAtCreate) -> dict[str, Any]:
    contributor = graph_service.get_node(contributor_id)
    if not contributor:
        # Allow contributor-slug forms without the prefix too
        fallback = graph_service.get_node(f"contributor:{contributor_id}")
        if fallback:
            contributor = fallback
            contributor_id = fallback["id"]
        else:
            raise HTTPException(status_code=404, detail=f"Contributor '{contributor_id}' not found")

    title = body.title.strip()
    event_id = _event_id_for_meeting(title, body.when, body.where)
    existing_event = graph_service.get_node(event_id)
    if existing_event:
        event_node = existing_event
        created = False
    else:
        properties: dict[str, Any] = {
            "when": body.when.strip() if body.when else None,
            "where": body.where.strip() if body.where else None,
            "url": body.url.strip() if body.url else None,
            "teaching_note": body.teaching_note.strip() if body.teaching_note else None,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        properties = {k: v for k, v in properties.items() if v}
        event_node = graph_service.create_node(
            id=event_id,
            type="event",
            name=title,
            description=body.teaching_note or title,
            properties=properties,
        )
        created = True

    created_by = body.added_by or "met_at_endpoint"

    # The contributor's met-at edge — role="attended" keeps this distinct
    # from hosting roles ("primary", "co-leading", "hosting", "added-by")
    # that the main gathering endpoint uses.
    graph_service.create_edge_strict(
        from_id=contributor_id,
        to_id=event_id,
        type="contributes-to",
        properties={"kind": "event", "role": "attended"},
        strength=1.0,
        created_by=created_by,
    )

    # Hosts — teachers who held the gathering. We honor the explicit
    # name the caller provided (OG-scraping gives marketing titles, not
    # person names). URL, when present, becomes canonical_url so
    # clicking the host on /me takes the reader to the teacher's own
    # presence on the web — not a thin internal profile page we don't
    # actively tend.
    hosts: list[dict[str, Any]] = []
    for h in body.hosts:
        name = h.name.strip()
        url = h.url.strip() if h.url else None
        host_id = _placeholder_person_id(name)
        host_node = graph_service.get_node(host_id)
        if host_node:
            # Existing node — if the caller supplies a URL and we didn't
            # have one, add it. Name stays authoritative to what's stored.
            if url and not host_node.get("canonical_url"):
                # Lightweight patch: re-create with merged properties.
                # (The graph_service.create_node path is idempotent by id
                # and updates description/properties on hit.)
                graph_service.create_node(
                    id=host_id,
                    type="contributor",
                    name=host_node.get("name") or name,
                    description=host_node.get("description") or f"Held open for {name} — awaiting a claim.",
                    properties={
                        "claimed": False,
                        "contributor_type": "HUMAN",
                        "author_display_name": host_node.get("name") or name,
                        "canonical_url": url,
                    },
                )
                host_node["canonical_url"] = url
        else:
            host_node = graph_service.create_node(
                id=host_id,
                type="contributor",
                name=name,
                description=f"Held open for {name} — awaiting a claim.",
                properties={
                    "claimed": False,
                    "contributor_type": "HUMAN",
                    "author_display_name": name,
                    **({"canonical_url": url} if url else {}),
                },
            )
        _link_host(event_id, host_node, role="primary", created_by=created_by)
        hosts.append({
            "id": host_node.get("id"),
            "name": host_node.get("name"),
            "canonical_url": host_node.get("canonical_url") or url,
        })

    # Teaching resonance — each concept the gathering's frequency carries.
    # When the person sees the list on /me, they recognise the territory.
    resonances: list[dict[str, Any]] = []
    for cid in body.resonates_with:
        concept_id = cid.strip()
        if not concept_id:
            continue
        concept_node = graph_service.get_node(concept_id)
        if not concept_node:
            continue
        graph_service.create_edge_strict(
            from_id=event_id,
            to_id=concept_id,
            type="resonates-with",
            properties={"kind": "teaching"},
            strength=1.0,
            created_by=created_by,
        )
        resonances.append({"concept_id": concept_id, "name": concept_node.get("name")})

    return {
        "event": event_node,
        "created": created,
        "attendee": {"id": contributor_id, "name": contributor.get("name")},
        "hosts": hosts,
        "resonates_with": resonances,
    }


@router.get(
    "/contributors/{contributor_id}/met-at",
    summary="List the gatherings a contributor was met at",
    description=(
        "Returns each gathering the contributor has an 'attended' edge to, "
        "plus the concepts the gathering's teaching resonates with. This is "
        "what /me and /profile render as 'You arrived via…' / 'Met at…'."
    ),
)
async def contributor_meetings(contributor_id: str) -> dict[str, Any]:
    contributor = graph_service.get_node(contributor_id)
    if not contributor:
        fallback = graph_service.get_node(f"contributor:{contributor_id}")
        if fallback:
            contributor = fallback
            contributor_id = fallback["id"]
        else:
            return {"contributor_id": contributor_id, "meetings": []}

    # Fetch all outgoing contributes-to edges, filter to role=attended,
    # and pull the event node + its resonates-with concepts.
    edges = graph_service.list_edges(from_id=contributor_id, edge_type="contributes-to", limit=100) or {}
    rows = edges.get("items", []) if isinstance(edges, dict) else edges
    meetings: list[dict[str, Any]] = []
    for edge in rows:
        props = edge.get("properties") or {}
        if props.get("role") != "attended":
            continue
        event_id = edge.get("to_id")
        if not event_id:
            continue
        event_node = graph_service.get_node(event_id)
        if not event_node or event_node.get("type") != "event":
            continue
        resonance_edges = graph_service.list_edges(from_id=event_id, edge_type="resonates-with", limit=50) or {}
        resonance_rows = resonance_edges.get("items", []) if isinstance(resonance_edges, dict) else resonance_edges
        resonances: list[dict[str, Any]] = []
        for rn in resonance_rows:
            concept_id = rn.get("to_id")
            if not concept_id:
                continue
            concept_node = graph_service.get_node(concept_id)
            if not concept_node:
                continue
            resonances.append({
                "concept_id": concept_id,
                "name": concept_node.get("name"),
            })
        # Hosts — all inbound contributes-to edges with role=primary.
        host_edges = graph_service.list_edges(to_id=event_id, edge_type="contributes-to", limit=50) or {}
        host_rows = host_edges.get("items", []) if isinstance(host_edges, dict) else host_edges
        hosts: list[dict[str, Any]] = []
        for he in host_rows:
            props = he.get("properties") or {}
            if props.get("role") != "primary":
                continue
            host_id = he.get("from_id")
            if not host_id:
                continue
            host_node = graph_service.get_node(host_id)
            if not host_node:
                continue
            hosts.append({
                "id": host_id,
                "name": host_node.get("name"),
                "canonical_url": host_node.get("canonical_url"),
            })
        # graph_service.get_node spreads properties at top-level, not
        # nested — read directly from the node dict.
        meetings.append({
            "event_id": event_id,
            "title": event_node.get("name"),
            "when": event_node.get("when"),
            "where": event_node.get("where"),
            "url": event_node.get("url"),
            "teaching_note": event_node.get("teaching_note"),
            "hosts": hosts,
            "resonates_with": resonances,
        })

    return {"contributor_id": contributor_id, "meetings": meetings}
