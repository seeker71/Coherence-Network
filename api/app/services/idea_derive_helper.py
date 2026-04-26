"""Derive an Idea from an idea_id when no canonical record exists.

Extracted from idea_service.py (#163). When the runtime sees an idea_id
the DB doesn't know yet (commit-evidence tracking, derived ideas), this
helper produces a synthetic Idea with safe defaults — pulling metadata
from a registry/graph match if one exists, falling back to derived
naming via _humanize_idea_id.

Public surface (re-exported from idea_service):
  _derived_idea_for_id, _idea_to_metadata
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.idea import Idea, IdeaLifecycle, IdeaType, ManifestationStatus
from app.services import idea_registry_service
from app.services.idea_resonance_helpers import _find_closest_graph_idea, _humanize_idea_id

logger = logging.getLogger(__name__)


def _idea_to_metadata(idea: Any) -> dict[str, Any]:
    """Extract metadata dict from an Idea object for signal inheritance."""
    d: dict[str, Any] = {
        "name": idea.name,
        "description": idea.description,
        "interfaces": idea.interfaces,
        "potential_value": idea.potential_value,
        "actual_value": idea.actual_value,
        "estimated_cost": idea.estimated_cost,
        "actual_cost": idea.actual_cost,
        "confidence": idea.confidence,
        "resistance_risk": idea.resistance_risk,
        "idea_type": idea.idea_type.value if idea.idea_type else "standalone",
        "parent_idea_id": idea.parent_idea_id,
        "child_idea_ids": idea.child_idea_ids or [],
        "manifestation_status": idea.manifestation_status.value if idea.manifestation_status else "none",
    }
    if getattr(idea, "lifecycle", None) is not None:
        d["lifecycle"] = idea.lifecycle.value if hasattr(idea.lifecycle, "value") else str(idea.lifecycle)
    if getattr(idea, "duplicate_of", None) is not None:
        d["duplicate_of"] = idea.duplicate_of
    return d


def _derived_idea_for_id(idea_id: str) -> Idea:
    # Try to find metadata from DB — exact match first, then fuzzy match
    metadata: dict[str, Any] = {}
    try:
        db_ideas = idea_registry_service.load_ideas()
        # Exact match
        for idea in db_ideas:
            if idea.id == idea_id:
                metadata = _idea_to_metadata(idea)
                break
        # Node-type fallback — idea may exist as a non-idea node (e.g. spec).
        # Read its actual stored properties so updates via the idea API persist.
        if not metadata:
            try:
                from app.services import graph_service as _gs
                raw = _gs.get_node(idea_id)
                if raw:
                    # Flatten the node dict (to_dict() already merges properties)
                    metadata = {k: raw[k] for k in [
                        "name", "description", "potential_value", "actual_value",
                        "estimated_cost", "actual_cost", "confidence",
                        "resistance_risk", "idea_type", "parent_idea_id",
                        "child_idea_ids", "manifestation_status", "duplicate_of",
                        "lifecycle", "interfaces",
                    ] if raw.get(k) is not None}
                    logger.debug("Node-type fallback for derived idea %s (type=%s)", idea_id, raw.get("type"))
            except Exception:
                logger.debug("Node-type fallback failed for derived idea %s", idea_id, exc_info=True)

        # Fuzzy match — inherit scores from closest graph idea
        if not metadata:
            closest = _find_closest_graph_idea(idea_id, db_ideas)
            if closest:
                metadata = _idea_to_metadata(closest)
                # Keep the discovered ID's auto-generated name, not the matched idea's name
                metadata.pop("name", None)
                metadata.pop("description", None)
                logger.debug("Fuzzy matched idea %s → %s", idea_id, closest.id)
    except Exception:
        logger.warning("Failed to load seed metadata for derived idea %s", idea_id, exc_info=True)
    name = str(metadata.get("name") or _humanize_idea_id(idea_id))
    description = str(
        metadata.get("description")
        or f"Automatically derived from commit-evidence tracking for idea id '{idea_id}'."
    )
    interfaces = metadata.get("interfaces")
    if not isinstance(interfaces, list) or not all(isinstance(x, str) for x in interfaces):
        interfaces = ["machine:api", "human:web", "machine:commit-evidence"]

    # Copy all numeric and enum fields from seed, with safe defaults
    potential_value = float(metadata.get("potential_value", 70.0))
    actual_value = float(metadata.get("actual_value", 0.0))
    estimated_cost = float(metadata.get("estimated_cost", 12.0))
    actual_cost = float(metadata.get("actual_cost", 0.0))
    confidence = float(metadata.get("confidence", 0.55))
    resistance_risk = float(metadata.get("resistance_risk", 3.0))

    # Hierarchy fields
    idea_type_str = metadata.get("idea_type", "standalone")
    try:
        idea_type = IdeaType(idea_type_str)
    except ValueError:
        idea_type = IdeaType.STANDALONE
    parent_idea_id = metadata.get("parent_idea_id")
    child_idea_ids = metadata.get("child_idea_ids", [])
    if not isinstance(child_idea_ids, list):
        child_idea_ids = []

    # Status
    status_str = metadata.get("manifestation_status", "none")
    try:
        status = ManifestationStatus(status_str)
    except ValueError:
        status = ManifestationStatus.NONE

    # Lifecycle
    lifecycle_str = metadata.get("lifecycle", "active") or "active"
    try:
        lifecycle = IdeaLifecycle(lifecycle_str)
    except (ValueError, AttributeError):
        lifecycle = IdeaLifecycle.ACTIVE

    duplicate_of = metadata.get("duplicate_of") or None

    return Idea(
        id=idea_id,
        name=name,
        description=description,
        potential_value=potential_value,
        actual_value=actual_value,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        resistance_risk=resistance_risk,
        confidence=max(0.0, min(confidence, 1.0)),
        manifestation_status=status,
        lifecycle=lifecycle,
        duplicate_of=duplicate_of,
        interfaces=interfaces,
        open_questions=[],
        idea_type=idea_type,
        parent_idea_id=parent_idea_id,
        child_idea_ids=child_idea_ids,
        slug=idea_id,
        slug_history=[],
    )
