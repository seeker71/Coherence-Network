"""Contributor growth model — tracks progression over time."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ContributionType = Literal[
    "code", "spec", "question", "review", "share", "research",
    "direction", "design", "testing", "documentation", "mentoring",
    "feedback", "compute", "infrastructure", "attention", "stake",
    "deposit", "promotion", "other",
]


LEVEL_THRESHOLDS: list[tuple[int, str, str]] = [
    (0,   "Seed",    "Just planted — every thought matters."),
    (3,   "Sprout",  "Growing — your questions shape the system."),
    (10,  "Root",    "Establishing depth — connecting ideas."),
    (25,  "Branch",  "Reaching out — others follow your lead."),
    (60,  "Canopy",  "Creating shade — your work shelters new ideas."),
    (150, "Forest",  "A living system — generative, self-sustaining."),
]


def compute_level(total_contributions: int) -> dict:
    """Compute contributor level from total contribution count."""
    level_name = "Seed"
    level_desc = LEVEL_THRESHOLDS[0][2]
    level_index = 0
    for i, (threshold, name, desc) in enumerate(LEVEL_THRESHOLDS):
        if total_contributions >= threshold:
            level_name = name
            level_desc = desc
            level_index = i

    next_threshold = None
    if level_index + 1 < len(LEVEL_THRESHOLDS):
        next_threshold = LEVEL_THRESHOLDS[level_index + 1][0]

    progress_to_next = 0.0
    if next_threshold is not None:
        current_threshold = LEVEL_THRESHOLDS[level_index][0]
        span = next_threshold - current_threshold
        if span > 0:
            progress_to_next = min(1.0, (total_contributions - current_threshold) / span)

    return {
        "name": level_name,
        "description": level_desc,
        "index": level_index,
        "progress_to_next": round(progress_to_next, 3),
        "next_threshold": next_threshold,
    }


class WeekBucket(BaseModel):
    """Single week of contributions."""
    week_start: str  # ISO date of Monday
    count: int = Field(ge=0)
    types: dict[str, int] = Field(default_factory=dict)
    total_cc: float = Field(ge=0.0, default=0.0)

    model_config = ConfigDict(from_attributes=True)


class Milestone(BaseModel):
    """A named milestone the contributor has reached."""
    name: str
    description: str
    reached_at: datetime | None = None
    contribution_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ContributorGrowthSnapshot(BaseModel):
    """Full growth picture for a contributor."""
    contributor_id: str
    display_name: str

    # Totals
    total_contributions: int = Field(ge=0)
    total_cc: float = Field(ge=0.0, default=0.0)
    contributions_by_type: dict[str, int] = Field(default_factory=dict)

    # Level
    level: dict = Field(default_factory=dict)

    # Streak
    current_streak_weeks: int = Field(ge=0, default=0)
    longest_streak_weeks: int = Field(ge=0, default=0)
    last_active_at: datetime | None = None

    # Timeline — last 26 weeks (6 months)
    weekly_timeline: list[WeekBucket] = Field(default_factory=list)

    # Growth indicators (vs prior period)
    contributions_last_30d: int = Field(ge=0, default=0)
    contributions_prev_30d: int = Field(ge=0, default=0)
    growth_pct: float | None = None  # None if no prior data

    # Milestones
    milestones: list[Milestone] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
