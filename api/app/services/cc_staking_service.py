"""CC Staking Service — create positions, unstake with cooldown tiers, attribution.

Cooldown tiers (per-position, not per-transaction):
  - < 100 CC: instant (0 hours)
  - 100-1000 CC: 24 hours
  - > 1000 CC: 72 hours

Attribution grows linearly proportional to usage events on the staked idea.
No guaranteed yield — returns are purely outcome-based.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func

from app.models.cc_economics import StakePosition, UserStakingSummary, UnstakeResponse
from app.services.cc_treasury_service import StakePositionRow
from app.services.unified_db import session


def _cooldown_hours(amount_cc: float) -> int:
    """Determine cooldown hours based on amount tier."""
    if amount_cc < 100:
        return 0
    if amount_cc <= 1000:
        return 24
    return 72


def _row_to_position(row: StakePositionRow) -> StakePosition:
    """Convert an ORM row to a StakePosition model."""
    cooldown_hours: Optional[int] = None
    available_at: Optional[datetime] = None

    if row.status == "cooling_down" and row.cooldown_until:
        # Compute cooldown hours from original stake amount tier
        cooldown_hours = _cooldown_hours(row.amount_cc)
        available_at = row.cooldown_until

    return StakePosition(
        stake_id=row.stake_id,
        user_id=row.user_id,
        idea_id=row.idea_id,
        amount_cc=row.amount_cc,
        attribution_cc=row.attribution_cc,
        staked_at=row.staked_at or datetime.now(timezone.utc),
        status=row.status,
        cooldown_hours=cooldown_hours,
        available_at=available_at,
    )


def create_stake(user_id: str, idea_id: str, amount_cc: float) -> StakePosition:
    """Create a new staking position. Caller must verify balance beforehand."""
    stake_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc)
    row = StakePositionRow(
        stake_id=stake_id,
        user_id=user_id,
        idea_id=idea_id,
        amount_cc=amount_cc,
        attribution_cc=amount_cc,  # Starts equal to staked amount
        staked_at=now,
        status="active",
        cooldown_until=None,
    )
    with session() as s:
        s.add(row)

    return StakePosition(
        stake_id=stake_id,
        user_id=user_id,
        idea_id=idea_id,
        amount_cc=amount_cc,
        attribution_cc=amount_cc,
        staked_at=now,
        status="active",
        cooldown_hours=None,
        available_at=None,
    )


def unstake(stake_id: str, user_id: str) -> Optional[UnstakeResponse]:
    """Initiate unstake with cooldown. Returns None if stake not found.

    Raises ValueError if already in cooldown.
    """
    with session() as s:
        row = (
            s.query(StakePositionRow)
            .filter(StakePositionRow.stake_id == stake_id, StakePositionRow.user_id == user_id)
            .first()
        )
        if row is None:
            return None

        if row.status == "cooling_down":
            raise ValueError("Stake is already in cooldown")

        if row.status == "withdrawn":
            raise ValueError("Stake has already been withdrawn")

        hours = _cooldown_hours(row.amount_cc)
        now = datetime.now(timezone.utc)

        if hours == 0:
            row.status = "withdrawn"
            row.cooldown_until = now
            available_at = now
        else:
            row.status = "cooling_down"
            row.cooldown_until = now + timedelta(hours=hours)
            available_at = row.cooldown_until

        s.flush()

        return UnstakeResponse(
            stake_id=row.stake_id,
            amount_cc=row.amount_cc,
            attribution_cc=row.attribution_cc,
            cooldown_hours=hours,
            available_at=available_at,
            status=row.status,
        )


def get_stake(stake_id: str) -> Optional[StakePosition]:
    """Get a single staking position by ID."""
    with session() as s:
        row = s.query(StakePositionRow).filter(StakePositionRow.stake_id == stake_id).first()
        if row is None:
            return None
        return _row_to_position(row)


def get_user_positions(user_id: str) -> UserStakingSummary:
    """Get all staking positions for a user with totals."""
    with session() as s:
        rows = (
            s.query(StakePositionRow)
            .filter(StakePositionRow.user_id == user_id)
            .order_by(StakePositionRow.staked_at.desc())
            .all()
        )

    positions = [_row_to_position(r) for r in rows]
    active = [p for p in positions if p.status in ("active", "cooling_down")]
    total_staked = sum(p.amount_cc for p in active)
    total_attribution = sum(p.attribution_cc for p in active)

    return UserStakingSummary(
        user_id=user_id,
        positions=positions,
        total_staked_cc=total_staked,
        total_attribution_cc=total_attribution,
    )


def update_attribution(idea_id: str, usage_event_count: int) -> int:
    """Update attribution for all active stakes on an idea based on usage events.

    Attribution grows linearly: attribution_cc = amount_cc * (1 + 0.01 * usage_events).
    Returns the number of positions updated.
    """
    if usage_event_count <= 0:
        return 0

    with session() as s:
        rows = (
            s.query(StakePositionRow)
            .filter(StakePositionRow.idea_id == idea_id, StakePositionRow.status == "active")
            .all()
        )
        updated = 0
        for row in rows:
            # Linear growth: 1% per usage event
            row.attribution_cc = row.amount_cc * (1.0 + 0.01 * usage_event_count)
            updated += 1
        s.flush()
    return updated
