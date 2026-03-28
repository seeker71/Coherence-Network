from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContributorRecognitionSnapshot(BaseModel):
    contributor_id: UUID
    name: str
    total_contributions: int = Field(ge=0)
    total_cost: Decimal = Field(default=Decimal("0"))
    average_coherence_score: float = Field(ge=0.0, le=1.0)
    window_days: int = Field(default=30, ge=1)
    current_window_contributions: int = Field(ge=0)
    prior_window_contributions: int = Field(ge=0)
    delta_contributions: int

    model_config = ConfigDict(from_attributes=True)
