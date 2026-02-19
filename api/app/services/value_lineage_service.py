"""Service for persistent value lineage and payout attribution previews."""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models.value_lineage import (
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

DEFAULT_STAGE_WEIGHTS: dict[str, float] = {
    "idea": 0.1,
    "research": 0.2,
    "spec": 0.2,
    "spec_upgrade": 0.15,
    "implementation": 0.5,
    "review": 0.2,
}

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


def _default_path() -> Path:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    return logs_dir / "value_lineage.json"


def _path() -> Path:
    configured = os.getenv("VALUE_LINEAGE_PATH")
    return Path(configured) if configured else _default_path()


def _ensure_store() -> None:
    path = _path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"links": [], "events": []}, indent=2), encoding="utf-8")


def _read_store() -> dict:
    _ensure_store()
    path = _path()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"links": [], "events": []}
    if not isinstance(data, dict):
        return {"links": [], "events": []}
    links = data.get("links") if isinstance(data.get("links"), list) else []
    events = data.get("events") if isinstance(data.get("events"), list) else []
    return {"links": links, "events": events}


def _write_store(data: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_link(payload: LineageLinkCreate) -> LineageLink:
    now = datetime.now(timezone.utc)
    link = LineageLink(
        id=f"lnk_{uuid4().hex[:12]}",
        idea_id=payload.idea_id,
        spec_id=payload.spec_id,
        implementation_refs=payload.implementation_refs,
        contributors=payload.contributors,
        investments=payload.investments,
        estimated_cost=round(float(payload.estimated_cost), 4),
        created_at=now,
        updated_at=now,
    )
    data = _read_store()
    data["links"].append(link.model_dump(mode="json"))
    _write_store(data)
    return link


def get_link(lineage_id: str) -> LineageLink | None:
    data = _read_store()
    for raw in data["links"]:
        try:
            link = LineageLink(**raw)
        except Exception:
            continue
        if link.id == lineage_id:
            return link
    return None


def list_links(limit: int = 200) -> list[LineageLink]:
    data = _read_store()
    out: list[LineageLink] = []
    for raw in data["links"]:
        try:
            out.append(LineageLink(**raw))
        except Exception:
            continue
    out.sort(key=lambda x: x.updated_at, reverse=True)
    return out[: max(1, min(limit, 2000))]


def add_usage_event(lineage_id: str, payload: UsageEventCreate) -> UsageEvent | None:
    link = get_link(lineage_id)
    if link is None:
        return None
    event = UsageEvent(
        id=f"evt_{uuid4().hex[:12]}",
        lineage_id=lineage_id,
        source=payload.source,
        metric=payload.metric,
        value=round(float(payload.value), 4),
        captured_at=datetime.now(timezone.utc),
    )
    data = _read_store()
    updated_links = []
    for raw in data["links"]:
        if raw.get("id") == lineage_id:
            raw["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_links.append(raw)
    data["links"] = updated_links
    data["events"].append(event.model_dump(mode="json"))
    _write_store(data)
    return event


def _lineage_events(lineage_id: str) -> list[UsageEvent]:
    data = _read_store()
    out: list[UsageEvent] = []
    for raw in data["events"]:
        try:
            ev = UsageEvent(**raw)
        except Exception:
            continue
        if ev.lineage_id == lineage_id:
            out.append(ev)
    return out


def list_usage_events(limit: int = 500) -> list[UsageEvent]:
    data = _read_store()
    out: list[UsageEvent] = []
    for raw in data["events"]:
        try:
            out.append(UsageEvent(**raw))
        except Exception:
            continue
    out.sort(key=lambda x: x.captured_at, reverse=True)
    return out[: max(1, min(limit, 5000))]


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
