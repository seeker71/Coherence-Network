"""CC Economics Router — endpoints for supply, exchange rate, and staking.

Spec: cc-economics-and-value-coherence
Endpoints:
  GET  /api/cc/supply          - Supply metrics with coherence score
  GET  /api/cc/exchange-rate   - Exchange rate with spread and cache metadata
  POST /api/cc/stake           - Stake CC into an idea
  POST /api/cc/unstake         - Unstake a position with cooldown
  GET  /api/cc/staking/{user_id} - All staking positions for a user
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.cc_economics import (
    CCExchangeRate,
    CCSupply,
    StakePosition,
    StakeRequest,
    UnstakeRequest,
    UnstakeResponse,
    UserStakingSummary,
)
from app.services import cc_economics_service

router = APIRouter(prefix="/cc", tags=["cc-economics"])


@router.get("/supply", response_model=CCSupply)
async def get_supply():
    """Return current CC supply metrics with coherence score."""
    result = cc_economics_service.supply()
    if result is None:
        raise HTTPException(status_code=503, detail="Treasury data temporarily unavailable")
    return result


@router.get("/exchange-rate", response_model=CCExchangeRate)
async def get_exchange_rate():
    """Return current exchange rate with spread and cache metadata."""
    result = cc_economics_service.exchange_rate()
    if result is None:
        raise HTTPException(status_code=503, detail="Exchange rate unavailable")
    return result


@router.post("/stake", response_model=StakePosition, status_code=201)
async def stake_cc(request: StakeRequest):
    """Stake CC into an idea."""
    try:
        return cc_economics_service.stake(request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/unstake", response_model=UnstakeResponse)
async def unstake_cc(request: UnstakeRequest):
    """Unstake a position with cooldown."""
    try:
        return cc_economics_service.unstake(request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/staking/{user_id}", response_model=UserStakingSummary)
async def get_staking_positions(user_id: str):
    """Return all staking positions for a user."""
    return cc_economics_service.get_staking_positions(user_id)
