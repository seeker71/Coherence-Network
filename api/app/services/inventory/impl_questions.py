"""Implementation request question detection and task sync."""

from __future__ import annotations

import hashlib

from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service

from app.services.inventory.constants import (
    IMPLEMENTATION_REQUEST_PATTERN,
    _sanitize_oauth_only_language,
)
from app.services.inventory.lineage import build_system_lineage_inventory


def _is_implementation_request_question(question: str, answer: str | None = None) -> bool:
    text = f"{question or ''} {answer or ''}".strip()
    if not text:
        return False
    return IMPLEMENTATION_REQUEST_PATTERN.search(text) is not None


def _question_fingerprint(idea_id: str, question: str) -> str:
    payload = f"{idea_id.strip().lower()}::{question.strip().lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _active_impl_question_fingerprints() -> set[str]:
    tasks, _ = agent_service.list_tasks(limit=100000, offset=0)
    fingerprints: set[str] = set()
    for task in tasks:
        status = task.get("status")
        status_value = status.value if hasattr(status, "value") else str(status)
        if status_value not in {"pending", "running", "needs_decision"}:
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if context.get("source") != "implementation_request_question":
            continue
        fingerprint = context.get("question_fingerprint")
        if isinstance(fingerprint, str) and fingerprint.strip():
            fingerprints.add(fingerprint)
    return fingerprints


def sync_implementation_request_question_tasks() -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    questions = []
    questions.extend(inventory.get("questions", {}).get("unanswered", []))
    questions.extend(inventory.get("questions", {}).get("answered", []))

    ranked = sorted(
        [row for row in questions if isinstance(row, dict)],
        key=lambda row: -float(row.get("question_roi") or 0.0),
    )

    existing_fingerprints = _active_impl_question_fingerprints()
    created_tasks: list[dict] = []
    skipped_existing_count = 0
    skipped_non_impl_count = 0

    for row in ranked:
        idea_id = str(row.get("idea_id") or "").strip()
        question = str(row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip() or None
        if not idea_id or not question:
            skipped_non_impl_count += 1
            continue
        if not _is_implementation_request_question(question, answer):
            skipped_non_impl_count += 1
            continue

        fingerprint = _question_fingerprint(idea_id, question)
        if fingerprint in existing_fingerprints:
            skipped_existing_count += 1
            continue

        question_for_direction = _sanitize_oauth_only_language(question)
        direction = (
            f"Implementation request for idea '{idea_id}': {question_for_direction} "
            "Produce a measurable artifact (spec->test->impl), link evidence, and update ROI signals."
        )
        if answer:
            answer_for_direction = _sanitize_oauth_only_language(answer)
            direction += f" Use this answer as implementation contract: {answer_for_direction}"

        task = agent_service.create_task(
            AgentTaskCreate(
                direction=direction,
                task_type=TaskType.IMPL,
                context={
                    "source": "implementation_request_question",
                    "idea_id": idea_id,
                    "question": question,
                    "question_fingerprint": fingerprint,
                    "task_fingerprint": fingerprint,
                    "question_roi": float(row.get("question_roi") or 0.0),
                    "answer_roi": float(row.get("answer_roi") or 0.0),
                },
            )
        )
        existing_fingerprints.add(fingerprint)
        created_tasks.append(
            {
                "task_id": task["id"],
                "idea_id": idea_id,
                "question": question,
                "question_roi": float(row.get("question_roi") or 0.0),
            }
        )

    return {
        "result": "implementation_tasks_synced",
        "created_count": len(created_tasks),
        "skipped_existing_count": skipped_existing_count,
        "skipped_non_impl_count": skipped_non_impl_count,
        "created_tasks": created_tasks,
    }
