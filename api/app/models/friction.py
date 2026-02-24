"""Friction event and report models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FrictionEvent(BaseModel):
    id: str = Field(min_length=1)
    timestamp: datetime
    task_id: Optional[str] = None
    endpoint: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    provider: Optional[str] = None
    billing_provider: Optional[str] = None
    tool: Optional[str] = None
    model: Optional[str] = None
    return_code: Optional[int] = None
    stage: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    unblock_condition: str = Field(min_length=1)
    energy_loss_estimate: float = Field(ge=0.0)
    cost_of_delay: float = Field(ge=0.0)
    status: str = Field(min_length=1)
    resolved_at: Optional[datetime] = None
    time_open_hours: Optional[float] = Field(default=None, ge=0.0)
    resolution_action: Optional[str] = None
    notes: Optional[str] = None


class FrictionReportRow(BaseModel):
    key: str
    count: int = Field(ge=0)
    energy_loss: float = Field(ge=0.0)
    cost_of_delay: Optional[float] = Field(default=None, ge=0.0)


class FrictionReport(BaseModel):
    window_days: int = Field(ge=1)
    from_ts: datetime = Field(alias="from")
    to_ts: datetime = Field(alias="to")
    total_events: int = Field(ge=0)
    open_events: int = Field(ge=0)
    total_energy_loss: float = Field(ge=0.0)
    total_cost_of_delay: float = Field(ge=0.0)
    top_block_types: list[FrictionReportRow] = Field(default_factory=list)
    top_stages: list[FrictionReportRow] = Field(default_factory=list)
    source_file: str
    ignored_lines: int = Field(ge=0)


class FrictionEntryPoint(BaseModel):
    key: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    severity: str = Field(min_length=1, max_length=40)
    status: str = Field(min_length=1, max_length=40)
    event_count: int = Field(ge=0)
    energy_loss: float = Field(ge=0.0)
    cost_of_delay: float = Field(ge=0.0)
    wasted_minutes: float = Field(ge=0.0)
    recommended_action: str = Field(min_length=1)
    evidence_links: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class FrictionEntryPointReport(BaseModel):
    generated_at: datetime
    window_days: int = Field(ge=1)
    total_entry_points: int = Field(ge=0)
    open_entry_points: int = Field(ge=0)
    entry_points: list[FrictionEntryPoint] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
