"""Pydantic response models for the public pulse API.

These models are the contract between the monitor and the /pulse web page.
They are designed to be directly serialised to JSON and consumed by a
TypeScript server component without further shaping.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Breath status vocabulary — NOT "up/down/degraded".
BreathStatus = Literal["breathing", "strained", "silent", "unknown"]
# Silence severity — "strained" is intermittent failures, "silent" is prolonged.
Severity = Literal["strained", "silent"]


class OrganNow(BaseModel):
    """Current state of one organ."""

    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    description: str
    status: BreathStatus
    latency_ms: int | None = None
    last_sample_at: str | None = Field(
        default=None, description="ISO8601 UTC of the most recent sample"
    )
    detail: str | None = Field(
        default=None, description="Short human note when not breathing"
    )


class OngoingSilence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organ: str
    started_at: str
    severity: Severity
    duration_seconds: int


class PulseNow(BaseModel):
    """GET /pulse/now response."""

    model_config = ConfigDict(extra="forbid")

    overall: BreathStatus
    checked_at: str = Field(description="ISO8601 UTC of this snapshot")
    witness_started_at: str = Field(
        description="ISO8601 UTC when the pulse monitor itself came up"
    )
    organs: list[OrganNow]
    ongoing_silences: list[OngoingSilence]


class DailyBar(BaseModel):
    """One day in an organ's 90-day timeline."""

    model_config = ConfigDict(extra="forbid")

    date: str = Field(description="YYYY-MM-DD, UTC")
    status: BreathStatus
    samples: int
    failures: int


class OrganHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    description: str
    uptime_pct: float = Field(
        description="Steady-breath percentage across the requested window"
    )
    daily: list[DailyBar]


class PulseHistory(BaseModel):
    """GET /pulse/history response."""

    model_config = ConfigDict(extra="forbid")

    days: int
    generated_at: str
    organs: list[OrganHistory]


class Silence(BaseModel):
    """A past quiet moment."""

    model_config = ConfigDict(extra="forbid")

    id: int
    organ: str
    organ_label: str
    started_at: str
    ended_at: str | None
    duration_seconds: int
    severity: Severity
    note: str | None = None


class PulseSilences(BaseModel):
    """GET /pulse/silences response."""

    model_config = ConfigDict(extra="forbid")

    days: int
    generated_at: str
    silences: list[Silence]


class WitnessHealth(BaseModel):
    """GET /pulse/health response — the witness's own liveness."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    version: str
    started_at: str
    uptime_seconds: int
    samples_total: int
