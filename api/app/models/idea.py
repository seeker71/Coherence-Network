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
    question_id: Optional[str] = None
    parent_idea_id: Optional[str] = None
    parent_question_id: Optional[str] = None
    evolved_from_answer_of: Optional[str] = None
    asked_by: Optional[str] = None
    answered_by: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    answer: Optional[str] = None
    measured_delta: Optional[float] = None


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


class IdeaPortfolioResponse(BaseModel):
    ideas: list[IdeaWithScore]
    summary: IdeaSummary


class IdeaUpdate(BaseModel):
    actual_value: Optional[float] = Field(default=None, ge=0.0)
    actual_cost: Optional[float] = Field(default=None, ge=0.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    manifestation_status: Optional[ManifestationStatus] = None


class IdeaQuestionAnswerUpdate(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    measured_delta: Optional[float] = None
    answered_by: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    evolved_from_answer_of: Optional[str] = None


class RoiMeasurementCreate(BaseModel):
    subject_type: str = Field(pattern="^(idea|question)$")
    subject_id: str = Field(min_length=1)
    idea_id: Optional[str] = None
    estimated_roi: Optional[float] = None
    actual_roi: Optional[float] = None
    actual_value: Optional[float] = Field(default=None, ge=0.0)
    actual_cost: Optional[float] = Field(default=None, ge=0.0)
    measured_delta: Optional[float] = None
    estimated_cost: Optional[float] = Field(default=None, ge=0.0)
    source: str = Field(default="api")
    measured_by: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class RoiEstimatorWeightsUpdate(BaseModel):
    idea_multiplier: Optional[float] = Field(default=None, gt=0.0, le=10.0)
    question_multiplier: Optional[float] = Field(default=None, gt=0.0, le=10.0)
    answer_multiplier: Optional[float] = Field(default=None, gt=0.0, le=10.0)
    updated_by: Optional[str] = None
