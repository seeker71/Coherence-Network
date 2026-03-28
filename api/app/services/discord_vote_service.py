"""Service for Discord reaction votes on idea open questions (spec-164).

All DB access goes through the unified_db session.
The question_votes table is created on first call via ensure_schema().
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.adapters.discord_vote_model import QuestionVoteModel
from app.models.discord_vote import QuestionVoteCounts, QuestionVoteResponse
from app.services import unified_db


def ensure_schema() -> None:
    """Create question_votes table if it doesn't exist."""
    from app.adapters.discord_vote_model import QuestionVoteModel  # noqa: F401 — import registers model
    from app.services.unified_db import Base
    eng = unified_db.engine()
    Base.metadata.create_all(bind=eng, checkfirst=True)


def vote(
    idea_id: str,
    question_idx: int,
    discord_user_id: str,
    polarity: str,
) -> tuple[QuestionVoteResponse, bool]:
    """Record a vote.

    Returns:
        (QuestionVoteResponse, created) where created=False means duplicate (409).
    """
    ensure_schema()

    with unified_db.session() as db:
        # Try to insert
        new_vote = QuestionVoteModel(
            idea_id=idea_id,
            question_idx=question_idx,
            discord_user_id=discord_user_id,
            polarity=polarity,
        )
        db.add(new_vote)
        try:
            db.flush()
            created = True
        except IntegrityError:
            db.rollback()
            created = False

        # Fetch aggregate counts
        rows = (
            db.query(QuestionVoteModel.polarity, func.count().label("n"))
            .filter_by(idea_id=idea_id, question_idx=question_idx)
            .group_by(QuestionVoteModel.polarity)
            .all()
        )

    counts = QuestionVoteCounts()
    for row in rows:
        if row.polarity == "positive":
            counts.positive = row.n
        elif row.polarity == "negative":
            counts.negative = row.n
        elif row.polarity == "excited":
            counts.excited = row.n

    return (
        QuestionVoteResponse(
            question_index=question_idx,
            votes=counts,
            your_vote=polarity,
        ),
        created,
    )


def get_counts(idea_id: str, question_idx: int) -> QuestionVoteCounts:
    """Return aggregate vote counts for a question (used by GET /api/ideas/:id)."""
    ensure_schema()
    with unified_db.session() as db:
        rows = (
            db.query(QuestionVoteModel.polarity, func.count().label("n"))
            .filter_by(idea_id=idea_id, question_idx=question_idx)
            .group_by(QuestionVoteModel.polarity)
            .all()
        )
    counts = QuestionVoteCounts()
    for row in rows:
        setattr(counts, row.polarity, row.n)
    return counts
