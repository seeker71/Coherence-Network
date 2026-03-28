"""Pydantic models for Discord reaction voting on idea open questions (spec-164)."""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class QuestionVoteCreate(BaseModel):
    polarity: Literal["positive", "negative", "excited"]
    discord_user_id: str = Field(min_length=1)


class QuestionVoteCounts(BaseModel):
    positive: int = Field(default=0, ge=0)
    negative: int = Field(default=0, ge=0)
    excited: int = Field(default=0, ge=0)


class QuestionVoteResponse(BaseModel):
    question_index: int
    votes: QuestionVoteCounts
    your_vote: str
