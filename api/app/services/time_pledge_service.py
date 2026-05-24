"""Time pledge service — convert pledged labor hours into CC equivalents.

A pledge is a contributor's commitment to spend N hours on an idea. The
service converts hours to a CC equivalent using a configurable rate
(default DEFAULT_CC_PER_HOUR = 500.0 CC/hour) and records the pledge in
an append-only table. Fulfillment marks the pledge complete and records
a matching contribution_ledger entry of type ``return``.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import contribution_ledger_service, unified_db as _udb
from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default rate honest until calibrated against real labor flows. The
# spec's worked example (2 hours = 1000 CC) implies this rate.
DEFAULT_CC_PER_HOUR = 500.0

# Pledges expire 7 days after creation by default.
DEFAULT_EXPIRY_DAYS = 7


# ---------------------------------------------------------------------------
# ORM
# ---------------------------------------------------------------------------


class TimePledgeRecord(Base):
    __tablename__ = "time_pledges"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contributor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    idea_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    hours_pledged: Mapped[float] = mapped_column(Float, nullable=False)
    pledge_type: Mapped[str] = mapped_column(String, nullable=False, default="review")
    cc_equivalent: Mapped[float] = mapped_column(Float, nullable=False)
    cc_per_hour_rate: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    contribution_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


def current_cc_per_hour_rate() -> float:
    """Return the active CC-per-hour rate. Stable until governance updates it."""
    return DEFAULT_CC_PER_HOUR


def cc_equivalent_for_hours(hours: float, rate: float | None = None) -> float:
    """Convert labor hours to CC equivalent. Pure function."""
    rate_used = rate if rate is not None else current_cc_per_hour_rate()
    return round(float(hours) * rate_used, 4)


def _record_to_dict(rec: TimePledgeRecord) -> dict:
    return {
        "pledge_id": rec.id,
        "contributor_id": rec.contributor_id,
        "idea_id": rec.idea_id,
        "hours_pledged": rec.hours_pledged,
        "pledge_type": rec.pledge_type,
        "cc_equivalent": rec.cc_equivalent,
        "cc_per_hour_rate": rec.cc_per_hour_rate,
        "status": rec.status,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
        "fulfilled_at": rec.fulfilled_at.isoformat() if rec.fulfilled_at else None,
        "contribution_id": rec.contribution_id,
        "evidence_url": rec.evidence_url,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_pledge(
    contributor_id: str,
    idea_id: str,
    hours_pledged: float,
    pledge_type: str = "review",
    expiry_days: int = DEFAULT_EXPIRY_DAYS,
) -> dict:
    """Create a time pledge. Returns the pledge as a dict."""
    _udb.ensure_schema()

    if hours_pledged <= 0:
        raise ValueError("hours_pledged must be > 0")

    rate = current_cc_per_hour_rate()
    cc_equiv = cc_equivalent_for_hours(hours_pledged, rate)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=expiry_days)
    pledge_id = f"tp_{uuid4().hex[:12]}"

    rec = TimePledgeRecord(
        id=pledge_id,
        contributor_id=contributor_id,
        idea_id=idea_id,
        hours_pledged=float(hours_pledged),
        pledge_type=pledge_type,
        cc_equivalent=cc_equiv,
        cc_per_hour_rate=rate,
        status="pending",
        created_at=now,
        expires_at=expires,
    )
    with _session() as s:
        s.add(rec)

    return _record_to_dict(rec)


def get_pledge(pledge_id: str) -> Optional[dict]:
    _udb.ensure_schema()
    with _session() as s:
        rec = s.query(TimePledgeRecord).filter_by(id=pledge_id).first()
        if rec is None:
            return None
        return _record_to_dict(rec)


def list_pledges(contributor_id: str, status: Optional[str] = None) -> list[dict]:
    _udb.ensure_schema()
    with _session() as s:
        q = s.query(TimePledgeRecord).filter_by(contributor_id=contributor_id)
        if status:
            q = q.filter_by(status=status)
        recs = q.order_by(TimePledgeRecord.created_at.desc()).all()
        return [_record_to_dict(r) for r in recs]


def fulfill_pledge(
    pledge_id: str,
    contributor_id: str,
    contribution_id: str,
    evidence_url: Optional[str] = None,
) -> dict:
    """Mark a pledge fulfilled and record the matching CC return.

    Raises:
        ValueError: pledge not found.
        PermissionError: pledge belongs to a different contributor.
        RuntimeError: pledge already fulfilled.
    """
    _udb.ensure_schema()
    now = datetime.now(timezone.utc)

    with _session() as s:
        rec = s.query(TimePledgeRecord).filter_by(id=pledge_id).first()
        if rec is None:
            raise ValueError(f"Pledge not found: {pledge_id}")
        if rec.contributor_id != contributor_id:
            raise PermissionError(f"Pledge {pledge_id} does not belong to {contributor_id}")
        if rec.status == "fulfilled":
            raise RuntimeError(f"Pledge already fulfilled at {rec.fulfilled_at}")

        rec.status = "fulfilled"
        rec.fulfilled_at = now
        rec.contribution_id = contribution_id
        rec.evidence_url = evidence_url
        s.add(rec)

        # Record the CC return in the ledger.
        contribution_ledger_service.record_contribution(
            contributor_id=contributor_id,
            contribution_type="return",
            amount_cc=rec.cc_equivalent,
            idea_id=rec.idea_id,
            metadata={
                "trigger": "pledge_fulfilled",
                "pledge_id": pledge_id,
                "contribution_id": contribution_id,
                "evidence_url": evidence_url,
                "hours_pledged": rec.hours_pledged,
                "pledge_type": rec.pledge_type,
            },
        )
        return _record_to_dict(rec)


def _reset_for_tests() -> None:
    """Drop all pledge rows. Tests only."""
    _udb.ensure_schema()
    with _session() as s:
        s.query(TimePledgeRecord).delete()
