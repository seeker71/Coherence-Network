"""Treasury Service — simple crypto deposit ledger with CC conversion.

Records crypto deposits (ETH/BTC), converts to CC at configurable rates,
and optionally auto-stakes on ideas. No smart contracts or private keys —
just an append-only ledger backed by the contribution ledger.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services import contribution_ledger_service
from app.services.config_service import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (overridden by ~/.coherence-network/config.json -> treasury)
# ---------------------------------------------------------------------------

DEFAULT_ETH_ADDRESS = ""  # to be set by owner
DEFAULT_BTC_ADDRESS = ""  # to be set by owner

CC_PER_ETH = 1000.0   # 1 ETH = 1000 CC
CC_PER_BTC = 10000.0   # 1 BTC = 10000 CC

VALID_ASSETS = {"eth", "btc"}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_treasury_config() -> dict:
    """Load treasury config from ~/.coherence-network/config.json."""
    config = get_config()
    return config.get("treasury", {
        "eth_address": DEFAULT_ETH_ADDRESS,
        "btc_address": DEFAULT_BTC_ADDRESS,
        "cc_per_eth": CC_PER_ETH,
        "cc_per_btc": CC_PER_BTC,
    })


def _rate_for_asset(asset: str) -> float:
    """Return CC-per-unit rate for the given asset."""
    tc = get_treasury_config()
    if asset == "eth":
        return float(tc.get("cc_per_eth", CC_PER_ETH))
    if asset == "btc":
        return float(tc.get("cc_per_btc", CC_PER_BTC))
    raise ValueError(f"Unsupported asset: {asset}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_treasury_info() -> dict:
    """Return treasury wallet addresses and current conversion rates."""
    tc = get_treasury_config()
    return {
        "eth_address": tc.get("eth_address", DEFAULT_ETH_ADDRESS),
        "btc_address": tc.get("btc_address", DEFAULT_BTC_ADDRESS),
        "cc_per_eth": float(tc.get("cc_per_eth", CC_PER_ETH)),
        "cc_per_btc": float(tc.get("cc_per_btc", CC_PER_BTC)),
    }


def record_deposit(
    contributor_id: str,
    asset: str,
    amount: float,
    tx_hash: str,
    wallet_address: str | None = None,
) -> dict:
    """Record a crypto deposit, convert to CC.

    Returns: {deposit_id, asset, amount, cc_converted, contributor_id, tx_hash, recorded_at}
    """
    asset = asset.lower().strip()
    if asset not in VALID_ASSETS:
        raise ValueError(f"Invalid asset type: {asset}. Must be one of: {', '.join(sorted(VALID_ASSETS))}")

    if amount <= 0:
        raise ValueError("Deposit amount must be positive")

    if not tx_hash or not tx_hash.strip():
        raise ValueError("Transaction hash is required")

    rate = _rate_for_asset(asset)
    cc_amount = round(amount * rate, 4)
    deposit_id = f"dep_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    metadata = {
        "deposit_id": deposit_id,
        "asset": asset,
        "amount": amount,
        "tx_hash": tx_hash.strip(),
        "wallet_address": wallet_address or "",
        "rate_used": rate,
    }

    # Record as contribution in the append-only ledger
    contribution_ledger_service.record_contribution(
        contributor_id=contributor_id,
        contribution_type="deposit",
        amount_cc=cc_amount,
        idea_id=None,
        metadata=metadata,
    )

    return {
        "deposit_id": deposit_id,
        "asset": asset,
        "amount": amount,
        "cc_converted": cc_amount,
        "contributor_id": contributor_id,
        "tx_hash": tx_hash.strip(),
        "recorded_at": now.isoformat(),
    }


def auto_stake_deposit(
    contributor_id: str,
    cc_amount: float,
    strategy: str = "highest_roi",
) -> dict:
    """Automatically stake deposited CC on ideas.

    Strategies:
    - "highest_roi": stake all on the highest ROI idea
    - "spread": spread evenly across top 3 ideas
    - specific idea_id: stake on one specific idea
    """
    from app.services import idea_service, stake_compute_service

    results: list[dict] = []

    if strategy == "highest_roi":
        ideas_response = idea_service.list_ideas()
        ideas = ideas_response.ideas if hasattr(ideas_response, "ideas") else []
        if not ideas:
            return {"strategy": strategy, "stakes": [], "message": "No ideas available to stake on"}

        # Sort by value_gap / estimated_cost (ROI)
        def _roi(idea):
            cost = idea.estimated_cost if idea.estimated_cost > 0 else 1.0
            gap = (idea.potential_value or 0) - (idea.actual_value or 0)
            return gap / cost

        sorted_ideas = sorted(ideas, key=_roi, reverse=True)
        best = sorted_ideas[0]
        result = stake_compute_service.execute_stake(
            idea_id=best.id,
            staker_id=contributor_id,
            amount_cc=cc_amount,
            rationale=f"Auto-staked from treasury deposit (strategy: highest_roi)",
        )
        results.append({"idea_id": best.id, "idea_name": best.name, "amount_cc": cc_amount, "result": result})

    elif strategy == "spread":
        ideas_response = idea_service.list_ideas()
        ideas = ideas_response.ideas if hasattr(ideas_response, "ideas") else []
        if not ideas:
            return {"strategy": strategy, "stakes": [], "message": "No ideas available to stake on"}

        def _roi(idea):
            cost = idea.estimated_cost if idea.estimated_cost > 0 else 1.0
            gap = (idea.potential_value or 0) - (idea.actual_value or 0)
            return gap / cost

        sorted_ideas = sorted(ideas, key=_roi, reverse=True)
        top_ideas = sorted_ideas[:3]
        per_idea = round(cc_amount / len(top_ideas), 4)

        for idea in top_ideas:
            result = stake_compute_service.execute_stake(
                idea_id=idea.id,
                staker_id=contributor_id,
                amount_cc=per_idea,
                rationale=f"Auto-staked from treasury deposit (strategy: spread)",
            )
            results.append({"idea_id": idea.id, "idea_name": idea.name, "amount_cc": per_idea, "result": result})

    else:
        # Treat strategy as a specific idea_id
        result = stake_compute_service.execute_stake(
            idea_id=strategy,
            staker_id=contributor_id,
            amount_cc=cc_amount,
            rationale=f"Auto-staked from treasury deposit (specific idea)",
        )
        results.append({"idea_id": strategy, "amount_cc": cc_amount, "result": result})

    return {
        "strategy": strategy,
        "stakes": results,
        "total_cc_staked": cc_amount,
    }


def get_deposit_history(contributor_id: str) -> list[dict]:
    """Get all deposits for a contributor."""
    history = contribution_ledger_service.get_contributor_history(contributor_id, limit=500)
    deposits = []
    for rec in history:
        if rec.get("contribution_type") != "deposit":
            continue
        meta = rec.get("metadata_json", "{}")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        deposits.append({
            "deposit_id": meta.get("deposit_id", rec.get("id")),
            "asset": meta.get("asset", ""),
            "amount": meta.get("amount", 0),
            "cc_converted": rec.get("amount_cc", 0),
            "tx_hash": meta.get("tx_hash", ""),
            "wallet_address": meta.get("wallet_address", ""),
            "recorded_at": rec.get("recorded_at"),
        })
    return deposits


def get_treasury_balance() -> dict:
    """Get total deposits by asset type and total CC outstanding."""
    # Scan all contribution ledger records of type "deposit"
    # Use a broad search — get all contributors' history is not ideal,
    # but the ledger is append-only and typically small
    from app.services.unified_db import ensure_schema
    from app.services.contribution_ledger_service import ContributionLedgerRecord, _session, _ensure_schema

    _ensure_schema()
    with _session() as s:
        recs = (
            s.query(ContributionLedgerRecord)
            .filter_by(contribution_type="deposit")
            .all()
        )

    totals_by_asset: dict[str, float] = {}
    total_cc = 0.0
    deposit_count = 0

    for rec in recs:
        meta = rec.metadata_json
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        asset = meta.get("asset", "unknown")
        amount = meta.get("amount", 0)
        totals_by_asset.setdefault(asset, 0.0)
        totals_by_asset[asset] += float(amount)
        total_cc += rec.amount_cc
        deposit_count += 1

    return {
        "deposits_by_asset": {k: round(v, 8) for k, v in totals_by_asset.items()},
        "total_cc_converted": round(total_cc, 4),
        "deposit_count": deposit_count,
    }
