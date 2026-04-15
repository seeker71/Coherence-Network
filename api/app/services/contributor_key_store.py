"""Per-contributor API key store.

Durably records personal API keys minted via `POST /api/auth/keys` and
`POST /api/onboard`. Supersedes the in-memory `_KEY_STORE` dict that
previously lived in `auth_keys.py`.

The store only ever sees the *hash* of a raw key. The raw key is returned
from `mint(...)` exactly once and never stored. This is the usual
revocable-credential shape (GitHub PATs, Stripe API keys, etc.).

Attribution design (see also `app/middleware/attribution.py`):
- Verifying a key here ONLY identifies WHO — it does not authorise WHAT.
- Scopes are recorded on mint but not enforced in this layer. Scope
  enforcement is a separate concern left for a dedicated spec.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services.unified_db import Base, ensure_schema, session as db_session


logger = logging.getLogger(__name__)


DEFAULT_SCOPES: list[str] = ["own:read", "own:write", "contribute", "stake", "vote"]


class ContributorApiKeyRecord(Base):
    """ORM table for per-contributor API keys.

    Schema:
        id            SHA-256 hex of the raw key (lookup key)
        contributor_id canonical contributor id / handle
        label         optional user label ("laptop", "ci", etc.)
        provider      linked identity provider at mint time
        provider_id   linked identity id at mint time
        scopes_json   JSON array of scope strings
        created_at    ISO8601 UTC
        last_used_at  ISO8601 UTC, refreshed on successful verify
        revoked_at    ISO8601 UTC when revoked, NULL while active
    """

    __tablename__ = "contributor_api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contributor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scopes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    last_used_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revoked_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)


# --- dataclass views (what routes see, never the raw row) ---------------


@dataclass(frozen=True)
class KeyRow:
    """Metadata about a minted key. Never contains the raw secret."""

    id: str
    contributor_id: str
    label: Optional[str]
    provider: Optional[str]
    provider_id: Optional[str]
    scopes: list[str]
    created_at: str
    last_used_at: Optional[str]
    revoked_at: Optional[str]

    @property
    def fingerprint(self) -> str:
        """First four and last four chars of the hash, for visual disambiguation."""
        return f"{self.id[:4]}…{self.id[-4:]}"

    @property
    def active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True)
class KeyMinted:
    """Returned once from mint() — holds the raw secret plus metadata."""

    raw_key: str
    row: KeyRow


# --- helpers -------------------------------------------------------------


def _iso_utc(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _to_row(record: ContributorApiKeyRecord) -> KeyRow:
    try:
        scopes = json.loads(record.scopes_json)
        if not isinstance(scopes, list):
            scopes = []
    except Exception:
        scopes = []
    return KeyRow(
        id=record.id,
        contributor_id=record.contributor_id,
        label=record.label,
        provider=record.provider,
        provider_id=record.provider_id,
        scopes=[str(s) for s in scopes],
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
    )


# --- public API ----------------------------------------------------------


def mint(
    contributor_id: str,
    *,
    label: Optional[str] = None,
    provider: Optional[str] = None,
    provider_id: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    now: Optional[datetime] = None,
) -> KeyMinted:
    """Mint a new personal API key for a contributor.

    The raw key is returned exactly once inside the KeyMinted result. Only
    the SHA-256 hash is persisted, so a lost key cannot be recovered — the
    contributor must mint a new one.
    """
    ensure_schema()
    if not contributor_id:
        raise ValueError("contributor_id is required")

    raw_key = f"cc_{contributor_id}_{secrets.token_hex(16)}"
    key_hash = _hash_key(raw_key)
    created_at = _iso_utc(now)
    scopes_list = scopes if scopes is not None else DEFAULT_SCOPES

    record = ContributorApiKeyRecord(
        id=key_hash,
        contributor_id=contributor_id,
        label=label,
        provider=provider,
        provider_id=provider_id,
        scopes_json=json.dumps(scopes_list),
        created_at=created_at,
        last_used_at=None,
        revoked_at=None,
    )

    with db_session() as session:
        session.add(record)
        session.flush()
        row = _to_row(record)

    logger.info(
        "contributor_key_minted contributor=%s label=%s provider=%s",
        contributor_id,
        label,
        provider,
    )
    return KeyMinted(raw_key=raw_key, row=row)


def verify(raw_key: str, *, now: Optional[datetime] = None) -> Optional[KeyRow]:
    """Verify a raw key and return its metadata row, or None.

    Revoked keys return None. Successful verifications refresh
    `last_used_at`. Verification is cheap: one indexed primary-key lookup.
    """
    if not raw_key:
        return None
    ensure_schema()
    key_hash = _hash_key(raw_key)
    stamp = _iso_utc(now)
    with db_session() as session:
        record = session.get(ContributorApiKeyRecord, key_hash)
        if record is None:
            return None
        if record.revoked_at is not None:
            return None
        record.last_used_at = stamp
        session.flush()
        return _to_row(record)


def list_for(contributor_id: str, *, include_revoked: bool = False) -> list[KeyRow]:
    """List keys minted for a contributor, newest first. No raw keys."""
    ensure_schema()
    with db_session() as session:
        stmt = select(ContributorApiKeyRecord).where(
            ContributorApiKeyRecord.contributor_id == contributor_id
        )
        if not include_revoked:
            stmt = stmt.where(ContributorApiKeyRecord.revoked_at.is_(None))
        stmt = stmt.order_by(ContributorApiKeyRecord.created_at.desc())
        rows = session.execute(stmt).scalars().all()
        return [_to_row(r) for r in rows]


def revoke(
    key_id: str,
    *,
    owner_contributor_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """Revoke a key by its hash id.

    If `owner_contributor_id` is given, the record's contributor_id must
    match — prevents one contributor from revoking another's keys via the
    HTTP layer. Passing None bypasses the owner check (intended only for
    admin/maintenance callers).

    Returns True when a key was revoked, False when it did not exist, was
    already revoked, or belonged to a different contributor.
    """
    ensure_schema()
    with db_session() as session:
        record = session.get(ContributorApiKeyRecord, key_id)
        if record is None:
            return False
        if record.revoked_at is not None:
            return False
        if owner_contributor_id is not None and record.contributor_id != owner_contributor_id:
            return False
        record.revoked_at = _iso_utc(now)
        session.flush()
    logger.info("contributor_key_revoked id=%s owner=%s", key_id, owner_contributor_id)
    return True


def count_active() -> int:
    ensure_schema()
    with db_session() as session:
        stmt = select(func.count()).select_from(ContributorApiKeyRecord).where(
            ContributorApiKeyRecord.revoked_at.is_(None)
        )
        return int(session.execute(stmt).scalar_one())


def get_by_id(key_id: str) -> Optional[KeyRow]:
    ensure_schema()
    with db_session() as session:
        record = session.get(ContributorApiKeyRecord, key_id)
        return _to_row(record) if record else None
