"""Marketplace service: publish, browse, fork, reputation, and federation sync.

Implements spec 121: OpenClaw Idea Marketplace.

Storage: in-memory for MVP (same pattern as other lightweight services).
All writes are thread-safe via a single module-level lock.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores (MVP — no DB migration needed)
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# listing_id -> MarketplaceListing
_listings: dict[str, "MarketplaceListing"] = {}

# content_hash -> listing_id (for duplicate detection)
_hash_index: dict[str, str] = {}

# fork_id -> MarketplaceFork
_forks: dict[str, "MarketplaceFork"] = {}

# author_id -> [listing_id, ...]
_author_listings: dict[str, list[str]] = {}


# ---------------------------------------------------------------------------
# Lazy imports to avoid circular deps
# ---------------------------------------------------------------------------

def _get_idea(idea_id: str):
    """Fetch an idea from the idea service, returning None if not found."""
    from app.services import idea_service
    try:
        ideas = idea_service.list_ideas()
        for idea in ideas.ideas:
            if idea.id == idea_id:
                return idea
    except Exception:
        logger.warning("Failed to fetch idea %s", idea_id, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Content hash computation
# ---------------------------------------------------------------------------

def _compute_content_hash(name: str, description: str) -> str:
    """SHA-256 of normalized (lowercased, stripped) name + description."""
    normalized = (name.strip().lower() + "|" + description.strip().lower())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

def _check_quality_gate(idea) -> list[dict]:
    """Return a list of field-level errors; empty list means gate passed."""
    errors: list[dict] = []
    if idea.confidence < 0.3:
        errors.append({
            "field": "confidence",
            "message": f"Must be >= 0.3, got {idea.confidence}",
        })
    # value_basis must have at least one non-empty entry
    vb = getattr(idea, "value_basis", None)
    if not vb or not any(v for v in vb.values()):
        errors.append({
            "field": "value_basis",
            "message": "At least one entry required",
        })
    return errors


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def publish_idea(
    idea_id: str,
    tags: list[str],
    author_display_name: str,
    visibility: str = "public",
    instance_id: Optional[str] = None,
) -> tuple[Optional["MarketplaceListing"], str, Optional[str]]:
    """Publish an idea to the marketplace.

    Returns (listing, status, existing_listing_id_or_none).
    status is one of: "created", "not_found", "quality_gate", "duplicate".
    """
    from app.models.marketplace import (
        MarketplaceListing,
        QualityGateError,
    )

    idea = _get_idea(idea_id)
    if idea is None:
        return None, "not_found", None

    errors = _check_quality_gate(idea)
    if errors:
        return errors, "quality_gate", None

    content_hash = _compute_content_hash(idea.name, idea.description)

    with _lock:
        # Duplicate detection
        existing_id = _hash_index.get(content_hash)
        if existing_id and existing_id in _listings:
            return None, "duplicate", existing_id

        # Build listing
        origin_instance = instance_id or os.getenv("INSTANCE_ID", "local-instance")
        author_id = f"{author_display_name}@{origin_instance}"
        listing_id = f"mkt_{uuid4().hex[:12]}"

        listing = MarketplaceListing(
            listing_id=listing_id,
            idea_id=idea_id,
            origin_instance_id=origin_instance,
            author_id=author_id,
            author_display_name=author_display_name,
            name=idea.name,
            description=idea.description,
            potential_value=idea.potential_value,
            estimated_cost=idea.estimated_cost,
            confidence=idea.confidence,
            tags=list(tags),
            content_hash=content_hash,
            visibility=visibility,
            published_at=datetime.now(timezone.utc),
            fork_count=0,
            adoption_score=0.0,
            status="active",
        )

        _listings[listing_id] = listing
        _hash_index[content_hash] = listing_id

        # Track author
        if author_id not in _author_listings:
            _author_listings[author_id] = []
        _author_listings[author_id].append(listing_id)

    # Kick off federation sync (fire-and-forget, failures logged not raised)
    try:
        _sync_listing_to_federation(listing)
    except Exception:
        logger.warning("Federation sync failed for listing %s", listing_id, exc_info=True)

    return listing, "created", None


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------

def browse_listings(
    page: int = 1,
    page_size: int = 20,
    tags: Optional[str] = None,
    sort: str = "recent",
    search: Optional[str] = None,
    min_confidence: Optional[float] = None,
) -> "BrowseResponse":
    """Return a paginated, filtered, sorted list of marketplace listings."""
    from app.models.marketplace import BrowseResponse

    with _lock:
        items = [l for l in _listings.values() if l.status == "active"]

    # Tag filter
    if tags:
        tag_set = {t.strip().lower() for t in tags.split(",") if t.strip()}
        items = [l for l in items if tag_set.intersection({t.lower() for t in l.tags})]

    # Min confidence filter
    if min_confidence is not None:
        items = [l for l in items if l.confidence >= min_confidence]

    # Full-text search on name + description
    if search:
        q = search.strip().lower()
        items = [l for l in items if q in l.name.lower() or q in l.description.lower()]

    # Sort
    if sort == "popular":
        items.sort(key=lambda l: (l.fork_count, l.adoption_score), reverse=True)
    elif sort == "value":
        items.sort(key=lambda l: l.adoption_score, reverse=True)
    else:  # "recent"
        items.sort(key=lambda l: l.published_at, reverse=True)

    total = len(items)
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size
    page_items = items[offset: offset + page_size]

    return BrowseResponse(
        listings=page_items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Fork
# ---------------------------------------------------------------------------

def fork_listing(
    listing_id: str,
    forker_id: str,
    notes: str = "",
) -> tuple[Optional["MarketplaceFork"], str]:
    """Fork a marketplace listing, creating a local idea copy.

    Returns (fork, status) where status is 'created' or 'not_found'.
    """
    from app.models.marketplace import MarketplaceFork

    with _lock:
        listing = _listings.get(listing_id)
        if listing is None:
            return None, "not_found"

    # Create a local idea copy
    local_idea_id = _create_forked_idea(listing, forker_id, notes)

    # Create a value lineage link for origin author attribution
    lineage_link_id = _create_lineage_link(listing, local_idea_id, forker_id)

    fork_id = f"fork_{uuid4().hex[:12]}"
    fork = MarketplaceFork(
        fork_id=fork_id,
        local_idea_id=local_idea_id,
        forked_from_listing_id=listing_id,
        forked_from_idea_id=listing.idea_id,
        forked_from_instance_id=listing.origin_instance_id,
        forked_by=forker_id,
        notes=notes,
        forked_at=datetime.now(timezone.utc),
        lineage_link_id=lineage_link_id,
    )

    with _lock:
        _forks[fork_id] = fork
        # Increment fork count on listing
        if listing_id in _listings:
            current = _listings[listing_id]
            # Rebuild with incremented fork count
            updated = current.model_copy(update={"fork_count": current.fork_count + 1})
            _listings[listing_id] = updated

    return fork, "created"


def _create_forked_idea(listing, forker_id: str, notes: str) -> str:
    """Create a local idea from a marketplace listing, return its id."""
    from app.models.idea import IdeaCreate
    from app.services import idea_service

    new_id = f"forked-{listing.idea_id[:20]}-{uuid4().hex[:6]}"
    fork_description = listing.description
    if notes:
        fork_description = f"{fork_description}\n\n[Forked by {forker_id}: {notes}]"

    idea_create = IdeaCreate(
        id=new_id,
        name=f"[Fork] {listing.name}",
        description=fork_description,
        potential_value=listing.potential_value,
        estimated_cost=listing.estimated_cost,
        confidence=listing.confidence,
        tags=list(listing.tags),
        value_basis={"forked_from": f"marketplace listing {listing.listing_id}"},
    )
    try:
        idea_service.create_idea(idea_create)
    except Exception:
        logger.warning("Failed to create local idea for fork", exc_info=True)

    return new_id


def _create_lineage_link(listing, local_idea_id: str, forker_id: str) -> Optional[str]:
    """Create a value lineage link with origin_author role for attribution."""
    try:
        from app.services import value_lineage_service
        link_id = f"vl_{uuid4().hex[:12]}"
        # The origin author gets 10% attribution weight on downstream value
        value_lineage_service.create_link(
            idea_id=local_idea_id,
            contributor_id=listing.author_id,
            role="origin_author",
            weight=0.10,
            metadata={
                "marketplace_listing_id": listing.listing_id,
                "origin_idea_id": listing.idea_id,
                "origin_instance_id": listing.origin_instance_id,
                "forked_by": forker_id,
            },
        )
        return link_id
    except Exception:
        logger.warning("Failed to create lineage link for fork", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Reputation
# ---------------------------------------------------------------------------

def get_author_reputation(author_id: str) -> Optional["AuthorReputation"]:
    """Compute reputation score for an author across all their listings."""
    from app.models.marketplace import AuthorReputation

    with _lock:
        listing_ids = _author_listings.get(author_id, [])
        author_listings = [_listings[lid] for lid in listing_ids if lid in _listings]

    if not author_listings and author_id not in _author_listings:
        return None

    total_forks = sum(l.fork_count for l in author_listings)
    total_adoption_cc = sum(l.adoption_score for l in author_listings)

    # reputation = sum(adoption_score * confidence) / (1 + age_penalty)
    now = datetime.now(timezone.utc)
    reputation_score = 0.0
    for listing in author_listings:
        age_days = (now - listing.published_at).days
        age_penalty = age_days / 365.0  # gentle annual decay
        contribution = (listing.adoption_score * listing.confidence) / (1.0 + age_penalty)
        reputation_score += contribution

    return AuthorReputation(
        author_id=author_id,
        reputation_score=round(reputation_score, 4),
        total_publications=len(author_listings),
        total_forks=total_forks,
        total_adoption_cc=total_adoption_cc,
        computed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Federation sync adapter
# ---------------------------------------------------------------------------

def _sync_listing_to_federation(listing) -> None:
    """Push a marketplace listing as a MARKETPLACE_LISTING federated payload."""
    try:
        from app.services import federation_service
        payload = {
            "type": "MARKETPLACE_LISTING",
            "listing_id": listing.listing_id,
            "data": listing.model_dump(mode="json"),
        }
        federation_service.broadcast_marketplace_payload(payload)
    except Exception:
        logger.warning("Federation broadcast not available", exc_info=True)


def ingest_federated_listing(payload_data: dict) -> bool:
    """Accept a MARKETPLACE_LISTING payload from a remote instance."""
    from app.models.marketplace import MarketplaceListing

    try:
        listing = MarketplaceListing(**payload_data)
        with _lock:
            if listing.content_hash in _hash_index:
                return False  # Already exists
            _listings[listing.listing_id] = listing
            _hash_index[listing.content_hash] = listing.listing_id
            if listing.author_id not in _author_listings:
                _author_listings[listing.author_id] = []
            _author_listings[listing.author_id].append(listing.listing_id)
        return True
    except Exception:
        logger.warning("Failed to ingest federated listing", exc_info=True)
        return False


def ingest_federated_fork(payload_data: dict) -> bool:
    """Accept a MARKETPLACE_FORK payload from a remote instance and update fork count."""
    try:
        listing_id = payload_data.get("forked_from_listing_id")
        if not listing_id:
            return False
        with _lock:
            if listing_id in _listings:
                current = _listings[listing_id]
                updated = current.model_copy(update={"fork_count": current.fork_count + 1})
                _listings[listing_id] = updated
        return True
    except Exception:
        logger.warning("Failed to ingest federated fork", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Internal helpers (for testing)
# ---------------------------------------------------------------------------

def _reset_store() -> None:
    """Clear all in-memory state. For testing only."""
    with _lock:
        _listings.clear()
        _hash_index.clear()
        _forks.clear()
        _author_listings.clear()


def get_listing(listing_id: str) -> Optional["MarketplaceListing"]:
    """Get a listing by ID."""
    with _lock:
        return _listings.get(listing_id)
