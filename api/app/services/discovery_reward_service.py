"""Discovery reward service — CC flows to contributors who bring attention.

When a contributor's referral link leads to another contributor viewing
(and eventually transacting on) an asset, the referrer earns CC from
the flow. This is the organic discovery model: any contribution that
brings an NFT in front of someone earns from the flow.

All formulas are community-configurable via reward_policy_service.
Every reward event embeds the exact policy snapshot that produced it,
so the flow is fully transparent and traceable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func

log = logging.getLogger(__name__)


def _get_discovery_policies(workspace_id: str = "coherence-network") -> dict[str, Any]:
    """Read the active discovery reward policies for a workspace."""
    from app.services import reward_policy_service

    return {
        "view_reward_cc": reward_policy_service.get_policy_value(
            "discovery.view_reward_cc", workspace_id,
        ),
        "transaction_fee_rate": reward_policy_service.get_policy_value(
            "discovery.transaction_fee_rate", workspace_id,
        ),
        "max_view_rewards_daily": reward_policy_service.get_policy_value(
            "discovery.max_view_rewards_daily", workspace_id,
        ),
    }


def reward_discovery_view(
    referrer_contributor_id: str,
    asset_id: str,
    viewer_contributor_id: str,
    workspace_id: str = "coherence-network",
) -> dict[str, Any] | None:
    """Reward a referrer for bringing a qualified view.

    A 'qualified view' means both the referrer and the viewer are
    identified contributors. Returns the reward entry including the
    policy snapshot that produced it, or None if conditions are unmet.
    """
    try:
        from app.services import cc_treasury_service, reward_policy_service
        from app.services.cc_oracle_service import get_exchange_rate

        policies = _get_discovery_policies(workspace_id)
        view_reward_cc = policies["view_reward_cc"]
        max_daily = policies["max_view_rewards_daily"]

        # Check daily cap
        today_rewards = _count_today_rewards(referrer_contributor_id, view_reward_cc)
        if today_rewards >= max_daily:
            log.debug("discovery: daily cap reached for %s (%d/%d)",
                      referrer_contributor_id, today_rewards, max_daily)
            return None

        rate = get_exchange_rate()
        if not cc_treasury_service.can_mint(rate):
            log.debug("discovery: minting paused, skipping view reward")
            return None

        # Mint the view reward
        entry = cc_treasury_service.mint(
            user_id=referrer_contributor_id,
            amount_cc=view_reward_cc,
            deposit_usd=0.0,
            exchange_rate=rate,
        )

        # Snapshot the policy for traceability
        policy_snapshot = reward_policy_service.get_policy_snapshot(workspace_id)

        # Record in graph for traceability
        _record_discovery_event(
            referrer_id=referrer_contributor_id,
            viewer_id=viewer_contributor_id,
            asset_id=asset_id,
            reward_cc=view_reward_cc,
            event_type="view_reward",
            policy_snapshot=policy_snapshot,
        )

        log.info(
            "discovery: rewarded %s with %.4f CC for bringing %s to %s (workspace=%s)",
            referrer_contributor_id, view_reward_cc, viewer_contributor_id,
            asset_id, workspace_id,
        )
        return {
            "referrer": referrer_contributor_id,
            "viewer": viewer_contributor_id,
            "asset_id": asset_id,
            "reward_cc": view_reward_cc,
            "ledger_entry_id": entry.id,
            "workspace_id": workspace_id,
            "policy_applied": {
                "view_reward_cc": view_reward_cc,
                "max_daily": max_daily,
                "today_count": today_rewards + 1,
            },
            "policy_snapshot": policy_snapshot,
        }
    except Exception as e:
        log.warning("discovery: view reward failed: %s", e)
        return None


def reward_discovery_transaction(
    referrer_contributor_id: str,
    asset_id: str,
    transactor_contributor_id: str,
    transaction_cc: float,
    workspace_id: str = "coherence-network",
) -> dict[str, Any] | None:
    """Reward a referrer when their referral leads to a CC transaction.

    The referrer earns a percentage of the transaction value as a
    discovery fee. The percentage is community-configurable.
    """
    try:
        from app.services import cc_treasury_service, reward_policy_service
        from app.services.cc_oracle_service import get_exchange_rate

        policies = _get_discovery_policies(workspace_id)
        fee_rate = policies["transaction_fee_rate"]

        reward_cc = round(transaction_cc * fee_rate, 8)
        if reward_cc <= 0:
            return None

        rate = get_exchange_rate()
        if not cc_treasury_service.can_mint(rate):
            log.debug("discovery: minting paused, skipping transaction reward")
            return None

        entry = cc_treasury_service.mint(
            user_id=referrer_contributor_id,
            amount_cc=reward_cc,
            deposit_usd=0.0,
            exchange_rate=rate,
        )

        policy_snapshot = reward_policy_service.get_policy_snapshot(workspace_id)

        _record_discovery_event(
            referrer_id=referrer_contributor_id,
            viewer_id=transactor_contributor_id,
            asset_id=asset_id,
            reward_cc=reward_cc,
            event_type="transaction_reward",
            policy_snapshot=policy_snapshot,
        )

        log.info(
            "discovery: rewarded %s with %.4f CC (%.1f%% of %.2f) on %s (workspace=%s)",
            referrer_contributor_id, reward_cc, fee_rate * 100,
            transaction_cc, asset_id, workspace_id,
        )
        return {
            "referrer": referrer_contributor_id,
            "transactor": transactor_contributor_id,
            "asset_id": asset_id,
            "transaction_cc": transaction_cc,
            "reward_cc": reward_cc,
            "ledger_entry_id": entry.id,
            "workspace_id": workspace_id,
            "policy_applied": {
                "transaction_fee_rate": fee_rate,
                "formula": f"{transaction_cc} * {fee_rate} = {reward_cc}",
            },
            "policy_snapshot": policy_snapshot,
        }
    except Exception as e:
        log.warning("discovery: transaction reward failed: %s", e)
        return None


def get_referrer_earnings(
    contributor_id: str,
    days: int = 30,
    workspace_id: str = "coherence-network",
) -> dict[str, Any]:
    """Get discovery earnings for a referrer over a time period."""
    try:
        from app.services.read_tracking_service import AssetViewEvent
        from app.services.unified_db import session

        policies = _get_discovery_policies(workspace_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        with session() as s:
            referral_count = (
                s.query(func.count(AssetViewEvent.id))
                .filter(
                    AssetViewEvent.referrer_contributor_id == contributor_id,
                    AssetViewEvent.created_at >= since,
                )
                .scalar()
            ) or 0

            unique_viewers = (
                s.query(func.count(func.distinct(AssetViewEvent.contributor_id)))
                .filter(
                    AssetViewEvent.referrer_contributor_id == contributor_id,
                    AssetViewEvent.created_at >= since,
                    AssetViewEvent.contributor_id.isnot(None),
                )
                .scalar()
            ) or 0

            unique_assets = (
                s.query(func.count(func.distinct(AssetViewEvent.asset_id)))
                .filter(
                    AssetViewEvent.referrer_contributor_id == contributor_id,
                    AssetViewEvent.created_at >= since,
                )
                .scalar()
            ) or 0

        max_daily = policies["max_view_rewards_daily"]
        view_reward = policies["view_reward_cc"]
        capped_referrals = min(referral_count, max_daily * days)

        return {
            "contributor_id": contributor_id,
            "workspace_id": workspace_id,
            "days": days,
            "total_referrals": referral_count,
            "unique_viewers_referred": unique_viewers,
            "unique_assets_shared": unique_assets,
            "estimated_view_rewards_cc": round(capped_referrals * view_reward, 4),
            "active_policy": policies,
        }
    except Exception as e:
        log.warning("discovery: earnings query failed: %s", e)
        return {
            "contributor_id": contributor_id,
            "workspace_id": workspace_id,
            "days": days,
            "total_referrals": 0,
            "unique_viewers_referred": 0,
            "unique_assets_shared": 0,
            "estimated_view_rewards_cc": 0,
            "active_policy": {},
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_today_rewards(contributor_id: str, view_reward_cc: float) -> int:
    """Count how many view rewards a contributor has received today."""
    try:
        from app.services import cc_treasury_service
        from app.services.unified_db import session

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        with session() as s:
            count = (
                s.query(func.count(cc_treasury_service.TreasuryLedgerEntry.id))
                .filter(
                    cc_treasury_service.TreasuryLedgerEntry.user_id == contributor_id,
                    cc_treasury_service.TreasuryLedgerEntry.action == "mint",
                    cc_treasury_service.TreasuryLedgerEntry.created_at >= today_start,
                    cc_treasury_service.TreasuryLedgerEntry.amount_cc == view_reward_cc,
                )
                .scalar()
            ) or 0
        return count
    except Exception:
        return 0


def _record_discovery_event(
    referrer_id: str,
    viewer_id: str,
    asset_id: str,
    reward_cc: float,
    event_type: str,
    policy_snapshot: dict[str, Any] | None = None,
) -> None:
    """Record a discovery event as a graph edge for traceability.

    The policy_snapshot is embedded in the edge properties so anyone
    can trace exactly which formula produced this reward.
    """
    try:
        from app.services import graph_service

        properties: dict[str, Any] = {
            "viewer_id": viewer_id,
            "reward_cc": reward_cc,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if policy_snapshot:
            properties["policy_snapshot"] = policy_snapshot

        graph_service.create_edge(
            from_id=referrer_id,
            to_id=asset_id,
            edge_type="discovery_reward",
            properties=properties,
            strength=reward_cc,
            created_by="discovery_reward_service",
        )
    except Exception as e:
        log.debug("discovery: graph edge creation failed: %s", e)
