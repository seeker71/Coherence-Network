"""Models for discovery registry submission readiness."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RegistrySubmissionStatus(str, Enum):
    SUBMISSION_READY = "submission_ready"
    MISSING_ASSETS = "missing_assets"


class RegistryStatSource(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"


class RegistrySubmissionRecord(BaseModel):
    registry_id: str = Field(min_length=1)
    registry_name: str = Field(min_length=1)
    category: str = Field(pattern="^(mcp|skill)$")
    asset_name: str = Field(min_length=1)
    status: RegistrySubmissionStatus
    install_hint: str = Field(min_length=1)
    source_paths: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    missing_files: list[str] = Field(default_factory=list)
    notes: str = Field(min_length=1)


class RegistrySubmissionSummary(BaseModel):
    target_count: int = Field(ge=0)
    submission_ready_count: int = Field(ge=0)
    missing_asset_count: int = Field(ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    core_requirement_met: bool = False


class RegistrySubmissionInventory(BaseModel):
    summary: RegistrySubmissionSummary
    items: list[RegistrySubmissionRecord] = Field(default_factory=list)


class RegistryStats(BaseModel):
    registry_id: str
    registry_name: str
    install_count: Optional[int] = None
    download_count: Optional[int] = None
    star_count: Optional[int] = None
    fetched_at: Optional[datetime] = None
    source: RegistryStatSource
    error: Optional[str] = None


class RegistryStatsSummary(BaseModel):
    total_installs: int = 0
    total_downloads: int = 0
    registries_with_counts: int = 0
    registries_unavailable: int = 0
    last_updated: Optional[datetime] = None


class RegistryStatsList(BaseModel):
    summary: RegistryStatsSummary
    items: list[RegistryStats] = Field(default_factory=list)


class RegistryDashboardItem(BaseModel):
    registry_id: str
    registry_name: str
    category: str
    status: RegistrySubmissionStatus
    missing_files: list[str] = Field(default_factory=list)
    install_hint: str
    install_count: Optional[int] = None
    download_count: Optional[int] = None
    stat_source: RegistryStatSource = RegistryStatSource.UNAVAILABLE


class RegistryDashboard(BaseModel):
    submission_summary: RegistrySubmissionSummary
    stats_summary: RegistryStatsSummary
    items: list[RegistryDashboardItem] = Field(default_factory=list)
