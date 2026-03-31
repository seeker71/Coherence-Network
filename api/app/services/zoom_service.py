"""Zoom service — fractal subtree traversal and coherence score computation (Spec 182).

Key operations:
  - get_pillars: return the 5 root pillar nodes with metadata
  - get_zoom: return a subtree rooted at node_id up to N levels deep
  - add_question / resolve_question: manage open questions stored in node payload

Coherence score formula:
  Leaf (no children): sum of payload quality weights
  Non-leaf: weighted average of children's scores by edge type
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_

from app.models.graph import Edge, Node
from app.models.graph_zoom import (
    OpenQuestion,
    PillarListResponse,
    PillarNode,
    QuestionResponse,
    ZoomNode,
    ZoomResponse,
)
from app.services.unified_db import session

# Five canonical pillar IDs (stable, never renamed per spec)
PILLAR_IDS = ["traceability", "trust", "freedom", "uniqueness", "collaboration"]

# Edge-type weights for coherence aggregation (higher = more important signal)
EDGE_WEIGHTS: dict[str, float] = {
    "implements": 1.5,
    "depends-on": 1.2,
    "parent-of": 1.0,
}
DEFAULT_EDGE_WEIGHT = 1.0

# Nodes with child_count >= GARDEN_THRESHOLD get view_hint="garden"
import os as _os
_GARDEN_THRESHOLD = int(_os.environ.get("ZOOM_GARDEN_THRESHOLD", "2"))


def _lifecycle_state(node: Node) -> str:
    props = node.properties or {}
    return props.get("lifecycle_state", node.phase or "water")


def _open_questions(node: Node) -> list[dict[str, Any]]:
    props = node.properties or {}
    return list(props.get("open_questions", []))


def _leaf_coherence(node: Node) -> float:
    """Compute coherence for a leaf node from payload quality signals."""
    props = node.properties or {}
    score = 0.0
    if props.get("description") or node.description:
        score += 0.3
    if props.get("tags"):
        score += 0.1
    questions = props.get("open_questions", [])
    if questions:
        score += 0.2
        total_q = len(questions)
        resolved = sum(1 for q in questions if q.get("resolved", False))
        score += 0.4 * (resolved / total_q) if total_q > 0 else 0.0
    return max(0.0, min(1.0, score))


def _compute_coherence(node: Node, children_and_edges: list[tuple[Node, str]]) -> float:
    """Compute coherence score for a node.

    If the node has children, use weighted average of their scores.
    Otherwise derive from payload quality.
    """
    if not children_and_edges:
        # Pull stored score first; fall back to leaf formula
        props = node.properties or {}
        stored = props.get("coherence_score")
        if stored is not None:
            try:
                return max(0.0, min(1.0, float(stored)))
            except (TypeError, ValueError):
                pass
        return _leaf_coherence(node)

    total_weight = 0.0
    weighted_sum = 0.0
    for child, edge_type in children_and_edges:
        child_score = _get_node_coherence_score(child)
        w = EDGE_WEIGHTS.get(edge_type, DEFAULT_EDGE_WEIGHT)
        weighted_sum += child_score * w
        total_weight += w

    if total_weight == 0:
        return 0.0
    return max(0.0, min(1.0, weighted_sum / total_weight))


def _get_node_coherence_score(node: Node) -> float:
    """Return stored coherence score or derive from payload."""
    props = node.properties or {}
    stored = props.get("coherence_score")
    if stored is not None:
        try:
            return max(0.0, min(1.0, float(stored)))
        except (TypeError, ValueError):
            pass
    return _leaf_coherence(node)


def _view_hint(child_count: int, current_depth: int) -> str:
    """Return 'garden' for nodes with many children or deep in hierarchy."""
    if current_depth >= 2 or child_count >= _GARDEN_THRESHOLD:
        return "garden"
    return "graph"


def _build_zoom_node(
    node: Node,
    children_with_edges: list[tuple[Node, str]],  # (child_node, edge_type)
    all_edges: list[dict[str, Any]],
    current_depth: int,
) -> ZoomNode:
    """Build a ZoomNode from ORM data, without recursing into children."""
    questions_raw = _open_questions(node)
    open_qs = [
        OpenQuestion(
            id=q.get("id", ""),
            question=q.get("question", ""),
            created_at=q.get("created_at", ""),
            resolved=q.get("resolved", False),
            resolved_at=q.get("resolved_at"),
        )
        for q in questions_raw
    ]

    coherence = _compute_coherence(node, children_with_edges)
    child_count = len(children_with_edges)
    hint = _view_hint(child_count, current_depth)

    return ZoomNode(
        id=node.id,
        name=node.name,
        node_type=node.type,
        coherence_score=coherence,
        lifecycle_state=_lifecycle_state(node),
        view_hint=hint,
        open_questions=open_qs,
        children=[],  # filled in by recursive builder
        edges=all_edges,
    )


def _fetch_children(node_id: str, s) -> list[tuple[Node, str]]:
    """Return list of (child_node, edge_type) for direct children of node_id."""
    edges = s.query(Edge).filter(Edge.from_id == node_id).all()
    result = []
    for edge in edges:
        child = s.get(Node, edge.to_id)
        if child:
            result.append((child, edge.type))
    return result


def _edges_for_node(node_id: str, s) -> list[dict[str, Any]]:
    """Return edge dicts for outgoing edges from node_id."""
    edges = s.query(Edge).filter(Edge.from_id == node_id).all()
    return [{"from": e.from_id, "to": e.to_id, "edge_type": e.type} for e in edges]


def _build_subtree(
    node: Node,
    depth: int,
    current_depth: int,
    s,
    node_count: list[int],
) -> ZoomNode:
    """Recursively build a ZoomNode subtree up to `depth` levels."""
    node_count[0] += 1
    children_with_edges = _fetch_children(node.id, s)
    edge_dicts = _edges_for_node(node.id, s)

    zoom = _build_zoom_node(node, children_with_edges, edge_dicts, current_depth)

    if depth > 0 and children_with_edges:
        child_nodes = []
        for child_node, _etype in children_with_edges:
            child_zoom = _build_subtree(child_node, depth - 1, current_depth + 1, s, node_count)
            child_nodes.append(child_zoom)
        zoom.children = child_nodes

    return zoom


def get_pillars() -> PillarListResponse:
    """Return the 5 root pillar nodes with summary metadata."""
    with session() as s:
        pillars = []
        for pid in PILLAR_IDS:
            node = s.get(Node, pid)
            if node is None:
                continue
            children = _fetch_children(pid, s)
            child_count = len(children)
            questions = _open_questions(node)
            open_q_count = sum(1 for q in questions if not q.get("resolved", False))
            coherence = _compute_coherence(node, children)
            pillars.append(PillarNode(
                id=node.id,
                name=node.name,
                node_type=node.type,
                coherence_score=coherence,
                child_count=child_count,
                open_question_count=open_q_count,
                lifecycle_state=_lifecycle_state(node),
            ))
        return PillarListResponse(pillars=pillars, total=len(pillars))


def get_zoom(node_id: str, depth: int) -> ZoomResponse:
    """Return the fractal subtree rooted at node_id up to depth levels.

    Raises KeyError if node not found.
    """
    with session() as s:
        root = s.get(Node, node_id)
        if root is None:
            raise KeyError(node_id)

        node_count: list[int] = [0]
        zoom_node = _build_subtree(root, depth, 0, s, node_count)

        return ZoomResponse(
            node=zoom_node,
            depth_requested=depth,
            total_nodes_in_subtree=node_count[0],
        )


def add_question(node_id: str, question_text: str) -> QuestionResponse:
    """Add an open question to a node's payload. Returns the created question.

    Raises KeyError if node not found.
    """
    with session() as s:
        node = s.get(Node, node_id)
        if node is None:
            raise KeyError(node_id)

        props = dict(node.properties or {})
        questions: list[dict] = list(props.get("open_questions", []))

        q_id = f"q{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        new_q: dict[str, Any] = {
            "id": q_id,
            "question": question_text,
            "created_at": now,
            "resolved": False,
            "resolved_at": None,
        }
        questions.append(new_q)
        props["open_questions"] = questions
        node.properties = props
        s.commit()

        return QuestionResponse(
            id=q_id,
            question=question_text,
            created_at=now,
            resolved=False,
            resolved_at=None,
            node_id=node_id,
        )


def resolve_question(node_id: str, question_id: str, resolved: bool) -> QuestionResponse:
    """Mark a question as resolved or re-open it.

    Raises KeyError if node or question not found.
    """
    with session() as s:
        node = s.get(Node, node_id)
        if node is None:
            raise KeyError(f"node:{node_id}")

        props = dict(node.properties or {})
        questions: list[dict] = list(props.get("open_questions", []))

        target = next((q for q in questions if q.get("id") == question_id), None)
        if target is None:
            raise KeyError(f"question:{question_id}")

        target["resolved"] = resolved
        if resolved:
            target["resolved_at"] = datetime.now(timezone.utc).isoformat()
        else:
            target["resolved_at"] = None

        props["open_questions"] = questions
        node.properties = props
        s.commit()

        return QuestionResponse(
            id=target["id"],
            question=target["question"],
            created_at=target.get("created_at", ""),
            resolved=target["resolved"],
            resolved_at=target.get("resolved_at"),
            node_id=node_id,
        )
