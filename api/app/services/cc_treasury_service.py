"""CC Treasury Service — ledger, mint/burn, balance tracking, coherence invariant.

Stores treasury state as ORM rows in the unified DB. Enforces the hard
constraint: no unbacked CC may ever exist.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Float, String, func

from app.services.unified_db import Base, session


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class TreasuryLedgerEntry(Base):
    """Append-only ledger of all CC treasury operations."""

    __tablename__ = "cc_treasury_ledger"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    action = Column(String, nullable=False)  # mint, burn, stake, unstake, fee
    amount_cc = Column(Float, nullable=False)
    user_id = Column(String, nullable=False)
    idea_id = Column(String, nullable=True)
    treasury_balance_after = Column(Float, nullable=False)
    coherence_score_after = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class StakePositionRow(Base):
    """Persistent staking position record."""

    __tablename__ = "cc_stake_positions"

    stake_id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    user_id = Column(String, nullable=False, index=True)
    idea_id = Column(String, nullable=False, index=True)
    amount_cc = Column(Float, nullable=False)
    attribution_cc = Column(Float, nullable=False)
    staked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, nullable=False, default="active")
    cooldown_until = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Treasury state
# ---------------------------------------------------------------------------

# In-memory treasury state backed by DB ledger. On startup these are
# recomputed from the ledger. For the initial implementation we keep a
# module-level cache that is authoritative within a single process.

_treasury: dict[str, float] = {
    "total_minted": 0.0,
    "total_burned": 0.0,
    "treasury_value_usd": 0.0,
}


def _outstanding() -> float:
    return _treasury["total_minted"] - _treasury["total_burned"]


def _coherence_score(exchange_rate: float) -> float:
    outstanding = _outstanding()
    if outstanding <= 0:
        return 1.0  # No CC outstanding means fully backed
    return _treasury["treasury_value_usd"] / (outstanding / exchange_rate)


def coherence_status(exchange_rate: float) -> str:
    score = _coherence_score(exchange_rate)
    if score < 1.0:
        return "paused"
    if score < 1.05:
        return "warning"
    return "healthy"


def can_mint(exchange_rate: float) -> bool:
    """Return True if minting is allowed (coherence score >= 1.0)."""
    return _coherence_score(exchange_rate) >= 1.0


def get_supply(exchange_rate: float) -> dict:
    """Return current supply metrics."""
    return {
        "total_minted": _treasury["total_minted"],
        "total_burned": _treasury["total_burned"],
        "outstanding": _outstanding(),
        "treasury_value_usd": _treasury["treasury_value_usd"],
        "exchange_rate": exchange_rate,
        "coherence_score": round(_coherence_score(exchange_rate), 6),
        "coherence_status": coherence_status(exchange_rate),
        "as_of": datetime.now(timezone.utc),
    }


def mint(user_id: str, amount_cc: float, deposit_usd: float, exchange_rate: float) -> TreasuryLedgerEntry:
    """Mint CC on deposit. Updates treasury and writes ledger entry."""
    _treasury["total_minted"] += amount_cc
    _treasury["treasury_value_usd"] += deposit_usd

    entry = _write_ledger("mint", amount_cc, user_id, None, exchange_rate)
    return entry


def burn(user_id: str, amount_cc: float, withdrawal_usd: float, exchange_rate: float) -> TreasuryLedgerEntry:
    """Burn CC on withdrawal. Updates treasury and writes ledger entry."""
    _treasury["total_burned"] += amount_cc
    _treasury["treasury_value_usd"] -= withdrawal_usd

    entry = _write_ledger("burn", amount_cc, user_id, None, exchange_rate)
    return entry


def record_stake(user_id: str, amount_cc: float, idea_id: str, exchange_rate: float) -> TreasuryLedgerEntry:
    """Record a staking action in the treasury ledger."""
    return _write_ledger("stake", amount_cc, user_id, idea_id, exchange_rate)


def record_unstake(user_id: str, amount_cc: float, idea_id: str, exchange_rate: float) -> TreasuryLedgerEntry:
    """Record an unstaking action in the treasury ledger."""
    return _write_ledger("unstake", amount_cc, user_id, idea_id, exchange_rate)


def get_user_balance(user_id: str) -> float:
    """Compute a user's available CC balance from ledger entries.

    Balance = sum(mint amounts for user) - sum(burn amounts) - sum(active stakes).
    """
    with session() as s:
        # Sum mints for user
        minted = (
            s.query(func.coalesce(func.sum(TreasuryLedgerEntry.amount_cc), 0.0))
            .filter(TreasuryLedgerEntry.user_id == user_id, TreasuryLedgerEntry.action == "mint")
            .scalar()
        )
        # Sum burns for user
        burned = (
            s.query(func.coalesce(func.sum(TreasuryLedgerEntry.amount_cc), 0.0))
            .filter(TreasuryLedgerEntry.user_id == user_id, TreasuryLedgerEntry.action == "burn")
            .scalar()
        )
        # Sum active stakes
        staked = (
            s.query(func.coalesce(func.sum(StakePositionRow.amount_cc), 0.0))
            .filter(
                StakePositionRow.user_id == user_id,
                StakePositionRow.status.in_(["active", "cooling_down"]),
            )
            .scalar()
        )
        return float(minted) - float(burned) - float(staked)


def get_ledger_entries(user_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    """Return recent ledger entries, optionally filtered by user."""
    with session() as s:
        q = s.query(TreasuryLedgerEntry).order_by(TreasuryLedgerEntry.created_at.desc())
        if user_id:
            q = q.filter(TreasuryLedgerEntry.user_id == user_id)
        rows = q.limit(limit).all()
        return [
            {
                "id": r.id,
                "action": r.action,
                "amount_cc": r.amount_cc,
                "user_id": r.user_id,
                "idea_id": r.idea_id,
                "treasury_balance_after": r.treasury_balance_after,
                "coherence_score_after": r.coherence_score_after,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def _write_ledger(
    action: str,
    amount_cc: float,
    user_id: str,
    idea_id: Optional[str],
    exchange_rate: float,
) -> TreasuryLedgerEntry:
    """Write an entry to the treasury ledger."""
    entry_id = uuid.uuid4().hex[:16]
    score = _coherence_score(exchange_rate)
    entry = TreasuryLedgerEntry(
        id=entry_id,
        action=action,
        amount_cc=amount_cc,
        user_id=user_id,
        idea_id=idea_id,
        treasury_balance_after=_treasury["treasury_value_usd"],
        coherence_score_after=round(score, 6),
        created_at=datetime.now(timezone.utc),
    )
    with session() as s:
        s.add(entry)
    return entry


def reset_treasury() -> None:
    """Reset in-memory treasury state. For testing only."""
    _treasury["total_minted"] = 0.0
    _treasury["total_burned"] = 0.0
    _treasury["treasury_value_usd"] = 0.0
