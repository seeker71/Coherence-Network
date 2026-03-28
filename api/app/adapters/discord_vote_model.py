"""SQLAlchemy ORM model for Discord reaction votes on idea open questions (spec-164).

Table: question_votes
Columns: id, idea_id, question_idx, discord_user_id, polarity, created_at
Unique constraint: (idea_id, question_idx, discord_user_id) — one vote per user per question.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.services.unified_db import Base


class QuestionVoteModel(Base):
    __tablename__ = "question_votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idea_id = Column(String, nullable=False, index=True)
    question_idx = Column(Integer, nullable=False)
    discord_user_id = Column(String, nullable=False)
    polarity = Column(String(10), nullable=False)  # positive|negative|excited
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "idea_id", "question_idx", "discord_user_id",
            name="uq_question_vote_per_user",
        ),
    )
