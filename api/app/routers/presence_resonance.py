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

from app.services import graph_service, resonance_service


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
