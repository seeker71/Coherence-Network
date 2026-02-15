"""Unified inventory service for ideas, questions, specs, implementations, and usage."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services import idea_service, runtime_service, value_lineage_service


def _question_roi(value_to_whole: float, estimated_cost: float) -> float:
    if estimated_cost <= 0:
        return 0.0
    return round(float(value_to_whole) / float(estimated_cost), 4)


def _answer_roi(measured_delta: float | None, estimated_cost: float) -> float:
    if measured_delta is None or estimated_cost <= 0:
        return 0.0
    return round(float(measured_delta) / float(estimated_cost), 4)

FALLBACK_SPECS: list[dict[str, str]] = [
    {
        "spec_id": "048",
        "title": "value lineage and payout attribution",
        "path": "specs/048-value-lineage-and-payout-attribution.md",
    },
    {
        "spec_id": "049",
        "title": "system lineage inventory and runtime telemetry",
        "path": "specs/049-system-lineage-inventory-and-runtime-telemetry.md",
    },
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _discover_specs(limit: int = 300) -> list[dict]:
    specs_dir = _project_root() / "specs"
    if not specs_dir.exists():
        return FALLBACK_SPECS[: max(1, min(limit, 2000))]
    files = sorted(specs_dir.glob("*.md"))
    out: list[dict] = []
    for path in files[: max(1, min(limit, 2000))]:
        stem = path.stem
        spec_id = stem.split("-", 1)[0] if "-" in stem else stem
        title = stem.replace("-", " ")
        out.append(
            {
                "spec_id": spec_id,
                "title": title,
                "path": str(path),
            }
        )
    return out or FALLBACK_SPECS[: max(1, min(limit, 2000))]


def build_system_lineage_inventory(runtime_window_seconds: int = 3600) -> dict:
    ideas_response = idea_service.list_ideas()
    ideas = [item.model_dump(mode="json") for item in ideas_response.ideas]

    answered_questions: list[dict] = []
    unanswered_questions: list[dict] = []
    for idea in ideas_response.ideas:
        for q in idea.open_questions:
            row = {
                "idea_id": idea.id,
                "idea_name": idea.name,
                "question": q.question,
                "value_to_whole": q.value_to_whole,
                "estimated_cost": q.estimated_cost,
                "question_roi": _question_roi(q.value_to_whole, q.estimated_cost),
                "answer": q.answer,
                "measured_delta": q.measured_delta,
                "answer_roi": _answer_roi(q.measured_delta, q.estimated_cost),
            }
            if q.answer:
                answered_questions.append(row)
            else:
                unanswered_questions.append(row)

    unanswered_questions.sort(key=lambda x: -float(x.get("question_roi") or 0.0))
    answered_questions.sort(
        key=lambda x: (
            -float(x.get("answer_roi") or 0.0),
            -float(x.get("question_roi") or 0.0),
        )
    )

    links = value_lineage_service.list_links(limit=300)
    events = value_lineage_service.list_usage_events(limit=1000)
    link_rows = []
    for link in links:
        valuation = value_lineage_service.valuation(link.id)
        link_rows.append(
            {
                "lineage_id": link.id,
                "idea_id": link.idea_id,
                "spec_id": link.spec_id,
                "implementation_refs": link.implementation_refs,
                "estimated_cost": link.estimated_cost,
                "valuation": valuation.model_dump(mode="json") if valuation else None,
            }
        )

    runtime_summary = [x.model_dump(mode="json") for x in runtime_service.summarize_by_idea(runtime_window_seconds)]
    spec_items = _discover_specs()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ideas": {
            "summary": ideas_response.summary.model_dump(mode="json"),
            "items": ideas,
        },
        "questions": {
            "total": len(answered_questions) + len(unanswered_questions),
            "answered_count": len(answered_questions),
            "unanswered_count": len(unanswered_questions),
            "answered": answered_questions,
            "unanswered": unanswered_questions,
        },
        "specs": {
            "count": len(spec_items),
            "items": spec_items,
        },
        "implementation_usage": {
            "lineage_links_count": len(link_rows),
            "usage_events_count": len(events),
            "lineage_links": link_rows,
        },
        "runtime": {
            "window_seconds": runtime_window_seconds,
            "ideas": runtime_summary,
        },
    }


def next_highest_roi_task_from_answered_questions(create_task: bool = False) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    answered = inventory.get("questions", {}).get("answered", [])
    if not isinstance(answered, list) or not answered:
        return {"result": "no_answered_questions"}

    ranked = sorted(
        [row for row in answered if isinstance(row, dict)],
        key=lambda row: (
            -float(row.get("answer_roi") or 0.0),
            -float(row.get("question_roi") or 0.0),
        ),
    )
    top = ranked[0]
    idea_id = str(top.get("idea_id") or "unknown")
    question = str(top.get("question") or "").strip()
    answer = str(top.get("answer") or "").strip()
    question_roi = float(top.get("question_roi") or 0.0)
    answer_roi = float(top.get("answer_roi") or 0.0)

    direction = (
        f"Highest-ROI follow-up for idea '{idea_id}': {question} "
        f"Use this answer as working contract: {answer} "
        "Produce a measurable artifact with tests, link to value-lineage usage, and update inventory metrics."
    )
    report: dict = {
        "result": "task_suggested",
        "idea_id": idea_id,
        "question": question,
        "question_roi": question_roi,
        "answer_roi": answer_roi,
        "direction": direction,
    }
    if not create_task:
        return report

    from app.models.agent import AgentTaskCreate, TaskType
    from app.services import agent_service

    task = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.IMPL,
            context={
                "source": "inventory_high_roi",
                "idea_id": idea_id,
                "question_roi": question_roi,
                "answer_roi": answer_roi,
            },
        )
    )
    report["created_task"] = {
        "id": task["id"],
        "status": task["status"].value if hasattr(task["status"], "value") else str(task["status"]),
        "task_type": task["task_type"].value if hasattr(task["task_type"], "value") else str(task["task_type"]),
    }
    return report
