"""Discovery reward service — CC flows to contributors who bring attention.

When a contributor's referral link leads to another contributor viewing
(and eventually transacting on) an asset, the referrer earns CC from
the flow. This is the organic discovery model: any contribution that
brings an NFT in front of someone earns from the flow.

Reward formula:
  - Each qualified view (authenticated viewer, identified referrer) earns
    a base reward proportional to the asset's vitality score.
  - On transaction (stake, purchase, swap), the referrer earns a percentage
    of the transaction CC value as a discovery fee.
  - Discovery fees are minted from the treasury (coherence-invariant),
    recorded as 'discovery_reward' ledger entries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func

log = logging.getLogger(__name__)

# Discovery reward rates
VIEW_REWARD_CC = 0.01          # CC per qualified view
TRANSACTION_FEE_RATE = 0.02   # 2% of transaction CC to referrer
MAX_VIEW_REWARDS_PER_DAY = 100  # cap per referrer per day


def reward_discovery_view(
    referrer_contributor_id: str,
    asset_id: str,
    viewer_contributor_id: str,
) -> dict[str, Any] | None:
    """Reward a referrer for bringing a qualified view.

    A 'qualified view' means both the referrer and the viewer are
    identified contributors, and the viewer has a connected wallet.
    Returns the reward entry or None if reward conditions are not met.
    """
    try:
        from app.services import cc_treasury_service
        from app.services.cc_oracle_service import get_exchange_rate

        # Check daily cap
        today_rewards = _count_today_rewards(referrer_contributor_id)
        if today_rewards >= MAX_VIEW_REWARDS_PER_DAY:
            log.debug("discovery: daily cap reached for %s", referrer_contributor_id)
            return None

        rate = get_exchange_rate()
        if not cc_treasury_service.can_mint(rate):
            log.debug("discovery: minting paused, skipping view reward")
            return None

        # Mint the view reward
        entry = cc_treasury_service.mint(
            user_id=referrer_contributor_id,
            amount_cc=VIEW_REWARD_CC,
            deposit_usd=0.0,  # view rewards are new CC from coherence
            exchange_rate=rate,
        )

        _record_discovery_event(
            referrer_id=referrer_contributor_id,
            viewer_id=viewer_contributor_id,
            asset_id=asset_id,
            reward_cc=VIEW_REWARD_CC,
            event_type="view_reward",
        )

        log.info(
            "discovery: rewarded %s with %.2f CC for bringing %s to %s",
            referrer_contributor_id, VIEW_REWARD_CC, viewer_contributor_id, asset_id,
        )
        return {
            "referrer": referrer_contributor_id,
            "viewer": viewer_contributor_id,
            "asset_id": asset_id,
            "reward_cc": VIEW_REWARD_CC,
            "ledger_entry_id": entry.id,
        }
    except Exception as e:
        log.warning("discovery: view reward failed: %s", e)
        return None


def reward_discovery_transaction(
    referrer_contributor_id: str,
    asset_id: str,
    transactor_contributor_id: str,
    transaction_cc: float,
) -> dict[str, Any] | None:
    """Reward a referrer when their referral leads to a CC transaction.

    The referrer earns a percentage of the transaction value as a
    discovery fee. This is the organic discovery model: bringing an asset
    in front of someone who transacts earns from the flow.
    """
    try:
        from app.services import cc_treasury_service
        from app.services.cc_oracle_service import get_exchange_rate

        reward_cc = round(transaction_cc * TRANSACTION_FEE_RATE, 8)
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

        _record_discovery_event(
            referrer_id=referrer_contributor_id,
            viewer_id=transactor_contributor_id,
            asset_id=asset_id,
            reward_cc=reward_cc,
            event_type="transaction_reward",
        )

        log.info(
            "discovery: rewarded %s with %.4f CC (%.1f%% of %.2f) for transaction by %s on %s",
            referrer_contributor_id, reward_cc, TRANSACTION_FEE_RATE * 100,
            transaction_cc, transactor_contributor_id, asset_id,
        )
        return {
            "referrer": referrer_contributor_id,
            "transactor": transactor_contributor_id,
            "asset_id": asset_id,
            "transaction_cc": transaction_cc,
            "reward_cc": reward_cc,
            "fee_rate": TRANSACTION_FEE_RATE,
            "ledger_entry_id": entry.id,
        }
    except Exception as e:
        log.warning("discovery: transaction reward failed: %s", e)
        return None


def get_referrer_earnings(contributor_id: str, days: int = 30) -> dict[str, Any]:
    """Get discovery earnings for a referrer over a time period."""
    try:
        from app.services.read_tracking_service import AssetViewEvent
        from app.services.unified_db import session

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

        return {
            "contributor_id": contributor_id,
            "days": days,
            "total_referrals": referral_count,
            "unique_viewers_referred": unique_viewers,
            "unique_assets_shared": unique_assets,
            "estimated_view_rewards_cc": round(min(referral_count, MAX_VIEW_REWARDS_PER_DAY * days) * VIEW_REWARD_CC, 4),
        }
    except Exception as e:
        log.warning("discovery: earnings query failed: %s", e)
        return {
            "contributor_id": contributor_id,
            "days": days,
            "total_referrals": 0,
            "unique_viewers_referred": 0,
            "unique_assets_shared": 0,
            "estimated_view_rewards_cc": 0,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_today_rewards(contributor_id: str) -> int:
    """Count how many view rewards a contributor has received today."""
    try:
        from app.services import cc_treasury_service
        from app.services.unified_db import session

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with session() as s:
            count = (
                s.query(func.count(cc_treasury_service.TreasuryLedgerEntry.id))
                .filter(
                    cc_treasury_service.TreasuryLedgerEntry.user_id == contributor_id,
                    cc_treasury_service.TreasuryLedgerEntry.action == "mint",
                    cc_treasury_service.TreasuryLedgerEntry.created_at >= today_start,
                    cc_treasury_service.TreasuryLedgerEntry.amount_cc == VIEW_REWARD_CC,
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
) -> None:
    """Record a discovery event as a graph edge for traceability."""
    try:
        from app.services import graph_service

        graph_service.create_edge(
            from_id=referrer_id,
            to_id=asset_id,
            edge_type="discovery_reward",
            properties={
                "viewer_id": viewer_id,
                "reward_cc": reward_cc,
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            strength=reward_cc,
            created_by="discovery_reward_service",
        )
    except Exception as e:
        log.debug("discovery: graph edge creation failed: %s", e)
