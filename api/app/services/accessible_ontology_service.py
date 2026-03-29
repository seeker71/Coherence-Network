"""Accessible ontology service — plain-language contributions by non-technical users.

Supports:
- Concept suggestions (plain text, no IDs required)
- Relationship suggestions between concepts
- Endorsements (upvotes on existing concepts)
- Review queue: pending → approved/rejected

Approved concept suggestions are auto-promoted into the live concept store.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services import concept_service

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_concept_suggestions: dict[str, dict[str, Any]] = {}
_relationship_suggestions: dict[str, dict[str, Any]] = {}
_endorsements: dict[str, list[str]] = {}  # concept_id -> [contributor_ids]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(name: str) -> str:
    """Convert a plain name to a URL-safe concept ID."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return f"user.suggested.{slug[:60]}"


# ---------------------------------------------------------------------------
# Concept suggestions
# ---------------------------------------------------------------------------

def suggest_concept(
    *,
    name: str,
    plain_description: str,
    contributor: str = "anonymous",
    example_use: str = "",
    related_to: list[str] | None = None,
) -> dict[str, Any]:
    """Create a concept suggestion without requiring technical knowledge."""
    suggestion_id = str(uuid.uuid4())
    proposed_id = _slugify(name)
    record: dict[str, Any] = {
        "id": suggestion_id,
        "proposed_concept_id": proposed_id,
        "name": name,
        "plain_description": plain_description,
        "example_use": example_use,
        "related_to": related_to or [],
        "contributor": contributor,
        "status": "pending",
        "created_at": _now(),
        "reviewed_at": None,
        "reviewed_by": None,
        "review_note": None,
        "promoted_concept_id": None,
    }
    _concept_suggestions[suggestion_id] = record
    return record


def list_concept_suggestions(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    items = list(_concept_suggestions.values())
    if status:
        items = [s for s in items if s["status"] == status]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


def get_concept_suggestion(suggestion_id: str) -> dict[str, Any] | None:
    return _concept_suggestions.get(suggestion_id)


def approve_concept_suggestion(
    suggestion_id: str,
    *,
    reviewer: str = "maintainer",
    review_note: str = "",
    final_id: str | None = None,
    final_name: str | None = None,
) -> dict[str, Any]:
    """Approve a suggestion and auto-promote it into the live ontology."""
    record = _concept_suggestions.get(suggestion_id)
    if not record:
        raise KeyError(f"Suggestion '{suggestion_id}' not found")
    if record["status"] != "pending":
        raise ValueError(f"Suggestion is already '{record['status']}'")

    concept_id = final_id or record["proposed_concept_id"]
    name = final_name or record["name"]

    # Ensure unique ID
    if concept_service.get_concept(concept_id):
        concept_id = f"{concept_id}-{suggestion_id[:8]}"

    concept_service.create_concept(
        {
            "id": concept_id,
            "name": name,
            "description": record["plain_description"],
            "type_id": "codex.ucore.user",
            "level": 0,
            "keywords": [],
            "parent_concepts": [],
            "child_concepts": [],
            "axes": [],
        }
    )

    record.update(
        {
            "status": "approved",
            "reviewed_at": _now(),
            "reviewed_by": reviewer,
            "review_note": review_note,
            "promoted_concept_id": concept_id,
        }
    )
    return record


def reject_concept_suggestion(
    suggestion_id: str,
    *,
    reviewer: str = "maintainer",
    review_note: str = "",
) -> dict[str, Any]:
    record = _concept_suggestions.get(suggestion_id)
    if not record:
        raise KeyError(f"Suggestion '{suggestion_id}' not found")
    if record["status"] != "pending":
        raise ValueError(f"Suggestion is already '{record['status']}'")
    record.update(
        {
            "status": "rejected",
            "reviewed_at": _now(),
            "reviewed_by": reviewer,
            "review_note": review_note,
        }
    )
    return record


# ---------------------------------------------------------------------------
# Relationship suggestions
# ---------------------------------------------------------------------------

def suggest_relationship(
    *,
    from_concept_name: str,
    to_concept_name: str,
    plain_relationship: str,
    contributor: str = "anonymous",
    example_sentence: str = "",
) -> dict[str, Any]:
    """Suggest a relationship in plain language ('X leads to Y', 'X is a type of Y')."""
    suggestion_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "id": suggestion_id,
        "from_concept_name": from_concept_name,
        "to_concept_name": to_concept_name,
        "plain_relationship": plain_relationship,
        "example_sentence": example_sentence,
        "contributor": contributor,
        "status": "pending",
        "created_at": _now(),
        "reviewed_at": None,
        "reviewed_by": None,
        "review_note": None,
    }
    _relationship_suggestions[suggestion_id] = record
    return record


def list_relationship_suggestions(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    items = list(_relationship_suggestions.values())
    if status:
        items = [s for s in items if s["status"] == status]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


def review_relationship_suggestion(
    suggestion_id: str,
    *,
    action: str,  # "approve" | "reject"
    reviewer: str = "maintainer",
    review_note: str = "",
) -> dict[str, Any]:
    record = _relationship_suggestions.get(suggestion_id)
    if not record:
        raise KeyError(f"Relationship suggestion '{suggestion_id}' not found")
    if record["status"] != "pending":
        raise ValueError(f"Suggestion is already '{record['status']}'")
    if action not in ("approve", "reject"):
        raise ValueError("action must be 'approve' or 'reject'")
    record.update(
        {
            "status": "approved" if action == "approve" else "rejected",
            "reviewed_at": _now(),
            "reviewed_by": reviewer,
            "review_note": review_note,
        }
    )
    return record


# ---------------------------------------------------------------------------
# Endorsements
# ---------------------------------------------------------------------------

def endorse_concept(concept_id: str, contributor: str = "anonymous") -> dict[str, Any]:
    """Upvote / endorse a concept to signal its importance."""
    if not concept_service.get_concept(concept_id):
        raise KeyError(f"Concept '{concept_id}' not found")
    endorsers = _endorsements.setdefault(concept_id, [])
    if contributor not in endorsers:
        endorsers.append(contributor)
    return {
        "concept_id": concept_id,
        "endorsement_count": len(endorsers),
        "contributor": contributor,
    }


def get_endorsements(concept_id: str) -> dict[str, Any]:
    if not concept_service.get_concept(concept_id):
        raise KeyError(f"Concept '{concept_id}' not found")
    endorsers = _endorsements.get(concept_id, [])
    return {
        "concept_id": concept_id,
        "endorsement_count": len(endorsers),
        "endorsers": endorsers,
    }


def top_endorsed(limit: int = 20) -> list[dict[str, Any]]:
    """Return concepts ranked by endorsement count."""
    ranked = [
        {"concept_id": cid, "endorsement_count": len(endorsers)}
        for cid, endorsers in _endorsements.items()
    ]
    ranked.sort(key=lambda x: x["endorsement_count"], reverse=True)
    return ranked[:limit]
