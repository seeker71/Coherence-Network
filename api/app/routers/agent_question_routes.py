"""Agent question routes — sub-agent questions with SSE answers."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.agent_question_service import (
    answer_question,
    create_question,
    get_question,
    get_question_events,
    list_questions,
)

router = APIRouter()


class AgentQuestionCreate(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=200)
    question: str = Field(..., min_length=1, max_length=5000)
    task_id: str | None = Field(default=None, max_length=200)
    thread_id: str | None = Field(default=None, max_length=200)
    choices: list[str] = Field(default_factory=list, max_length=20)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentQuestionAnswer(BaseModel):
    answer: str = Field(..., min_length=1, max_length=5000)
    answered_by: str = Field(default="web", min_length=1, max_length=200)


@router.post("/questions", status_code=201, summary="Open a human question from a sub-agent")
async def create_question_route(body: AgentQuestionCreate) -> dict[str, Any]:
    """Open a question that the web console can answer."""
    return create_question(
        agent_id=body.agent_id,
        question=body.question,
        task_id=body.task_id,
        thread_id=body.thread_id,
        choices=body.choices,
        context=body.context,
    )


@router.get("/questions", summary="List sub-agent questions")
async def list_questions_route(
    status: Literal["open", "answered"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List recent questions for the web console."""
    questions = list_questions(status=status, limit=limit)
    return {"questions": questions, "total": len(questions)}


@router.get("/questions/stream", summary="Server-Sent Events stream for sub-agent questions")
async def question_events_sse(
    after: int = Query(0, ge=0, description="Last event sequence already seen"),
    max_events: int = Query(100, ge=1, le=500),
    timeout_seconds: float = Query(30.0, ge=0.1, le=300.0),
):
    """Stream opened and answered question events."""

    async def event_generator():
        last_seen = after
        sent = 0
        elapsed = 0.0
        poll_seconds = 1.0

        while sent < max_events and elapsed <= timeout_seconds:
            events = get_question_events(after=last_seen)
            for event in events:
                last_seen = int(event["sequence"])
                sent += 1
                yield f"data: {json.dumps(event)}\n\n"
                if sent >= max_events:
                    break

            if sent >= max_events:
                break

            await asyncio.sleep(poll_seconds)
            elapsed += poll_seconds

        yield f"data: {json.dumps({'event_type': 'end', 'sequence': last_seen})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/questions/{question_id}", summary="Get one sub-agent question")
async def get_question_route(question_id: str) -> dict[str, Any]:
    """Return one question by id."""
    question = get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.post("/questions/{question_id}/answer", summary="Answer a sub-agent question")
async def answer_question_route(question_id: str, body: AgentQuestionAnswer) -> dict[str, Any]:
    """Record a human answer and notify stream listeners."""
    question = answer_question(
        question_id=question_id,
        answer=body.answer,
        answered_by=body.answered_by,
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question
