"""Agent question channel — in-memory queue and SSE event log."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

QuestionStatus = Literal["open", "answered"]

_MAX_QUESTIONS = 500
_MAX_EVENTS = 1000
_LOCK = threading.Lock()
_QUESTIONS: dict[str, dict[str, Any]] = {}
_QUESTION_ORDER: list[str] = []
_EVENTS: list[dict[str, Any]] = []
_NEXT_SEQUENCE = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        **question,
        "choices": list(question.get("choices") or []),
        "context": dict(question.get("context") or {}),
    }


def _emit_locked(event_type: str, question: dict[str, Any]) -> dict[str, Any]:
    global _NEXT_SEQUENCE
    event = {
        "id": f"qevt_{uuid.uuid4().hex[:12]}",
        "sequence": _NEXT_SEQUENCE,
        "event_type": event_type,
        "question_id": question["id"],
        "question": _copy_question(question),
        "timestamp": _now(),
    }
    _NEXT_SEQUENCE += 1
    _EVENTS.append(event)
    if len(_EVENTS) > _MAX_EVENTS:
        _EVENTS[:] = _EVENTS[-_MAX_EVENTS:]
    return dict(event)


def create_question(
    *,
    agent_id: str,
    question: str,
    task_id: str | None = None,
    thread_id: str | None = None,
    choices: list[str] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Open a question from a sub-agent for a human answer."""
    now = _now()
    item: dict[str, Any] = {
        "id": f"question_{uuid.uuid4().hex[:12]}",
        "agent_id": agent_id,
        "question": question,
        "task_id": task_id,
        "thread_id": thread_id,
        "choices": list(choices or []),
        "context": dict(context or {}),
        "status": "open",
        "answer": None,
        "answered_by": None,
        "created_at": now,
        "updated_at": now,
        "answered_at": None,
    }
    with _LOCK:
        _QUESTIONS[item["id"]] = item
        _QUESTION_ORDER.append(item["id"])
        if len(_QUESTION_ORDER) > _MAX_QUESTIONS:
            stale_ids = _QUESTION_ORDER[:-_MAX_QUESTIONS]
            _QUESTION_ORDER[:] = _QUESTION_ORDER[-_MAX_QUESTIONS:]
            for stale_id in stale_ids:
                _QUESTIONS.pop(stale_id, None)
        _emit_locked("question_opened", item)
        return _copy_question(item)


def get_question(question_id: str) -> dict[str, Any] | None:
    """Return one question by id."""
    with _LOCK:
        item = _QUESTIONS.get(question_id)
        return _copy_question(item) if item else None


def list_questions(
    *,
    status: QuestionStatus | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent questions, most recent first."""
    with _LOCK:
        question_ids = list(reversed(_QUESTION_ORDER))
        items = [_QUESTIONS[item_id] for item_id in question_ids if item_id in _QUESTIONS]
        if status:
            items = [item for item in items if item.get("status") == status]
        return [_copy_question(item) for item in items[:limit]]


def answer_question(
    *,
    question_id: str,
    answer: str,
    answered_by: str = "web",
) -> dict[str, Any] | None:
    """Answer an open question and emit the corresponding event."""
    with _LOCK:
        item = _QUESTIONS.get(question_id)
        if not item:
            return None
        now = _now()
        item["answer"] = answer
        item["answered_by"] = answered_by
        item["status"] = "answered"
        item["answered_at"] = now
        item["updated_at"] = now
        _emit_locked("question_answered", item)
        return _copy_question(item)


def get_question_events(after: int = 0) -> list[dict[str, Any]]:
    """Return event log entries with sequence greater than ``after``."""
    with _LOCK:
        return [dict(event) for event in _EVENTS if int(event["sequence"]) > after]


def reset_agent_questions() -> None:
    """Clear in-memory state for tests."""
    global _NEXT_SEQUENCE
    with _LOCK:
        _QUESTIONS.clear()
        _QUESTION_ORDER.clear()
        _EVENTS.clear()
        _NEXT_SEQUENCE = 1
