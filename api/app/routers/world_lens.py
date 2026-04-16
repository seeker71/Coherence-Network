"""World lens — see the world through a concept's or contributor's frequency.

Every concept and every contributor carries a frequency spectrum.
The world lens filters recent world sensings through that spectrum,
showing each entity how reality is already contributing to their
unique resonance.

Three views:
  - Concept lens:      what the world is contributing to this concept
  - Contributor lens:  what the world looks like through this person's frequency
  - Community lens:    what the world is contributing to this commintire's field
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from app.services import graph_service

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/world/concept/{concept_id}",
    summary="World through a concept's lens",
    description=(
        "Recent world signals that resonate with this concept. "
        "Each signal has been sensed through the new earth lens "
        "and linked to concepts it contributes to."
    ),
)
async def concept_lens(
    concept_id: str,
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """What the world is contributing to this concept."""
    try:
        # Get sensings linked to this concept
        edges = graph_service.list_edges(to_id=concept_id, limit=200)
        sensing_ids = [
            e["from_id"] for e in edges.get("items", [])
            if e.get("type") == "analogous-to"
        ]

        # Also check from_id (edges go both ways for analogous-to)
        edges_from = graph_service.list_edges(from_id=concept_id, limit=200)
        for e in edges_from.get("items", []):
            if e.get("type") == "analogous-to":
                target = e["to_id"]
                if target not in sensing_ids:
                    sensing_ids.append(target)

        # Fetch the sensing nodes
        signals = []
        for sid in sensing_ids[:limit * 2]:  # fetch extra to filter
            node = graph_service.get_node(sid)
            if not node:
                continue
            props = node.get("properties", {})
            if props.get("sensing_kind") != "skin":
                continue
            metadata = props.get("metadata", {})
            if metadata.get("lens") != "new_earth":
                continue

            signals.append({
                "id": node["id"],
                "headline": node.get("name", ""),
                "reflection": props.get("content", ""),
                "frequency_quality": metadata.get("frequency_quality", "curious"),
                "source_url": metadata.get("source_url", ""),
                "sensed_at": props.get("observed_at", node.get("created_at", "")),
            })

            if len(signals) >= limit:
                break

        # Get the concept details
        concept = graph_service.get_node(concept_id)
        concept_name = concept.get("name", concept_id) if concept else concept_id
        concept_hz = concept.get("properties", {}).get("sacred_frequency", {}).get("hz") if concept else None

        return {
            "concept_id": concept_id,
            "concept_name": concept_name,
            "frequency_hz": concept_hz,
            "signals": signals,
            "signal_count": len(signals),
        }
    except Exception as e:
        log.warning("world_lens: concept lens failed: %s", e)
        return {"concept_id": concept_id, "signals": [], "signal_count": 0}


@router.get(
    "/world/contributor/{contributor_id}",
    summary="World through a contributor's frequency",
    description=(
        "The world filtered through a contributor's unique frequency spectrum. "
        "Shows events that resonate with concepts this contributor has engaged with."
    ),
)
async def contributor_lens(
    contributor_id: str,
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """What the world looks like through this contributor's eyes."""
    try:
        # Find what concepts this contributor resonates with
        # (via their view history, contributions, or belief profile)
        from app.services import read_tracking_service

        # Get their viewing history — what they've paid attention to
        history = read_tracking_service.get_contributor_view_history(
            contributor_id, limit=50,
        )
        viewed_concepts = list(set(
            h["asset_id"] for h in history
            if h.get("asset_id", "").startswith("lc-")
        ))

        if not viewed_concepts:
            # Fallback: show general world signals
            return {
                "contributor_id": contributor_id,
                "frequency_profile": [],
                "signals": [],
                "signal_count": 0,
                "message": "Visit some concepts in the vision to build your frequency profile",
            }

        # Gather world signals linked to their resonant concepts
        all_signals = []
        seen_ids: set[str] = set()

        for concept_id in viewed_concepts[:10]:  # top 10 concepts
            edges = graph_service.list_edges(to_id=concept_id, limit=50)
            edges_from = graph_service.list_edges(from_id=concept_id, limit=50)

            sensing_ids = []
            for e in edges.get("items", []):
                if e.get("type") == "analogous-to":
                    sensing_ids.append(e["from_id"])
            for e in edges_from.get("items", []):
                if e.get("type") == "analogous-to":
                    sensing_ids.append(e["to_id"])

            for sid in sensing_ids:
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)

                node = graph_service.get_node(sid)
                if not node:
                    continue
                props = node.get("properties", {})
                if props.get("sensing_kind") != "skin":
                    continue
                metadata = props.get("metadata", {})
                if metadata.get("lens") != "new_earth":
                    continue

                all_signals.append({
                    "id": node["id"],
                    "headline": node.get("name", ""),
                    "reflection": props.get("content", ""),
                    "frequency_quality": metadata.get("frequency_quality", "curious"),
                    "source_url": metadata.get("source_url", ""),
                    "sensed_at": props.get("observed_at", node.get("created_at", "")),
                    "resonates_with_concept": concept_id,
                })

        # Sort by recency
        all_signals.sort(
            key=lambda s: s.get("sensed_at", ""),
            reverse=True,
        )

        return {
            "contributor_id": contributor_id,
            "frequency_profile": viewed_concepts[:10],
            "signals": all_signals[:limit],
            "signal_count": len(all_signals[:limit]),
        }
    except Exception as e:
        log.warning("world_lens: contributor lens failed: %s", e)
        return {"contributor_id": contributor_id, "signals": [], "signal_count": 0}


@router.get(
    "/world/community/{workspace_id}",
    summary="World through a community's collective frequency",
    description=(
        "The world filtered through a community's collective frequency — "
        "all the concepts its members have engaged with, all the signals "
        "that resonate with the community's field."
    ),
)
async def community_lens(
    workspace_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """What the world is contributing to this community's vision."""
    try:
        # Get all recent world sensings
        sensings = graph_service.list_nodes(type="event", limit=100)
        items = sensings.get("items", [])

        signals = []
        for node in items:
            props = node.get("properties", {})
            if props.get("sensing_kind") != "skin":
                continue
            metadata = props.get("metadata", {})
            if metadata.get("lens") != "new_earth":
                continue

            # Find which concepts this sensing links to
            edges = graph_service.list_edges(from_id=node["id"], limit=20)
            edges_to = graph_service.list_edges(to_id=node["id"], limit=20)
            linked_concepts = []
            for e in edges.get("items", []) + edges_to.get("items", []):
                other = e["to_id"] if e["from_id"] == node["id"] else e["from_id"]
                if other.startswith("lc-"):
                    linked_concepts.append(other)

            signals.append({
                "id": node["id"],
                "headline": node.get("name", ""),
                "reflection": props.get("content", ""),
                "frequency_quality": metadata.get("frequency_quality", "curious"),
                "source_url": metadata.get("source_url", ""),
                "sensed_at": props.get("observed_at", node.get("created_at", "")),
                "resonates_with": list(set(linked_concepts)),
            })

        signals.sort(key=lambda s: s.get("sensed_at", ""), reverse=True)

        return {
            "workspace_id": workspace_id,
            "signals": signals[:limit],
            "signal_count": len(signals[:limit]),
            "total_available": len(signals),
        }
    except Exception as e:
        log.warning("world_lens: community lens failed: %s", e)
        return {"workspace_id": workspace_id, "signals": [], "signal_count": 0}
