"""Tests for idea_standing_questions (spec: standing-questions-roi-and-next-task-generation).

Two pure functions, extracted from idea_service.py in #163:
  _ensure_standing_questions(ideas)        — add standing question to non-internal ideas
  _prune_internal_standing_questions(ideas) — remove it from internal ideas

Covers the spec's named requirements:
  - Every non-internal idea holds the standing improvement/measurement question
  - The standing question text is the canonical STANDING_QUESTION_TEXT
  - Default value_to_whole and estimated_cost depend on manifestation_status
  - Internal ideas never accumulate a standing question (prune removes any)
  - Functions are idempotent (running twice doesn't double-add)
"""
from __future__ import annotations

from app.models.idea import Idea, IdeaQuestion, ManifestationStatus
from app.services import idea_standing_questions
from app.services.idea_standing_questions import (
    STANDING_QUESTION_TEXT,
    _ensure_standing_questions,
    _prune_internal_standing_questions,
)


def _idea(
    *,
    id: str = "i-1",
    potential_value: float = 100.0,
    estimated_cost: float = 10.0,
    status: ManifestationStatus = ManifestationStatus.NONE,
    open_questions: list[IdeaQuestion] | None = None,
    interfaces: list[str] | None = None,
) -> Idea:
    return Idea(
        id=id,
        name=id,
        description=id,
        potential_value=potential_value,
        estimated_cost=estimated_cost,
        manifestation_status=status,
        open_questions=open_questions or [],
        interfaces=interfaces or [],
    )


# ---------------------------------------------------------------------------
# _ensure_standing_questions
# ---------------------------------------------------------------------------


def test_ensure_adds_standing_question_to_non_internal_idea():
    """A fresh non-internal idea gets exactly one standing question appended."""
    idea = _idea(id="public-idea", status=ManifestationStatus.NONE)
    ideas, changed = _ensure_standing_questions([idea])

    assert changed is True
    assert len(ideas[0].open_questions) == 1
    assert ideas[0].open_questions[0].question == STANDING_QUESTION_TEXT


def test_ensure_is_idempotent():
    """Running twice doesn't double-add — the second call sees the existing question."""
    idea = _idea(id="public-idea")
    _, first_changed = _ensure_standing_questions([idea])
    _, second_changed = _ensure_standing_questions([idea])

    assert first_changed is True
    assert second_changed is False
    assert sum(1 for q in idea.open_questions if q.question == STANDING_QUESTION_TEXT) == 1


def test_ensure_skips_internal_ideas(monkeypatch):
    """Internal ideas (per is_internal_idea_id) never get a standing question."""
    monkeypatch.setattr(
        idea_standing_questions,
        "is_internal_idea_id",
        lambda idea_id, interfaces: idea_id == "internal-1",
    )
    public = _idea(id="public-1")
    internal = _idea(id="internal-1")

    _ensure_standing_questions([public, internal])

    assert any(q.question == STANDING_QUESTION_TEXT for q in public.open_questions)
    assert not any(q.question == STANDING_QUESTION_TEXT for q in internal.open_questions)


def test_ensure_uses_higher_defaults_when_manifestation_is_progressing():
    """Ideas with status != NONE get value_to_whole=24, estimated_cost=2.
    Ideas with status == NONE get value_to_whole=20, estimated_cost=3."""
    progressing = _idea(id="p-1", status=ManifestationStatus.PARTIAL)
    fresh = _idea(id="f-1", status=ManifestationStatus.NONE)

    _ensure_standing_questions([progressing, fresh])

    p_q = next(q for q in progressing.open_questions if q.question == STANDING_QUESTION_TEXT)
    f_q = next(q for q in fresh.open_questions if q.question == STANDING_QUESTION_TEXT)

    assert p_q.value_to_whole == 24.0
    assert p_q.estimated_cost == 2.0
    assert f_q.value_to_whole == 20.0
    assert f_q.estimated_cost == 3.0


def test_ensure_returns_no_change_when_all_ideas_already_have_standing():
    """changed=False when nothing was added."""
    idea = _idea(
        id="i-1",
        open_questions=[
            IdeaQuestion(
                question=STANDING_QUESTION_TEXT,
                value_to_whole=20.0,
                estimated_cost=3.0,
            )
        ],
    )
    _, changed = _ensure_standing_questions([idea])
    assert changed is False
    assert len(idea.open_questions) == 1  # nothing duplicated


def test_ensure_preserves_existing_unrelated_questions():
    """Adding the standing question doesn't disturb other open questions."""
    existing = IdeaQuestion(
        question="What about user X?",
        value_to_whole=5.0,
        estimated_cost=1.0,
        answer="not yet",
    )
    idea = _idea(id="i-1", open_questions=[existing])

    _ensure_standing_questions([idea])

    assert len(idea.open_questions) == 2
    assert existing in idea.open_questions
    assert any(q.question == STANDING_QUESTION_TEXT for q in idea.open_questions)


# ---------------------------------------------------------------------------
# _prune_internal_standing_questions
# ---------------------------------------------------------------------------


def test_prune_removes_standing_question_from_internal_idea(monkeypatch):
    """An internal idea that somehow has a standing question gets it removed."""
    monkeypatch.setattr(
        idea_standing_questions,
        "is_internal_idea_id",
        lambda idea_id, interfaces: idea_id == "internal-1",
    )
    internal = _idea(
        id="internal-1",
        open_questions=[
            IdeaQuestion(
                question=STANDING_QUESTION_TEXT,
                value_to_whole=20.0,
                estimated_cost=3.0,
            )
        ],
    )
    ideas, changed = _prune_internal_standing_questions([internal])

    assert changed is True
    assert ideas[0].open_questions == []


def test_prune_leaves_non_internal_ideas_alone(monkeypatch):
    """Non-internal ideas keep their standing questions through prune."""
    monkeypatch.setattr(
        idea_standing_questions,
        "is_internal_idea_id",
        lambda idea_id, interfaces: False,
    )
    public = _idea(
        id="public-1",
        open_questions=[
            IdeaQuestion(
                question=STANDING_QUESTION_TEXT,
                value_to_whole=20.0,
                estimated_cost=3.0,
            )
        ],
    )
    _, changed = _prune_internal_standing_questions([public])

    assert changed is False
    assert len(public.open_questions) == 1


def test_prune_keeps_non_standing_questions_on_internal_ideas(monkeypatch):
    """Prune only removes the standing question — other open questions persist."""
    monkeypatch.setattr(
        idea_standing_questions,
        "is_internal_idea_id",
        lambda idea_id, interfaces: True,
    )
    other_q = IdeaQuestion(
        question="Something else entirely",
        value_to_whole=5.0,
        estimated_cost=1.0,
    )
    internal = _idea(
        id="internal-1",
        open_questions=[
            other_q,
            IdeaQuestion(
                question=STANDING_QUESTION_TEXT,
                value_to_whole=20.0,
                estimated_cost=3.0,
            ),
        ],
    )
    _prune_internal_standing_questions([internal])

    assert other_q in internal.open_questions
    assert not any(q.question == STANDING_QUESTION_TEXT for q in internal.open_questions)


def test_prune_returns_no_change_when_nothing_to_remove(monkeypatch):
    """changed=False when no internal idea had the standing question."""
    monkeypatch.setattr(
        idea_standing_questions,
        "is_internal_idea_id",
        lambda idea_id, interfaces: True,
    )
    internal_no_standing = _idea(id="internal-1", open_questions=[])

    _, changed = _prune_internal_standing_questions([internal_no_standing])

    assert changed is False
