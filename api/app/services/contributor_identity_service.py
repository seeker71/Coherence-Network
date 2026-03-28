"""Contributor Identity Service — flexible multi-identity linking.

A contributor can link multiple identities (GitHub, Ethereum, email, etc.)
to their canonical contributor name. Identities can be verified via OAuth
or signatures, or simply recorded as unverified for manual entry.

Uses the unified SQLite store (same pattern as federation_service.py).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, Boolean
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class ContributorIdentityRecord(Base):
    __tablename__ = "contributor_identities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contributor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


# ---------------------------------------------------------------------------
# Supported providers
# ---------------------------------------------------------------------------

from app.services.identity_providers import SUPPORTED_PROVIDERS  # noqa: E402


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def link_identity(
    contributor_id: str,
    provider: str,
    provider_id: str,
    display_name: str | None = None,
    avatar_url: str | None = None,
    verified: bool = False,
    metadata: dict | None = None,
) -> dict:
    """Link an identity to a contributor. Returns the record as a dict.

    If an identity for the same contributor+provider already exists, it is
    updated rather than duplicated.
    """
    _ensure_schema()

    meta_json = json.dumps(metadata or {})
    now = datetime.now(timezone.utc)

    with _session() as s:
        # Check for existing identity for this contributor+provider
        existing = (
            s.query(ContributorIdentityRecord)
            .filter_by(contributor_id=contributor_id, provider=provider)
            .first()
        )
        if existing:
            existing.provider_id = provider_id
            existing.display_name = display_name
            existing.avatar_url = avatar_url
            existing.verified = verified
            existing.metadata_json = meta_json
            existing.linked_at = now
            record_id = existing.id
        else:
            record_id = f"cid_{uuid4().hex[:12]}"
            rec = ContributorIdentityRecord(
                id=record_id,
                contributor_id=contributor_id,
                provider=provider,
                provider_id=provider_id,
                display_name=display_name,
                avatar_url=avatar_url,
                verified=verified,
                linked_at=now,
                metadata_json=meta_json,
            )
            s.add(rec)

    return {
        "id": record_id,
        "contributor_id": contributor_id,
        "provider": provider,
        "provider_id": provider_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "verified": verified,
        "linked_at": now.isoformat(),
        "metadata_json": meta_json,
    }


def get_identities(contributor_id: str) -> list[dict]:
    """Return all linked identities for a contributor."""
    _ensure_schema()
    with _session() as s:
        recs = (
            s.query(ContributorIdentityRecord)
            .filter_by(contributor_id=contributor_id)
            .order_by(ContributorIdentityRecord.linked_at.desc())
            .all()
        )
        return [
            {
                "id": rec.id,
                "contributor_id": rec.contributor_id,
                "provider": rec.provider,
                "provider_id": rec.provider_id,
                "display_name": rec.display_name,
                "avatar_url": rec.avatar_url,
                "verified": rec.verified,
                "linked_at": rec.linked_at.isoformat() if rec.linked_at else None,
                "metadata_json": rec.metadata_json,
            }
            for rec in recs
        ]


def find_contributor_by_identity(provider: str, provider_id: str) -> str | None:
    """Look up a contributor_id by provider+provider_id. Returns None if not found."""
    _ensure_schema()
    with _session() as s:
        rec = (
            s.query(ContributorIdentityRecord)
            .filter_by(provider=provider, provider_id=provider_id)
            .first()
        )
        if rec:
            return rec.contributor_id
    return None


def verify_identity(contributor_id: str, provider: str, provider_id: str) -> bool:
    """Mark a linked identity as verified (e.g. after gist or signature proof)."""
    _ensure_schema()
    with _session() as s:
        rec = (
            s.query(ContributorIdentityRecord)
            .filter_by(
                contributor_id=contributor_id,
                provider=provider,
                provider_id=provider_id,
            )
            .first()
        )
        if not rec:
            return False
        rec.verified = True
        return True


def unlink_identity(contributor_id: str, provider: str) -> bool:
    """Remove a linked identity. Returns True if something was deleted."""
    _ensure_schema()
    with _session() as s:
        rec = (
            s.query(ContributorIdentityRecord)
            .filter_by(contributor_id=contributor_id, provider=provider)
            .first()
        )
        if rec:
            s.delete(rec)
            return True
    return False
