"""Pydantic models for the daily engagement bundle (morning brief + opportunities)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NewsMatchBrief(BaseModel):
    """Single news item matched to an idea."""

    score: float = Field(ge=0.0, le=1.0)
    title: str
    url: str
    source: str = ""
    idea_id: str = ""
    idea_name: str = ""
    reason: str = ""
    matched_keywords: list[str] = Field(default_factory=list)


class IdeaOpportunity(BaseModel):
    """Idea with open questions that may need contributor skills."""

    idea_id: str
    name: str
    skill_overlap_score: float = Field(ge=0.0, le=1.0, description="Overlap with your staked-idea keywords")
    open_questions: list[str] = Field(default_factory=list)


class TaskOpportunity(BaseModel):
    """Agent task waiting for a provider."""

    task_id: str
    direction: str
    task_type: str
    status: str


class ContributorNearby(BaseModel):
    """Another contributor in the graph (for collaboration discovery)."""

    node_id: str
    name: str
    description: str = ""
    contributor_type: str = ""


class NetworkPattern(BaseModel):
    """Lightweight signal of what the network is surfacing."""

    kind: str
    label: str
    detail: str = ""
    score: Optional[float] = None


class MorningBriefSection(BaseModel):
    """News resonance slice of the bundle."""

    articles_scanned: int = 0
    ideas_considered: int = 0
    staked_idea_count: int = 0
    top_matches: list[NewsMatchBrief] = Field(default_factory=list)


class DailyEngagementResponse(BaseModel):
    """Full personalized daily engagement payload."""

    type: str = Field(default="daily-engagement")
    generated_at: datetime
    contributor_id: str
    morning_brief: MorningBriefSection
    ideas_needing_skills: list[IdeaOpportunity] = Field(default_factory=list)
    tasks_for_providers: list[TaskOpportunity] = Field(default_factory=list)
    contributors_nearby: list[ContributorNearby] = Field(default_factory=list)
    network_patterns: list[NetworkPattern] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
