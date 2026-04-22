from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from typing import Optional

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
    AGENT = "AGENT"


class ContributorBase(BaseModel):
    type: ContributorType
    name: str
    email: EmailField
    wallet_address: Optional[str] = None
    hourly_rate: Optional[Decimal] = None
    daily_cc_budget: Optional[Decimal] = Field(None, description="Max CC spend per 24h")
    monthly_cc_budget: Optional[Decimal] = Field(None, description="Max CC spend per month")
    locale: Optional[str] = Field(
        default=None,
        description="Preferred language (ISO 639-1: en, de, es, id, ...). "
                    "Drives which view of a concept the contributor sees, which language "
                    "their new contributions default to, and the UI chrome language. "
                    "None means no preference set — fall back to cookie/browser/default.",
    )


class ContributorCreate(ContributorBase):
    pass


class Contributor(ContributorBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Claim signals. A contributor created directly (graduate, register)
    # is claimed by the person who made them. A contributor minted as
    # a placeholder (e.g. by the inspired-by resolver so a door stays
    # open for an artist or teacher named here) is unclaimed until the
    # real person walks through it.
    claimed: bool = Field(
        default=True,
        description=(
            "True when the node represents a person or group who themselves "
            "walked in. False on placeholder nodes held open for someone else "
            "to claim."
        ),
    )
    canonical_url: Optional[str] = Field(
        default=None,
        description=(
            "Primary outward-facing URL for this identity. Filled on "
            "placeholder nodes created by the inspired-by resolver; "
            "optional for self-registered contributors."
        ),
    )

    model_config = ConfigDict(from_attributes=True)
