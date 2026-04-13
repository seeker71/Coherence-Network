"""Interest registration service — privacy-first community gathering.

People express interest in The Living Collective. Every registration creates
a graph node with consent flags controlling what's visible to others.
No personal information is ever exposed without explicit consent.

Properties stored on each interested-person node:
    name            — display name (shown only if consent_share_name)
    email           — NEVER exposed via API, used only for updates
    location        — general area (shown only if consent_share_location)
    skills          — what they bring (shown only if consent_share_skills)
    offering        — how they want to contribute (free text)
    resonant_roles  — which roles call to them (list of role slugs)
    message         — personal message / why they're drawn
    consent_share_name      — show name in community directory
    consent_share_location  — show location in community directory
    consent_share_skills    — show skills in community directory
    consent_findable        — appear in community directory at all
    consent_email_updates   — receive progress emails
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services import graph_service

logger = logging.getLogger(__name__)

NODE_TYPE = "interested-person"

# Fields that are NEVER returned in public API responses
_PRIVATE_FIELDS = frozenset({"email", "ip_address"})

# All recognized consent flags with their defaults (opt-out by default)
_CONSENT_DEFAULTS = {
    "consent_share_name": False,
    "consent_share_location": False,
    "consent_share_skills": False,
    "consent_findable": False,
    "consent_email_updates": False,
}

# The 6 roles from the vision
VALID_ROLES = frozenset({
    "living-structure-weaver",
    "nourishment-alchemist",
    "frequency-holder",
    "vitality-keeper",
    "transmission-source",
    "form-grower",
})


def register_interest(
    *,
    name: str,
    email: str,
    location: str = "",
    skills: str = "",
    offering: str = "",
    resonant_roles: list[str] | None = None,
    message: str = "",
    consent_share_name: bool = False,
    consent_share_location: bool = False,
    consent_share_skills: bool = False,
    consent_findable: bool = False,
    consent_email_updates: bool = False,
) -> dict[str, Any]:
    """Register a person's interest. Returns the created node dict (with private fields stripped)."""
    node_id = f"ip-{uuid.uuid4().hex[:10]}"

    # Validate roles
    roles = [r for r in (resonant_roles or []) if r in VALID_ROLES]

    properties: dict[str, Any] = {
        "email": email,
        "location": location,
        "skills": skills,
        "offering": offering,
        "resonant_roles": roles,
        "message": message,
        "consent_share_name": consent_share_name,
        "consent_share_location": consent_share_location,
        "consent_share_skills": consent_share_skills,
        "consent_findable": consent_findable,
        "consent_email_updates": consent_email_updates,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }

    node = graph_service.create_node(
        id=node_id,
        type=NODE_TYPE,
        name=name,
        description=offering or message or "",
        properties=properties,
    )

    # Create edges to resonant roles (as concept connections)
    for role in roles:
        try:
            graph_service.create_edge(
                from_id=node_id,
                to_id=f"lc-{role}",  # concept node IDs follow this pattern
                type="drawn-to",
                properties={"source": "registration"},
            )
        except Exception:
            # Role concept may not exist yet — that's fine
            logger.debug("Could not link %s to role concept lc-%s", node_id, role)

    logger.info("Registered interest: %s (roles: %s, findable: %s)", node_id, roles, consent_findable)
    return _strip_private(node)


def list_community(*, limit: int = 200) -> list[dict[str, Any]]:
    """List people who have consented to being findable. Private fields always stripped."""
    result = graph_service.list_nodes(type=NODE_TYPE, limit=limit)
    all_nodes = result.get("items", [])
    visible = []
    for node in all_nodes:
        props = node.get("properties", node)
        # Only include people who explicitly opted in
        if props.get("consent_findable", False):
            visible.append(_apply_consent_filter(node))
    return visible


def get_person_public(person_id: str) -> dict[str, Any] | None:
    """Get a single person's public profile (consent-filtered)."""
    node = graph_service.get_node(person_id)
    if not node or node.get("type") != NODE_TYPE:
        return None
    props = node.get("properties", node)
    if not props.get("consent_findable", False):
        return None
    return _apply_consent_filter(node)


def get_interest_stats() -> dict[str, Any]:
    """Aggregate stats — no personal information."""
    result = graph_service.list_nodes(type=NODE_TYPE, limit=10000)
    all_nodes = result.get("items", [])
    total = len(all_nodes)
    findable = sum(1 for n in all_nodes if (n.get("properties", n)).get("consent_findable", False))

    role_counts: dict[str, int] = {}
    location_counts: dict[str, int] = {}
    for node in all_nodes:
        props = node.get("properties", node)
        for role in props.get("resonant_roles", []):
            role_counts[role] = role_counts.get(role, 0) + 1
        loc = props.get("location", "")
        if loc:
            # Only count general regions, not specific addresses
            region = loc.split(",")[0].strip() if "," in loc else loc
            location_counts[region] = location_counts.get(region, 0) + 1

    return {
        "total_interested": total,
        "findable_count": findable,
        "role_interest": role_counts,
        "location_regions": location_counts,
    }


def _strip_private(node: dict[str, Any]) -> dict[str, Any]:
    """Remove private fields from a node dict."""
    result = {k: v for k, v in node.items() if k not in _PRIVATE_FIELDS}
    if "properties" in result and isinstance(result["properties"], dict):
        result["properties"] = {k: v for k, v in result["properties"].items() if k not in _PRIVATE_FIELDS}
    return result


def _apply_consent_filter(node: dict[str, Any]) -> dict[str, Any]:
    """Apply consent flags to control what's visible. Always strips private fields."""
    result = _strip_private(node)
    props = result.get("properties", result)

    # If name not consented, replace with anonymous
    if not props.get("consent_share_name", False):
        result["name"] = "A resonant soul"
        if "properties" in result:
            result["properties"].pop("name", None)

    # If location not consented, remove it
    if not props.get("consent_share_location", False):
        if isinstance(result.get("properties"), dict):
            result["properties"].pop("location", None)
        result.pop("location", None)

    # If skills not consented, remove them
    if not props.get("consent_share_skills", False):
        if isinstance(result.get("properties"), dict):
            result["properties"].pop("skills", None)
        result.pop("skills", None)

    return result
