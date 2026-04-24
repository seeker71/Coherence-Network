"""Settlement models — daily batch settlement per story-protocol-integration R8.

The settlement batch aggregates render events for a day and computes
CC distribution per asset per concept pool. Applies the evidence-
verification multiplier (up to 5× per R9). Output is a frozen
SettlementBatch record with per-asset entries.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ConceptPool(BaseModel):
    """Sum of CC directed to a single concept from a single asset's reads."""

    model_config = ConfigDict(frozen=True)

    concept_id: str
    cc_amount: Decimal


class SettlementEntry(BaseModel):
    """One asset's contribution to a settlement batch."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    read_count: int
    base_cc_pool: Decimal                # before multiplier
    evidence_multiplier: Decimal         # 1.0 if no verified evidence, up to 5.0
    effective_cc_pool: Decimal           # base_cc_pool * evidence_multiplier
    cc_to_asset_creator: Decimal
    cc_to_renderer_creators: Decimal
    cc_to_host_nodes: Decimal
    concept_pools: List[ConceptPool] = Field(default_factory=list)


class SettlementBatch(BaseModel):
    """The daily settlement record for spec R8."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    batch_date: date_type
    entries: List[SettlementEntry] = Field(default_factory=list)
    total_read_count: int = 0
    total_cc_distributed: Decimal = Decimal("0")
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
