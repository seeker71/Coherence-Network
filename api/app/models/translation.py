"""Pydantic models for concept framing translation (cross-lens / worldview views)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TranslationLens(str, Enum):
    """Supported worldview lenses for conceptual framing (not natural-language translation)."""

    scientific = "scientific"
    economic = "economic"
    spiritual = "spiritual"
    artistic = "artistic"
    philosophical = "philosophical"


class OntologyConceptRef(BaseModel):
    """A scored ontology node used to bridge an idea into a target lens."""

    id: str
    name: str
    score: float = Field(ge=0.0, le=1.0, description="Relevance 0–1 within this lens.")
    axes: list[str] = Field(default_factory=list)


class AnalogousIdeaRef(BaseModel):
    """Another idea that resonates structurally (cross-view synthesis), not keyword spam."""

    idea_id: str
    name: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    cross_domain: bool = False


class IdeaTranslationResponse(BaseModel):
    """GET /api/ideas/{id}/translate — reframe through a worldview lens using ontology + resonance."""

    idea_id: str
    view: str
    translation_kind: Literal["concept_framing"] = "concept_framing"
    summary: str
    lens_description: str
    bridging_concepts: list[OntologyConceptRef]
    analogous_ideas: list[AnalogousIdeaRef]


class ConceptTranslationResponse(BaseModel):
    """GET /api/concepts/{id}/translate — move between lenses for a single ontology concept."""

    concept_id: str
    from_lens: str
    to_lens: str
    translation_kind: Literal["concept_framing"] = "concept_framing"
    summary: str
    source_axes: list[str] = Field(default_factory=list)
    target_bridging_concepts: list[OntologyConceptRef]
