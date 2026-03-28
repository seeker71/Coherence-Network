"""Contributor graph helpers used by auth/onboarding (see identity-driven-onboarding)."""

from __future__ import annotations

from uuid import uuid4

from app.services import graph_service


def get_contributor(contributor_id: str) -> dict | None:
    """Return the graph node for contributor:{name}, or None."""
    return graph_service.get_node(f"contributor:{contributor_id}")


def create_contributor(*, name: str, contributor_type: str = "HUMAN") -> dict:
    """Create a contributor node (same shape as POST /api/contributors)."""
    node_id = f"contributor:{name}"
    existing = graph_service.get_node(node_id)
    if existing:
        return existing
    email = f"{name}@coherence.network"
    return graph_service.create_node(
        id=node_id,
        type="contributor",
        name=name,
        description=f"{contributor_type} contributor",
        phase="water",
        properties={
            "contributor_type": contributor_type,
            "email": email,
            "wallet_address": None,
            "hourly_rate": None,
            "legacy_id": str(uuid4()),
        },
    )
