"""Investment UX: preview ROI, portfolio positions, and flow visualization."""

from __future__ import annotations

import json
from typing import Any

from app.services import contribution_ledger_service, idea_service

# Cap displayed ROI multiplier to avoid absurd UI values from edge-case data
_MAX_ROI_DISPLAY = 50.0


def preview_investment(idea_id: str, amount_cc: float) -> dict[str, Any]:
    """Project return for a marginal CC stake using the idea's live roi_cc."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise ValueError("idea_not_found")
    amt = max(0.0, float(amount_cc))
    roi = float(idea.roi_cc or 0.0)
    projected_return = amt * roi
    return {
        "idea_id": idea_id,
        "idea_name": idea.name,
        "amount_cc": round(amt, 4),
        "roi_cc": round(roi, 4),
        "projected_return_cc": round(projected_return, 4),
        "projected_value_cc": round(amt + projected_return, 4),
        "remaining_cost_cc": round(float(idea.remaining_cost_cc or 0.0), 4),
        "value_gap_cc": round(float(idea.value_gap_cc or 0.0), 4),
        "free_energy_score": round(float(idea.free_energy_score or 0.0), 4),
    }


def build_portfolio(contributor_id: str) -> dict[str, Any]:
    """Aggregate stakes per idea with estimated mark value from live roi_cc."""
    history = contribution_ledger_service.get_contributor_history(contributor_id, limit=500)
    by_idea: dict[str, dict[str, Any]] = {}

    for rec in history:
        iid = rec.get("idea_id")
        if not iid:
            continue
        ctype = rec.get("contribution_type") or ""
        if ctype == "stake":
            slot = by_idea.setdefault(iid, {"staked_cc": 0.0, "time_hours": 0.0})
            slot["staked_cc"] = float(slot["staked_cc"]) + float(rec.get("amount_cc") or 0.0)
        elif ctype == "time_commitment":
            slot = by_idea.setdefault(iid, {"staked_cc": 0.0, "time_hours": 0.0})
            meta = _parse_meta(rec.get("metadata_json"))
            slot["time_hours"] = float(slot["time_hours"]) + float(meta.get("hours") or 0.0)

    positions: list[dict[str, Any]] = []
    total_staked = 0.0
    total_mark = 0.0

    for iid, agg in by_idea.items():
        idea = idea_service.get_idea(iid)
        roi = min(float(idea.roi_cc or 0.0) if idea else 0.0, _MAX_ROI_DISPLAY)
        staked = float(agg["staked_cc"])
        hours = float(agg.get("time_hours") or 0.0)
        mark = staked * (1.0 + roi) if staked > 0 else 0.0
        total_staked += staked
        total_mark += mark
        positions.append({
            "idea_id": iid,
            "idea_name": idea.name if idea else iid,
            "staked_cc": round(staked, 4),
            "time_hours_committed": round(hours, 4),
            "roi_cc": round(float(idea.roi_cc or 0.0) if idea else 0.0, 4),
            "current_value_cc": round(mark, 4),
            "manifestation_status": getattr(idea, "manifestation_status", None) if idea else None,
        })

    positions.sort(key=lambda p: p["current_value_cc"], reverse=True)

    return {
        "contributor_id": contributor_id,
        "positions": positions,
        "totals": {
            "staked_cc": round(total_staked, 4),
            "estimated_mark_value_cc": round(total_mark, 4),
        },
    }


def build_investment_flow(contributor_id: str) -> dict[str, Any]:
    """Nodes and edges for CC flow visualization + chronological timeline."""
    history = contribution_ledger_service.get_contributor_history(contributor_id, limit=200)

    nodes: list[dict[str, str]] = [
        {"id": "_contributor", "label": contributor_id, "type": "contributor"},
    ]
    idea_seen: set[str] = set()
    edges: list[dict[str, Any]] = []
    needs_network_sink = False

    for rec in reversed(history):
        iid = rec.get("idea_id")
        ctype = rec.get("contribution_type") or "unknown"
        meta = _parse_meta(rec.get("metadata_json"))
        base = {
            "amount_cc": float(rec.get("amount_cc") or 0.0),
            "kind": ctype,
            "recorded_at": rec.get("recorded_at"),
            "hours": meta.get("hours"),
            "commitment": meta.get("commitment"),
        }
        if iid:
            if iid not in idea_seen:
                idea = idea_service.get_idea(iid)
                nodes.append({
                    "id": iid,
                    "label": idea.name if idea else iid,
                    "type": "idea",
                })
                idea_seen.add(iid)
            edges.append({"source": "_contributor", "target": iid, **base})
        else:
            needs_network_sink = True
            edges.append({"source": "_contributor", "target": "_network", **base})

    if needs_network_sink:
        nodes.append({"id": "_network", "label": "Other / network", "type": "sink"})

    return {
        "contributor_id": contributor_id,
        "nodes": nodes,
        "edges": edges,
        "timeline": history,
    }


def _parse_meta(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        return json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}


def record_time_commitment(
    idea_id: str,
    contributor_id: str,
    hours: float,
    commitment: str,
) -> dict[str, Any]:
    """Append-only time investment (review / implement)."""
    if commitment not in ("review", "implement"):
        raise ValueError("invalid_commitment")
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise ValueError("idea_not_found")
    h = max(0.0, float(hours))
    return contribution_ledger_service.record_contribution(
        contributor_id=contributor_id,
        contribution_type="time_commitment",
        amount_cc=0.0,
        idea_id=idea_id,
        metadata={
            "hours": h,
            "commitment": commitment,
            "note": f"time:{commitment}",
        },
    )
