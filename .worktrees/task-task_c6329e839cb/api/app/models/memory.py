"""Models for the agent-memory-system spec.

See specs/agent-memory-system.md for the full contract. These models
define the write/manage/read loop shapes used by the memory service
and router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class MomentKind(str, Enum):
    """The aliveness marker required on every memory moment (spec R1).

    Raw activity logs without an explicit kind are rejected — memory
    writes happen at moments of aliveness, not on a cron.
    """

    DECISION = "decision"
    SURPRISE = "surprise"
    COMPLETION = "completion"
    ABANDONMENT = "abandonment"
    WEIGHT = "weight"


class FeltQuality(str, Enum):
    """Felt-sense quality of a moment (optional)."""

    EXPANSION = "expansion"
    CONTRACTION = "contraction"
    STILLNESS = "stillness"
    CHARGE = "charge"


class MemoryMomentCreate(BaseModel):
    """Payload for POST /api/memory/moment."""

    about: str = Field(description="Node this moment attaches to (person, project, self).")
    kind: MomentKind
    why: str = Field(min_length=1, description="Reason the moment matters. Non-empty.")
    felt_quality: Optional[FeltQuality] = None
    related_to: List[str] = Field(default_factory=list)


class MemoryMoment(MemoryMomentCreate):
    """Server-side moment record."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsolidatedPrinciple(BaseModel):
    """A distilled principle earned from many moments."""

    id: UUID = Field(default_factory=uuid4)
    about: str
    text: str
    source_moment_ids: List[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryRecall(BaseModel):
    """Composed retrieval shape — never raw moment rows.

    Four fields the caller receives instead of a list of matches:
      - synthesis: natural-language paragraph distilled from graph + semantic + recency
      - felt_sense: coarse orientation word (warm, wary, tired, eager, uncertain, unknown)
      - open_threads: promises unfulfilled, topics mid-flight
      - earned_conclusions: one-sentence principles this relationship has earned
    """

    about: str
    synthesis: str
    felt_sense: str = "unknown"
    open_threads: List[str] = Field(default_factory=list)
    earned_conclusions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ConsolidationResult(BaseModel):
    """Outcome of a single consolidation pass on one node."""

    about: str
    window: str
    input_moment_count: int
    input_token_estimate: int
    output_principle_count: int
    output_token_estimate: int
    moments_archived: int
    log_entry: Optional[str] = None
