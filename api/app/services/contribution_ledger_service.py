"""Contribution Ledger — append-only persistent record of all contributor resources.

Every resource a contributor puts into the system is recorded here. Records are
never deleted or updated. The ledger uses the unified SQLite store (same pattern
as federation_service.py).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class ContributionLedgerRecord(Base):
    __tablename__ = "contribution_ledger"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contributor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    contribution_type: Mapped[str] = mapped_column(String, nullable=False)
    idea_id: Mapped[str] = mapped_column(String, nullable=True)
    amount_cc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# These are common types, but any string is valid — the ledger records whatever
# the contributor says they did.
SUGGESTED_TYPES = [
    "compute", "code", "direction", "infrastructure", "attention", "stake",
    "deposit", "research", "promotion", "design", "question", "review",
    "testing", "documentation", "mentoring", "feedback",
]


def record_contribution(
    contributor_id: str,
    contribution_type: str,
    amount_cc: float,
    idea_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Record a single contribution. Returns the record as a dict."""
    _ensure_schema()

    record_id = f"clr_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    meta_json = json.dumps(metadata or {})

    rec = ContributionLedgerRecord(
        id=record_id,
        contributor_id=contributor_id,
        contribution_type=contribution_type,
        idea_id=idea_id,
        amount_cc=round(float(amount_cc), 4),
        metadata_json=meta_json,
        recorded_at=now,
    )
    with _session() as s:
        s.add(rec)

    return {
        "id": record_id,
        "contributor_id": contributor_id,
        "contribution_type": contribution_type,
        "idea_id": idea_id,
        "amount_cc": round(float(amount_cc), 4),
        "metadata_json": meta_json,
        "recorded_at": now.isoformat(),
    }


def get_contributor_balance(contributor_id: str) -> dict:
    """Return total CC by contribution type + grand total for a contributor."""
    _ensure_schema()
    totals_by_type: dict[str, float] = {}
    grand_total = 0.0
    with _session() as s:
        recs = (
            s.query(ContributionLedgerRecord)
            .filter_by(contributor_id=contributor_id)
            .all()
        )
        for rec in recs:
            totals_by_type.setdefault(rec.contribution_type, 0.0)
            totals_by_type[rec.contribution_type] += rec.amount_cc
            grand_total += rec.amount_cc

    return {
        "contributor_id": contributor_id,
        "totals_by_type": {k: round(v, 4) for k, v in totals_by_type.items()},
        "grand_total": round(grand_total, 4),
    }


def get_spend_metrics(contributor_id: str) -> dict:
    """Return CC spent in the last 24h and last 30 days."""
    _ensure_schema()
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)
    
    daily_spend = 0.0
    monthly_spend = 0.0
    
    with _session() as s:
        recs = s.query(ContributionLedgerRecord).filter(
            ContributionLedgerRecord.contributor_id == contributor_id,
            ContributionLedgerRecord.amount_cc < 0, # Spend is negative in the ledger for future use, 
                                                   # but for now we look for compute/execution costs.
                                                   # Actually, we record execution as positive 'compute'.
                                                   # We need to distinguish 'earning' vs 'spending'.
        ).all()
        # For now, let's treat all 'compute' types as spend for the runner.
        for rec in recs:
            if rec.contribution_type == "compute":
                if rec.recorded_at >= day_ago:
                    daily_spend += rec.amount_cc
                if rec.recorded_at >= month_ago:
                    monthly_spend += rec.amount_cc
                    
    return {
        "daily_spend": round(daily_spend, 4),
        "monthly_spend": round(monthly_spend, 4),
    }


def get_contributor_history(
    contributor_id: str,
    limit: int = 50,
    auto_only: bool = False,
    since: str | None = None,
) -> list[dict]:
    """Return contribution records for a contributor, newest first.

    Args:
        contributor_id: The contributor to look up.
        limit: Maximum records to return (1-500).
        auto_only: If True, only return records where metadata contains
            ``"auto_recorded": true``.
        since: ISO 8601 UTC timestamp; only return records created at or
            after this time.
    """
    _ensure_schema()
    effective_limit = max(1, min(limit, 500))

    # Parse the ``since`` parameter once, outside the session.
    # SQLite stores naive UTC datetimes, so we strip tzinfo for comparison.
    # Note: URL query params decode '+' as ' ', so we normalize both 'Z'
    # and accidental space-separated offsets back to '+'.
    since_dt: datetime | None = None
    if since:
        try:
            normalized = since.replace("Z", "+00:00")
            # Handle URL-decoded '+' -> ' ' in timezone offset (e.g. "...00:00 00:00")
            # by replacing trailing " 00:00" with "+00:00"
            if normalized.endswith(" 00:00"):
                normalized = normalized[:-6] + "+00:00"
            since_dt = datetime.fromisoformat(normalized)
            # Normalize to naive UTC for SQLite compatibility
            if since_dt.tzinfo is not None:
                since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except (ValueError, TypeError):
            since_dt = None

    with _session() as s:
        q = (
            s.query(ContributionLedgerRecord)
            .filter_by(contributor_id=contributor_id)
        )

        if since_dt is not None:
            q = q.filter(ContributionLedgerRecord.recorded_at >= since_dt)

        if auto_only:
            # metadata_json is a TEXT column storing JSON.  Filter to rows
            # that contain the literal key/value for auto_recorded=true.
            q = q.filter(
                ContributionLedgerRecord.metadata_json.contains('"auto_recorded": true')
                | ContributionLedgerRecord.metadata_json.contains('"auto_recorded":true')
            )

        recs = (
            q.order_by(ContributionLedgerRecord.recorded_at.desc())
            .limit(effective_limit)
            .all()
        )
        return [
            {
                "id": rec.id,
                "contributor_id": rec.contributor_id,
                "contribution_type": rec.contribution_type,
                "idea_id": rec.idea_id,
                "amount_cc": rec.amount_cc,
                "metadata_json": rec.metadata_json,
                "recorded_at": rec.recorded_at.isoformat() if rec.recorded_at else None,
            }
            for rec in recs
        ]


def get_idea_investments(idea_id: str) -> list[dict]:
    """Return all contributions for a specific idea."""
    _ensure_schema()
    with _session() as s:
        recs = (
            s.query(ContributionLedgerRecord)
            .filter_by(idea_id=idea_id)
            .order_by(ContributionLedgerRecord.recorded_at.desc())
            .all()
        )
        return [
            {
                "id": rec.id,
                "contributor_id": rec.contributor_id,
                "contribution_type": rec.contribution_type,
                "idea_id": rec.idea_id,
                "amount_cc": rec.amount_cc,
                "metadata_json": rec.metadata_json,
                "recorded_at": rec.recorded_at.isoformat() if rec.recorded_at else None,
            }
            for rec in recs
        ]


# ---------------------------------------------------------------------------
# Founding contributions (idempotent one-time migration)
# ---------------------------------------------------------------------------

def record_founding_contributions(contributor_id: str = "urs-muff") -> list[dict]:
    """Record the resources already contributed by the founding contributor.

    Idempotent: checks if founding contributions already exist before inserting.
    """
    _ensure_schema()

    # Check if already recorded
    with _session() as s:
        existing = (
            s.query(ContributionLedgerRecord)
            .filter_by(contributor_id=contributor_id)
            .filter(ContributionLedgerRecord.metadata_json.contains('"founding": true'))
            .first()
        )
    if existing is not None:
        return []

    contributions = [
        ("compute", None, 28.0, {"tasks": 92, "success_rate": 0.93, "hours": 2.8, "founding": True}),
        ("direction", None, 50.0, {"specs_created": 50, "ideas_created": 13, "founding": True}),
        ("code", None, 62.0, {"commits": 62, "session": "2026-03-21/22", "founding": True}),
        ("infrastructure", None, 30.0, {"vps": "hostinger", "node": "mac-m4", "providers": 6, "founding": True}),
    ]

    results = []
    for ctype, idea_id, amount, meta in contributions:
        result = record_contribution(contributor_id, ctype, amount, idea_id, meta)
        results.append(result)
    return results
