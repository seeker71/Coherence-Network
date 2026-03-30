"""Models for Discord bot integration and idea question voting (spec 164)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoteCreate(BaseModel):
    """Request body for casting a vote on an idea question."""
    voter_id: str = Field(min_length=1, description="Contributor or Discord user ID")
    direction: str = Field(
        default="up",
        pattern="^(up|down)$",
        description="Vote direction: 'up' or 'down'",
    )


class VoteResult(BaseModel):
    """Response after casting a vote."""
    idea_id: str
    question_index: int
    question: str
    votes_up: int = Field(ge=0)
    votes_down: int = Field(ge=0)
    voter_id: str


class IdeaEmbed(BaseModel):
    """Simplified idea representation for Discord embeds."""
    id: str
    name: str
    description: str
    stage: str
    manifestation_status: str
    free_energy_score: float = 0.0
    roi_cc: float = 0.0
    value_gap: float = 0.0
    open_questions_count: int = 0
    colour: int = 0x5865F2  # Discord blurple default


class PortfolioSummary(BaseModel):
    """Summary data for /cc-status command."""
    total_ideas: int = 0
    validated_ideas: int = 0
    top_roi_idea: str | None = None
    top_roi_value: float = 0.0
    total_value_gap: float = 0.0
