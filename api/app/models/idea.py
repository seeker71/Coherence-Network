"""Idea portfolio models for federated prioritization."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ManifestationStatus(str, Enum):
    NONE = "none"
    PARTIAL = "partial"
    VALIDATED = "validated"


class IdeaQuestion(BaseModel):
    question: str = Field(min_length=1)
    value_to_whole: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    answer: Optional[str] = None
    measured_delta: Optional[float] = None


class IdeaQuestionCreate(BaseModel):
    question: str = Field(min_length=1)
    value_to_whole: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)


class Idea(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0)
    actual_value: float = Field(default=0.0, ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    actual_cost: float = Field(default=0.0, ge=0.0)
    resistance_risk: float = Field(default=1.0, ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    manifestation_status: ManifestationStatus = ManifestationStatus.NONE
    interfaces: list[str] = Field(default_factory=list)
    open_questions: list[IdeaQuestion] = Field(default_factory=list)


class IdeaWithScore(Idea):
    free_energy_score: float = Field(ge=0.0)
    value_gap: float = Field(ge=0.0)


class IdeaSummary(BaseModel):
    total_ideas: int = Field(ge=0)
    unvalidated_ideas: int = Field(ge=0)
    validated_ideas: int = Field(ge=0)
    total_potential_value: float = Field(ge=0.0)
    total_actual_value: float = Field(ge=0.0)
    total_value_gap: float = Field(ge=0.0)


class PaginationInfo(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    returned: int = Field(ge=0)
    has_more: bool = False


class IdeaPortfolioResponse(BaseModel):
    ideas: list[IdeaWithScore]
    summary: IdeaSummary
    pagination: PaginationInfo | None = None


class IdeaUpdate(BaseModel):
    actual_value: Optional[float] = Field(default=None, ge=0.0)
    actual_cost: Optional[float] = Field(default=None, ge=0.0)
    potential_value: Optional[float] = Field(default=None, ge=0.0)
    estimated_cost: Optional[float] = Field(default=None, ge=0.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    manifestation_status: Optional[ManifestationStatus] = None


class IdeaCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    potential_value: float = Field(ge=0.0)
    estimated_cost: float = Field(ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    interfaces: list[str] = Field(default_factory=list)
    open_questions: list[IdeaQuestionCreate] = Field(default_factory=list)


class IdeaQuestionAnswerUpdate(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    measured_delta: Optional[float] = None


class IdeaStorageInfo(BaseModel):
    backend: str = Field(min_length=1)
    database_url: str = Field(min_length=1)
    idea_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    bootstrap_source: str = Field(min_length=1)
