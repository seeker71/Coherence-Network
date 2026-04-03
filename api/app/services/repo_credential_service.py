"""Repo Credential Service — per-contributor, per-repo credential tracking.

Spec 169: Each contributor can provide credentials (token, SSH key, etc.)
for each repo they have access to. This enables routing tasks to contributors
with the right permissions.

Raw credentials are NEVER stored in this database — only SHA-256 hashes for 
verification and status tracking. The actual secrets are managed in 
~/.coherence-network/keys.json or other secure local storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.services import unified_db as _udb
from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class RepoCredentialRecord(Base):
    """Stores per-contributor, per-repo credential metadata (hashed)."""
    __tablename__ = "repo_credentials"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contributor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    repo_url: Mapped[str] = mapped_column(String, nullable=False, index=True)
    credential_type: Mapped[str] = mapped_column(String, nullable=False) # e.g. github_token, ssh_key, pat
    credential_hash: Mapped[str] = mapped_column(String, nullable=False) # SHA-256 of the raw secret
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list) # ["push", "pull", "pr_create"]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active") # active, expired, revoked


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_credential(
    contributor_id: str,
    repo_url: str,
    credential_type: str,
    credential_hash: str,
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
) -> dict:
    """Register a new credential (or update existing for same contributor+repo)."""
    _udb.ensure_schema()
    now = datetime.now(timezone.utc)
    
    with _udb.session() as s:
        # Check for existing
        existing = (
            s.query(RepoCredentialRecord)
            .filter_by(contributor_id=contributor_id, repo_url=repo_url)
            .first()
        )
        if existing:
            existing.credential_type = credential_type
            existing.credential_hash = credential_hash
            existing.scopes = scopes or []
            existing.expires_at = expires_at
            existing.status = "active"
            record_id = existing.id
        else:
            record_id = f"cred_{uuid4().hex[:12]}"
            rec = RepoCredentialRecord(
                id=record_id,
                contributor_id=contributor_id,
                repo_url=repo_url,
                credential_type=credential_type,
                credential_hash=credential_hash,
                scopes=scopes or [],
                expires_at=expires_at,
                created_at=now,
                status="active"
            )
            s.add(rec)
            
    return {
        "id": record_id,
        "contributor_id": contributor_id,
        "repo_url": repo_url,
        "credential_type": credential_type,
        "status": "active",
        "created_at": now.isoformat()
    }

def get_credentials(contributor_id: str | None = None, repo_url: str | None = None) -> list[dict]:
    """List credentials, optionally filtered by contributor or repo."""
    _udb.ensure_schema()
    with _udb.session() as s:
        query = s.query(RepoCredentialRecord)
        if contributor_id:
            query = query.filter_by(contributor_id=contributor_id)
        if repo_url:
            query = query.filter_by(repo_url=repo_url)
            
        recs = query.order_by(RepoCredentialRecord.created_at.desc()).all()
        return [
            {
                "id": rec.id,
                "contributor_id": rec.contributor_id,
                "repo_url": rec.repo_url,
                "credential_type": rec.credential_type,
                "scopes": rec.scopes,
                "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
                "last_used_at": rec.last_used_at.isoformat() if rec.last_used_at else None,
                "status": rec.status
            }
            for rec in recs
        ]

def delete_credential(credential_id: str) -> bool:
    """Remove a credential record."""
    _udb.ensure_schema()
    with _udb.session() as s:
        rec = s.query(RepoCredentialRecord).filter_by(id=credential_id).first()
        if rec:
            s.delete(rec)
            return True
    return False

def mark_credential_used(credential_id: str) -> None:
    """Update last_used_at timestamp."""
    _udb.ensure_schema()
    with _udb.session() as s:
        rec = s.query(RepoCredentialRecord).filter_by(id=credential_id).first()
        if rec:
            rec.last_used_at = datetime.now(timezone.utc)
