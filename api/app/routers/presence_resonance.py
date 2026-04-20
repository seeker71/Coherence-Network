"""Presence ↔ vision-concept resonance threads.

Each presence (artist, sanctuary, gathering, venue) carries a
frequency spectrum — the words that describe what they make, where
they hold space, what they open. Each Living Collective concept
(ceremony, breath, nervous-system, attunement) carries its own
spectrum. Where they overlap, there is resonance, and the resonance
— made into a ``resonates-with`` edge — lets a visitor walking
either page cross the bridge into the other.

Separate from the cross-idea resonance kernel in ``resonance.py``
(which handles /api/resonance/* for the idea graph). These endpoints
live under /api/presences/{id}/resonances/* so the presence page can
own its own resonance shape without tangling with the idea kernel.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services import graph_service, inspired_by_service, resonance_service


router = APIRouter()


@router.post(
    "/presences/{presence_id}/resonances/attune",
    status_code=200,
    summary="Compute and write resonance edges from this presence to vision concepts",
)
async def attune(presence_id: str) -> dict[str, Any]:
    if not graph_service.get_node(presence_id):
        raise HTTPException(status_code=404, detail=f"Presence '{presence_id}' not found")
    return resonance_service.attune(presence_id)


@router.post(
    "/presences/{presence_id}/cross-references/scan",
    status_code=200,
    summary="Scan existing nodes for mentions of this presence and lay referenced-by edges",
)
async def scan_cross_refs(presence_id: str) -> dict[str, Any]:
    """Retroactive scan endpoint. New identities minted through the
    resolver get this automatically; existing presences need a
    manual trigger to backfill the mentions that were already in
    the graph when they arrived. Idempotent — re-running only
    writes the edges that don't exist yet."""
    node = graph_service.get_node(presence_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Presence '{presence_id}' not found")
    written = inspired_by_service._scan_cross_references(node)
    return {"presence_id": presence_id, "written_count": len(written), "written": written}


@router.get(
    "/concepts/{concept_id}/carried-by",
    summary="List the presences that resonate with (carry) this concept",
)
async def carried_by(concept_id: str) -> dict[str, Any]:
    """The reverse of /api/presences/{id}/resonances.

    A visitor reading the Ceremony concept sees the artists,
    sanctuaries, gatherings, and communities that carry its
    frequency — each one a doorway into their own presence page.
    Completes the bidirectional bridge of the resonance graph.
    """
    edges = graph_service.list_edges(
        to_id=concept_id, edge_type="resonates-with", limit=200,
    ).get("items", [])
    items: list[dict[str, Any]] = []
    for e in edges:
        presence = graph_service.get_node(e["from_id"])
        if not presence:
            continue
        props = e.get("properties") or {}
        items.append({
            "presence_id": presence["id"],
            "presence_name": presence.get("name") or presence["id"],
            "presence_type": presence.get("type", "contributor"),
            "image_url": presence.get("image_url"),
            "score": props.get("score", e.get("strength", 0.0)),
            "shared_tokens": props.get("shared_tokens", []),
            "method": props.get("method", "keyword-overlap"),
        })
    items.sort(key=lambda x: x.get("score") or 0.0, reverse=True)
    return {"items": items, "count": len(items)}


@router.get(
    "/presences/{presence_id}/resonances",
    summary="List the vision concepts this presence resonates with",
)
async def list_resonances(presence_id: str) -> dict[str, Any]:
    edges = graph_service.list_edges(
        from_id=presence_id, edge_type="resonates-with", limit=50,
    ).get("items", [])
    items: list[dict[str, Any]] = []
    for e in edges:
        concept = graph_service.get_node(e["to_id"])
        if not concept:
            continue
        props = e.get("properties") or {}
        # Each concept carries its own sacred frequency (hz); surfacing
        # it lets the client paint the chip in the concept's actual
        # colour rather than a single shared accent. Turns the row into
        # a literal frequency spectrum of the presence.
        sacred = concept.get("sacred_frequency")
        if isinstance(sacred, dict):
            hz_value = sacred.get("hz")
        else:
            hz_value = sacred
        items.append({
            "concept_id": concept["id"],
            "concept_name": concept.get("name") or concept["id"],
            "hz": hz_value if isinstance(hz_value, (int, float)) else None,
            "score": props.get("score", e.get("strength", 0.0)),
            "shared_tokens": props.get("shared_tokens", []),
            "method": props.get("method", "keyword-overlap"),
        })
    items.sort(key=lambda x: x.get("score") or 0.0, reverse=True)
    return {"items": items, "count": len(items)}
