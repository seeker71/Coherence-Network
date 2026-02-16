"""Spec registry models for contributor-authored specs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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


class SpecRegistryCreate(BaseModel):
    spec_id: str = Field(min_length=1)
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
