"""Models for discovery registry submission readiness."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RegistrySubmissionStatus(str, Enum):
    SUBMISSION_READY = "submission_ready"
    MISSING_ASSETS = "missing_assets"


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
    proof_url: str | None = None
    proof_path: str | None = None
    proof_note: str = Field(min_length=1)
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
