"""Onboarding Service -- Trust-on-First-Use (TOFU) MVP.

Spec 168: zero-friction handle claim -> session token.
"""
from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    contributor_id: Mapped[str] = mapped_column(String, primary_key=True)
    handle: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    session_token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    trust_level: Mapped[str] = mapped_column(String, nullable=False, default="tofu")
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hint_github: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hint_wallet: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session():
    with _udb.session() as s:
        yield s


def _make_contributor_id(handle: str) -> str:
    return "onboard:" + hashlib.sha1(handle.lower().encode()).hexdigest()[:16]


def _make_token() -> str:
    return os.urandom(32).hex()


def register(
    handle: str,
    email: Optional[str] = None,
    hint_github: Optional[str] = None,
    hint_wallet: Optional[str] = None,
) -> dict:
    """Claim a handle and return a TOFU session token.

    Raises ValueError("handle_taken") if the handle is already registered.
    """
    _ensure_schema()
    contributor_id = _make_contributor_id(handle)
    with _session() as db:
        if db.query(OnboardingSession).filter(OnboardingSession.handle == handle).first():
            raise ValueError("handle_taken")
        existing = db.query(OnboardingSession).filter(
            OnboardingSession.contributor_id == contributor_id
        ).first()
        if existing:
            return {
                "contributor_id": existing.contributor_id,
                "session_token": existing.session_token,
                "trust_level": existing.trust_level,
                "handle": existing.handle,
                "created": False,
            }
        token = _make_token()
        row = OnboardingSession(
            contributor_id=contributor_id, handle=handle, session_token=token,
            trust_level="tofu", email=email, hint_github=hint_github, hint_wallet=hint_wallet,
        )
        db.add(row)
        db.commit()
        return {
            "contributor_id": contributor_id, "session_token": token,
            "trust_level": "tofu", "handle": handle, "created": True,
        }


def resolve_session(token: str) -> Optional[dict]:
    """Return contributor profile from session token, or None."""
    _ensure_schema()
    with _session() as db:
        row = db.query(OnboardingSession).filter(
            OnboardingSession.session_token == token
        ).first()
        if not row:
            return None
        try:
            from app.services import contributor_identity_service as _cis
            linked = len(_cis.get_identities(row.contributor_id))
        except Exception:
            linked = 0
        return {
            "contributor_id": row.contributor_id, "handle": row.handle,
            "trust_level": row.trust_level, "linked_identities": linked,
            "email": row.email, "hint_github": row.hint_github, "hint_wallet": row.hint_wallet,
        }


_IDEA_ID = "identity-driven-onboarding"
_EVIDENCE_SPECS = (
    "specs/168-identity-driven-onboarding-tofu.md",
    "specs/task_957a8a7e00501874.md",
)


def get_roi_signals() -> dict:
    """Compute live ROI signals for the onboarding funnel.

    Includes stable decision metadata for audits: MVP uses TOFU (no verification),
    OAuth upgrade tracked under spec-169. See spec 168 Evidence section.
    """
    _ensure_schema()
    with _session() as db:
        rows = db.query(OnboardingSession).all()
        total = len(rows)
        verified = [r for r in rows if r.trust_level == "verified"]
        verified_count = len(verified)
        verified_ratio = round(verified_count / total, 4) if total > 0 else 0.0
        durations = [
            (r.verified_at - r.created_at).total_seconds() / 86400.0
            for r in verified if r.verified_at and r.created_at
        ]
        avg_days = round(sum(durations) / len(durations), 2) if durations else None
        return {
            "handle_registrations": total,
            "verified_count": verified_count,
            "verified_ratio": verified_ratio,
            "avg_time_to_verify_days": avg_days,
            "spec_ref": "spec-168",
            "idea_id": _IDEA_ID,
            "mvp_trust_mode": "tofu",
            "oauth_upgrade_spec_ref": "spec-169",
            "evidence_spec_paths": list(_EVIDENCE_SPECS),
        }
