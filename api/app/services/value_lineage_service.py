"""Service for persistent value lineage and payout attribution previews."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.value_lineage import (
    LineageContributors,
    LineageInvestment,
    LineageLink,
    LineageLinkCreate,
    LineageValuation,
    MinimumE2EFlowResponse,
    PayoutPreview,
    PayoutRow,
    UsageEvent,
    UsageEventCreate,
)
from app.services import unified_db as _udb
from app.services.unified_db import Base

# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class LineageLinkRecord(Base):
    __tablename__ = "value_lineage_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    idea_id: Mapped[str] = mapped_column(String, nullable=False)
    spec_id: Mapped[str] = mapped_column(String, nullable=False)
    implementation_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    contributors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    investments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class UsageEventRecord(Base):
    __tablename__ = "value_lineage_usage_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lineage_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _record_to_link(rec: LineageLinkRecord) -> LineageLink:
    return LineageLink(
        id=rec.id,
        idea_id=rec.idea_id,
        spec_id=rec.spec_id,
        implementation_refs=json.loads(rec.implementation_refs_json),
        contributors=LineageContributors(**json.loads(rec.contributors_json)),
        investments=[LineageInvestment(**i) for i in json.loads(rec.investments_json)],
        estimated_cost=rec.estimated_cost,
        created_at=_ensure_utc(rec.created_at),
        updated_at=_ensure_utc(rec.updated_at),
    )


def _record_to_event(rec: UsageEventRecord) -> UsageEvent:
    return UsageEvent(
        id=rec.id,
        lineage_id=rec.lineage_id,
        source=rec.source,
        metric=rec.metric,
        value=rec.value,
        captured_at=_ensure_utc(rec.captured_at),
    )


DEFAULT_STAGE_WEIGHTS: dict[str, float] = {
    "idea": 0.07,
    "research": 0.15,
    "spec": 0.15,
    "spec_upgrade": 0.11,
    "implementation": 0.37,
    "review": 0.15,
}
# Sum = 1.0 (normalized from original 1.35, preserving relative ratios)

# Backward-compatible alias for older call sites and docs.
DEFAULT_ROLE_WEIGHTS = DEFAULT_STAGE_WEIGHTS

DEFAULT_OBJECTIVE_WEIGHTS: dict[str, float] = {
    "coherence": 0.35,
    "energy_flow": 0.2,
    "awareness": 0.2,
    "friction_relief": 0.15,
    "balance": 0.1,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _active_contributors(link: LineageLink) -> dict[str, str]:
    contributors = {
        "idea": link.contributors.idea,
        "research": link.contributors.research,
        "spec": link.contributors.spec,
        "spec_upgrade": link.contributors.spec_upgrade,
        "implementation": link.contributors.implementation,
        "review": link.contributors.review,
    }
    return {role: who for role, who in contributors.items() if isinstance(who, str) and who}


def _lineage_investments(link: LineageLink) -> list[LineageInvestment]:
    investments = list(link.investments)
    seen_pairs = {(item.stage, item.contributor) for item in investments}
    for role, contributor in _active_contributors(link).items():
        key = (role, contributor)
        if key in seen_pairs:
            continue
        investments.append(
            LineageInvestment(
                stage=role,
                contributor=contributor,
                energy_units=1.0,
                coherence_score=0.7,
                awareness_score=0.7,
                friction_score=0.3,
            )
        )
        seen_pairs.add(key)
    return investments


def _compute_global_signals(
    summary: LineageValuation, events: list[UsageEvent], investments: list[LineageInvestment], stage_totals: dict[str, float]
) -> dict[str, float]:
    unique_sources = len({event.source for event in events if event.source})
    unique_metrics = len({event.metric for event in events if event.metric})
    event_count = len(events)
    awareness = (
        ((unique_sources + unique_metrics) / max(1.0, 2.0 * event_count))
        if event_count > 0
        else 0.0
    )
    friction = (
        sum(float(item.friction_score) for item in investments) / float(len(investments))
        if investments
        else 0.0
    )
    coherence = _clamp(float(summary.roi_ratio) / (1.0 + float(summary.roi_ratio)))
    energy_flow = (
        _clamp(float(summary.measured_value_total) / max(float(summary.measured_value_total) + float(summary.estimated_cost), 1.0))
        if (summary.measured_value_total > 0 or summary.estimated_cost > 0)
        else 0.0
    )
    target_stage_energy = (
        sum(stage_totals.values()) / max(1.0, float(len([value for value in stage_totals.values() if value > 0.0])))
        if stage_totals
        else 0.0
    )
    if target_stage_energy <= 0:
        balance = 0.0
    else:
        stage_scores: list[float] = []
        for total in stage_totals.values():
            if total <= 0:
                continue
            imbalance = abs(total - target_stage_energy) / target_stage_energy
            stage_scores.append(_clamp(1.0 - imbalance))
        balance = (sum(stage_scores) / len(stage_scores)) if stage_scores else 0.0

    return {
        "coherence": round(coherence, 4),
        "energy_flow": round(energy_flow, 4),
        "awareness": round(_clamp(awareness), 4),
        "friction": round(_clamp(friction), 4),
        "balance": round(_clamp(balance), 4),
    }


def _effective_weight(
    investment: LineageInvestment,
    *,
    stage_weight: float,
    stage_energy_total: float,
    target_stage_energy: float,
    signals: dict[str, float],
) -> float:
    if stage_weight <= 0:
        return 0.0
    if target_stage_energy <= 0:
        balance_factor = 0.5
    else:
        imbalance = abs(stage_energy_total - target_stage_energy) / target_stage_energy
        balance_factor = _clamp(1.0 - imbalance)
    objective_score = (
        (DEFAULT_OBJECTIVE_WEIGHTS["coherence"] * _clamp(float(investment.coherence_score)))
        + (DEFAULT_OBJECTIVE_WEIGHTS["energy_flow"] * _clamp(float(signals["energy_flow"])))
        + (DEFAULT_OBJECTIVE_WEIGHTS["awareness"] * _clamp(float(investment.awareness_score)))
        + (DEFAULT_OBJECTIVE_WEIGHTS["friction_relief"] * _clamp(1.0 - float(investment.friction_score)))
        + (DEFAULT_OBJECTIVE_WEIGHTS["balance"] * balance_factor)
    )
    energy_factor = math.sqrt(max(float(investment.energy_units), 1e-9))
    return max(stage_weight * energy_factor * objective_score, 0.0)


def _empty_payout_preview(lineage_id: str, summary: LineageValuation, payout_pool: float) -> PayoutPreview:
    return PayoutPreview(
        lineage_id=lineage_id,
        payout_pool=round(float(payout_pool), 4),
        measured_value_total=summary.measured_value_total,
        estimated_cost=summary.estimated_cost,
        roi_ratio=summary.roi_ratio,
        weights=DEFAULT_STAGE_WEIGHTS,
        objective_weights=DEFAULT_OBJECTIVE_WEIGHTS,
        signals={"coherence": 0.0, "energy_flow": 0.0, "awareness": 0.0, "friction": 0.0, "balance": 0.0},
        payouts=[],
    )


def _build_payout_rows(
    investments: list[LineageInvestment],
    *,
    stage_totals: dict[str, float],
    target_stage_energy: float,
    signals: dict[str, float],
    payout_pool: float,
) -> list[PayoutRow]:
    aggregate: dict[tuple[str, str], dict[str, float | str]] = {}
    for item in investments:
        stage_weight = float(DEFAULT_STAGE_WEIGHTS.get(item.stage, 0.0))
        effective = _effective_weight(
            item,
            stage_weight=stage_weight,
            stage_energy_total=float(stage_totals.get(item.stage, 0.0)),
            target_stage_energy=target_stage_energy,
            signals=signals,
        )
        key = (item.stage, item.contributor)
        if key not in aggregate:
            aggregate[key] = {
                "role": item.stage,
                "contributor": item.contributor,
                "energy_units": 0.0,
                "effective_weight": 0.0,
            }
        aggregate[key]["energy_units"] = float(aggregate[key]["energy_units"]) + float(item.energy_units)
        aggregate[key]["effective_weight"] = float(aggregate[key]["effective_weight"]) + float(effective)

    rows = sorted(aggregate.values(), key=lambda entry: (str(entry["role"]), str(entry["contributor"])))
    total_effective_weight = sum(float(entry["effective_weight"]) for entry in rows)
    payouts: list[PayoutRow] = []
    for entry in rows:
        normalized_weight = (
            float(entry["effective_weight"]) / total_effective_weight if total_effective_weight > 0 else 0.0
        )
        payouts.append(
            PayoutRow(
                role=str(entry["role"]),
                contributor=str(entry["contributor"]),
                amount=round(float(payout_pool) * normalized_weight, 4),
                energy_units=round(float(entry["energy_units"]), 4),
                effective_weight=round(float(entry["effective_weight"]), 6),
            )
        )
    return payouts


def checkpoint() -> dict[str, object]:
    _ensure_schema()
    with _session() as s:
        link_count = s.query(LineageLinkRecord).count()
        event_count = s.query(UsageEventRecord).count()
        max_link_updated_at: datetime | None = None
        max_event_captured_at: datetime | None = None
        last_link = (
            s.query(LineageLinkRecord)
            .order_by(LineageLinkRecord.updated_at.desc())
            .first()
        )
        if last_link:
            max_link_updated_at = last_link.updated_at
        last_event = (
            s.query(UsageEventRecord)
            .order_by(UsageEventRecord.captured_at.desc())
            .first()
        )
        if last_event:
            max_event_captured_at = last_event.captured_at

    return {
        "path": _udb.database_url(),
        "link_count": link_count,
        "event_count": event_count,
        "max_link_updated_at": max_link_updated_at.isoformat() if max_link_updated_at else None,
        "max_event_captured_at": max_event_captured_at.isoformat() if max_event_captured_at else None,
        "file_size": 0,
        "file_mtime_ns": 0,
    }


def create_link(payload: LineageLinkCreate) -> LineageLink:
    _ensure_schema()
    now = datetime.now(timezone.utc)
    link_id = f"lnk_{uuid4().hex[:12]}"
    rec = LineageLinkRecord(
        id=link_id,
        idea_id=payload.idea_id,
        spec_id=payload.spec_id,
        implementation_refs_json=json.dumps(payload.implementation_refs),
        contributors_json=json.dumps(payload.contributors.model_dump(mode="json")),
        investments_json=json.dumps([i.model_dump(mode="json") for i in payload.investments]),
        estimated_cost=round(float(payload.estimated_cost), 4),
        created_at=now,
        updated_at=now,
    )
    with _session() as s:
        s.add(rec)
    return LineageLink(
        id=link_id,
        idea_id=payload.idea_id,
        spec_id=payload.spec_id,
        implementation_refs=payload.implementation_refs,
        contributors=payload.contributors,
        investments=payload.investments,
        estimated_cost=round(float(payload.estimated_cost), 4),
        created_at=now,
        updated_at=now,
    )


def get_link(lineage_id: str) -> LineageLink | None:
    _ensure_schema()
    with _session() as s:
        rec = s.query(LineageLinkRecord).filter_by(id=lineage_id).first()
        if rec is None:
            return None
        return _record_to_link(rec)


def list_links(limit: int = 200) -> list[LineageLink]:
    _ensure_schema()
    effective_limit = max(1, min(limit, 2000))
    with _session() as s:
        recs = (
            s.query(LineageLinkRecord)
            .order_by(LineageLinkRecord.updated_at.desc())
            .limit(effective_limit)
            .all()
        )
        return [_record_to_link(r) for r in recs]


def add_usage_event(lineage_id: str, payload: UsageEventCreate) -> UsageEvent | None:
    _ensure_schema()
    now = datetime.now(timezone.utc)
    event_id = f"evt_{uuid4().hex[:12]}"
    with _session() as s:
        link_rec = s.query(LineageLinkRecord).filter_by(id=lineage_id).first()
        if link_rec is None:
            return None
        link_rec.updated_at = now
        rec = UsageEventRecord(
            id=event_id,
            lineage_id=lineage_id,
            source=payload.source,
            metric=payload.metric,
            value=round(float(payload.value), 4),
            captured_at=now,
        )
        s.add(rec)
    return UsageEvent(
        id=event_id,
        lineage_id=lineage_id,
        source=payload.source,
        metric=payload.metric,
        value=round(float(payload.value), 4),
        captured_at=now,
    )


def _lineage_events(lineage_id: str) -> list[UsageEvent]:
    _ensure_schema()
    with _session() as s:
        recs = (
            s.query(UsageEventRecord)
            .filter_by(lineage_id=lineage_id)
            .all()
        )
        return [_record_to_event(r) for r in recs]


def list_usage_events(limit: int = 500) -> list[UsageEvent]:
    _ensure_schema()
    effective_limit = max(1, min(limit, 5000))
    with _session() as s:
        recs = (
            s.query(UsageEventRecord)
            .order_by(UsageEventRecord.captured_at.desc())
            .limit(effective_limit)
            .all()
        )
        return [_record_to_event(r) for r in recs]


def valuation(lineage_id: str) -> LineageValuation | None:
    link = get_link(lineage_id)
    if link is None:
        return None
    events = _lineage_events(lineage_id)
    measured_value_total = round(sum(float(ev.value) for ev in events), 4)
    estimated_cost = round(float(link.estimated_cost), 4)
    roi = round((measured_value_total / estimated_cost), 4) if estimated_cost > 0 else 0.0
    return LineageValuation(
        lineage_id=lineage_id,
        idea_id=link.idea_id,
        spec_id=link.spec_id,
        measured_value_total=measured_value_total,
        estimated_cost=estimated_cost,
        roi_ratio=roi,
        event_count=len(events),
    )


def payout_preview(lineage_id: str, payout_pool: float) -> PayoutPreview | None:
    link = get_link(lineage_id)
    if link is None:
        return None
    summary = valuation(lineage_id)
    if summary is None:
        return None

    investments = _lineage_investments(link)
    if not investments:
        return _empty_payout_preview(lineage_id, summary, payout_pool)

    stage_totals: dict[str, float] = defaultdict(float)
    for item in investments:
        stage_totals[item.stage] += float(item.energy_units)
    active_stage_totals = [value for value in stage_totals.values() if value > 0.0]
    target_stage_energy = (
        sum(active_stage_totals) / float(len(active_stage_totals)) if active_stage_totals else 0.0
    )
    events = _lineage_events(lineage_id)
    signals = _compute_global_signals(summary, events, investments, stage_totals)
    payouts = _build_payout_rows(
        investments,
        stage_totals=stage_totals,
        target_stage_energy=target_stage_energy,
        signals=signals,
        payout_pool=payout_pool,
    )

    return PayoutPreview(
        lineage_id=lineage_id,
        payout_pool=round(float(payout_pool), 4),
        measured_value_total=summary.measured_value_total,
        estimated_cost=summary.estimated_cost,
        roi_ratio=summary.roi_ratio,
        weights=DEFAULT_STAGE_WEIGHTS,
        objective_weights=DEFAULT_OBJECTIVE_WEIGHTS,
        signals=signals,
        payouts=payouts,
    )


def run_minimum_e2e_flow() -> MinimumE2EFlowResponse:
    link = create_link(
        LineageLinkCreate(
            idea_id="oss-interface-alignment",
            spec_id="050-canonical-route-registry-and-runtime-mapping",
            implementation_refs=["runtime-minimum-e2e"],
            contributors={
                "idea": "codex-idea",
                "spec": "codex-spec",
                "implementation": "codex-impl",
                "review": "human-review",
            },
            estimated_cost=2.0,
        )
    )
    event = add_usage_event(
        link.id,
        UsageEventCreate(source="api", metric="minimum_e2e_validated", value=5.0),
    )
    valuation_report = valuation(link.id)
    payout = payout_preview(link.id, 100.0)
    if event is None or valuation_report is None or payout is None:
        raise RuntimeError("Minimum E2E flow failed to produce expected artifacts")

    checks = []
    if valuation_report.measured_value_total == 5.0:
        checks.append("valuation_matches_usage")
    if payout.payout_pool == 100.0 and len(payout.payouts) >= 1:
        checks.append("payout_preview_generated")
    checks.append("lineage_created")
    checks.append("usage_event_created")

    return MinimumE2EFlowResponse(
        lineage_id=link.id,
        usage_event_id=event.id,
        valuation=valuation_report,
        payout_preview=payout,
        checks=checks,
    )
