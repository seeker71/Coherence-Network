"""Pydantic models for data hygiene / data-health API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TableHealthRow(BaseModel):
    name: str
    row_count: int = Field(ge=0)
    previous_snapshot_at: Optional[datetime] = None
    previous_row_count: Optional[int] = Field(default=None, ge=0)
    delta_24h: Optional[int] = None
    pct_change_24h: Optional[float] = None
    status: str = Field(description="ok | warn | breach")


class DataHygieneSnapshotItem(BaseModel):
    id: str
    captured_at: datetime
    source: str
    table_counts: dict[str, int]


class DataHealthResponse(BaseModel):
    generated_at: datetime
    database_kind: str
    health_score: float = Field(ge=0.0, le=1.0)
    last_snapshot_at: Optional[datetime] = None
    snapshot_stale_hours: Optional[float] = None
    tables: list[TableHealthRow]
    open_friction_ids: list[str]
    investigation_hints: list[str]
    runtime_events_facets: Optional[dict[str, Any]] = None


class SnapshotsListResponse(BaseModel):
    snapshots: list[DataHygieneSnapshotItem]
    limit: int
    total_returned: int


class SnapshotCreateResponse(BaseModel):
    id: str
    captured_at: datetime
    source: str
    table_counts: dict[str, int]
    alerts_raised: int
