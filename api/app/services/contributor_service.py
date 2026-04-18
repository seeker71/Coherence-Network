"""Contributor service — thin helpers used by auth_keys and other non-router code.

Wraps graph_service so callers don't need to import routers directly.
"""

from __future__ import annotations

from uuid import uuid4


def get_contributor(contributor_id: str) -> dict | None:
    """Return the graph node for *contributor_id* (by name), or None if not found."""
    from app.services import graph_service

    node = graph_service.get_node(f"contributor:{contributor_id}")
    if node:
        return node
    # Secondary search: scan all contributors by name/legacy_id
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("name") == contributor_id or n.get("legacy_id") == contributor_id:
            return n
    return None


def graduate_by_name(
    author_name: str,
    device_fingerprint: str | None = None,
    invited_by: str | None = None,
) -> tuple[str, bool]:
    """Soft-identity graduation shared across voice + reaction + invite.

    Returns ``(contributor_id, created)``. Idempotent: repeated calls
    with the same name + fingerprint return the same id with
    ``created=False``.

    When minting a new node, ``author_display_name`` and ``invited_by``
    are attached to graph properties so both the community-facing
    /people page and the invite-chain lineage are preserved
    server-side, not only in the client's localStorage.

    A visitor becomes a real contributor the moment they express
    care — a voice, a heart, a comment. No signup screen, no
    private key. The gesture IS the registration.
    """
    from app.services import graph_service

    trimmed = (author_name or "").strip()
    if not trimmed:
        raise ValueError("author_name is required")
    fp = (device_fingerprint or uuid4().hex[:8]).strip()[:24]
    safe_name = "".join(c for c in trimmed.lower() if c.isalnum() or c in "-_") or "friend"
    safe_fp = "".join(c for c in fp.lower() if c.isalnum() or c in "-_") or uuid4().hex[:8]
    candidate_id = f"{safe_name}-{safe_fp}"[:64]
    node_id = f"contributor:{candidate_id}"

    existing = graph_service.get_node(node_id)
    if existing:
        return candidate_id, False

    graph_service.create_node(
        id=node_id,
        type="contributor",
        name=candidate_id,
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"{candidate_id}@coherence.network",
            "author_display_name": trimmed,
            "invited_by": (invited_by or "").strip() or None,
        },
    )
    return candidate_id, True


def create_contributor(
    name: str,
    contributor_type: str = "HUMAN",
    email: str | None = None,
) -> dict:
    """Create a contributor graph node.  Returns the node dict.

    Safe to call when the contributor may already exist — callers should catch
    exceptions if strict uniqueness enforcement is not desired.
    """
    from app.services import graph_service

    node_id = f"contributor:{name}"
    effective_email = email or f"{name}@coherence.network"
    graph_service.create_node(
        id=node_id,
        type="contributor",
        name=name,
        description=f"{contributor_type} contributor",
        phase="water",
        properties={
            "contributor_type": contributor_type,
            "email": effective_email,
        },
    )
    return graph_service.get_node(node_id) or {"id": node_id, "name": name}
