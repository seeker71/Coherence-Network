"""Import stack models — spec 022."""

from typing import Optional

from pydantic import BaseModel, Field


class ImportPackage(BaseModel):
    """Package in imported stack with coherence."""

    name: str = Field(description="Package name (e.g. react, @scope/pkg)")
    version: str = Field(description="Resolved version")
    coherence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Coherence score; null if unknown",
    )
    status: str = Field(description="known | unknown")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Child packages as name@version",
    )


class RiskSummary(BaseModel):
    """Aggregate risk counts. High coherence = healthy = low risk."""

    unknown: int = Field(default=0, ge=0, description="Not in GraphStore")
    high_risk: int = Field(default=0, ge=0, description="coherence < 0.4 or unknown")
    medium_risk: int = Field(default=0, ge=0, description="0.4 <= coherence < 0.7")
    low_risk: int = Field(default=0, ge=0, description="coherence >= 0.7 (healthy)")


class ImportStackResponse(BaseModel):
    """Response from POST /api/import/stack."""

    packages: list[ImportPackage] = Field(
        default_factory=list,
        description="Packages with coherence",
    )
    risk_summary: RiskSummary = Field(
        default_factory=RiskSummary,
        description="Aggregate risk counts",
    )
