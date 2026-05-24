"""Cross-instance identity — recognition by shared pubkey, not central registry.

A contributor on instance A and a contributor on instance B can recognize
each other without either deferring to a central identity service. Each
contributor holds their own keypair; their identity IS the public key.
Cross-instance recognition is signature verification, not lookup.

This service holds two small tables:

  contributor_pubkeys
    contributor_id (PK) → public_key_hex
    The local contributor's claimed pubkey. Set only after the contributor
    proves possession by signing the claim payload. Rotation requires a
    signature from the OLD pubkey.

  cross_instance_identity
    (local_contributor_id, peer_instance_id, peer_contributor_id, pubkey)
    THIS instance's view of "the contributor I know locally as X is also
    known on peer P as Y." Recorded when a peer sends a recognition
    envelope and the shared pubkey matches a local claim.

Nothing here is authoritative for any other instance. We only record what
WE recognize; the peer maintains its own view of the same person from its
own side. Sovereignty is preserved by symmetric recognition, not by
central deference.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.identity_signing import verify_signature
from app.services.unified_db import Base

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class ContributorPubkey(Base):
    """A pubkey a contributor has claimed (and proven possession of) locally."""

    __tablename__ = "contributor_pubkeys"

    contributor_id: Mapped[str] = mapped_column(String, primary_key=True)
    public_key_hex: Mapped[str] = mapped_column(String, nullable=False, index=True)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    rotated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class CrossInstanceIdentityRecord(Base):
    """THIS instance's recognition that a peer's contributor shares our pubkey."""

    __tablename__ = "cross_instance_identity"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    local_contributor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    peer_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    peer_contributor_id: Mapped[str] = mapped_column(String, nullable=False)
    public_key_hex: Mapped[str] = mapped_column(String, nullable=False, index=True)
    recognized_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ClaimRejection(Exception):
    """The pubkey claim could not be honored — signature missing or invalid."""


class RotationRejection(Exception):
    """A pubkey is already claimed; rotation requires a signature from the old key."""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


def _reset_for_tests() -> None:
    """Clear pubkey + recognition state — used by test fixtures."""
    _ensure_schema()
    with _session() as s:
        s.query(CrossInstanceIdentityRecord).delete()
        s.query(ContributorPubkey).delete()


# ---------------------------------------------------------------------------
# Claim payload — canonical shape
# ---------------------------------------------------------------------------


def claim_payload(
    *,
    contributor_id: str,
    public_key_hex: str,
    issued_at: str,
    rotates_from: str | None = None,
) -> dict:
    """Canonical claim payload that gets signed.

    `rotates_from` carries the OLD pubkey when this claim is replacing
    an existing one; the rotation signature uses the old key.
    """
    payload: dict = {
        "contributor_id": contributor_id,
        "public_key_hex": public_key_hex,
        "issued_at": issued_at,
    }
    if rotates_from is not None:
        payload["rotates_from"] = rotates_from
    return payload


# ---------------------------------------------------------------------------
# Pubkey claim — the contributor proves possession
# ---------------------------------------------------------------------------


def get_pubkey(contributor_id: str) -> str | None:
    """Return the locally claimed pubkey for a contributor, or None."""
    _ensure_schema()
    with _session() as s:
        rec = s.query(ContributorPubkey).filter_by(contributor_id=contributor_id).first()
        return rec.public_key_hex if rec else None


def find_contributor_by_pubkey(public_key_hex: str) -> str | None:
    """Reverse lookup: which local contributor (if any) claimed this pubkey."""
    _ensure_schema()
    with _session() as s:
        rec = s.query(ContributorPubkey).filter_by(public_key_hex=public_key_hex).first()
        return rec.contributor_id if rec else None


def claim_pubkey(
    *,
    contributor_id: str,
    public_key_hex: str,
    claim_signature: str,
    claim_payload_dict: dict,
    rotation_signature: str | None = None,
    rotation_payload_dict: dict | None = None,
) -> dict:
    """Link a pubkey to a contributor after verifying signature(s).

    First-time claim: `claim_signature` must verify against the NEW pubkey
    over `claim_payload_dict`. The payload must name this contributor and
    this pubkey (we check it matches the arguments before trusting it).

    Re-claim of the same pubkey: idempotent — same checks pass, no change
    recorded.

    Rotation (different pubkey for the same contributor): the caller must
    also pass `rotation_signature` over `rotation_payload_dict`, verified
    against the OLD pubkey. The old key authorizes the swap; the new key
    proves possession of the new identity.
    """
    _ensure_schema()

    # 1. The claim payload must name the contributor + pubkey we are about to
    #    record. A signed-but-mismatched payload is a forgery surface.
    if claim_payload_dict.get("contributor_id") != contributor_id:
        raise ClaimRejection("claim payload contributor_id mismatch")
    if claim_payload_dict.get("public_key_hex") != public_key_hex:
        raise ClaimRejection("claim payload public_key_hex mismatch")

    # 2. The new-key signature must verify — proves possession of the new key.
    if not verify_signature(claim_payload_dict, claim_signature, public_key_hex):
        raise ClaimRejection("claim signature does not verify against new pubkey")

    with _session() as s:
        existing = s.query(ContributorPubkey).filter_by(contributor_id=contributor_id).first()

        if existing is None:
            # First-time claim — pubkey was free, signature verified, link it.
            s.add(
                ContributorPubkey(
                    contributor_id=contributor_id,
                    public_key_hex=public_key_hex,
                    claimed_at=datetime.now(timezone.utc),
                )
            )
            return {
                "contributor_id": contributor_id,
                "public_key_hex": public_key_hex,
                "claimed": True,
                "rotated": False,
            }

        if existing.public_key_hex == public_key_hex:
            # Idempotent re-claim — no state change, no error.
            return {
                "contributor_id": contributor_id,
                "public_key_hex": public_key_hex,
                "claimed": True,
                "rotated": False,
                "idempotent": True,
            }

        # Different pubkey for an already-claimed contributor → rotation.
        # The OLD key must sign approval of the swap. The contributor owns
        # rotation; the instance just verifies the cryptographic continuity.
        if rotation_signature is None or rotation_payload_dict is None:
            raise RotationRejection(
                "pubkey rotation requires a rotation_signature from the old pubkey"
            )
        if rotation_payload_dict.get("contributor_id") != contributor_id:
            raise RotationRejection("rotation payload contributor_id mismatch")
        if rotation_payload_dict.get("public_key_hex") != public_key_hex:
            raise RotationRejection("rotation payload public_key_hex mismatch")
        if rotation_payload_dict.get("rotates_from") != existing.public_key_hex:
            raise RotationRejection("rotation payload rotates_from does not match old pubkey")
        if not verify_signature(
            rotation_payload_dict, rotation_signature, existing.public_key_hex
        ):
            raise RotationRejection("rotation signature does not verify against old pubkey")

        existing.public_key_hex = public_key_hex
        existing.rotated_at = datetime.now(timezone.utc)
        return {
            "contributor_id": contributor_id,
            "public_key_hex": public_key_hex,
            "claimed": True,
            "rotated": True,
        }


# ---------------------------------------------------------------------------
# Cross-instance recognition — peer says "X on me has pubkey Y"
# ---------------------------------------------------------------------------


def recognize_peer_identity(
    *,
    peer_instance_id: str,
    peer_contributor_id: str,
    public_key_hex: str,
) -> dict:
    """Record a cross-instance identity link if the pubkey matches a local claim.

    Returns a dict describing what happened. If no local contributor has
    claimed the shared pubkey, we record nothing — we do not speculate
    about who a peer's contributor might be on our side.

    Idempotent: re-receiving the same (peer_instance, peer_contributor,
    pubkey) for the same local contributor does not create a duplicate.
    """
    _ensure_schema()
    with _session() as s:
        local = s.query(ContributorPubkey).filter_by(public_key_hex=public_key_hex).first()
        if local is None:
            return {
                "recognized": False,
                "reason": "no local contributor claims this pubkey",
                "peer_instance_id": peer_instance_id,
                "peer_contributor_id": peer_contributor_id,
            }

        existing = (
            s.query(CrossInstanceIdentityRecord)
            .filter_by(
                local_contributor_id=local.contributor_id,
                peer_instance_id=peer_instance_id,
                peer_contributor_id=peer_contributor_id,
                public_key_hex=public_key_hex,
            )
            .first()
        )
        if existing is not None:
            return {
                "recognized": True,
                "idempotent": True,
                "local_contributor_id": local.contributor_id,
                "peer_instance_id": peer_instance_id,
                "peer_contributor_id": peer_contributor_id,
                "public_key_hex": public_key_hex,
            }

        from uuid import uuid4

        record = CrossInstanceIdentityRecord(
            id=f"xid_{uuid4().hex[:12]}",
            local_contributor_id=local.contributor_id,
            peer_instance_id=peer_instance_id,
            peer_contributor_id=peer_contributor_id,
            public_key_hex=public_key_hex,
            recognized_at=datetime.now(timezone.utc),
            signature_verified=True,
        )
        s.add(record)
        return {
            "recognized": True,
            "idempotent": False,
            "local_contributor_id": local.contributor_id,
            "peer_instance_id": peer_instance_id,
            "peer_contributor_id": peer_contributor_id,
            "public_key_hex": public_key_hex,
        }


def list_aliases(local_contributor_id: str) -> list[dict]:
    """All known cross-instance aliases for a local contributor."""
    _ensure_schema()
    with _session() as s:
        recs = (
            s.query(CrossInstanceIdentityRecord)
            .filter_by(local_contributor_id=local_contributor_id)
            .order_by(CrossInstanceIdentityRecord.recognized_at.desc())
            .all()
        )
        return [
            {
                "peer_instance_id": r.peer_instance_id,
                "peer_contributor_id": r.peer_contributor_id,
                "public_key_hex": r.public_key_hex,
                "recognized_at": r.recognized_at.isoformat() if r.recognized_at else None,
                "signature_verified": r.signature_verified,
            }
            for r in recs
        ]


__all__ = [
    "ClaimRejection",
    "RotationRejection",
    "ContributorPubkey",
    "CrossInstanceIdentityRecord",
    "claim_payload",
    "claim_pubkey",
    "get_pubkey",
    "find_contributor_by_pubkey",
    "list_aliases",
    "recognize_peer_identity",
]
