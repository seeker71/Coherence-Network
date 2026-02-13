from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ContributorType(str, Enum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class ContributorBase(BaseModel):
    type: ContributorType
    name: str
    email: str
    wallet_address: Optional[str] = None
    hourly_rate: Optional[Decimal] = None


class ContributorCreate(ContributorBase):
    pass


class Contributor(ContributorBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
