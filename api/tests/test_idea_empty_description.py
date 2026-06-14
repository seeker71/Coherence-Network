"""Idea read model tolerates empty description (real data: ~15% of ideas have none).

The strict `description: min_length=1` made the ideas listing hard-fail on real
nodes that carry no description; the read model now accepts empty so the listing
serves them. Creation stays strict via IdeaCreate.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.idea import Idea, IdeaWithScore, IdeaCreate


def _base_kwargs(**over):
    kw = dict(
        id="idea-x",
        name="An idea",
        description="",
        potential_value=1.0,
        estimated_cost=0.1,
    )
    kw.update(over)
    return kw


def test_idea_accepts_empty_description():
    idea = Idea(**_base_kwargs())
    assert idea.description == ""


def test_idea_with_score_inherits_tolerance():
    # IdeaWithScore is the shape the native /api/ideas projection emits.
    iws = IdeaWithScore(**_base_kwargs(coherence_score=0.0, free_energy_score=0.0, value_gap=0.0))
    assert iws.description == ""


def test_idea_still_requires_name_and_id():
    with pytest.raises(ValidationError):
        Idea(**_base_kwargs(name=""))
    with pytest.raises(ValidationError):
        Idea(**_base_kwargs(id=""))


def test_creation_stays_strict():
    # IdeaCreate is a separate write model — new ideas must still carry a description.
    with pytest.raises(ValidationError):
        IdeaCreate(name="An idea", description="")
