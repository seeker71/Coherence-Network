"""PostgreSQL persistence for Graph Health snapshots and signals (spec-172)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.graph_health import (
    ConvergenceGuardResponse,
    GravityWell,
    GraphHealthSnapshot,
    GraphSignal,
    OrphanCluster,
    SurfaceCandidate,
    SPEC_REF,
)
from app.services.unified_db import Base, session as db_session

logger = logging.getLogger(__name__)

CONVERGENCE_GUARD_TTL_DAYS = 90


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class GraphHealthSnapshotRecord(Base):
    __tablename__ = "graph_health_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    balance_score: Mapped[float] = mapped_column(Float, nullable=False)
    entropy_score: Mapped[float] = mapped_column(Float, nullable=False)
    concentration_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    concept_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gravity_wells_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    orphan_clusters_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    surface_candidates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    signals_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class GraphSignalRecord(Base):
    __tablename__ = "graph_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    concept_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class ConvergenceGuardRecord(Base):
    __tablename__ = "graph_convergence_guards"

    concept_id: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    set_by: Mapped[str] = mapped_column(String, nullable=False)
    set_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------

def _snapshot_from_record(r: GraphHealthSnapshotRecord) -> GraphHealthSnapshot:
    def _load(raw: str, model):
        items = json.loads(raw or "[]")
        return [model(**i) for i in items]

    return GraphHealthSnapshot(
        id=r.id,
        computed_at=r.computed_at.replace(tzinfo=timezone.utc) if r.computed_at.tzinfo is None else r.computed_at,
        balance_score=r.balance_score,
        entropy_score=r.entropy_score,
        concentration_ratio=r.concentration_ratio,
        concept_count=r.concept_count,
        edge_count=r.edge_count,
        gravity_wells=_load(r.gravity_wells_json, GravityWell),
        orphan_clusters=_load(r.orphan_clusters_json, OrphanCluster),
        surface_candidates=_load(r.surface_candidates_json, SurfaceCandidate),
        signals=_load(r.signals_json, GraphSignal),
        spec_ref=SPEC_REF,
    )


def _signal_from_record(r: GraphSignalRecord) -> GraphSignal:
    def _tz(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    return GraphSignal(
        id=r.id,
        type=r.type,
        concept_id=r.concept_id,
        cluster_id=r.cluster_id,
        severity=r.severity,
        created_at=_tz(r.created_at),  # type: ignore[arg-type]
        resolved=r.resolved,
        resolved_at=_tz(r.resolved_at),
        resolution=r.resolution,
        resolved_by=r.resolved_by,
    )


# ---------------------------------------------------------------------------
# Public repo functions
# ---------------------------------------------------------------------------

def save_snapshot(snapshot: GraphHealthSnapshot) -> None:
    """Persist a health snapshot to PostgreSQL."""
    def _dump(items) -> str:
        return json.dumps([i.model_dump(mode="json") for i in items])

    with db_session() as sess:
        rec = GraphHealthSnapshotRecord(
            id=snapshot.id,
            computed_at=snapshot.computed_at,
            balance_score=snapshot.balance_score,
            entropy_score=snapshot.entropy_score,
            concentration_ratio=snapshot.concentration_ratio,
            concept_count=snapshot.concept_count,
            edge_count=snapshot.edge_count,
            gravity_wells_json=_dump(snapshot.gravity_wells),
            orphan_clusters_json=_dump(snapshot.orphan_clusters),
            surface_candidates_json=_dump(snapshot.surface_candidates),
            signals_json=_dump(snapshot.signals),
        )
        sess.merge(rec)
        sess.commit()


def get_latest_snapshot() -> Optional[GraphHealthSnapshot]:
    with db_session() as sess:
        rec = (
            sess.query(GraphHealthSnapshotRecord)
            .order_by(GraphHealthSnapshotRecord.computed_at.desc())
            .first()
        )
        return _snapshot_from_record(rec) if rec else None


def get_snapshot_history(
    limit: int = 10,
    since: Optional[datetime] = None,
) -> tuple[list[GraphHealthSnapshot], int]:
    with db_session() as sess:
        q = sess.query(GraphHealthSnapshotRecord).order_by(
            GraphHealthSnapshotRecord.computed_at.desc()
        )
        if since:
            q = q.filter(GraphHealthSnapshotRecord.computed_at >= since)
        total = q.count()
        records = q.limit(limit).all()
        return [_snapshot_from_record(r) for r in records], total


def upsert_signal(signal: GraphSignal) -> None:
    """Create or update a signal record."""
    with db_session() as sess:
        existing = sess.query(GraphSignalRecord).filter_by(id=signal.id).first()
        if existing:
            existing.resolved = signal.resolved
            existing.resolved_at = signal.resolved_at
            existing.resolution = signal.resolution
            existing.resolved_by = signal.resolved_by
        else:
            rec = GraphSignalRecord(
                id=signal.id,
                type=signal.type,
                concept_id=signal.concept_id,
                cluster_id=signal.cluster_id,
                severity=signal.severity,
                created_at=signal.created_at,
                resolved=signal.resolved,
            )
            sess.add(rec)
        sess.commit()


def get_signal(signal_id: str) -> Optional[GraphSignal]:
    with db_session() as sess:
        rec = sess.query(GraphSignalRecord).filter_by(id=signal_id).first()
        return _signal_from_record(rec) if rec else None


def resolve_signal(
    signal_id: str, resolution: str, resolved_by: str
) -> Optional[GraphSignal]:
    with db_session() as sess:
        rec = sess.query(GraphSignalRecord).filter_by(id=signal_id).first()
        if rec is None:
            return None
        rec.resolved = True
        rec.resolved_at = datetime.now(timezone.utc)
        rec.resolution = resolution
        rec.resolved_by = resolved_by
        sess.commit()
        return _signal_from_record(rec)


def list_signals(
    signal_type: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: Optional[bool] = False,
) -> list[GraphSignal]:
    with db_session() as sess:
        q = sess.query(GraphSignalRecord)
        if signal_type:
            q = q.filter(GraphSignalRecord.type == signal_type)
        if severity:
            q = q.filter(GraphSignalRecord.severity == severity)
        if resolved is not None:
            q = q.filter(GraphSignalRecord.resolved == resolved)
        q = q.order_by(GraphSignalRecord.created_at.desc())
        return [_signal_from_record(r) for r in q.all()]


def set_convergence_guard(
    concept_id: str, reason: str, set_by: str
) -> ConvergenceGuardResponse:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=CONVERGENCE_GUARD_TTL_DAYS)
    with db_session() as sess:
        rec = sess.query(ConvergenceGuardRecord).filter_by(concept_id=concept_id).first()
        if rec:
            rec.reason = reason
            rec.set_by = set_by
            rec.set_at = now
            rec.expires_at = expires
        else:
            rec = ConvergenceGuardRecord(
                concept_id=concept_id,
                reason=reason,
                set_by=set_by,
                set_at=now,
                expires_at=expires,
            )
            sess.add(rec)
        sess.commit()
    return ConvergenceGuardResponse(
        concept_id=concept_id,
        convergence_guard=True,
        reason=reason,
        set_at=now,
    )


def delete_convergence_guard(concept_id: str) -> bool:
    with db_session() as sess:
        rec = sess.query(ConvergenceGuardRecord).filter_by(concept_id=concept_id).first()
        if rec is None:
            return False
        sess.delete(rec)
        sess.commit()
        return True


def get_convergence_guard(concept_id: str) -> Optional[ConvergenceGuardRecord]:
    now = datetime.now(timezone.utc)
    with db_session() as sess:
        rec = sess.query(ConvergenceGuardRecord).filter_by(concept_id=concept_id).first()
        if rec is None:
            return None
        # Expired guards are treated as absent
        expires = rec.expires_at.replace(tzinfo=timezone.utc) if rec.expires_at.tzinfo is None else rec.expires_at
        if expires < now:
            sess.delete(rec)
            sess.commit()
            return None
        return rec


def count_active_convergence_guards() -> int:
    now = datetime.now(timezone.utc)
    with db_session() as sess:
        return (
            sess.query(ConvergenceGuardRecord)
            .filter(ConvergenceGuardRecord.expires_at > now)
            .count()
        )


def get_roi_stats(period_days: int = 30) -> dict:
    """Aggregate ROI metrics over the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=period_days)
    with db_session() as sess:
        def _actioned(sig_type: str) -> int:
            return (
                sess.query(GraphSignalRecord)
                .filter(
                    GraphSignalRecord.type == sig_type,
                    GraphSignalRecord.resolved == True,  # noqa: E712
                    GraphSignalRecord.resolved_at >= since,
                )
                .count()
            )

        split_actioned = _actioned("split_signal")
        merge_actioned = _actioned("merge_signal")
        surface_actioned = _actioned("surface_signal")

        # Snapshots for delta calculation
        snapshots = (
            sess.query(GraphHealthSnapshotRecord)
            .filter(GraphHealthSnapshotRecord.computed_at >= since)
            .order_by(GraphHealthSnapshotRecord.computed_at.asc())
            .all()
        )

        balance_delta = 0.0
        entropy_delta = 0.0
        if len(snapshots) >= 2:
            balance_delta = round(snapshots[-1].balance_score - snapshots[0].balance_score, 4)
            entropy_delta = round(snapshots[-1].entropy_score - snapshots[0].entropy_score, 4)

        total_resolved = (
            sess.query(GraphSignalRecord)
            .filter(
                GraphSignalRecord.resolved == True,  # noqa: E712
                GraphSignalRecord.resolved_at >= since,
            )
            .count()
        )
        total_signals = (
            sess.query(GraphSignalRecord)
            .filter(GraphSignalRecord.created_at >= since)
            .count()
        )
        false_positive_rate = 0.0
        if total_signals > 0:
            # Approximation: signals created but never resolved within the period
            unresolved = total_signals - total_resolved
            false_positive_rate = round(unresolved / total_signals, 3)

        guards_active = count_active_convergence_guards()

    note = None
    if len(snapshots) < 2:
        note = "Insufficient history — check back after first full measurement period"

    return {
        "period_days": period_days,
        "balance_score_delta": balance_delta,
        "entropy_score_delta": entropy_delta,
        "split_signals_actioned": split_actioned,
        "merge_signals_actioned": merge_actioned,
        "surface_signals_actioned": surface_actioned,
        "false_positive_rate": false_positive_rate,
        "convergence_guards_active": guards_active,
        "note": note,
    }
