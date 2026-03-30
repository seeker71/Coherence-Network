"""Proactive questions from recent commit evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services import idea_service

from app.services.inventory.constants import _question_roi
from app.services.inventory.evidence import _latest_commit_evidence_records


def _proactive_question_template(change_intent: str) -> tuple[str, float, float]:
    intent = change_intent.strip().lower()
    if intent == "runtime_fix":
        return (
            "What invariant, integration test, or monitor would have prevented \"{scope}\" before human escalation?",
            34.0,
            3.0,
        )
    if intent == "runtime_feature":
        return (
            "Before shipping \"{scope}\", what dependency/interlink question should the system ask to avoid follow-up fixes?",
            28.0,
            2.5,
        )
    if intent == "process_only":
        return (
            "What automation should detect and auto-create a task when process drift like \"{scope}\" appears again?",
            20.0,
            2.0,
        )
    if intent == "test_only":
        return (
            "Which production e2e flow remains unverified after \"{scope}\", and how do we gate it automatically?",
            24.0,
            2.0,
        )
    return (
        "What question should the system ask upfront to prevent repeating work similar to \"{scope}\"?",
        16.0,
        2.0,
    )


def _scope_bonus(scope: str) -> float:
    text = scope.lower()
    bonus = 0.0
    keywords = {
        "manual": 5.0,
        "missing": 4.0,
        "gap": 4.0,
        "duplicate": 4.0,
        "deploy": 3.0,
        "ci": 3.0,
        "e2e": 3.0,
        "runtime": 2.0,
        "validation": 2.0,
        "link": 2.0,
    }
    for key, value in keywords.items():
        if key in text:
            bonus += value
    return bonus


def _normalize_idea_ids_for_record(
    record: dict[str, Any],
    known_ids: set[str],
    actionable_ids: set[str],
) -> list[str]:
    raw = record.get("idea_ids")
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, str):
                continue
            idea_id = item.strip()
            if not idea_id:
                continue
            out.append(idea_id)
    fallback_id = "portfolio-governance" if "portfolio-governance" in actionable_ids else ""
    if not fallback_id and actionable_ids:
        fallback_id = sorted(actionable_ids)[0]
    if not out and fallback_id:
        out.append(fallback_id)

    normalized: list[str] = []
    for idea_id in out:
        candidate = idea_id if idea_id in known_ids else fallback_id
        if not candidate:
            continue
        if candidate not in actionable_ids:
            continue
        normalized.append(candidate)

    deduped: list[str] = []
    seen: set[str] = set()
    for idea_id in normalized:
        if idea_id in seen:
            continue
        seen.add(idea_id)
        deduped.append(idea_id)
    return deduped


def derive_proactive_questions_from_recent_changes(
    limit: int = 20,
    top: int = 20,
    include_internal_ideas: bool = False,
) -> dict[str, Any]:
    records = _latest_commit_evidence_records(limit=limit)
    top_n = max(1, min(top, 200))
    all_ideas = idea_service.list_ideas(include_internal=True).ideas
    known_idea_ids = {item.id for item in all_ideas}
    if include_internal_ideas:
        actionable_idea_ids = set(known_idea_ids)
    else:
        actionable_idea_ids = {
            item.id
            for item in all_ideas
            if not idea_service.is_internal_idea_id(item.id, item.interfaces)
        }
    intent_breakdown: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for record in records:
        contributors = record.get("contributors")
        if isinstance(contributors, list) and contributors:
            contributor_types = [
                str(item.get("contributor_type") or "").strip().lower()
                for item in contributors
                if isinstance(item, dict) and str(item.get("contributor_type") or "").strip()
            ]
            if contributor_types and all(value == "machine" for value in contributor_types):
                continue
        change_intent = str(record.get("change_intent") or "unknown").strip().lower() or "unknown"
        intent_breakdown[change_intent] = intent_breakdown.get(change_intent, 0) + 1
        scope = str(record.get("commit_scope") or "").strip() or "recent feature/fix"
        template, base_value, base_cost = _proactive_question_template(change_intent)
        value = round(base_value + _scope_bonus(scope), 4)
        cost = round(max(base_cost, 0.1), 4)
        question_text = template.format(scope=scope)
        source_file = str(record.get("_evidence_file") or "")
        source_date = str(record.get("date") or "")

        for idea_id in _normalize_idea_ids_for_record(record, known_idea_ids, actionable_idea_ids):
            dedupe_key = f"{idea_id.lower()}::{question_text.strip().lower()}"
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            candidates.append(
                {
                    "idea_id": idea_id,
                    "question": question_text,
                    "value_to_whole": value,
                    "estimated_cost": cost,
                    "question_roi": _question_roi(value, cost),
                    "source_commit_scope": scope,
                    "change_intent": change_intent,
                    "source_date": source_date,
                    "source_file": source_file,
                }
            )
    ranked = sorted(
        candidates,
        key=lambda row: (
            -float(row.get("question_roi") or 0.0),
            -float(row.get("value_to_whole") or 0.0),
            str(row.get("idea_id") or ""),
        ),
    )[:top_n]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "recent_records": len(records),
            "candidate_questions": len(candidates),
            "returned_questions": len(ranked),
            "intent_breakdown": intent_breakdown,
        },
        "recent_records": [
            {
                "date": str(record.get("date") or ""),
                "change_intent": str(record.get("change_intent") or "unknown"),
                "commit_scope": str(record.get("commit_scope") or ""),
                "idea_ids": record.get("idea_ids") if isinstance(record.get("idea_ids"), list) else [],
                "source_file": str(record.get("_evidence_file") or ""),
            }
            for record in records
        ],
        "questions": ranked,
    }


def sync_proactive_questions_from_recent_changes(
    limit: int = 20,
    max_add: int = 20,
    include_internal_ideas: bool = False,
) -> dict[str, Any]:
    report = derive_proactive_questions_from_recent_changes(
        limit=limit,
        top=max_add * 3,
        include_internal_ideas=include_internal_ideas,
    )
    questions = report.get("questions")
    ranked = [row for row in questions if isinstance(row, dict)] if isinstance(questions, list) else []
    max_allowed = max(1, min(max_add, 200))

    created: list[dict[str, Any]] = []
    skipped_existing_count = 0
    skipped_missing_idea_count = 0

    for row in ranked:
        if len(created) >= max_allowed:
            break
        idea_id = str(row.get("idea_id") or "").strip()
        question = str(row.get("question") or "").strip()
        if not idea_id or not question:
            skipped_missing_idea_count += 1
            continue

        updated, added = idea_service.add_question(
            idea_id=idea_id,
            question=question,
            value_to_whole=float(row.get("value_to_whole") or 0.0),
            estimated_cost=float(row.get("estimated_cost") or 0.0),
        )
        if updated is None:
            skipped_missing_idea_count += 1
            continue
        if not added:
            skipped_existing_count += 1
            continue
        created.append(
            {
                "idea_id": idea_id,
                "question": question,
                "question_roi": float(row.get("question_roi") or 0.0),
                "source_commit_scope": str(row.get("source_commit_scope") or ""),
                "change_intent": str(row.get("change_intent") or ""),
            }
        )

    return {
        "result": "proactive_questions_synced",
        "generated_at": report.get("generated_at"),
        "scanned_records": int((report.get("summary") or {}).get("recent_records") or 0),
        "candidate_count": int((report.get("summary") or {}).get("candidate_questions") or 0),
        "created_count": len(created),
        "skipped_existing_count": skipped_existing_count,
        "skipped_missing_idea_count": skipped_missing_idea_count,
        "intent_breakdown": (report.get("summary") or {}).get("intent_breakdown", {}),
        "created_questions": created,
    }
