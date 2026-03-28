"""Fractal Node + Edge primitives service — semantic layer for the universal graph.

Implements spec-169: typed node/edge vocabulary, Ice/Water/Gas lifecycle enforcement,
fractal sub-node support, and constraint validation for the graph layer.

The central claim of spec-169:
  Everything meaningful in the Coherence Network is a node.
  Relationships are typed. The graph, when traversed, encodes value lineage,
  attribution chains, dependency trees, and the epistemic state of the system.
  Any node can contain sub-nodes of the same shape (fractal).
"""

from __future__ import annotations

import logging
from typing import Any

from app.config.node_types import (
    CANONICAL_NODE_TYPES,
    NODE_TYPE_REGISTRY,
    VALID_PHASE_TRANSITIONS,
    ALL_NODE_TYPES,
    NODE_TYPE_FAMILIES,
    is_valid_phase_transition,
    is_phase_allowed_for_type,
)
from app.config.edge_types import (
    CANONICAL_EDGE_TYPES,
    EDGE_TYPE_FAMILIES,
    ALL_EDGE_TYPES,
)
from app.services import graph_service

log = logging.getLogger(__name__)


# ── Phase transition ──────────────────────────────────────────────────


def transition_node_phase(
    node_id: str,
    to_phase: str,
    reason: str = "",
    actor: str = "system",
) -> dict[str, Any]:
    """Transition a node's lifecycle phase (gas ↔ water ↔ ice).

    Validates:
      - The node exists.
      - The target phase is a valid value (gas/water/ice).
      - The transition is allowed (e.g. gas→water is ok, water→water is a no-op).
      - The target phase is allowed for the node's type.

    Returns the updated node dict, or an error dict with 'error' key.
    """
    node = graph_service.get_node(node_id)
    if not node:
        return {"error": "not_found", "node_id": node_id}

    current_phase = node.get("phase", "water")
    valid_phases = {"gas", "water", "ice"}

    if to_phase not in valid_phases:
        return {
            "error": "invalid_phase",
            "detail": f"'{to_phase}' is not a valid phase. Choose from: gas, water, ice.",
        }

    if current_phase == to_phase:
        return {"error": "no_op", "detail": f"Node is already in phase '{to_phase}'.", "node": node}

    if not is_valid_phase_transition(current_phase, to_phase):
        return {
            "error": "invalid_transition",
            "detail": (
                f"Transition {current_phase!r} → {to_phase!r} is not allowed. "
                f"Valid targets from '{current_phase}': {VALID_PHASE_TRANSITIONS.get(current_phase, [])}."
            ),
        }

    node_type = node.get("type", "")
    if not is_phase_allowed_for_type(node_type, to_phase):
        return {
            "error": "phase_not_allowed_for_type",
            "detail": (
                f"Phase '{to_phase}' is not allowed for node type '{node_type}'. "
                f"Allowed phases: {NODE_TYPE_REGISTRY.get(node_type, {}).get('allowed_phases', ['gas', 'water', 'ice'])}."
            ),
        }

    # Persist transition
    props = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
    transitions = list(props.get("phase_transitions", []))
    transitions.append({
        "from": current_phase,
        "to": to_phase,
        "reason": reason,
        "actor": actor,
    })

    updated = graph_service.update_node(
        node_id,
        phase=to_phase,
        properties={"phase_transitions": transitions},
    )
    if not updated:
        return {"error": "update_failed", "node_id": node_id}

    log.info("Node %s phase transition: %s → %s (actor=%s)", node_id, current_phase, to_phase, actor)
    return {
        "node_id": node_id,
        "previous_phase": current_phase,
        "current_phase": to_phase,
        "node": updated,
    }


# ── Sub-node (fractal) support ────────────────────────────────────────


def create_sub_node(
    parent_id: str,
    *,
    type: str,
    name: str,
    description: str = "",
    properties: dict[str, Any] | None = None,
    phase: str | None = None,
    created_by: str = "system",
) -> dict[str, Any]:
    """Create a node as a fractal sub-node of parent_id.

    - Creates the child node.
    - Creates a parent-of edge from parent → child.
    - Inherits parent's phase if not specified.

    Returns the child node dict with the edge included.
    """
    parent = graph_service.get_node(parent_id)
    if not parent:
        return {"error": "parent_not_found", "parent_id": parent_id}

    parent_meta = NODE_TYPE_REGISTRY.get(parent.get("type", ""), {})
    if not parent_meta.get("fractal", True):
        return {
            "error": "not_fractal",
            "detail": f"Node type '{parent.get('type')}' does not support sub-nodes.",
        }

    # Default phase inherits from parent
    child_phase = phase or parent.get("phase", "water")

    child_props = dict(properties or {})
    child_props.setdefault("parent_id", parent_id)

    child = graph_service.create_node(
        type=type,
        name=name,
        description=description,
        properties=child_props,
        phase=child_phase,
    )

    # Link via parent-of edge
    edge = graph_service.create_edge(
        from_id=parent_id,
        to_id=child["id"],
        type="parent-of",
        properties={"created_by": created_by},
        strength=1.0,
        created_by=created_by,
    )

    return {
        "node": child,
        "parent_edge": edge,
        "parent_id": parent_id,
    }


def get_sub_nodes(
    parent_id: str,
    node_type: str | None = None,
    phase: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Get all direct sub-nodes of parent_id (via parent-of edges).

    Optionally filters by node_type and/or phase.
    """
    parent = graph_service.get_node(parent_id)
    if not parent:
        return {"error": "not_found", "parent_id": parent_id}

    # Get all outgoing parent-of edges
    edges_result = graph_service.list_edges_for_entity(
        entity_id=parent_id,
        edge_type="parent-of",
        direction="outgoing",
        limit=limit,
    )
    edges = edges_result.get("items", [])

    # Collect child IDs
    child_ids = [e["to_id"] for e in edges if "to_id" in e]
    if not child_ids:
        return {"parent_id": parent_id, "sub_nodes": [], "total": 0}

    # Fetch children, applying filters
    children = []
    for child_id in child_ids:
        node = graph_service.get_node(child_id)
        if not node:
            continue
        if node_type and node.get("type") != node_type:
            continue
        if phase and node.get("phase") != phase:
            continue
        children.append(node)

    return {
        "parent_id": parent_id,
        "sub_nodes": children,
        "total": len(children),
    }


# ── Type constraint validation ────────────────────────────────────────


def validate_edge_for_types(
    from_type: str,
    to_type: str,
    edge_type: str,
) -> dict[str, Any]:
    """Check whether an edge type is semantically meaningful between two node types.

    This is advisory, not enforced — the graph layer will accept any valid edge type.
    Returns {'valid': True} or {'valid': False, 'warnings': [...]}.
    """
    warnings: list[str] = []

    # Check edge is canonical
    if edge_type not in CANONICAL_EDGE_TYPES:
        warnings.append(f"Edge type '{edge_type}' is not in the canonical vocabulary.")

    # Semantic advice: parent-of / child-of should only link same-family types
    if edge_type in ("parent-of", "child-of"):
        from_meta = NODE_TYPE_REGISTRY.get(from_type, {})
        to_meta = NODE_TYPE_REGISTRY.get(to_type, {})
        from_family = from_meta.get("family_slug", "")
        to_family = to_meta.get("family_slug", "")
        if from_family and to_family and from_family != to_family:
            warnings.append(
                f"'{edge_type}' typically links nodes within the same family. "
                f"'{from_type}' (family: {from_family}) → '{to_type}' (family: {to_family}) "
                "crosses family boundaries — consider whether this is intentional."
            )
        if not from_meta.get("fractal", True):
            warnings.append(
                f"Node type '{from_type}' is not marked as fractal — "
                "sub-node containment may not be semantically meaningful."
            )

    # implements should point from implementation → spec
    if edge_type == "implements" and to_type not in ("spec", "idea", "concept"):
        warnings.append(
            f"'implements' typically points from an implementation to a spec/idea/concept, "
            f"but target type is '{to_type}'."
        )

    # depends-on makes most sense between operational types
    if edge_type == "depends-on" and from_type == "contributor":
        warnings.append(
            "A contributor 'depends-on' a node is unusual — consider 'contributes-to' instead."
        )

    return {"valid": len(warnings) == 0, "warnings": warnings}


# ── Vocabulary getters ────────────────────────────────────────────────


def get_node_type_registry() -> dict[str, Any]:
    """Return the full node type registry for the API."""
    return {
        "total": len(ALL_NODE_TYPES),
        "families": NODE_TYPE_FAMILIES,
        "valid_phase_transitions": VALID_PHASE_TRANSITIONS,
        "phases": {
            "gas": "Speculative, volatile, pre-form. Ideas not yet committed.",
            "water": "Active, flowing, being worked on.",
            "ice": "Stable, archived, frozen potential. Reference or completed.",
        },
    }


def get_edge_type_registry(family: str | None = None) -> dict[str, Any]:
    """Return edge types grouped by family, optionally filtered."""
    families = EDGE_TYPE_FAMILIES
    if family:
        families = [f for f in families if f["slug"] == family or f["name"] == family]
    total = sum(len(f["types"]) for f in families)
    return {"total": total, "families": families}
