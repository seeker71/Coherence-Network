"""Onboarding Service - Trust-on-First-Use (TOFU) identity registration.
Spec: specs/168-identity-driven-onboarding-tofu.md
"""
from __future__ import annotations
import hashlib, os
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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

def _ensure_schema(): _udb.ensure_schema()

@contextmanager
def _session():
    with _udb.session() as s: yield s

def _make_contributor_id(handle: str) -> str:
    return "onboard:" + hashlib.sha1(handle.lower().encode()).hexdigest()[:16]

def _make_session_token() -> str:
    return os.urandom(32).hex()

def register(handle: str, email=None, hint_github=None, hint_wallet=None) -> dict:
    """Claim a handle and receive a TOFU session token. Raises ValueError('handle_taken') if taken."""
    _ensure_schema()
    contributor_id = _make_contributor_id(handle)
    with _session() as db:
        if db.query(OnboardingSession).filter(OnboardingSession.handle == handle).first():
            raise ValueError("handle_taken")
        if (ex := db.query(OnboardingSession).filter(OnboardingSession.contributor_id == contributor_id).first()):
            return {"contributor_id": ex.contributor_id, "session_token": ex.session_token, "trust_level": ex.trust_level, "handle": ex.handle, "created": False}
        token = _make_session_token()
        db.add(OnboardingSession(contributor_id=contributor_id, handle=handle, session_token=token, trust_level="tofu", email=email, hint_github=hint_github, hint_wallet=hint_wallet))
        db.commit()
        return {"contributor_id": contributor_id, "session_token": token, "trust_level": "tofu", "handle": handle, "created": True}

def resolve_session(token: str) -> Optional[dict]:
    """Return contributor profile from a session token, or None."""
    _ensure_schema()
    with _session() as db:
        row = db.query(OnboardingSession).filter(OnboardingSession.session_token == token).first()
        if not row: return None
        try:
            from app.services import contributor_identity_service as _cis
            linked = len(_cis.get_identities(row.contributor_id))
        except Exception: linked = 0
        return {"contributor_id": row.contributor_id, "handle": row.handle, "trust_level": row.trust_level, "linked_identities": linked, "email": row.email, "hint_github": row.hint_github, "hint_wallet": row.hint_wallet}

def upgrade_trust(contributor_id: str, provider: str, provider_id: str, display_name=None, avatar_url=None, metadata=None) -> dict:
    """Upgrade TOFU session to verified. Raises ValueError('contributor_not_found') if no session."""
    _ensure_schema()
    with _session() as db:
        row = db.query(OnboardingSession).filter(OnboardingSession.contributor_id == contributor_id).first()
        if not row: raise ValueError("contributor_not_found")
        try:
            from app.services import contributor_identity_service as _cis
            _cis.link_identity(contributor_id=contributor_id, provider=provider, provider_id=provider_id, display_name=display_name, avatar_url=avatar_url, verified=True, metadata=metadata)
        except Exception: pass
        row.trust_level = "verified"
        row.verified_at = datetime.now(timezone.utc)
        db.commit()
        return {"contributor_id": contributor_id, "trust_level": "verified", "provider": provider, "provider_id": provider_id}

def get_roi_signals() -> dict:
    """Compute live ROI signals for the onboarding funnel."""
    _ensure_schema()
    with _session() as db:
        rows = db.query(OnboardingSession).all()
        total = len(rows)
        verified = [r for r in rows if r.trust_level == "verified"]
        verified_count = len(verified)
        verified_ratio = round(verified_count / total, 4) if total > 0 else 0.0
        durations = [(r.verified_at - r.created_at).total_seconds() / 86400.0 for r in verified if r.verified_at and r.created_at]
        return {"handle_registrations": total, "verified_count": verified_count, "verified_ratio": verified_ratio, "avg_time_to_verify_days": round(sum(durations) / len(durations), 2) if durations else None, "spec_ref": "spec-168"}
