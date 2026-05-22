"""Investment service — positions, ROI projection, history.

The core abstraction is a Position: a contributor's stake in one idea
along with its current value and ROI. The three endpoints
(invest-preview, investments-list, investment-history) are all projections
of the same underlying ledger + idea state.

Pure functions over the contribution ledger + idea registry. Everything
that writes (recording a stake, recording a fulfillment) lives in the
specialized services (stake_compute_service, time_pledge_service); this
file only reads and computes.
"""

from __future__ import annotations

import json
from typing import Optional

from app.models.idea import IdeaStage
from app.services import contribution_ledger_service, idea_service, time_pledge_service


# ---------------------------------------------------------------------------
# Constants — stage progression model
# ---------------------------------------------------------------------------

# Stage -> unlock percentage. The earlier the stake on the lifecycle, the
# more value is "locked" against future returns; later stages have most of
# the value already realized.
_STAGE_UNLOCK_PCT: dict[str, int] = {
    IdeaStage.NONE.value: 0,
    IdeaStage.SPECCED.value: 10,
    IdeaStage.IMPLEMENTING.value: 40,
    IdeaStage.TESTING.value: 70,
    IdeaStage.REVIEWING.value: 90,
    IdeaStage.COMPLETE.value: 100,
}

# Typical pipeline velocity (days), for surface display only. Calibrated
# from observation — refine when enough historical data exists.
_PIPELINE_VELOCITY_DAYS: list[int] = [2, 5]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stage_value(idea) -> str:
    stage = getattr(idea, "stage", IdeaStage.NONE.value)
    return stage.value if hasattr(stage, "value") else str(stage or "none")


def _coherence_score(idea) -> float:
    """Approximate coherence from the idea's free-energy weighted shape.

    Uses confidence × (potential_value / max(estimated_cost, 1)) clamped to
    [0, 1]. Falls back to confidence alone when value/cost are degenerate.
    """
    confidence = float(getattr(idea, "confidence", 0.5) or 0.5)
    pv = float(getattr(idea, "potential_value", 0.0) or 0.0)
    ec = float(getattr(idea, "estimated_cost", 0.0) or 0.0)
    if ec <= 0 or pv <= 0:
        return round(max(0.0, min(1.0, confidence)), 4)
    ratio = min(1.0, pv / (pv + ec))
    return round(max(0.0, min(1.0, 0.5 * confidence + 0.5 * ratio)), 4)


def _stage_unlock_pct(idea) -> int:
    return _STAGE_UNLOCK_PCT.get(_stage_value(idea), 0)


def _projection_multipliers(coherence_score: float, prior_roi_avg: float) -> tuple[float, float]:
    """Return (low_multiplier, high_multiplier) for the ROI range.

    Honest until calibration: anchored on coherence + prior_roi, widening
    when there's no prior signal. low = 0.8 + 0.6 * coherence; high =
    low + (0.5 + prior_roi_avg). Both >= 0.
    """
    low = round(0.8 + 0.6 * coherence_score, 4)
    high = round(low + 0.5 + max(0.0, prior_roi_avg), 4)
    return low, high


# ---------------------------------------------------------------------------
# Aggregation: ledger -> positions
# ---------------------------------------------------------------------------


def _stake_records_by_contributor(
    contributor_id: str,
) -> list[dict]:
    """Return raw 'stake' ledger records for a contributor."""
    history = contribution_ledger_service.get_contributor_history(
        contributor_id=contributor_id, limit=500
    )
    return [r for r in history if r.get("contribution_type") == "stake"]


def _idea_stake_totals(idea_id: str) -> tuple[float, list[str], list[float]]:
    """Sum stakes for an idea. Returns (total_cc, contributor_ids, per_stake_amounts)."""
    investments = contribution_ledger_service.get_idea_investments(idea_id)
    total = 0.0
    contributors: list[str] = []
    amounts: list[float] = []
    for inv in investments:
        if inv.get("contribution_type") == "stake":
            amt = float(inv.get("amount_cc", 0.0))
            total += amt
            amounts.append(amt)
            cid = inv.get("contributor_id", "")
            if cid and cid not in contributors:
                contributors.append(cid)
    return round(total, 4), contributors, amounts


def _prior_roi_avg(idea_id: str) -> float:
    """Average ROI for stakers on an idea other than the current viewer.

    Pulls 'return' records on the idea, divides by total stake. Honest
    placeholder: returns 0.0 when no returns recorded yet.
    """
    investments = contribution_ledger_service.get_idea_investments(idea_id)
    total_returns = 0.0
    total_stakes = 0.0
    for inv in investments:
        ctype = inv.get("contribution_type")
        amt = float(inv.get("amount_cc", 0.0))
        if ctype == "return":
            total_returns += amt
        elif ctype == "stake":
            total_stakes += amt
    if total_stakes <= 0:
        return 0.0
    return round(max(0.0, total_returns / total_stakes), 4)


def _position_current_value(invested_cc: float, idea) -> float:
    """Current value of a position based on stage unlock and coherence.

    multiplier = 1 + (stage_unlock_pct / 100) * coherence_score
    """
    unlock = _stage_unlock_pct(idea) / 100.0
    coherence = _coherence_score(idea)
    multiplier = 1.0 + unlock * coherence
    return round(invested_cc * multiplier, 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_positions(contributor_id: str) -> list[dict]:
    """Compute one Position per (contributor, idea) the contributor staked on."""
    stakes = _stake_records_by_contributor(contributor_id)

    # Aggregate stakes by idea_id (multiple stakes on same idea sum together).
    by_idea: dict[str, dict] = {}
    for rec in stakes:
        idea_id = rec.get("idea_id")
        if not idea_id:
            continue
        agg = by_idea.setdefault(
            idea_id,
            {"invested_cc": 0.0, "earliest_staked_at": None},
        )
        agg["invested_cc"] += float(rec.get("amount_cc", 0.0))
        rec_at = rec.get("recorded_at")
        if rec_at and (agg["earliest_staked_at"] is None or rec_at < agg["earliest_staked_at"]):
            agg["earliest_staked_at"] = rec_at

    positions: list[dict] = []
    for idea_id, agg in by_idea.items():
        idea = idea_service.get_idea(idea_id)
        if idea is None:
            # Idea was removed — still show position with stub name.
            positions.append({
                "idea_id": idea_id,
                "idea_name": idea_id,
                "invested_cc": round(agg["invested_cc"], 4),
                "current_value_cc": round(agg["invested_cc"], 4),
                "gain_loss_cc": 0.0,
                "roi_pct": 0.0,
                "stage": "none",
                "unlock_pct": 0,
                "staked_at": agg["earliest_staked_at"],
            })
            continue

        invested = round(agg["invested_cc"], 4)
        current = _position_current_value(invested, idea)
        gain_loss = round(current - invested, 4)
        roi_pct = round((gain_loss / invested) * 100.0, 4) if invested > 0 else 0.0

        positions.append({
            "idea_id": idea_id,
            "idea_name": idea.name,
            "invested_cc": invested,
            "current_value_cc": current,
            "gain_loss_cc": gain_loss,
            "roi_pct": roi_pct,
            "stage": _stage_value(idea),
            "unlock_pct": _stage_unlock_pct(idea),
            "staked_at": agg["earliest_staked_at"],
        })

    # Sort by gain/loss descending (most rewarding positions first).
    positions.sort(key=lambda p: p["gain_loss_cc"], reverse=True)
    return positions


def compute_portfolio(contributor_id: str) -> dict:
    """Compute the full portfolio (summary + positions)."""
    positions = compute_positions(contributor_id)
    total_invested = round(sum(p["invested_cc"] for p in positions), 4)
    total_current = round(sum(p["current_value_cc"] for p in positions), 4)
    total_gain_loss = round(total_current - total_invested, 4)
    active = sum(1 for p in positions if p["stage"] not in ("complete", "none"))

    return {
        "contributor_id": contributor_id,
        "summary": {
            "total_invested_cc": total_invested,
            "total_current_value_cc": total_current,
            "total_gain_loss_cc": total_gain_loss,
            "total_positions": len(positions),
            "active_positions": active,
        },
        "positions": positions,
    }


def compute_preview(idea_id: str) -> Optional[dict]:
    """ROI preview for an idea — projection range + summary stats."""
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return None

    total_staked, contributors, _ = _idea_stake_totals(idea_id)
    prior_roi = _prior_roi_avg(idea_id)
    coherence = _coherence_score(idea)
    low, high = _projection_multipliers(coherence, prior_roi)

    return {
        "idea_id": idea_id,
        "idea_name": idea.name,
        "stage": _stage_value(idea),
        "coherence_score": coherence,
        "total_cc_staked": total_staked,
        "prior_investments_count": len(contributors),
        "prior_roi_avg": prior_roi,
        "projections": {
            "low_multiplier": low,
            "high_multiplier": high,
            "basis": "coherence_score + prior_roi_avg",
        },
        "stage_unlock_pct": _stage_unlock_pct(idea),
        "pipeline_velocity_days": list(_PIPELINE_VELOCITY_DAYS),
    }


def compute_history(
    contributor_id: str,
    limit: int = 100,
    since: Optional[str] = None,
    idea_id: Optional[str] = None,
) -> dict:
    """Investment-relevant timeline events for a contributor.

    Filters the ledger to types that show CC flow into and out of
    investments: stake, return, compute, plus pledge create/fulfill from
    the pledge table.
    """
    history = contribution_ledger_service.get_contributor_history(
        contributor_id=contributor_id, limit=limit, since=since
    )

    relevant_types = {"stake", "return", "compute"}
    events: list[dict] = []
    for rec in history:
        ctype = rec.get("contribution_type", "")
        if ctype not in relevant_types:
            continue
        if idea_id and rec.get("idea_id") != idea_id:
            continue
        meta: dict = {}
        try:
            meta = json.loads(rec.get("metadata_json") or "{}")
        except (ValueError, TypeError):
            meta = {}
        events.append({
            "event_id": rec.get("id", ""),
            "event_type": ctype,
            "idea_id": rec.get("idea_id"),
            "amount_cc": float(rec.get("amount_cc", 0.0)),
            "recorded_at": rec.get("recorded_at"),
            "metadata": meta,
        })

    # Include pledge create/fulfill events (these don't live in the
    # contribution_ledger directly).
    pledges = time_pledge_service.list_pledges(contributor_id)
    for p in pledges:
        if idea_id and p.get("idea_id") != idea_id:
            continue
        events.append({
            "event_id": p["pledge_id"],
            "event_type": "pledge",
            "idea_id": p.get("idea_id"),
            "amount_cc": float(p.get("cc_equivalent", 0.0)),
            "recorded_at": p.get("created_at"),
            "metadata": {
                "hours_pledged": p.get("hours_pledged"),
                "pledge_type": p.get("pledge_type"),
                "status": p.get("status"),
            },
        })

    # Sort newest first by recorded_at; None-safe.
    events.sort(key=lambda e: e.get("recorded_at") or "", reverse=True)
    if limit > 0:
        events = events[:limit]

    return {"contributor_id": contributor_id, "events": events}
