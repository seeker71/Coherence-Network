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


def _classify_perspective(contributor: str | None) -> str:
    if not contributor:
        return "unknown"
    token = contributor.strip().lower()
    if not token:
        return "unknown"
    machine_markers = (
        "codex",
        "claude",
        "gpt",
        "bot",
        "agent",
        "automation",
        "ci",
        "github-actions",
    )
    if any(marker in token for marker in machine_markers):
        return "machine"
    return "human"


def _normalized_question_key(question: str) -> str:
    return " ".join((question or "").strip().lower().split())


def _detect_duplicate_questions(question_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    for row in question_rows:
        if not isinstance(row, dict):
            continue
        idea_id = str(row.get("idea_id") or "").strip()
        question = str(row.get("question") or "").strip()
        if not idea_id or not question:
            continue
        key = (idea_id, _normalized_question_key(question))
        item = grouped.get(
            key,
            {
                "idea_id": idea_id,
                "question": question,
                "occurrences": 0,
                "question_rois": [],
            },
        )
        item["occurrences"] += 1
        roi = row.get("question_roi")
        if isinstance(roi, (int, float)):
            item["question_rois"].append(float(roi))
        grouped[key] = item

    duplicates: list[dict] = []
    for value in grouped.values():
        count = int(value.get("occurrences") or 0)
        if count < 2:
            continue
        rois = value.get("question_rois") or []
        duplicates.append(
            {
                "idea_id": value.get("idea_id"),
                "question": value.get("question"),
                "occurrences": count,
                "max_question_roi": round(max(rois), 4) if rois else 0.0,
            }
        )
    duplicates.sort(
        key=lambda row: (
            -int(row.get("occurrences") or 0),
            -float(row.get("max_question_roi") or 0.0),
        )
    )
    return duplicates


def _build_evidence_contract(
    *,
    ideas: list[dict],
    unanswered_questions: list[dict],
    duplicate_questions: list[dict],
    link_rows: list[dict],
    contributor_rows: list[dict],
    next_question: dict | None,
    operating_console_status: dict,
) -> dict:
    standing_phrase = "how can we improve this idea"
    total_ideas = len(ideas)
    ideas_with_standing = 0
    for idea in ideas:
        open_questions = idea.get("open_questions") if isinstance(idea.get("open_questions"), list) else []
        has_standing = any(
            isinstance(q, dict)
            and standing_phrase in str(q.get("question") or "").strip().lower()
            for q in open_questions
        )
        if has_standing:
            ideas_with_standing += 1
    standing_ratio = round((ideas_with_standing / total_ideas), 4) if total_ideas > 0 else 0.0
    has_next_work = bool(next_question) if unanswered_questions else True
    dup_count = len(duplicate_questions)
    link_count = len(link_rows)
    has_attribution = (len(contributor_rows) > 0) if link_count > 0 else True

    checks = [
        {
            "subsystem_id": "idea_governance",
            "standing_question": "What evidence supports this claim now, what would falsify it, and who acts if it drifts?",
            "claim": "Every idea has a standing improvement/measurement question.",
            "evidence": [{"metric": "standing_question_coverage_ratio", "value": standing_ratio, "source": "ideas.items[].open_questions"}],
            "falsifier": "Coverage ratio drops below 1.0",
            "threshold": {"operator": ">=", "value": 1.0},
            "owner_role": "spec-review",
            "auto_action": "create heal task to restore standing questions",
            "review_cadence": "per monitor cycle",
            "status": "ok" if standing_ratio >= 1.0 else "needs_attention",
        },
        {
            "subsystem_id": "roi_queue",
            "standing_question": "Is next ROI work selected from evidence-backed queue and visible to operators?",
            "claim": "If there are unanswered questions, next ROI work item must exist.",
            "evidence": [
                {"metric": "unanswered_count", "value": len(unanswered_questions), "source": "questions.unanswered_count"},
                {"metric": "next_roi_item_present", "value": has_next_work, "source": "next_roi_work.item"},
            ],
            "falsifier": "Unanswered questions exist but next ROI item is missing.",
            "threshold": {"operator": "==", "value": True},
            "owner_role": "orchestration",
            "auto_action": "create implementation task for next ROI item",
            "review_cadence": "per monitor cycle",
            "status": "ok" if has_next_work else "needs_attention",
        },
        {
            "subsystem_id": "inventory_quality",
            "standing_question": "Is inventory internally consistent with no duplicate question groups per idea?",
            "claim": "Duplicate normalized questions per idea must be zero.",
            "evidence": [{"metric": "duplicate_question_groups", "value": dup_count, "source": "quality_issues.duplicate_idea_questions.count"}],
            "falsifier": "Duplicate question group count is greater than zero.",
            "threshold": {"operator": "==", "value": 0},
            "owner_role": "data-quality",
            "auto_action": "create heal task to deduplicate and migrate",
            "review_cadence": "per monitor cycle",
            "status": "ok" if dup_count == 0 else "needs_attention",
        },
        {
            "subsystem_id": "contribution_attribution",
            "standing_question": "Can we prove who contributed idea/spec/implementation for valued work?",
            "claim": "Attribution evidence exists when lineage links exist.",
            "evidence": [
                {"metric": "lineage_links_count", "value": link_count, "source": "implementation_usage.lineage_links_count"},
                {"metric": "attribution_rows", "value": len(contributor_rows), "source": "contributors.attributions"},
            ],
            "falsifier": "Lineage links exist but attribution rows are missing.",
            "threshold": {"operator": "==", "value": True},
            "owner_role": "contributors-review",
            "auto_action": "create review task to fill contributor attribution",
            "review_cadence": "per monitor cycle",
            "status": "ok" if has_attribution else "needs_attention",
        },
        {
            "subsystem_id": "operating_console",
            "standing_question": "Is the operating console being prioritized when ROI indicates it should be next?",
            "claim": "Operating console ROI rank is tracked with explicit next/not-next signal.",
            "evidence": [
                {"metric": "operating_console_rank", "value": operating_console_status.get("estimated_roi_rank"), "source": "operating_console.estimated_roi_rank"},
                {"metric": "operating_console_is_next", "value": bool(operating_console_status.get("is_next")), "source": "operating_console.is_next"},
            ],
            "falsifier": "Operating console rank is missing from inventory.",
            "threshold": {"operator": "is_not_null", "value": True},
            "owner_role": "ui-governance",
            "auto_action": "create task from /api/inventory/roi/next-task when it becomes next",
            "review_cadence": "per monitor cycle",
            "status": "ok" if operating_console_status.get("estimated_roi_rank") is not None else "needs_attention",
        },
    ]
    violations = [row for row in checks if row.get("status") != "ok"]
    return {
        "checks": checks,
        "violations_count": len(violations),
        "violations": violations,
    }

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
    estimated_roi_by_idea: dict[str, float] = {}
    for item in ideas:
        idea_id = str(item.get("id") or "")
        estimated_cost = float(item.get("estimated_cost") or 0.0)
        potential_value = float(item.get("potential_value") or 0.0)
        estimated_roi_by_idea[idea_id] = round((potential_value / estimated_cost), 4) if estimated_cost > 0 else 0.0

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
                "idea_estimated_roi": float(estimated_roi_by_idea.get(idea.id) or 0.0),
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
    all_questions = [*answered_questions, *unanswered_questions]
    duplicate_questions = _detect_duplicate_questions(all_questions)

    links = value_lineage_service.list_links(limit=300)
    events = value_lineage_service.list_usage_events(limit=1000)
    link_rows = []
    contributor_rows: list[dict] = []
    perspective_counts: dict[str, int] = {"human": 0, "machine": 0, "unknown": 0}
    for link in links:
        valuation = value_lineage_service.valuation(link.id)
        for role in ("idea", "spec", "implementation", "review"):
            contributor = getattr(link.contributors, role, None)
            if not contributor:
                continue
            perspective = _classify_perspective(contributor)
            perspective_counts[perspective] = perspective_counts.get(perspective, 0) + 1
            contributor_rows.append(
                {
                    "lineage_id": link.id,
                    "idea_id": link.idea_id,
                    "spec_id": link.spec_id,
                    "role": role,
                    "contributor": contributor,
                    "perspective": perspective,
                    "estimated_cost": link.estimated_cost,
                    "measured_value_total": valuation.measured_value_total if valuation else 0.0,
                    "roi_ratio": valuation.roi_ratio if valuation else 0.0,
                }
            )
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

    roi_rows: list[dict] = []
    for item in ideas:
        estimated_cost = float(item.get("estimated_cost") or 0.0)
        actual_cost = float(item.get("actual_cost") or 0.0)
        potential_value = float(item.get("potential_value") or 0.0)
        actual_value = float(item.get("actual_value") or 0.0)
        estimated_roi = round((potential_value / estimated_cost), 4) if estimated_cost > 0 else 0.0
        actual_roi = round((actual_value / actual_cost), 4) if actual_cost > 0 else None
        roi_rows.append(
            {
                "idea_id": str(item.get("id") or ""),
                "idea_name": str(item.get("name") or ""),
                "manifestation_status": str(item.get("manifestation_status") or ""),
                "potential_value": potential_value,
                "actual_value": actual_value,
                "estimated_cost": estimated_cost,
                "actual_cost": actual_cost,
                "estimated_roi": estimated_roi,
                "actual_roi": actual_roi,
                "missing_actual_roi": actual_cost <= 0.0,
            }
        )
    estimated_sorted = sorted(roi_rows, key=lambda row: -float(row.get("estimated_roi") or 0.0))
    actual_present = [row for row in roi_rows if isinstance(row.get("actual_roi"), float)]
    actual_sorted = sorted(actual_present, key=lambda row: -float(row.get("actual_roi") or 0.0))
    missing_actual = [row for row in roi_rows if bool(row.get("missing_actual_roi"))]
    missing_actual.sort(
        key=lambda row: (
            -float(row.get("estimated_roi") or 0.0),
            -float(row.get("potential_value") or 0.0),
        )
    )
    ranked_estimated = sorted(roi_rows, key=lambda row: -float(row.get("estimated_roi") or 0.0))

    next_question = None
    if unanswered_questions:
        next_question = sorted(
            unanswered_questions,
            key=lambda row: (
                -float(row.get("idea_estimated_roi") or 0.0),
                -float(row.get("question_roi") or 0.0),
            ),
        )[0]

    operating_console_id = "web-ui-governance"
    operating_console_rank = None
    for idx, row in enumerate(ranked_estimated, start=1):
        if row.get("idea_id") == operating_console_id:
            operating_console_rank = idx
            break
    operating_console = next((row for row in roi_rows if row.get("idea_id") == operating_console_id), None)
    operating_console_status = {
        "idea_id": operating_console_id,
        "estimated_roi": float((operating_console or {}).get("estimated_roi") or 0.0),
        "estimated_roi_rank": operating_console_rank,
        "is_next": bool(next_question and next_question.get("idea_id") == operating_console_id),
    }
    evidence_contract = _build_evidence_contract(
        ideas=ideas,
        unanswered_questions=unanswered_questions,
        duplicate_questions=duplicate_questions,
        link_rows=link_rows,
        contributor_rows=contributor_rows,
        next_question=next_question,
        operating_console_status=operating_console_status,
    )

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
        "quality_issues": {
            "duplicate_idea_questions": {
                "count": len(duplicate_questions),
                "groups": duplicate_questions,
            }
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
        "contributors": {
            "attribution_count": len(contributor_rows),
            "by_perspective": perspective_counts,
            "attributions": contributor_rows,
        },
        "roi_insights": {
            "most_estimated_roi": estimated_sorted[:5],
            "least_estimated_roi": sorted(roi_rows, key=lambda row: float(row.get("estimated_roi") or 0.0))[:5],
            "most_actual_roi": actual_sorted[:5],
            "least_actual_roi": sorted(actual_present, key=lambda row: float(row.get("actual_roi") or 0.0))[:5],
            "missing_actual_roi_high_potential": missing_actual[:5],
        },
        "next_roi_work": {
            "selection_basis": "highest_idea_estimated_roi_then_question_roi",
            "item": next_question,
        },
        "operating_console": operating_console_status,
        "evidence_contract": evidence_contract,
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


def next_highest_estimated_roi_task(create_task: bool = False) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    item = inventory.get("next_roi_work", {}).get("item")
    if not isinstance(item, dict) or not item:
        return {"result": "no_unanswered_questions"}

    idea_id = str(item.get("idea_id") or "unknown")
    question = str(item.get("question") or "").strip()
    idea_estimated_roi = float(item.get("idea_estimated_roi") or 0.0)
    question_roi = float(item.get("question_roi") or 0.0)
    direction = (
        f"Next highest estimated-ROI work item for idea '{idea_id}': {question} "
        f"(idea_estimated_roi={idea_estimated_roi}, question_roi={question_roi}). "
        "Produce measurable implementation with tests and update system-lineage metrics."
    )
    report: dict = {
        "result": "task_suggested",
        "selection_basis": "estimated_roi_queue",
        "idea_id": idea_id,
        "question": question,
        "idea_estimated_roi": idea_estimated_roi,
        "question_roi": question_roi,
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
                "source": "inventory_estimated_roi",
                "idea_id": idea_id,
                "idea_estimated_roi": idea_estimated_roi,
                "question_roi": question_roi,
            },
        )
    )
    report["created_task"] = {
        "id": task["id"],
        "status": task["status"].value if hasattr(task["status"], "value") else str(task["status"]),
        "task_type": task["task_type"].value if hasattr(task["task_type"], "value") else str(task["task_type"]),
    }
    return report


def _create_or_reuse_issue_task(
    *,
    condition: str,
    signature: str,
    direction: str,
    context: dict,
) -> dict:
    from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
    from app.services import agent_service

    existing, _ = agent_service.list_tasks(limit=200)
    for task in existing:
        ctx = task.get("context") if isinstance(task, dict) else None
        if not isinstance(ctx, dict):
            continue
        if ctx.get("issue_signature") != signature:
            continue
        status = task.get("status")
        status_text = status.value if hasattr(status, "value") else str(status)
        if status_text in (
            TaskStatus.PENDING.value,
            TaskStatus.RUNNING.value,
            TaskStatus.NEEDS_DECISION.value,
        ):
            return {
                "id": task.get("id"),
                "status": status_text,
                "task_type": task.get("task_type").value
                if hasattr(task.get("task_type"), "value")
                else str(task.get("task_type")),
                "deduped": True,
            }

    created = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.HEAL,
            context={
                **context,
                "source": "inventory_issue_scan",
                "issue_condition": condition,
                "issue_signature": signature,
            },
        )
    )
    return {
        "id": created["id"],
        "status": created["status"].value if hasattr(created["status"], "value") else str(created["status"]),
        "task_type": created["task_type"].value if hasattr(created["task_type"], "value") else str(created["task_type"]),
        "deduped": False,
    }


def scan_inventory_issues(create_tasks: bool = False) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    dup = (
        inventory.get("quality_issues", {})
        .get("duplicate_idea_questions", {})
    )
    groups = dup.get("groups") if isinstance(dup, dict) else []
    duplicate_groups = [g for g in groups if isinstance(g, dict)]
    issues: list[dict] = []
    if duplicate_groups:
        issues.append(
            {
                "condition": "duplicate_idea_questions",
                "severity": "medium",
                "priority": 2,
                "count": len(duplicate_groups),
                "groups": duplicate_groups,
                "suggested_action": "Deduplicate questions per idea and keep one canonical phrasing with ROI/cost values.",
            }
        )

    report: dict = {
        "generated_at": inventory.get("generated_at"),
        "issues": issues,
        "issues_count": len(issues),
        "created_tasks": [],
    }
    if not create_tasks or not issues:
        return report

    issue = issues[0]
    signature = f"{issue['condition']}:{issue['count']}"
    top = duplicate_groups[0]
    direction = (
        "Inventory issue: duplicate idea questions detected. "
        f"Condition={issue['condition']} groups={issue['count']}. "
        f"Top duplicate: idea={top.get('idea_id')} question='{top.get('question')}' occurrences={top.get('occurrences')}. "
        "Implement canonical dedupe and migration, add tests, and validate inventory no longer reports duplicates."
    )
    report["created_tasks"].append(
        _create_or_reuse_issue_task(
            condition=issue["condition"],
            signature=signature,
            direction=direction,
            context={"issue_count": issue["count"]},
        )
    )
    return report


def scan_evidence_contract(create_tasks: bool = False) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    evidence = inventory.get("evidence_contract", {})
    violations = evidence.get("violations") if isinstance(evidence.get("violations"), list) else []
    issues: list[dict] = []
    for row in violations:
        if not isinstance(row, dict):
            continue
        subsystem_id = str(row.get("subsystem_id") or "unknown")
        issues.append(
            {
                "condition": f"evidence_contract::{subsystem_id}",
                "severity": "medium",
                "priority": 2,
                "subsystem_id": subsystem_id,
                "claim": row.get("claim"),
                "falsifier": row.get("falsifier"),
                "suggested_action": row.get("auto_action"),
                "owner_role": row.get("owner_role"),
            }
        )

    report: dict = {
        "generated_at": inventory.get("generated_at"),
        "issues": issues,
        "issues_count": len(issues),
        "created_tasks": [],
    }
    if not create_tasks or not issues:
        return report

    for issue in issues:
        condition = str(issue["condition"])
        subsystem_id = str(issue.get("subsystem_id") or "unknown")
        signature = f"{condition}:1"
        direction = (
            "Evidence contract violation detected. "
            f"Subsystem={subsystem_id}. Claim='{issue.get('claim')}'. "
            f"Falsifier='{issue.get('falsifier')}'. "
            "Collect objective evidence, correct thresholds/assumptions, add tests, and close the violation."
        )
        report["created_tasks"].append(
            _create_or_reuse_issue_task(
                condition=condition,
                signature=signature,
                direction=direction,
                context={
                    "subsystem_id": subsystem_id,
                    "owner_role": issue.get("owner_role"),
                },
            )
        )
    return report
