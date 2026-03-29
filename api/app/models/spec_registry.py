"""Spec registry models for contributor-authored specs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class SpecRegistryEntry(BaseModel):
    spec_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0, default=0.0)
    actual_value: float = Field(ge=0.0, default=0.0)
    estimated_cost: float = Field(ge=0.0, default=0.0)
    actual_cost: float = Field(ge=0.0, default=0.0)
    value_gap: float = Field(ge=0.0, default=0.0)
    cost_gap: float = Field(default=0.0)
    estimated_roi: float = Field(ge=0.0, default=0.0)
    actual_roi: float = Field(ge=0.0, default=0.0)
    idea_id: Optional[str] = None
    process_summary: Optional[str] = None
    pseudocode_summary: Optional[str] = None
    implementation_summary: Optional[str] = None
    created_by_contributor_id: Optional[str] = None
    updated_by_contributor_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    content_path: Optional[str] = None
    content_hash: Optional[str] = None


class SpecRegistryCreate(BaseModel):
    spec_id: Optional[str] = Field(
        default=None,
        description="UUID4 identifier. Auto-generated when omitted. "
                    "Legacy numeric/slug IDs accepted for backward-compat seeding.",
    )
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0, default=0.0)
    estimated_cost: float = Field(ge=0.0, default=0.0)
    actual_value: float = Field(ge=0.0, default=0.0)
    actual_cost: float = Field(ge=0.0, default=0.0)
    idea_id: Optional[str] = None
    process_summary: Optional[str] = None
    pseudocode_summary: Optional[str] = None
    implementation_summary: Optional[str] = None
    created_by_contributor_id: Optional[str] = None
    content_path: Optional[str] = None
    content_hash: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _auto_uuid_spec_id(cls, values: dict) -> dict:
        """Auto-generate a UUID4 when 'spec_id' is absent or empty."""
        if not values.get("spec_id"):
            values["spec_id"] = str(uuid4())
        return values


class SpecRegistryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    summary: Optional[str] = Field(default=None, min_length=1)
    potential_value: Optional[float] = Field(default=None, ge=0.0)
    estimated_cost: Optional[float] = Field(default=None, ge=0.0)
    actual_value: Optional[float] = Field(default=None, ge=0.0)
    actual_cost: Optional[float] = Field(default=None, ge=0.0)
    idea_id: Optional[str] = None
    process_summary: Optional[str] = None
    pseudocode_summary: Optional[str] = None
    implementation_summary: Optional[str] = None
    updated_by_contributor_id: Optional[str] = None
    content_path: Optional[str] = None
    content_hash: Optional[str] = None
