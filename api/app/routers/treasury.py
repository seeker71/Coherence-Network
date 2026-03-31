# Implements: spec-122 (crypto treasury bridge)
"""Treasury endpoints — crypto deposit, CC minting, withdrawal, and reserve enforcement."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status

from app.models.treasury import (
    DepositRequest,
    WithdrawalRequest,
)
from app.services import treasury_service

router = APIRouter(prefix="/treasury", tags=["treasury"])


@router.post(
    "/deposit",
    summary="Initiate a crypto deposit",
    status_code=status.HTTP_201_CREATED,
)
async def create_deposit(body: DepositRequest) -> dict:
    """Initiate a BTC or ETH deposit to receive CC.

    Returns a deposit address, expected CC amount, locked exchange rate,
    and confirmation requirements.
    """
    try:
        deposit = treasury_service.initiate_deposit(body)
        return {
            "deposit_id": deposit.deposit_id,
            "user_id": deposit.user_id,
            "currency": deposit.currency.value,
            "deposit_address": deposit.deposit_address,
            "expected_amount_crypto": deposit.expected_amount_crypto,
            "locked_exchange_rate": {
                "cc_per_crypto": deposit.locked_exchange_rate.cc_per_crypto,
                "crypto_usd": deposit.locked_exchange_rate.crypto_usd,
                "cc_per_usd": deposit.locked_exchange_rate.cc_per_usd,
                "spread_pct": deposit.locked_exchange_rate.spread_pct,
                "locked_at": deposit.locked_exchange_rate.locked_at.isoformat(),
            },
            "expected_cc_amount": deposit.expected_cc_amount,
            "confirmations_required": deposit.confirmations_required,
            "status": deposit.status.value,
            "expires_at": deposit.expires_at.isoformat(),
            "created_at": deposit.created_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/deposit/{deposit_id}",
    summary="Check deposit confirmation status",
)
async def get_deposit_status(deposit_id: str) -> dict:
    """Check deposit status and confirmation count."""
    deposit = treasury_service.get_deposit(deposit_id)
    if deposit is None:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return {
        "deposit_id": deposit.deposit_id,
        "user_id": deposit.user_id,
        "currency": deposit.currency.value,
        "expected_amount_crypto": deposit.expected_amount_crypto,
        "received_amount_crypto": deposit.received_amount_crypto,
        "tx_hash": deposit.tx_hash,
        "confirmations": deposit.confirmations,
        "confirmations_required": deposit.confirmations_required,
        "status": deposit.status.value,
        "cc_minted": deposit.cc_minted,
        "confirmed_at": deposit.confirmed_at.isoformat() if deposit.confirmed_at else None,
    }


@router.get(
    "/balance",
    summary="Get user CC balance with crypto equivalents",
)
async def get_balance(user_id: str = Query(..., min_length=1)) -> dict:
    """Get a user's CC balance and BTC/ETH equivalents at current rates."""
    return treasury_service.get_user_balance(user_id)


@router.post(
    "/withdraw",
    summary="Request CC withdrawal to crypto",
    status_code=status.HTTP_201_CREATED,
)
async def create_withdrawal(body: WithdrawalRequest) -> dict:
    """Request CC withdrawal to BTC or ETH.

    Creates a governance ChangeRequest for pool payouts.
    Deposit capital returns use time-locked escrow without governance.
    """
    try:
        withdrawal = treasury_service.request_withdrawal(body)
        return {
            "withdrawal_id": withdrawal.withdrawal_id,
            "user_id": withdrawal.user_id,
            "cc_amount": withdrawal.cc_amount,
            "fee_cc": withdrawal.fee_cc,
            "net_cc": withdrawal.net_cc,
            "target_currency": withdrawal.target_currency.value,
            "estimated_crypto_amount": withdrawal.estimated_crypto_amount,
            "destination_address": withdrawal.destination_address,
            "governance_request_id": withdrawal.governance_request_id,
            "status": withdrawal.status.value,
            "required_approvals": 2,
            "created_at": withdrawal.created_at.isoformat(),
        }
    except ValueError as exc:
        msg = str(exc)
        if "balance" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=422, detail=msg)


@router.get(
    "/supply",
    summary="Get CC supply and reserve status",
)
async def get_supply() -> dict:
    """Public endpoint returning total CC supply, burned amount, and reserve ratio."""
    supply = treasury_service.get_treasury_supply()
    return {
        "total_cc_minted": supply.total_cc_minted,
        "total_cc_burned": supply.total_cc_burned,
        "cc_in_circulation": supply.cc_in_circulation,
        "total_btc_held": supply.total_btc_held,
        "total_eth_held": supply.total_eth_held,
        "reserve_ratio": supply.reserve_ratio,
        "reserve_status": supply.reserve_status.value,
        "withdrawals_paused": supply.withdrawals_paused,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/summary",
    summary="Get public treasury dashboard data",
)
async def get_summary() -> dict:
    """Public endpoint returning treasury summary for dashboard display."""
    return treasury_service.get_treasury_summary()
