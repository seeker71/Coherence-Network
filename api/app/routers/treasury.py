"""Treasury endpoints — crypto deposit recording and CC conversion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import treasury_service

router = APIRouter(prefix="/treasury", tags=["treasury"])


class DepositRequest(BaseModel):
    contributor_id: str
    asset: str  # "eth" or "btc"
    amount: float
    tx_hash: str
    wallet_address: str | None = None


class StakeRequest(BaseModel):
    contributor_id: str
    cc_amount: float
    strategy: str = "highest_roi"  # "highest_roi", "spread", or specific idea_id


@router.get("", summary="Treasury info")
async def get_treasury_info() -> dict:
    """Return treasury wallet addresses, conversion rates, and total CC."""
    info = treasury_service.get_treasury_info()
    balance = treasury_service.get_treasury_balance()
    return {**info, **balance}


@router.post("/deposit", summary="Record a crypto deposit", status_code=201)
async def record_deposit(body: DepositRequest) -> dict:
    """Record a crypto deposit and convert to CC."""
    try:
        return treasury_service.record_deposit(
            contributor_id=body.contributor_id,
            asset=body.asset,
            amount=body.amount,
            tx_hash=body.tx_hash,
            wallet_address=body.wallet_address,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/deposits/{contributor_id}", summary="Deposit history for a contributor")
async def get_deposit_history(contributor_id: str) -> dict:
    """Get all deposits for a contributor."""
    deposits = treasury_service.get_deposit_history(contributor_id)
    return {"contributor_id": contributor_id, "deposits": deposits}


@router.post("/deposit/{deposit_id}/stake", summary="Stake a deposit's CC on ideas")
async def stake_deposit(deposit_id: str, body: StakeRequest) -> dict:
    """Stake CC from a deposit on ideas using the given strategy."""
    try:
        return treasury_service.auto_stake_deposit(
            contributor_id=body.contributor_id,
            cc_amount=body.cc_amount,
            strategy=body.strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
