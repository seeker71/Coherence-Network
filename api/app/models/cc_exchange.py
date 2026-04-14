"""Models for CC ↔ External Exchange bridge.

Supports pluggable exchange adapters (New Earth Exchange, CES, timebanks).
Settlement starts manual (human confirms both sides) and upgrades to
API-based when external systems publish their protocols.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class ExchangeQuote(BaseModel):
    """A conversion quote between CC and an external credit system."""

    quote_id: str = Field(min_length=1)
    from_currency: str = Field(description="Source currency code (e.g. 'CC')")
    to_currency: str = Field(description="Target currency code (e.g. 'NEW_EARTH', 'CES')")
    rate: float = Field(gt=0, description="Units of to_currency per 1 unit of from_currency")
    amount_from: float = Field(gt=0)
    amount_to: float = Field(gt=0)
    adapter: str = Field(description="Exchange adapter that provided this quote")
    valid_until: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SwapRequest(BaseModel):
    """Request to swap CC ↔ external credits."""

    user_id: str = Field(min_length=1)
    from_currency: str = Field(min_length=1)
    to_currency: str = Field(min_length=1)
    amount: float = Field(gt=0, description="Amount in from_currency to swap")
    recipient_address: str = Field(
        default="",
        description="External account/ID to receive credits (empty for manual settlement)",
    )
    note: str = Field(default="", description="Optional note for the swap")


class SwapResult(BaseModel):
    """Result of initiating a swap."""

    tx_id: str
    status: str = Field(description="pending_confirmation, confirmed, settled, failed, expired")
    from_currency: str
    to_currency: str
    amount_from: float
    amount_to: float
    rate_used: float
    adapter: str
    initiated_at: datetime
    settlement_method: str = Field(
        default="manual",
        description="manual (human confirms) or api (automatic via exchange API)",
    )


class SwapConfirmation(BaseModel):
    """Confirmation of a completed swap."""

    tx_id: str
    status: str = Field(description="confirmed or failed")
    confirmed_at: datetime
    external_tx_ref: str = Field(default="", description="Reference from external system")
    confirmed_by: str = Field(default="", description="Who confirmed (user_id or 'api')")


class AdapterInfo(BaseModel):
    """Info about an available exchange adapter."""

    name: str
    display_name: str
    description: str
    currencies: list[str]
    settlement_method: str = Field(description="manual or api")
    healthy: bool
    base_rate: Optional[float] = Field(
        default=None,
        description="Current base rate (CC per 1 unit of this currency), if available",
    )
