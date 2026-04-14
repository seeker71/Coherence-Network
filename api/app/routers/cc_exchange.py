"""CC Exchange Router — bridge to external exchanges (New Earth, CES).

Endpoints:
  GET  /api/cc/exchange/adapters            - List available exchange adapters
  POST /api/cc/exchange/quote               - Get conversion quote
  POST /api/cc/exchange/swap                - Initiate a swap
  GET  /api/cc/exchange/swap/{tx_id}        - Check swap status
  POST /api/cc/exchange/swap/{tx_id}/confirm - Confirm manual settlement
  GET  /api/cc/exchange/history/{user_id}   - User's swap history
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.cc_exchange import (
    AdapterInfo,
    ExchangeQuote,
    SwapConfirmation,
    SwapRequest,
    SwapResult,
)
from app.services import cc_exchange_adapter

router = APIRouter(prefix="/cc/exchange", tags=["cc-exchange"])


@router.get("/adapters", response_model=list[AdapterInfo], summary="List available exchange adapters")
async def list_adapters():
    """List all registered exchange adapters with their health status and rates."""
    return cc_exchange_adapter.list_adapters()


@router.post("/quote", response_model=ExchangeQuote, summary="Get a conversion quote")
async def get_quote(from_currency: str = "CC", to_currency: str = "NEW_EARTH", amount: float = 100.0):
    """Get a conversion quote between CC and an external currency.

    Supported currencies: CC, NEW_EARTH, CES.
    Quote is valid for 15 minutes.
    """
    try:
        return cc_exchange_adapter.get_quote(from_currency, to_currency, amount)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/swap", response_model=SwapResult, status_code=201, summary="Initiate a swap")
async def initiate_swap(request: SwapRequest):
    """Initiate a swap between CC and an external credit system.

    For manual settlement adapters (New Earth, CES): creates a pending
    swap that requires human confirmation via the confirm endpoint.
    CC is held (burned) immediately; external side settles on confirmation.
    """
    try:
        return cc_exchange_adapter.initiate_swap(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/swap/{tx_id}", summary="Check swap status")
async def get_swap(tx_id: str):
    """Get the current status of a swap transaction."""
    swap = cc_exchange_adapter.get_swap(tx_id)
    if not swap:
        raise HTTPException(status_code=404, detail=f"Swap {tx_id} not found")
    return swap


@router.post("/swap/{tx_id}/confirm", response_model=SwapConfirmation, summary="Confirm manual settlement")
async def confirm_swap(tx_id: str, external_tx_ref: str = "", confirmed_by: str = ""):
    """Confirm that a manual settlement swap has completed on both sides.

    For swap-in (external → CC): mints CC to user on confirmation.
    For swap-out (CC → external): CC was already burned on initiation.
    """
    try:
        return cc_exchange_adapter.confirm_swap(tx_id, external_tx_ref, confirmed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{user_id}", summary="User's swap history")
async def get_history(user_id: str):
    """Get all swap transactions for a user."""
    swaps = cc_exchange_adapter.get_user_swaps(user_id)
    return {"user_id": user_id, "swaps": swaps, "total": len(swaps)}
