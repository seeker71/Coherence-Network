"""Coherence response models — spec 020."""

from pydantic import BaseModel, Field


class CoherenceResponse(BaseModel):
    """Coherence score and component breakdown per spec 018."""

    score: float = Field(ge=0.0, le=1.0, description="Overall coherence 0.0–1.0")
    components_with_data: int = Field(
        ge=0,
        le=8,
        default=2,
        description="Count of components with real data; rest are 0.5 stub (spec 020 data confidence)",
    )
    components: dict[str, float] = Field(
        description="Per-component scores (all 0.0–1.0)"
    )
