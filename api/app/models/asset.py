from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class AssetType(str, Enum):
    CODE = "CODE"
    MODEL = "MODEL"
    CONTENT = "CONTENT"
    DATA = "DATA"


class AssetBase(BaseModel):
    name: str
    asset_type: str
    type: AssetType = AssetType.CODE  # Default to CODE
    description: str = ""  # Optional description


class AssetCreate(AssetBase):
    pass


class Asset(AssetBase):
    id: UUID = Field(default_factory=uuid4)
    total_cost: Decimal = Decimal("0.00")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
