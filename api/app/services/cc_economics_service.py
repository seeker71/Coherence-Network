"""CC Economics Service — orchestrator for supply, exchange, and staking.

Coordinates between treasury, oracle, and staking services. Enforces the
treasury backing invariant and coherence score checks.
"""

from __future__ import annotations

from typing import Optional

from app.models.cc_economics import (
    CCExchangeRate,
    CCSupply,
    StakePosition,
    StakeRequest,
    UnstakeRequest,
    UnstakeResponse,
    UserStakingSummary,
)
from app.services import cc_oracle_service, cc_staking_service, cc_treasury_service


def supply() -> Optional[CCSupply]:
    """Return current CC supply metrics with coherence score.

    Returns None if treasury data is unavailable.
    """
    rate_info = cc_oracle_service.get_exchange_rate()
    if rate_info is None:
        return None

    data = cc_treasury_service.get_supply(rate_info.cc_per_usd)
    return CCSupply(**data)


def exchange_rate() -> Optional[CCExchangeRate]:
    """Return current exchange rate with spread and cache metadata.

    Returns None if oracle is unavailable and no cached value exists.
    """
    return cc_oracle_service.get_exchange_rate()


def stake(request: StakeRequest) -> StakePosition:
    """Stake CC into an idea.

    Raises:
        ValueError: If insufficient balance, idea not found, or CC operations paused.
    """
    # Check coherence score — operations pause if below 1.0
    rate_info = cc_oracle_service.get_exchange_rate()
    if rate_info is None:
        raise ValueError("Exchange rate unavailable")

    if not cc_treasury_service.can_mint(rate_info.cc_per_usd):
        raise ValueError("CC operations paused: coherence score below 1.0")

    # Check user balance
    balance = cc_treasury_service.get_user_balance(request.user_id)
    if balance < request.amount_cc:
        raise ValueError("Insufficient CC balance")

    # Check idea exists
    from app.services import graph_service
    idea = graph_service.get_node(request.idea_id)
    if idea is None:
        raise LookupError("Idea not found")

    # Create the stake position
    position = cc_staking_service.create_stake(
        user_id=request.user_id,
        idea_id=request.idea_id,
        amount_cc=request.amount_cc,
    )

    # Record in treasury ledger
    cc_treasury_service.record_stake(
        user_id=request.user_id,
        amount_cc=request.amount_cc,
        idea_id=request.idea_id,
        exchange_rate=rate_info.cc_per_usd,
    )

    return position


def unstake(request: UnstakeRequest) -> UnstakeResponse:
    """Unstake a position with cooldown.

    Raises:
        ValueError: If stake is already in cooldown.
        LookupError: If stake not found.
    """
    result = cc_staking_service.unstake(
        stake_id=request.stake_id,
        user_id=request.user_id,
    )
    if result is None:
        raise LookupError("Stake not found")

    # Record in treasury ledger
    rate_info = cc_oracle_service.get_exchange_rate()
    exchange_rate = rate_info.cc_per_usd if rate_info else 333.33
    cc_treasury_service.record_unstake(
        user_id=request.user_id,
        amount_cc=result.amount_cc,
        idea_id="",  # Unstake doesn't need idea_id in ledger
        exchange_rate=exchange_rate,
    )

    return result


def get_staking_positions(user_id: str) -> UserStakingSummary:
    """Return all staking positions for a user."""
    return cc_staking_service.get_user_positions(user_id)


def coherence_score() -> float:
    """Return the current coherence score.

    Returns 1.0 if no CC is outstanding (fully backed by definition).
    """
    rate_info = cc_oracle_service.get_exchange_rate()
    if rate_info is None:
        return 1.0
    data = cc_treasury_service.get_supply(rate_info.cc_per_usd)
    return data["coherence_score"]
