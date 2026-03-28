"""Brief Pydantic models — request and response schemas for the Daily Engagement Skill.

Spec: task_3610e59a86ceadce (Spec 171: OpenClaw Daily Engagement Skill)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Enums / constants
# ---------------------------------------------------------------------------

VALID_SECTIONS = frozenset(
    [
        "news_resonance",
        "ideas_needing_skills",
        "tasks_for_providers",
        "nearby_contributors",
        "network_patterns",
    ]
)

VALID_ACTIONS = frozenset(["claimed", "opened", "dismissed", "shared"])

VALID_TRENDS = frozenset(["improving", "stable", "degrading"])


# ---------------------------------------------------------------------------
# Section item models
# ---------------------------------------------------------------------------


class NewsResonanceItem(BaseModel):
    news_id: str
    title: str
    resonance_score: float
    matching_idea_id: str
    matching_idea_title: str
    url: str
    published_at: str


class IdeaNeedingSkillsItem(BaseModel):
    idea_id: str
    title: str
    skill_match: List[str]
    phase: str
    open_tasks: int
    coherence_score: float


class TaskForProvidersItem(BaseModel):
    task_id: str
    idea_title: str
    task_type: str
    provider: str
    waiting_since: str
    priority: str


class NearbyContributorItem(BaseModel):
    contributor_id: str
    display_name: str
    shared_concepts: List[str]
    hop_distance: int
    recent_contribution: str


class NetworkPatternItem(BaseModel):
    pattern_type: str
    description: str
    idea_ids: List[str]
    first_seen: str
    signal_strength: float


# ---------------------------------------------------------------------------
# Top-level response models
# ---------------------------------------------------------------------------


class BriefCta(BaseModel):
    recommended_action: str
    target_id: str
    reason: str


class BriefSections(BaseModel):
    news_resonance: Optional[List[NewsResonanceItem]] = None
    ideas_needing_skills: Optional[List[IdeaNeedingSkillsItem]] = None
    tasks_for_providers: Optional[List[TaskForProvidersItem]] = None
    nearby_contributors: Optional[List[NearbyContributorItem]] = None
    network_patterns: Optional[List[NetworkPatternItem]] = None


class DailyBriefResponse(BaseModel):
    brief_id: str
    generated_at: str
    contributor_id: Optional[str] = None
    sections: Dict[str, Any]
    cta: Optional[BriefCta] = None


# ---------------------------------------------------------------------------
# Feedback models
# ---------------------------------------------------------------------------


class BriefFeedbackRequest(BaseModel):
    brief_id: str
    section: str
    item_id: str
    action: str

    @field_validator("section")
    @classmethod
    def validate_section(cls, v: str) -> str:
        if v not in VALID_SECTIONS:
            raise ValueError(
                f"Invalid section: {v!r}. Must be one of {sorted(VALID_SECTIONS)}"
            )
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in VALID_ACTIONS:
            raise ValueError(
                f"Invalid action: {v!r}. Must be one of {sorted(VALID_ACTIONS)}"
            )
        return v


class BriefFeedbackResponse(BaseModel):
    id: str
    brief_id: str
    section: str
    item_id: str
    action: str
    recorded_at: str


# ---------------------------------------------------------------------------
# Engagement metrics model
# ---------------------------------------------------------------------------


class EngagementMetricsResponse(BaseModel):
    window_days: int
    briefs_generated: int
    unique_contributors: int
    section_click_rates: Dict[str, float]
    cta_conversion_rate: float
    actions_attributable_to_brief: int
    trend: str
