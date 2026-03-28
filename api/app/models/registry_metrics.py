"""Pydantic models for GET /api/registry/metrics — idea-4deb5bd7c800."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegistryMetricSource(BaseModel):
    source: str
    count: int
    fetched_at: str
    listing_url: str | None = None
    error: str | None = None


class RegistryMetricsResponse(BaseModel):
    total_installs: int = Field(
        ...,
        description="Sum of successful source counts (excludes failed sources with count=-1)",
    )
    sources: list[RegistryMetricSource]
    as_of: str
