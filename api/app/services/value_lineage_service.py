"""Service for persistent value lineage and payout attribution previews."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models.value_lineage import (
    LineageLink,
    LineageLinkCreate,
    LineageValuation,
    PayoutPreview,
    PayoutRow,
    UsageEvent,
    UsageEventCreate,
)

DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    "idea": 0.1,
    "spec": 0.2,
    "implementation": 0.5,
    "review": 0.2,
}


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

    contributors = {
        "idea": link.contributors.idea,
        "spec": link.contributors.spec,
        "implementation": link.contributors.implementation,
        "review": link.contributors.review,
    }
    active_roles = {role: who for role, who in contributors.items() if isinstance(who, str) and who}
    weights = {role: DEFAULT_ROLE_WEIGHTS[role] for role in active_roles}
    weight_total = sum(weights.values())
    payouts: list[PayoutRow] = []
    for role, contributor in active_roles.items():
        normalized_weight = (weights[role] / weight_total) if weight_total > 0 else 0.0
        amount = round(float(payout_pool) * normalized_weight, 4)
        payouts.append(PayoutRow(role=role, contributor=contributor, amount=amount))

    return PayoutPreview(
        lineage_id=lineage_id,
        payout_pool=round(float(payout_pool), 4),
        measured_value_total=summary.measured_value_total,
        estimated_cost=summary.estimated_cost,
        roi_ratio=summary.roi_ratio,
        weights=DEFAULT_ROLE_WEIGHTS,
        payouts=payouts,
    )
