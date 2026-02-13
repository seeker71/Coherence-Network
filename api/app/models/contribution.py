from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ContributionBase(BaseModel):
    contributor_id: UUID
    asset_id: UUID
    cost_amount: Decimal
    metadata: dict = Field(default_factory=dict)


class ContributionCreate(ContributionBase):
    pass


class Contribution(ContributionBase):
    id: UUID = Field(default_factory=uuid4)
    coherence_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
