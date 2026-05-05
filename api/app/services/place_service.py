"""Place service — where presences are rooted.

A place is a node in the graph (type="place") with stable slug-based
ids. Two presences typing "Boulder" hit the same node, so the page
can surface co-located presences without grepping free-text location
strings.

Idempotency is the contract: ``ensure_place`` is safe to call from
anywhere, the slug is stable across calls, and ``set_at_place`` upserts
the edge so a presence can shift role from "frequent" to "based"
without minting duplicate edges.

Roles:
  - home       the presence's daily ground
  - based      the presence's primary headquarters / operating ground
  - frequent   shows up here often, not rooted
  - founded    where this presence (community / org / scene) was born

The default is "based" — the most common claim a presence makes.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.services import graph_service


VALID_ROLES: frozenset[str] = frozenset({"home", "based", "frequent", "founded"})


def _slugify(text: str) -> str:
    """Lowercase + hyphen + strip — same shape gatherings.py uses for events."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
    return slug or "place"


def _place_id_for(name: str, region: str | None) -> str:
    """Stable id for a place. When region is given, prefix the slug with
    it so "Boulder, CO" and "Boulder, WA" land on different nodes.
    Without a region, the bare name slug is used — so two presences
    typing "Boulder" with no region collide on the same node, which is
    the desired idempotency for the common case."""
    if region:
        return f"place:{_slugify(region)}-{_slugify(name)}"
    return f"place:{_slugify(name)}"


def ensure_place(
    name: str,
    *,
    region: str | None = None,
    country: str | None = None,
) -> str:
    """Return a place_id, creating the node if missing. Idempotent.

    Two calls with the same (name, region) hit the same id. If the
    node already exists, its country is patched in only when the
    existing node didn't carry one — never overwrites.
    """
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ValueError("place name must be non-empty")

    cleaned_region = (region or "").strip() or None
    cleaned_country = (country or "").strip() or None

    place_id = _place_id_for(cleaned_name, cleaned_region)
    existing = graph_service.get_node(place_id)
    if existing:
        # Patch in country if the caller has one and we don't —
        # update_node merges new keys into existing properties, so
        # this only fills the gap, never overwrites.
        if cleaned_country and not existing.get("country"):
            graph_service.update_node(
                place_id,
                properties={"country": cleaned_country},
            )
        return place_id

    properties: dict[str, Any] = {
        "slug": _slugify(cleaned_name),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if cleaned_region:
        properties["region"] = cleaned_region
    if cleaned_country:
        properties["country"] = cleaned_country

    graph_service.create_node(
        id=place_id,
        type="place",
        name=cleaned_name,
        description=", ".join(p for p in (cleaned_name, cleaned_region, cleaned_country) if p),
        properties=properties,
        phase="earth",
    )
    return place_id


def _normalize_role(role: str | None) -> str:
    """Coerce role to a known value, defaulting to "based"."""
    candidate = (role or "").strip().lower()
    return candidate if candidate in VALID_ROLES else "based"


def _existing_at_place_edge(presence_id: str, place_id: str) -> dict[str, Any] | None:
    """Find any existing at-place edge between presence and place."""
    edges = graph_service.list_edges(
        edge_type="at-place",
        from_id=presence_id,
        to_id=place_id,
        limit=1,
    )
    items = edges.get("items", []) if isinstance(edges, dict) else edges
    return items[0] if items else None


def set_at_place(
    presence_id: str,
    place_or_name: str,
    *,
    role: str = "based",
    since: str | None = None,
) -> dict[str, Any]:
    """Root a presence in a place. Returns the edge + place context.

    `place_or_name` accepts an existing place id (starts with "place:")
    or a free-form name; in the latter case the place is ensured.

    Idempotent on the (presence, place) pair — a second call with a
    different role updates the role rather than minting a new edge.
    """
    presence = graph_service.get_node(presence_id)
    if not presence:
        raise ValueError(f"presence '{presence_id}' not found")

    text = (place_or_name or "").strip()
    if not text:
        raise ValueError("place must be a non-empty name or place_id")

    if text.startswith("place:"):
        place_node = graph_service.get_node(text)
        if not place_node:
            raise ValueError(f"place '{text}' not found")
        place_id = text
        place_name = place_node.get("name") or text
    else:
        place_id = ensure_place(text)
        place_node = graph_service.get_node(place_id)
        place_name = place_node.get("name") if place_node else text

    normalized_role = _normalize_role(role)
    properties: dict[str, Any] = {"role": normalized_role}
    if since:
        properties["since"] = since.strip()

    existing = _existing_at_place_edge(presence_id, place_id)
    if existing:
        # Edge already there — patch the role/since if changed.
        existing_props = existing.get("properties") or {}
        merged = {**existing_props, **properties}
        if merged != existing_props:
            graph_service.update_edge(existing["id"], properties=merged)
        return {
            "presence_id": presence_id,
            "place_id": place_id,
            "place_name": place_name,
            "role": normalized_role,
            "created": False,
        }

    graph_service.create_edge_strict(
        from_id=presence_id,
        to_id=place_id,
        type="at-place",
        properties=properties,
        strength=1.0,
        created_by="place_service",
    )
    return {
        "presence_id": presence_id,
        "place_id": place_id,
        "place_name": place_name,
        "role": normalized_role,
        "created": True,
    }


def clear_at_place(presence_id: str, place_id: str) -> dict[str, Any]:
    """Remove the at-place edge between a presence and a place.

    Returns ``{cleared: True}`` if an edge was removed, otherwise
    ``{cleared: False}``. Never raises for a missing edge — clearing
    nothing is a valid no-op.
    """
    existing = _existing_at_place_edge(presence_id, place_id)
    if not existing:
        return {"cleared": False, "presence_id": presence_id, "place_id": place_id}
    graph_service.delete_edge(existing["id"])
    return {"cleared": True, "presence_id": presence_id, "place_id": place_id}


def presences_at(place_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return presences rooted in a place. Each row has presence id,
    name, type, role on the edge, and image_url when the node carries
    one. Ordered by edge creation time (most-recent first).
    """
    edges = graph_service.list_edges(
        edge_type="at-place",
        to_id=place_id,
        limit=limit,
    )
    rows = edges.get("items", []) if isinstance(edges, dict) else edges
    out: list[dict[str, Any]] = []
    for edge in rows:
        from_node = edge.get("from_node") or {}
        presence_id = edge.get("from_id") or from_node.get("id")
        if not presence_id:
            continue
        # Pull the full node so we can read image_url / canonical_url
        # (the stub strips properties down to id/type/name).
        full = graph_service.get_node(presence_id) or {}
        props = edge.get("properties") or {}
        out.append({
            "presence_id": presence_id,
            "presence_name": full.get("name") or from_node.get("name") or presence_id,
            "presence_type": full.get("type") or from_node.get("type"),
            "role": props.get("role") or "based",
            "image_url": full.get("image_url"),
        })
    return out


def places_for(presence_id: str) -> list[dict[str, Any]]:
    """Return the places a presence is rooted in. Each row carries the
    place id, name, region, country, and the role on the edge."""
    edges = graph_service.list_edges(
        edge_type="at-place",
        from_id=presence_id,
        limit=50,
    )
    rows = edges.get("items", []) if isinstance(edges, dict) else edges
    out: list[dict[str, Any]] = []
    for edge in rows:
        place_id = edge.get("to_id")
        if not place_id:
            continue
        full = graph_service.get_node(place_id) or {}
        props = edge.get("properties") or {}
        out.append({
            "place_id": place_id,
            "place_name": full.get("name") or place_id,
            "region": full.get("region"),
            "country": full.get("country"),
            "role": props.get("role") or "based",
        })
    return out
