"""Idempotent seed for the 5 canonical pillar nodes and Trust subtree (Spec 182).

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING via SQLAlchemy
IntegrityError catch (works on both SQLite and PostgreSQL).

Usage:
    python -m api.seed.pillar_seed
    or call seed_pillars() from startup code.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError

from app.models.graph import Edge, Node
from app.services.unified_db import session

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pillar nodes
# ---------------------------------------------------------------------------
_PILLARS = [
    {"id": "traceability", "name": "Traceability"},
    {"id": "trust", "name": "Trust"},
    {"id": "freedom", "name": "Freedom"},
    {"id": "uniqueness", "name": "Uniqueness"},
    {"id": "collaboration", "name": "Collaboration"},
]

# ---------------------------------------------------------------------------
# Trust subtree (depth 2 and 3)
# ---------------------------------------------------------------------------
_TRUST_CHILDREN = [
    {"id": "coherence-scoring", "name": "Coherence Scoring"},
    {"id": "contribution-verification", "name": "Contribution Verification"},
    {"id": "identity-attestation", "name": "Identity Attestation"},
]

_COHERENCE_SCORING_CHILDREN = [
    {"id": "test-coverage-analysis", "name": "Test Coverage Analysis"},
    {"id": "documentation-quality-metrics", "name": "Documentation Quality Metrics"},
    {"id": "simplicity-index", "name": "Simplicity Index"},
]


def _upsert_node(s, node_id: str, name: str, coherence_score: float = 0.0) -> None:
    existing = s.get(Node, node_id)
    if existing:
        return
    node = Node(
        id=node_id,
        type="concept",
        name=name,
        description="",
        properties={"lifecycle_state": "water", "coherence_score": coherence_score, "open_questions": []},
        phase="water",
    )
    s.add(node)
    try:
        s.flush()
    except IntegrityError:
        s.rollback()
        log.debug("Node %s already exists (race), skipping", node_id)


def _upsert_edge(s, from_id: str, to_id: str, edge_type: str) -> None:
    existing = (
        s.query(Edge)
        .filter(Edge.from_id == from_id, Edge.to_id == to_id, Edge.type == edge_type)
        .first()
    )
    if existing:
        return
    import uuid
    edge = Edge(
        id=str(uuid.uuid4())[:12],
        from_id=from_id,
        to_id=to_id,
        type=edge_type,
        properties={},
        strength=1.0,
        created_by="pillar_seed",
    )
    s.add(edge)
    try:
        s.flush()
    except IntegrityError:
        s.rollback()
        log.debug("Edge %s->%s already exists (race), skipping", from_id, to_id)


def seed_pillars() -> None:
    """Idempotently seed pillar nodes and Trust subtree."""
    with session() as s:
        # Seed pillars
        for p in _PILLARS:
            _upsert_node(s, p["id"], p["name"])

        # Seed Trust subtree (depth 2)
        for child in _TRUST_CHILDREN:
            _upsert_node(s, child["id"], child["name"])
            _upsert_edge(s, "trust", child["id"], "parent-of")

        # Seed coherence-scoring subtree (depth 3)
        for child in _COHERENCE_SCORING_CHILDREN:
            _upsert_node(s, child["id"], child["name"])
            _upsert_edge(s, "coherence-scoring", child["id"], "parent-of")

        s.commit()
        log.info("pillar_seed complete: %d pillars, Trust subtree seeded", len(_PILLARS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_pillars()
    print("Seed complete.")
