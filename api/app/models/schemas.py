"""Shared Pydantic schemas for cross-cutting API and service contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedResponseCall(BaseModel):
    """Provider-agnostic Open Responses audit record for a task execution call."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: str = Field(..., min_length=1, max_length=1000)
    provider: str = Field(..., min_length=1, max_length=1000)
    model: str = Field(..., min_length=1, max_length=1000)
    request_schema: Literal["open_responses_v1"] = "open_responses_v1"
    output_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Task or provider output text (truncated for persistence).",
    )
