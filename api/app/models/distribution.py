from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class Payout(BaseModel):
    contributor_id: UUID
    amount: Decimal


class DistributionCreate(BaseModel):
    asset_id: UUID
    value_amount: Decimal


class Distribution(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    asset_id: UUID
    value_amount: Decimal
    payouts: list[Payout]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
