"""Flow simulator — visualize how CC moves through the community.

Simulates the full reward flow based on active policies:
  - Contributions earn CC (creation)
  - Views earn discovery rewards (attention)
  - Referrals earn transaction fees (presence)
  - Staking amplifies returns (commitment)
  - Coherence score multiplies everything (alignment)

The simulator reads real policies from the reward_policy_service
and projects CC flow for hypothetical scenarios, making the
invisible visible — the community can see exactly how energy moves
before and after adjusting any knob.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import reward_policy_service

router = APIRouter()


# ── Simulation models ────────────────────────────────────────────

class SimulationInput(BaseModel):
    """Community scenario to simulate."""
    contributors: int = Field(10, ge=1, le=10000, description="Active contributors")
    assets_created: int = Field(5, ge=0, le=1000, description="Assets created per month")
    views_per_asset: int = Field(100, ge=0, le=100000, description="Monthly views per asset")
    referral_rate: float = Field(0.15, ge=0, le=1.0, description="Fraction of views via referral")
    transaction_rate: float = Field(0.05, ge=0, le=1.0, description="Fraction of views that transact")
    avg_transaction_cc: float = Field(50.0, ge=0, description="Average CC per transaction")
    avg_contribution_cc: float = Field(100.0, ge=0, description="CC per contribution (creation)")
    avg_coherence_score: float = Field(0.75, ge=0, le=1.0, description="Community coherence")
    staking_rate: float = Field(0.3, ge=0, le=1.0, description="Fraction of CC staked")
    workspace_id: str = Field("coherence-network", description="Community to simulate for")


class FlowNode(BaseModel):
    """One node in the flow visualization."""
    id: str
    label: str
    cc_in: float = 0
    cc_out: float = 0
    detail: str = ""


class FlowEdge(BaseModel):
    """One edge in the flow visualization."""
    from_id: str
    to_id: str
    cc_amount: float
    label: str = ""


class SimulationResult(BaseModel):
    """Complete flow simulation with visualization data."""
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    totals: dict[str, Any]
    policy_snapshot: dict[str, Any]
    vitality_signals: list[dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────────

@router.post(
    "/flow/simulate",
    response_model=SimulationResult,
    summary="Simulate community CC flow",
    description=(
        "Project how CC flows through the community based on active "
        "policies and hypothetical activity levels. Adjust inputs to "
        "see how changing formulas or activity affects vitality."
    ),
)
async def simulate_flow(scenario: SimulationInput) -> SimulationResult:
    """Run a full flow simulation for a community scenario."""
    ws = scenario.workspace_id
    policies = _load_policies(ws)
    snapshot = reward_policy_service.get_policy_snapshot(ws)

    # ── Compute flows ──

    total_views = scenario.assets_created * scenario.views_per_asset
    referral_views = int(total_views * scenario.referral_rate)
    transactions = int(total_views * scenario.transaction_rate)

    # Creation rewards (contributions)
    creation_cc = scenario.contributors * scenario.avg_contribution_cc
    coherence_bonus = policies["coherence_bonus_multiplier"] if scenario.avg_coherence_score >= policies["coherence_bonus_threshold"] else 1.0
    creation_cc_with_bonus = creation_cc * coherence_bonus

    # Attention rewards (discovery views)
    view_reward = policies["view_reward_cc"]
    max_daily = policies["max_view_rewards_daily"]
    # Each referrer can earn max daily cap * 30 days
    max_per_referrer_month = max_daily * 30
    active_referrers = max(1, int(scenario.contributors * scenario.referral_rate))
    capped_referral_views = min(referral_views, active_referrers * max_per_referrer_month)
    attention_cc = capped_referral_views * view_reward

    # Presence rewards (transaction referral fees)
    fee_rate = policies["transaction_fee_rate"]
    total_transaction_cc = transactions * scenario.avg_transaction_cc
    presence_cc = total_transaction_cc * fee_rate

    # Staking lock-up
    total_earned = creation_cc_with_bonus + attention_cc + presence_cc
    staked_cc = total_earned * scenario.staking_rate
    circulating_cc = total_earned - staked_cc

    # ── Build flow graph ──

    nodes = [
        FlowNode(
            id="creation",
            label="Creation",
            cc_in=0,
            cc_out=creation_cc_with_bonus,
            detail=f"{scenario.contributors} contributors × {scenario.avg_contribution_cc} CC"
            + (f" × {coherence_bonus:.2f} bonus" if coherence_bonus > 1 else ""),
        ),
        FlowNode(
            id="attention",
            label="Attention",
            cc_in=0,
            cc_out=attention_cc,
            detail=f"{capped_referral_views:,} referral views × {view_reward} CC",
        ),
        FlowNode(
            id="presence",
            label="Presence",
            cc_in=0,
            cc_out=presence_cc,
            detail=f"{fee_rate*100:.1f}% of {total_transaction_cc:,.0f} CC in transactions",
        ),
        FlowNode(
            id="treasury",
            label="Treasury",
            cc_in=total_earned,
            cc_out=total_earned,
            detail=f"Mints {total_earned:,.2f} CC to reward the community",
        ),
        FlowNode(
            id="contributors",
            label="Contributors",
            cc_in=total_earned,
            cc_out=staked_cc,
            detail=f"{scenario.contributors} active, earning {total_earned/max(scenario.contributors,1):,.2f} CC each",
        ),
        FlowNode(
            id="staking",
            label="Staked",
            cc_in=staked_cc,
            cc_out=0,
            detail=f"{scenario.staking_rate*100:.0f}% of earnings committed to ideas",
        ),
        FlowNode(
            id="circulation",
            label="Circulating",
            cc_in=circulating_cc,
            cc_out=0,
            detail=f"Available for exchange, transfer, or spending",
        ),
    ]

    edges = [
        FlowEdge(from_id="treasury", to_id="creation", cc_amount=creation_cc_with_bonus, label="Creation rewards"),
        FlowEdge(from_id="treasury", to_id="attention", cc_amount=attention_cc, label="View rewards"),
        FlowEdge(from_id="treasury", to_id="presence", cc_amount=presence_cc, label="Referral fees"),
        FlowEdge(from_id="creation", to_id="contributors", cc_amount=creation_cc_with_bonus, label="To creators"),
        FlowEdge(from_id="attention", to_id="contributors", cc_amount=attention_cc, label="To referrers"),
        FlowEdge(from_id="presence", to_id="contributors", cc_amount=presence_cc, label="To discoverers"),
        FlowEdge(from_id="contributors", to_id="staking", cc_amount=staked_cc, label="Staked on ideas"),
        FlowEdge(from_id="contributors", to_id="circulation", cc_amount=circulating_cc, label="Circulating"),
    ]

    # ── Vitality signals ──

    vitality_signals = _compute_vitality_signals(scenario, policies, total_earned, total_views)

    totals = {
        "monthly_cc_minted": round(total_earned, 2),
        "creation_cc": round(creation_cc_with_bonus, 2),
        "attention_cc": round(attention_cc, 2),
        "presence_cc": round(presence_cc, 2),
        "staked_cc": round(staked_cc, 2),
        "circulating_cc": round(circulating_cc, 2),
        "cc_per_contributor": round(total_earned / max(scenario.contributors, 1), 2),
        "total_views": total_views,
        "referral_views": referral_views,
        "transactions": transactions,
        "coherence_bonus_applied": coherence_bonus > 1,
    }

    return SimulationResult(
        nodes=nodes,
        edges=edges,
        totals=totals,
        policy_snapshot=snapshot,
        vitality_signals=vitality_signals,
    )


@router.get(
    "/flow/live",
    summary="Live flow stats from real data",
    description="Current CC flow based on actual activity and active policies.",
)
async def live_flow(
    days: int = Query(30, ge=1, le=365),
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Real flow data — what's actually happening in the community."""
    try:
        from app.services import read_tracking_service
        from app.services import cc_treasury_service
        from app.services.unified_db import session
        from app.services.cc_treasury_service import TreasuryLedgerEntry
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func

        since = datetime.now(timezone.utc) - timedelta(days=days)
        policies = _load_policies(workspace_id)
        snapshot = reward_policy_service.get_policy_snapshot(workspace_id)

        # Real view stats
        trending = read_tracking_service.get_trending(limit=1000, days=days)
        total_views = sum(t["view_count"] for t in trending)
        unique_assets = len(trending)
        unique_viewers = sum(t.get("unique_viewers", 0) for t in trending)

        # Real treasury activity
        with session() as s:
            minted = (
                s.query(func.coalesce(func.sum(TreasuryLedgerEntry.amount_cc), 0.0))
                .filter(
                    TreasuryLedgerEntry.action == "mint",
                    TreasuryLedgerEntry.created_at >= since,
                )
                .scalar()
            ) or 0

            staked = (
                s.query(func.coalesce(func.sum(TreasuryLedgerEntry.amount_cc), 0.0))
                .filter(
                    TreasuryLedgerEntry.action == "stake",
                    TreasuryLedgerEntry.created_at >= since,
                )
                .scalar()
            ) or 0

        return {
            "days": days,
            "workspace_id": workspace_id,
            "views": {
                "total": total_views,
                "unique_assets": unique_assets,
                "unique_viewers": unique_viewers,
            },
            "cc": {
                "minted": round(float(minted), 2),
                "staked": round(float(staked), 2),
                "circulating": round(float(minted) - float(staked), 2),
            },
            "active_policies": policies,
            "policy_snapshot": snapshot,
            "top_trending": trending[:10],
        }
    except Exception as e:
        return {
            "days": days,
            "workspace_id": workspace_id,
            "error": str(e),
        }


# ── Internal ────────────────────────────────────────────────────

def _load_policies(workspace_id: str) -> dict[str, Any]:
    """Load policy values (unwrapped) for simulation."""
    gv = reward_policy_service.get_policy_value
    return {
        "view_reward_cc": gv("discovery.view_reward_cc", workspace_id) or 0.01,
        "transaction_fee_rate": gv("discovery.transaction_fee_rate", workspace_id) or 0.02,
        "max_view_rewards_daily": gv("discovery.max_view_rewards_daily", workspace_id) or 100,
        "coherence_bonus_threshold": gv("distribution.coherence_bonus_threshold", workspace_id) or 0.9,
        "coherence_bonus_multiplier": gv("distribution.coherence_bonus_multiplier", workspace_id) or 1.25,
    }


def _compute_vitality_signals(
    scenario: SimulationInput,
    policies: dict[str, Any],
    total_earned: float,
    total_views: int,
) -> list[dict[str, Any]]:
    """Sense what's alive and what needs attention in the community."""
    signals = []

    # Engagement depth: views per contributor
    views_per_contributor = total_views / max(scenario.contributors, 1)
    if views_per_contributor > 50:
        signals.append({
            "signal": "high_engagement",
            "value": round(views_per_contributor, 1),
            "message": f"Strong attention: {views_per_contributor:.0f} views per contributor",
            "vitality": "thriving",
        })
    elif views_per_contributor < 5:
        signals.append({
            "signal": "low_engagement",
            "value": round(views_per_contributor, 1),
            "message": f"Attention is sparse: {views_per_contributor:.1f} views per contributor",
            "vitality": "needs_energy",
        })

    # Discovery health: referral rate
    if scenario.referral_rate > 0.2:
        signals.append({
            "signal": "organic_growth",
            "value": scenario.referral_rate,
            "message": f"{scenario.referral_rate*100:.0f}% of views come through referrals — organic discovery is strong",
            "vitality": "thriving",
        })
    elif scenario.referral_rate < 0.05:
        signals.append({
            "signal": "low_referrals",
            "value": scenario.referral_rate,
            "message": "Referral rate is low — contributors can earn by sharing what they find valuable",
            "vitality": "opportunity",
        })

    # Coherence health
    if scenario.avg_coherence_score >= policies["coherence_bonus_threshold"]:
        signals.append({
            "signal": "coherence_bonus_active",
            "value": scenario.avg_coherence_score,
            "message": f"Community coherence ({scenario.avg_coherence_score:.2f}) earns {policies['coherence_bonus_multiplier']}× multiplier",
            "vitality": "thriving",
        })

    # Staking depth
    if scenario.staking_rate > 0.5:
        signals.append({
            "signal": "deep_commitment",
            "value": scenario.staking_rate,
            "message": f"{scenario.staking_rate*100:.0f}% of earnings are staked — deep commitment to ideas",
            "vitality": "thriving",
        })

    # Earning distribution
    cc_per_contributor = total_earned / max(scenario.contributors, 1)
    if cc_per_contributor > 0:
        signals.append({
            "signal": "earning_distribution",
            "value": round(cc_per_contributor, 2),
            "message": f"Each contributor earns ~{cc_per_contributor:,.0f} CC/month on average",
            "vitality": "informational",
        })

    # Creation vs attention balance
    creation_share = (scenario.contributors * scenario.avg_contribution_cc) / max(total_earned, 1)
    if creation_share > 0.8:
        signals.append({
            "signal": "creation_heavy",
            "value": round(creation_share, 2),
            "message": "Most CC flows to creators — consider boosting discovery rewards to spread attention",
            "vitality": "opportunity",
        })
    elif creation_share < 0.3:
        signals.append({
            "signal": "attention_heavy",
            "value": round(creation_share, 2),
            "message": "Most CC flows to discoverers — the community is attention-rich, creation-hungry",
            "vitality": "opportunity",
        })

    return signals
