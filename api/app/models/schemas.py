"""Shared schema models for cross-cutting API contracts (Open Responses interoperability)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedResponseCall(BaseModel):
    """Audit record for a normalized Open Responses–compatible execution (spec 109)."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(..., min_length=1, max_length=1000)
    provider: str = Field(..., min_length=1, max_length=1000)
    model: str = Field(..., min_length=1, max_length=1000)
    request_schema: Literal["open_responses_v1"] = "open_responses_v1"
    output_text: str = Field(..., min_length=1, max_length=1000)
