"""Wallets router — connect, verify, and manage on-chain wallets."""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import wallet_service

log = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class WalletConnectRequest(BaseModel):
    contributor_id: str = Field(..., description="Contributor linking the wallet")
    address: str = Field(..., description="On-chain wallet address")
    chain: str = Field("ethereum", description="Chain: ethereum, base, polygon")
    label: Optional[str] = Field(None, description="Human label, e.g. 'Main wallet'")


class WalletVerifyRequest(BaseModel):
    contributor_id: str
    address: str
    message: str = Field(..., description="The message the contributor signed")
    signature: str = Field(..., description="EIP-191 hex signature")


# ---------------------------------------------------------------------------
# POST /api/wallets/connect
# ---------------------------------------------------------------------------

@router.post(
    "/wallets/connect",
    summary="Connect wallet",
    description="Link an on-chain wallet address to a contributor identity.",
    status_code=201,
)
async def connect_wallet(req: WalletConnectRequest) -> dict[str, Any]:
    try:
        return wallet_service.connect_wallet(
            contributor_id=req.contributor_id,
            address=req.address,
            chain=req.chain,
            label=req.label,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ---------------------------------------------------------------------------
# POST /api/wallets/verify
# ---------------------------------------------------------------------------

@router.post(
    "/wallets/verify",
    summary="Verify wallet ownership",
    description="Verify wallet ownership via EIP-191 signed message.",
)
async def verify_wallet(req: WalletVerifyRequest) -> dict[str, Any]:
    try:
        return wallet_service.verify_wallet(
            contributor_id=req.contributor_id,
            address=req.address,
            message=req.message,
            signature=req.signature,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))


# ---------------------------------------------------------------------------
# GET /api/wallets/lookup/{address}
# (must be declared before the parametric {contributor_id} route)
# ---------------------------------------------------------------------------

@router.get(
    "/wallets/lookup/{address}",
    summary="Find contributor by wallet",
    description="Reverse lookup — find which contributor owns a wallet address.",
)
async def lookup_by_address(address: str) -> dict[str, Any]:
    result = wallet_service.get_contributor_by_wallet(address)
    if not result:
        raise HTTPException(status_code=404, detail=f"No contributor found for address {address}")
    return result


# ---------------------------------------------------------------------------
# GET /api/wallets/{contributor_id}
# ---------------------------------------------------------------------------

@router.get(
    "/wallets/{contributor_id}",
    summary="List contributor wallets",
    description="All wallets linked to a contributor.",
)
async def list_wallets(contributor_id: str) -> list[dict[str, Any]]:
    return wallet_service.get_wallets(contributor_id)


# ---------------------------------------------------------------------------
# DELETE /api/wallets/{wallet_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/wallets/{wallet_id}",
    summary="Disconnect wallet",
    description="Unlink a wallet from its contributor.",
)
async def disconnect_wallet(wallet_id: str) -> dict[str, Any]:
    removed = wallet_service.disconnect_wallet(wallet_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Wallet {wallet_id} not found")
    return {"deleted": True, "wallet_id": wallet_id}
