"""Standing-question maintenance for ideas.

Extracted from idea_service.py (#163). The standing question — *"How can
we improve this idea, show whether it is working yet, and make that
proof clearer over time?"* — is the question every non-internal idea
holds open for itself.

Public surface (re-exported from idea_service):
  STANDING_QUESTION_TEXT, _ensure_standing_questions,
  _prune_internal_standing_questions
"""

from __future__ import annotations

from app.models.idea import Idea, IdeaQuestion, ManifestationStatus
from app.services.idea_internal_filter import is_internal_idea_id


STANDING_QUESTION_TEXT = (
    "How can we improve this idea, show whether it is working yet, "
    "and make that proof clearer over time?"
)


def _ensure_standing_questions(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    for idea in ideas:
        if is_internal_idea_id(idea.id, idea.interfaces):
            continue
        has_standing = any(q.question == STANDING_QUESTION_TEXT for q in idea.open_questions)
        if has_standing:
            continue
        default_value = 24.0 if idea.manifestation_status != ManifestationStatus.NONE else 20.0
        default_cost = 2.0 if idea.manifestation_status != ManifestationStatus.NONE else 3.0
        idea.open_questions.append(
            IdeaQuestion(
                question=STANDING_QUESTION_TEXT,
                value_to_whole=default_value,
                estimated_cost=default_cost,
            )
        )
        changed = True
    return ideas, changed


def _prune_internal_standing_questions(ideas: list[Idea]) -> tuple[list[Idea], bool]:
    changed = False
    for idea in ideas:
        if not is_internal_idea_id(idea.id, idea.interfaces):
            continue
        before = len(idea.open_questions)
        if before == 0:
            continue
        idea.open_questions = [q for q in idea.open_questions if q.question != STANDING_QUESTION_TEXT]
        if len(idea.open_questions) != before:
            changed = True
    return ideas, changed
