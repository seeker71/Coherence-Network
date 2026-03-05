from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """RFC 7807 Problem Details error response.

    See: https://datatracker.ietf.org/doc/html/rfc7807
    """

    type: str = Field(
        default="about:blank",
        description="URI reference identifying the problem type.",
        examples=["about:blank", "https://coherence.network/errors/not-found"],
    )
    title: str = Field(
        description="Short human-readable summary of the problem.",
        examples=["Not Found", "Validation Error"],
    )
    status: int = Field(
        description="HTTP status code for this error.",
        examples=[400, 404, 422, 500],
    )
    detail: str = Field(
        description="Human-readable explanation specific to this occurrence.",
        examples=["Contributor not found"],
    )
    instance: Optional[str] = Field(
        default=None,
        description="URI reference identifying this specific occurrence.",
        examples=["/api/contributors/550e8400-e29b-41d4-a716-446655440000"],
    )
    code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code for programmatic handling.",
        examples=["CONTRIBUTOR_NOT_FOUND", "VALIDATION_ERROR"],
    )
