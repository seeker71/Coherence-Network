"""Onboarding service — Trust-on-First-Use (TOFU) identity registration.

Spec 168: Zero-friction contributor onboarding.

In-memory + SQLite store. No OAuth required at registration. Handles are
unique and immutable once registered. Session tokens expire after 30 days.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Optional

from sqlalchemy import Column, String, Float, Integer, text
from sqlalchemy.exc import IntegrityError

from app.services import unified_db

# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------

from app.services.unified_db import Base


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"
    __table_args__ = {"extend_existing": True}

    session_token = Column(String, primary_key=True, index=True)
    contributor_id = Column(String, nullable=False, index=True)
    handle = Column(String, nullable=False, unique=True, index=True)
    trust_level = Column(String, nullable=False, default="tofu")
    email = Column(String, nullable=True)
    hint_github = Column(String, nullable=True)
    hint_wallet = Column(String, nullable=True)
    linked_identities = Column(Integer, nullable=False, default=0)
    created_at = Column(Float, nullable=False, default=time.time)
    expires_at = Column(Float, nullable=False)


def _ensure_schema() -> None:
    Base.metadata.create_all(bind=unified_db.engine(), checkfirst=True)


def _make_contributor_id(handle: str) -> str:
    h = hashlib.sha256(handle.encode()).hexdigest()[:12]
    return f"cid_{h}"


def _make_session_token() -> str:
    return f"sess_{secrets.token_urlsafe(32)}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register(
    handle: str,
    email: Optional[str] = None,
    hint_github: Optional[str] = None,
    hint_wallet: Optional[str] = None,
) -> dict:
    """Register a new contributor via TOFU. Returns session token.

    Raises ValueError("handle_taken") if the handle is already registered.
    """
    _ensure_schema()

    contributor_id = _make_contributor_id(handle)
    session_token = _make_session_token()
    now = time.time()
    expires_at = now + 30 * 86400  # 30 days

    session = OnboardingSession(
        session_token=session_token,
        contributor_id=contributor_id,
        handle=handle,
        trust_level="tofu",
        email=email,
        hint_github=hint_github,
        hint_wallet=hint_wallet,
        linked_identities=0,
        created_at=now,
        expires_at=expires_at,
    )

    with unified_db.session() as db:
        # Check for existing handle
        existing = db.query(OnboardingSession).filter_by(handle=handle).first()
        if existing is not None:
            raise ValueError("handle_taken")

        db.add(session)
        try:
            db.flush()
            created = True
        except IntegrityError:
            db.rollback()
            raise ValueError("handle_taken")

    return {
        "contributor_id": contributor_id,
        "session_token": session_token,
        "trust_level": "tofu",
        "handle": handle,
        "created": created,
    }


def resolve_session(token: str) -> Optional[dict]:
    """Return contributor profile for a valid, unexpired session token.

    Returns None if the token is invalid or expired.
    """
    _ensure_schema()

    with unified_db.session() as db:
        row = db.query(OnboardingSession).filter_by(session_token=token).first()
        if row is None:
            return None
        if row.expires_at < time.time():
            return None
        return {
            "contributor_id": row.contributor_id,
            "handle": row.handle,
            "trust_level": row.trust_level,
            "linked_identities": row.linked_identities,
            "email": row.email,
            "hint_github": row.hint_github,
            "hint_wallet": row.hint_wallet,
        }


def get_roi_signals() -> dict:
    """Return live onboarding ROI signals."""
    _ensure_schema()

    with unified_db.session() as db:
        total = db.query(OnboardingSession).count()
        verified = (
            db.query(OnboardingSession)
            .filter(OnboardingSession.trust_level != "tofu")
            .count()
        )
        with_hints = (
            db.query(OnboardingSession)
            .filter(
                (OnboardingSession.hint_github.isnot(None))
                | (OnboardingSession.hint_wallet.isnot(None))
            )
            .count()
        )

    verified_ratio = (verified / total) if total > 0 else 0.0
    hint_ratio = (with_hints / total) if total > 0 else 0.0

    return {
        "handle_registrations": total,
        "verified_count": verified,
        "verified_ratio": round(verified_ratio, 4),
        "with_hints": with_hints,
        "hint_ratio": round(hint_ratio, 4),
        "avg_time_to_verify_days": None,  # computed when verified count > 0
    }
