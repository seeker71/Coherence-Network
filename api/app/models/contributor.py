from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

try:
    import email_validator  # type: ignore # noqa: F401
except ImportError:  # pragma: no cover - env-specific fallback
    EmailField = str
else:
    from pydantic import EmailStr as EmailField


class ContributorType(str, Enum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class ContributorBase(BaseModel):
    type: ContributorType
    name: str
    email: EmailField
    wallet_address: Optional[str] = None
    hourly_rate: Optional[Decimal] = None


class ContributorCreate(ContributorBase):
    pass


class Contributor(ContributorBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
