"""Idea ↔ Graph adapter — reads/writes ideas from graph_nodes table.

Drop-in replacement for idea_registry_service. Same interface, different backend.
The graph_service.list_nodes(type='idea') returns ideas with all properties flattened.
This adapter converts between graph node dicts and Idea model objects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.idea import (
    Idea,
    IdeaLifecycle,
    IdeaQuestion,
    IdeaStage,
    IdeaType,
    IdeaWorkType,
    ManifestationStatus,
)
from app.services import graph_service

log = logging.getLogger(__name__)


def _node_to_idea(node: dict[str, Any]) -> Idea:
    """Convert a graph node dict to an Idea model object."""

    # Parse enums safely
    try:
        status = ManifestationStatus(node.get("manifestation_status", "none") or "none")
    except (ValueError, KeyError):
        status = ManifestationStatus.NONE

    try:
        idea_type = IdeaType(node.get("idea_type", "standalone") or "standalone")
    except (ValueError, KeyError):
        idea_type = IdeaType.STANDALONE

    try:
        stage = IdeaStage(node.get("stage", "none") or "none")
    except (ValueError, KeyError):
        stage = IdeaStage.NONE

    try:
        work_type_str = node.get("work_type")
        work_type = IdeaWorkType(work_type_str) if work_type_str else None
    except (ValueError, KeyError):
        work_type = None

    try:
        lifecycle_str = node.get("lifecycle", "active") or "active"
        lifecycle = IdeaLifecycle(lifecycle_str)
    except (ValueError, KeyError):
        lifecycle = IdeaLifecycle.ACTIVE

    # Parse open questions
    raw_questions = node.get("open_questions", [])
    questions: list[IdeaQuestion] = []
    if isinstance(raw_questions, list):
        for q in raw_questions:
            if isinstance(q, dict):
                questions.append(IdeaQuestion(
                    question=q.get("question", ""),
                    value_to_whole=float(q.get("value_to_whole", 0)),
                    estimated_cost=float(q.get("estimated_cost", 0)),
                    answer=q.get("answer"),
                    measured_delta=float(q["measured_delta"]) if q.get("measured_delta") is not None else None,
                ))

    # Parse child_idea_ids
    raw_children = node.get("child_idea_ids", [])
    child_ids = raw_children if isinstance(raw_children, list) else []

    # Parse value_basis
    raw_vb = node.get("value_basis")
    value_basis = raw_vb if isinstance(raw_vb, dict) else None

    # Parse slug — backfill from id for legacy nodes
    raw_slug = node.get("slug") or ""
    slug = raw_slug if raw_slug else node["id"]

    # Parse slug_history
    raw_history = node.get("slug_history", [])
    if isinstance(raw_history, str):
        try:
            import json as _json
            raw_history = _json.loads(raw_history)
        except Exception:
            raw_history = []
    slug_history: list[str] = raw_history if isinstance(raw_history, list) else []

    # Parse workspace git url
    workspace_git_url = node.get("workspace_git_url") or None

    # Parse rollup_condition (super-idea rollup criteria)
    rollup_condition = node.get("rollup_condition") or None

    return Idea(
        id=node["id"],
        name=node.get("name", ""),
        description=node.get("description", ""),
        potential_value=float(node.get("potential_value", 0) or 0),
        actual_value=float(node.get("actual_value", 0) or 0),
        estimated_cost=float(node.get("estimated_cost", 0) or 0),
        actual_cost=float(node.get("actual_cost", 0) or 0),
        resistance_risk=float(node.get("resistance_risk", 1.0) or 1.0),
        confidence=float(node.get("confidence", 0.5) or 0.5),
        manifestation_status=status,
        stage=stage,
        interfaces=node.get("interfaces", []) or [],
        idea_type=idea_type,
        parent_idea_id=node.get("parent_idea_id"),
        child_idea_ids=child_ids,
        value_basis=value_basis,
        work_type=work_type,
        lifecycle=lifecycle,
        duplicate_of=node.get("duplicate_of"),
        last_activity_at=node.get("last_activity_at"),
        open_questions=questions,
        slug=slug,
        slug_history=slug_history,
        workspace_git_url=workspace_git_url,
        is_curated=bool(node.get("is_curated", False)),
        pillar=node.get("pillar") or None,
        workspace_id=node.get("workspace_id") or "coherence-network",
        rollup_condition=rollup_condition,
    )


def _idea_to_properties(idea: Idea) -> dict[str, Any]:
    """Convert an Idea model to a properties dict for graph_service."""
    props: dict[str, Any] = {}
    for field in [
        "potential_value", "actual_value", "estimated_cost", "actual_cost",
        "resistance_risk", "confidence", "manifestation_status", "stage",
        "interfaces", "idea_type", "parent_idea_id", "child_idea_ids",
        "value_basis", "work_type", "lifecycle", "duplicate_of", "last_activity_at",
        "slug", "workspace_git_url", "is_curated", "pillar", "workspace_id",
        "rollup_condition",
    ]:
        val = getattr(idea, field, None)
        if val is not None:
            # Convert enums to strings
            if hasattr(val, "value"):
                val = val.value
            props[field] = val

    # Serialize slug_history as JSON list
    if hasattr(idea, "slug_history"):
        props["slug_history"] = idea.slug_history if isinstance(idea.slug_history, list) else []

    # Serialize questions
    if idea.open_questions:
        props["open_questions"] = [q.model_dump() for q in idea.open_questions]

    return props


# ── Public API (same interface as idea_registry_service) ──


def load_ideas() -> list[Idea]:
    """Load all ideas from the graph."""
    result = graph_service.list_nodes(type="idea", limit=5000, offset=0)
    nodes = result.get("items", [])
    ideas = []
    for node in nodes:
        try:
            ideas.append(_node_to_idea(node))
        except Exception as e:
            log.warning("Failed to convert graph node %s to Idea: %s", node.get("id"), e)
    return ideas


def save_single_idea(idea: Idea, position: int = 0) -> None:
    """Create or update a single idea in the graph."""
    existing = graph_service.get_node(idea.id)
    props = _idea_to_properties(idea)

    # Map manifestation_status to phase
    status = idea.manifestation_status.value if hasattr(idea.manifestation_status, "value") else str(idea.manifestation_status)
    phase = "ice" if status == "validated" else "water" if status == "partial" else "gas"

    if existing:
        graph_service.update_node(idea.id, name=idea.name, description=idea.description, phase=phase, properties=props)
    else:
        graph_service.create_node(
            id=idea.id,
            type="idea",
            name=idea.name,
            description=idea.description,
            phase=phase,
            properties=props,
        )


def save_ideas(ideas: list[Idea], bootstrap_source: str | None = None) -> None:
    """Bulk save ideas to the graph."""
    for i, idea in enumerate(ideas):
        save_single_idea(idea, position=i)
    log.info("Saved %d ideas to graph (source=%s)", len(ideas), bootstrap_source or "api")


def ensure_schema() -> None:
    """No-op — graph tables are managed by graph_service."""
    pass


def storage_info() -> dict[str, Any]:
    """Return storage info about the graph-backed idea store."""
    from app.services.unified_db import database_url as _db_url
    idea_stats = graph_service.count_nodes(type="idea")
    question_stats = graph_service.count_nodes(type="question")
    return {
        "backend": "graph_nodes",
        "database_url": _db_url(),
        "idea_count": idea_stats.get("total", 0),
        "question_count": question_stats.get("total", 0),
        "bootstrap_source": "graph_nodes (type='idea')",
    }
