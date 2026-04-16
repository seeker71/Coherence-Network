"""Wallet service — links contributor identities to on-chain addresses.

Supports multiple wallets per contributor, multiple chains (ethereum, base,
polygon), and ownership verification via EIP-191 signature.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import mapped_column

from app.services.unified_db import Base

log = logging.getLogger(__name__)

_ready = False


def _ensure_ready() -> None:
    global _ready
    if _ready:
        return
    _ready = True
    from app.services.unified_db import ensure_schema
    ensure_schema()


def _session():
    from app.services.unified_db import session
    return session()


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class WalletRecord(Base):
    """On-chain wallet linked to a contributor identity."""
    __tablename__ = "wallets"

    id = mapped_column(String(64), primary_key=True)
    contributor_id = mapped_column(String(128), nullable=False, index=True)
    address = mapped_column(String(128), nullable=False, unique=True, index=True)
    chain = mapped_column(String(32), nullable=False, default="ethereum")
    verified = mapped_column(Boolean, default=False)
    verified_at = mapped_column(DateTime, nullable=True)
    label = mapped_column(String(128), nullable=True)
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wallet_to_dict(w: WalletRecord) -> dict[str, Any]:
    return {
        "id": w.id,
        "contributor_id": w.contributor_id,
        "address": w.address,
        "chain": w.chain,
        "verified": w.verified,
        "verified_at": w.verified_at.isoformat() if w.verified_at else None,
        "label": w.label,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def connect_wallet(
    contributor_id: str,
    address: str,
    chain: str = "ethereum",
    label: str | None = None,
) -> dict[str, Any]:
    """Link a wallet address to a contributor. Also updates contributor.wallet_address."""
    _ensure_ready()
    wallet_id = str(uuid4())
    normalized = address.lower().strip()

    with _session() as s:
        # Check for duplicate address
        existing = s.query(WalletRecord).filter_by(address=normalized).first()
        if existing:
            if existing.contributor_id == contributor_id:
                return _wallet_to_dict(existing)
            raise ValueError(f"Address {address} is already linked to another contributor")

        wallet = WalletRecord(
            id=wallet_id,
            contributor_id=contributor_id,
            address=normalized,
            chain=chain,
            verified=False,
            label=label,
        )
        s.add(wallet)

        # Update contributor.wallet_address if it's the first wallet
        try:
            from app.adapters.postgres_models import ContributorModel
            contributor = s.query(ContributorModel).filter_by(id=contributor_id).first()
            if contributor and not contributor.wallet_address:
                contributor.wallet_address = normalized
        except Exception as e:
            log.debug("wallet_service: could not update contributor record: %s", e)

        s.commit()
        return _wallet_to_dict(wallet)


def disconnect_wallet(wallet_id: str) -> bool:
    """Unlink a wallet. Returns True if found and removed."""
    _ensure_ready()
    with _session() as s:
        wallet = s.query(WalletRecord).filter_by(id=wallet_id).first()
        if not wallet:
            return False

        contributor_id = wallet.contributor_id
        address = wallet.address
        s.delete(wallet)

        # If this was the contributor's primary wallet_address, clear it
        # or set to the next available wallet
        try:
            from app.adapters.postgres_models import ContributorModel
            contributor = s.query(ContributorModel).filter_by(id=contributor_id).first()
            if contributor and contributor.wallet_address == address:
                next_wallet = (
                    s.query(WalletRecord)
                    .filter(WalletRecord.contributor_id == contributor_id)
                    .filter(WalletRecord.id != wallet_id)
                    .first()
                )
                contributor.wallet_address = next_wallet.address if next_wallet else None
        except Exception as e:
            log.debug("wallet_service: could not update contributor record: %s", e)

        s.commit()
        return True


def verify_wallet(
    contributor_id: str,
    address: str,
    message: str,
    signature: str,
) -> dict[str, Any]:
    """Verify wallet ownership via EIP-191 signature.

    The caller provides a message the contributor signed and the signature.
    We recover the signer address and check it matches.
    """
    _ensure_ready()
    normalized = address.lower().strip()

    # Recover signer from signature
    try:
        from eth_account.messages import encode_defunct
        from eth_account import Account

        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=signature)
    except ImportError:
        raise RuntimeError(
            "eth-account package is required for wallet verification. "
            "Install with: pip install eth-account"
        )
    except Exception as e:
        raise ValueError(f"Signature verification failed: {e}")

    if recovered.lower() != normalized:
        raise ValueError(
            f"Signature does not match address. "
            f"Expected {normalized}, recovered {recovered.lower()}"
        )

    with _session() as s:
        wallet = s.query(WalletRecord).filter_by(
            contributor_id=contributor_id,
            address=normalized,
        ).first()
        if not wallet:
            raise ValueError(
                f"No wallet record found for contributor {contributor_id} "
                f"with address {address}. Connect the wallet first."
            )

        wallet.verified = True
        wallet.verified_at = datetime.now(timezone.utc)
        s.commit()
        return _wallet_to_dict(wallet)


def get_wallets(contributor_id: str) -> list[dict[str, Any]]:
    """List all wallets for a contributor."""
    _ensure_ready()
    with _session() as s:
        rows = (
            s.query(WalletRecord)
            .filter_by(contributor_id=contributor_id)
            .order_by(WalletRecord.created_at)
            .all()
        )
        return [_wallet_to_dict(w) for w in rows]


def get_contributor_by_wallet(address: str) -> dict[str, Any] | None:
    """Reverse lookup — find contributor by wallet address."""
    _ensure_ready()
    normalized = address.lower().strip()
    with _session() as s:
        wallet = s.query(WalletRecord).filter_by(address=normalized).first()
        if not wallet:
            return None
        return {
            "contributor_id": wallet.contributor_id,
            "wallet": _wallet_to_dict(wallet),
        }
