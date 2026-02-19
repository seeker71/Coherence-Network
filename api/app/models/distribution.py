from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class PayoutSettlementStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SKIPPED_MISSING_WALLET = "skipped_missing_wallet"
    FAILED = "failed"


class DistributionSettlementStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    PARTIALLY_SETTLED = "partially_settled"
    FAILED = "failed"


class Payout(BaseModel):
    contributor_id: UUID
    amount: Decimal
    wallet_address: str | None = None
    settlement_status: PayoutSettlementStatus = PayoutSettlementStatus.PENDING
    tx_hash: str | None = None
    settled_at: datetime | None = None
    settlement_error: str | None = None


class DistributionCreate(BaseModel):
    asset_id: UUID
    value_amount: Decimal


class Distribution(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    asset_id: UUID
    value_amount: Decimal
    payouts: list[Payout]
    settlement_status: DistributionSettlementStatus = DistributionSettlementStatus.PENDING
    settled_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
