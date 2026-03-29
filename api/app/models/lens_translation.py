"""Pydantic models for worldview lens registry and translations (spec-181)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.belief import BeliefAxis


class WorldviewLensCreate(BaseModel):
    lens_id: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=4000)
    archetype_axes: dict[str, float] = Field(default_factory=dict)

    @field_validator("archetype_axes")
    @classmethod
    def validate_axes(cls, v: dict[str, float]) -> dict[str, float]:
        valid = {a.value for a in BeliefAxis}
        for k, weight in v.items():
            if k not in valid:
                raise ValueError(f"invalid axis '{k}'")
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"axis '{k}' weight must be between 0.0 and 1.0")
        return v


class TranslationRegenerateBody(BaseModel):
    force_regenerate: bool = True
    contributor_id: str | None = None


def lens_public_dict(lens_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Shape for GET /api/lenses and GET /api/lenses/{id}."""
    from app.services import translate_service

    axes = meta.get("archetype_axes")
    if not axes:
        axes = translate_service.get_lens_belief_vector(lens_id)
    return {
        "lens_id": lens_id,
        "name": meta.get("display_name") or lens_id.replace("_", " ").title(),
        "description": meta.get("description", ""),
        "archetype_axes": axes,
        "is_builtin": meta.get("category") != "custom",
        "created_at": meta.get("created_at") or "2026-01-01T00:00:00Z",
    }
