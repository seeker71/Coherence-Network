"""Shared Pydantic schemas for Open Responses interoperability layer (spec 109).

NormalizedResponseCall captures the provider-agnostic execution record so that
operator audits can verify the actual provider, model, and schema used for each
task execution.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NormalizedResponseCall(BaseModel):
    """Provider-agnostic execution record conforming to open_responses_v1 schema.

    Fields
    ------
    task_id         Identifier of the task that triggered the call.
    provider        Normalized provider name (e.g. 'claude', 'codex', 'gemini').
    model           Fully-qualified model identifier used for execution.
    request_schema  Always 'open_responses_v1' — marks the call as normalized.
    output_text     Raw text output returned by the provider.
    """

    task_id: str = Field(..., min_length=1, max_length=1000)
    provider: str = Field(..., min_length=1, max_length=1000)
    model: str = Field(..., min_length=1, max_length=1000)
    request_schema: Literal["open_responses_v1"] = "open_responses_v1"
    output_text: str = Field(default="", max_length=1000)
