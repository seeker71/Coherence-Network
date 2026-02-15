"""Unified inventory service for ideas, questions, specs, implementations, and usage."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services import idea_service, route_registry_service, runtime_service, value_lineage_service


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
    required_core_ids = set(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ()))
    present_ids = {str(i.get("id") or "").strip() for i in ideas if isinstance(i, dict)}
    missing_core_ids = sorted(i for i in required_core_ids if i not in present_ids)
    core_present = len(missing_core_ids) == 0
    ideas_by_id = {
        str(i.get("id") or "").strip(): i
        for i in ideas
        if isinstance(i, dict) and str(i.get("id") or "").strip()
    }
    missing_core_manifestations = sorted(
        idea_id
        for idea_id in required_core_ids
        if str((ideas_by_id.get(idea_id, {}) or {}).get("manifestation_status") or "none").strip().lower() == "none"
    )
    core_manifested = len(missing_core_manifestations) == 0

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
            "subsystem_id": "portfolio_completeness",
            "standing_question": "Are the overall system idea and required component ideas present in portfolio?",
            "claim": "All required core ideas exist in portfolio inventory.",
            "evidence": [
                {"metric": "required_core_ideas_total", "value": len(required_core_ids), "source": "idea_service.REQUIRED_CORE_IDEA_IDS"},
                {"metric": "missing_core_idea_ids", "value": missing_core_ids, "source": "ideas.items[].id"},
            ],
            "falsifier": "Any required core idea id is missing from ideas inventory.",
            "threshold": {"operator": "==", "value": []},
            "owner_role": "portfolio-governance",
            "auto_action": "create heal task to add missing core ideas",
            "review_cadence": "per monitor cycle",
            "status": "ok" if core_present else "needs_attention",
        },
        {
            "subsystem_id": "manifestation_coverage",
            "standing_question": "Are core system/component ideas manifested (not none)?",
            "claim": "All required core ideas have manifestation status partial or validated.",
            "evidence": [
                {"metric": "missing_core_manifestations", "value": missing_core_manifestations, "source": "ideas.items[].manifestation_status"},
            ],
            "falsifier": "Any required core idea has manifestation_status 'none'.",
            "threshold": {"operator": "==", "value": []},
            "owner_role": "delivery",
            "auto_action": "create implementation task for missing core manifestations",
            "review_cadence": "per monitor cycle",
            "status": "ok" if core_manifested else "needs_attention",
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


def _tracking_mechanism_assessment(
    *,
    ideas_count: int,
    specs_count: int,
    link_rows: list[dict],
    contributor_rows: list[dict],
    runtime_summary: list[dict],
    duplicate_questions: list[dict],
    unanswered_questions: list[dict],
) -> dict:
    lineage_count = len(link_rows)
    attribution_count = len(contributor_rows)
    duplicate_count = len(duplicate_questions)
    unanswered_count = len(unanswered_questions)
    runtime_coverage = 0
    for row in runtime_summary:
        if not isinstance(row, dict):
            continue
        if str(row.get("idea_id") or "").strip():
            runtime_coverage += 1
    runtime_coverage_ratio = round((runtime_coverage / ideas_count), 4) if ideas_count > 0 else 0.0

    evidence_signals = {
        "ideas_count": ideas_count,
        "specs_count": specs_count,
        "lineage_links_count": lineage_count,
        "attribution_rows_count": attribution_count,
        "runtime_idea_coverage_ratio": runtime_coverage_ratio,
        "duplicate_question_groups": duplicate_count,
        "unanswered_questions_count": unanswered_count,
    }

    improvements = [
        {
            "id": "tracking-improvement-runtime-coverage",
            "question": "How do we increase runtime mapping coverage across ideas?",
            "current_gap": "Runtime telemetry does not yet cover all idea IDs.",
            "estimated_cost_hours": 6.0,
            "potential_value": 40.0,
            "estimated_roi": round(40.0 / 6.0, 4),
            "action": "Add route-to-idea mappings for uncovered API and web routes and enforce coverage threshold in CI.",
        },
        {
            "id": "tracking-improvement-lineage-adoption",
            "question": "How do we ensure every implemented spec has value-lineage links?",
            "current_gap": "Lineage links are present but not guaranteed for all shipped changes.",
            "estimated_cost_hours": 8.0,
            "potential_value": 45.0,
            "estimated_roi": round(45.0 / 8.0, 4),
            "action": "Gate PR merge on lineage creation for touched specs and require contributor roles.",
        },
        {
            "id": "tracking-improvement-duplicate-question-prevention",
            "question": "How do we prevent duplicate idea questions from entering portfolio data?",
            "current_gap": "Duplicate questions are detected but prevention can still drift over time.",
            "estimated_cost_hours": 4.0,
            "potential_value": 22.0,
            "estimated_roi": round(22.0 / 4.0, 4),
            "action": "Enforce normalized uniqueness on question writes and add monitor alert thresholds.",
        },
        {
            "id": "tracking-improvement-unanswered-burn-rate",
            "question": "How do we reduce unanswered high-ROI questions faster?",
            "current_gap": "Question backlog can accumulate without a burn-rate SLO.",
            "estimated_cost_hours": 5.0,
            "potential_value": 28.0,
            "estimated_roi": round(28.0 / 5.0, 4),
            "action": "Track weekly unanswered burn rate and auto-create implementation tasks for top ROI unanswered rows.",
        },
        {
            "id": "tracking-improvement-spec-implementation-freshness",
            "question": "How do we detect stale spec-to-implementation mappings quickly?",
            "current_gap": "Spec tracking is maintained but freshness age is not currently scored.",
            "estimated_cost_hours": 7.0,
            "potential_value": 30.0,
            "estimated_roi": round(30.0 / 7.0, 4),
            "action": "Add freshness timestamps and attention issues when implementation/test mapping is stale.",
        },
    ]

    improvements.sort(
        key=lambda row: (
            -float(row.get("estimated_roi") or 0.0),
            float(row.get("estimated_cost_hours") or 0.0),
        )
    )

    current_mechanism = {
        "idea_tracking": "JSON portfolio persisted through idea service",
        "spec_tracking": "Specs in markdown with coverage/tracking docs",
        "linkage_tracking": "Value-lineage links + usage events API",
        "quality_tracking": "Inventory scans and evidence contract checks",
    }

    return {
        "current_mechanism": current_mechanism,
        "evidence_signals": evidence_signals,
        "improvements_ranked": improvements,
        "best_next_improvement": improvements[0] if improvements else None,
    }


def build_system_lineage_inventory(runtime_window_seconds: int = 3600) -> dict:
    ideas_response = idea_service.list_ideas()
    ideas = [item.model_dump(mode="json") for item in ideas_response.ideas]
    manifestation_rows = [
        {
            "idea_id": str(item.get("id") or ""),
            "idea_name": str(item.get("name") or ""),
            "manifestation_status": str(item.get("manifestation_status") or "none"),
            "actual_value": float(item.get("actual_value") or 0.0),
            "actual_cost": float(item.get("actual_cost") or 0.0),
        }
        for item in ideas
    ]
    manifestation_by_status: dict[str, int] = {"none": 0, "partial": 0, "validated": 0}
    for row in manifestation_rows:
        status = str(row.get("manifestation_status") or "none").strip().lower()
        if status not in manifestation_by_status:
            manifestation_by_status[status] = 0
        manifestation_by_status[status] += 1
    missing_manifestations = [
        row for row in manifestation_rows if str(row.get("manifestation_status") or "none").strip().lower() == "none"
    ]
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
    tracking_mechanism = _tracking_mechanism_assessment(
        ideas_count=len(ideas),
        specs_count=len(spec_items),
        link_rows=link_rows,
        contributor_rows=contributor_rows,
        runtime_summary=runtime_summary,
        duplicate_questions=duplicate_questions,
        unanswered_questions=unanswered_questions,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ideas": {
            "summary": ideas_response.summary.model_dump(mode="json"),
            "items": ideas,
        },
        "manifestations": {
            "total": len(manifestation_rows),
            "by_status": manifestation_by_status,
            "missing_count": len(missing_manifestations),
            "missing": missing_manifestations,
            "items": manifestation_rows,
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
        "tracking_mechanism": tracking_mechanism,
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
    required_core_ids = set(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ()))
    idea_items = inventory.get("ideas", {}).get("items")
    present_ids = {
        str(item.get("id") or "").strip()
        for item in (idea_items if isinstance(idea_items, list) else [])
        if isinstance(item, dict)
    }
    missing_core_ids = sorted(i for i in required_core_ids if i not in present_ids)
    core_missing_manifestations: list[str] = []
    manifestations = inventory.get("manifestations", {}).get("items")
    if isinstance(manifestations, list):
        status_by_id = {
            str(row.get("idea_id") or "").strip(): str(row.get("manifestation_status") or "none").strip().lower()
            for row in manifestations
            if isinstance(row, dict)
        }
        core_missing_manifestations = sorted(
            idea_id for idea_id in required_core_ids if status_by_id.get(idea_id, "none") == "none"
        )

    issues: list[dict] = []
    if missing_core_ids:
        issues.append(
            {
                "condition": "missing_core_ideas",
                "severity": "high",
                "priority": 1,
                "count": len(missing_core_ids),
                "missing_core_idea_ids": missing_core_ids,
                "suggested_action": "Add missing overall/component ideas to portfolio defaults and migrate persisted portfolio files.",
            }
        )
    if core_missing_manifestations:
        issues.append(
            {
                "condition": "missing_core_manifestations",
                "severity": "medium",
                "priority": 2,
                "count": len(core_missing_manifestations),
                "missing_core_manifestation_idea_ids": core_missing_manifestations,
                "suggested_action": "Prioritize implementation tasks to move core ideas from none to partial/validated.",
            }
        )
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

    issues.sort(key=lambda row: int(row.get("priority") or 99))
    issue = issues[0]
    signature = f"{issue['condition']}:{issue['count']}"
    if issue["condition"] == "duplicate_idea_questions":
        top = duplicate_groups[0]
        direction = (
            "Inventory issue: duplicate idea questions detected. "
            f"Condition={issue['condition']} groups={issue['count']}. "
            f"Top duplicate: idea={top.get('idea_id')} question='{top.get('question')}' occurrences={top.get('occurrences')}. "
            "Implement canonical dedupe and migration, add tests, and validate inventory no longer reports duplicates."
        )
    elif issue["condition"] == "missing_core_ideas":
        direction = (
            "Inventory issue: required core ideas missing from portfolio. "
            f"Missing IDs={','.join(issue.get('missing_core_idea_ids') or [])}. "
            "Add/migrate missing core ideas and ensure evidence contract passes."
        )
    else:
        direction = (
            "Inventory issue: core ideas missing manifestations. "
            f"Idea IDs={','.join(issue.get('missing_core_manifestation_idea_ids') or [])}. "
            "Create and execute tasks to move these ideas from none to partial/validated with measurable artifacts."
        )
    report["created_tasks"].append(
        _create_or_reuse_issue_task(
            condition=issue["condition"],
            signature=signature,
            direction=direction,
            context={"issue_count": issue["count"], "issue_payload": issue},
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


def _derived_ideas_from_answered_question(question_row: dict) -> list[dict]:
    question = str(question_row.get("question") or "").lower()
    out: list[dict] = []
    if "score tracking maturity" in question:
        out.append(
            {
                "idea_id": "tracking-maturity-scorecard",
                "name": "Tracking maturity scorecard and release gates",
                "description": "Compute subsystem tracking maturity scores and enforce minimum thresholds in release contracts.",
                "potential_value": 84.0,
                "estimated_cost": 9.0,
                "interfaces": ["machine:api", "human:web", "ai:automation"],
                "open_questions": [
                    {
                        "question": "Which score dimensions best predict tracking reliability and deployment risk?",
                        "value_to_whole": 24.0,
                        "estimated_cost": 2.0,
                    }
                ],
            }
        )
    if "audit signals" in question or "blind trust" in question:
        out.append(
            {
                "idea_id": "tracking-audit-anomaly-detection",
                "name": "Tracking audit anomaly detection",
                "description": "Detect suspicious or incomplete idea/spec/manifestation evidence and trigger review tasks automatically.",
                "potential_value": 82.0,
                "estimated_cost": 8.0,
                "interfaces": ["machine:api", "ai:automation", "human:operators"],
                "open_questions": [
                    {
                        "question": "Which anomaly rules provide high signal with low false positives for governance workflows?",
                        "value_to_whole": 23.0,
                        "estimated_cost": 2.0,
                    }
                ],
            }
        )
    return out


def _proposed_answer_for_question(question_row: dict, inventory: dict) -> tuple[str | None, float | None]:
    question = str(question_row.get("question") or "").strip().lower()
    if not question:
        return None, None

    if "route set is canonical" in question:
        routes = route_registry_service.get_canonical_routes()
        api_count = len(routes.get("api_routes") or [])
        web_count = len(routes.get("web_routes") or [])
        version = routes.get("version")
        milestone = routes.get("milestone")
        return (
            f"Canonical route contract is /api/inventory/routes/canonical (version={version}, milestone={milestone}) "
            f"with {api_count} API routes and {web_count} web routes. This should remain the source of truth.",
            5.0,
        )
    if "overall system is improving end-to-end value flow" in question:
        ideas_summary = inventory.get("ideas", {}).get("summary", {})
        runtime_rows = inventory.get("runtime", {}).get("ideas", [])
        quality_dup = (
            inventory.get("quality_issues", {})
            .get("duplicate_idea_questions", {})
            .get("count", 0)
        )
        evidence_violations = inventory.get("evidence_contract", {}).get("violations_count", 0)
        total_value_gap = float(ideas_summary.get("total_value_gap") or 0.0)
        total_actual_value = float(ideas_summary.get("total_actual_value") or 0.0)
        runtime_events = int(sum(int(row.get("event_count") or 0) for row in runtime_rows if isinstance(row, dict)))
        runtime_cost = round(
            sum(float(row.get("runtime_cost_estimate") or 0.0) for row in runtime_rows if isinstance(row, dict)),
            6,
        )
        return (
            "Evidence summary: "
            f"actual_value={total_actual_value}, value_gap={total_value_gap}, "
            f"runtime_events_24h={runtime_events}, runtime_cost_24h={runtime_cost}, "
            f"duplicate_question_groups={quality_dup}, evidence_violations={evidence_violations}. "
            "Improvement is supported when actual value rises and value gap/violations decrease while runtime cost stays bounded.",
            3.4,
        )
    if "leading indicators best represent energy flow" in question:
        return (
            "Use runtime event_count/source mix, runtime_cost_estimate by idea, and lineage valuation ROI "
            "(measured_value_total/estimated_cost) as leading indicators.",
            3.0,
        )
    if "best-known traceability practices" in question:
        return (
            "Current practice is strong but not yet best-in-class: we have idea/spec/test mappings, value-lineage, "
            "evidence contracts, and monitor scans; highest ROI gap is stricter merge-time enforcement and maturity scoring.",
            3.0,
        )
    if "depend on assumptions rather than verifiable evidence" in question:
        return (
            "Main assumption-heavy areas are terminology comprehension, manual review quality, and contributor identity confidence. "
            "Add explicit evidence checks and periodic calibration tests for each.",
            2.5,
        )
    if "tracking components are currently manual" in question:
        return (
            "Manual-heavy components include term alignment review, evidence interpretation, and cross-thread consolidation. "
            "Automate these with scorecards, anomaly scans, and standardized contributor contracts first.",
            2.8,
        )
    if "missing audit signals most reduce blind trust" in question:
        return (
            "Highest-value missing signals are immutable decision/audit trail IDs, evidence freshness SLA, "
            "and anomaly alerts for ROI jumps or missing attribution at deploy time.",
            2.8,
        )
    if "score tracking maturity per subsystem" in question:
        return (
            "Score each subsystem on completeness, evidence quality, automation coverage, and freshness; "
            "gate release when any critical subsystem falls below threshold.",
            3.2,
        )
    if "improve the ui" in question:
        missing = inventory.get("manifestations", {}).get("missing_count", 0)
        return (
            f"Prioritize a single browseable table for ideas/spec links/status plus issue actions; currently missing manifestations count is {missing}.",
            2.2,
        )
    if "missing from the ui for machine and human contributors" in question:
        return (
            "Missing key UI elements are full task queue management, contributor/contribution browse pages, and direct ROI anomaly views.",
            2.2,
        )
    return None, None


def auto_answer_high_roi_questions(limit: int = 3, create_derived_ideas: bool = False) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    unanswered = inventory.get("questions", {}).get("unanswered")
    rows = [row for row in (unanswered if isinstance(unanswered, list) else []) if isinstance(row, dict)]
    rows.sort(
        key=lambda row: (
            -float(row.get("question_roi") or 0.0),
            -float(row.get("idea_estimated_roi") or 0.0),
        )
    )
    selected = rows[: max(1, min(limit, 25))]
    answered_rows: list[dict] = []
    derived_rows: list[dict] = []
    skipped_rows: list[dict] = []

    for row in selected:
        idea_id = str(row.get("idea_id") or "").strip()
        question = str(row.get("question") or "").strip()
        if not idea_id or not question:
            continue
        answer, measured_delta = _proposed_answer_for_question(row, inventory)
        if not answer:
            skipped_rows.append({"idea_id": idea_id, "question": question, "reason": "no_evidence_template"})
            continue
        updated, found = idea_service.answer_question(
            idea_id=idea_id,
            question=question,
            answer=answer,
            measured_delta=measured_delta,
        )
        if not found or updated is None:
            skipped_rows.append({"idea_id": idea_id, "question": question, "reason": "question_not_found"})
            continue
        answered_rows.append(
            {
                "idea_id": idea_id,
                "question": question,
                "question_roi": float(row.get("question_roi") or 0.0),
                "answer_roi": round((float(measured_delta) / float(row.get("estimated_cost") or 1.0)), 4)
                if measured_delta is not None and float(row.get("estimated_cost") or 0.0) > 0.0
                else 0.0,
            }
        )
        if create_derived_ideas:
            for candidate in _derived_ideas_from_answered_question(row):
                created_idea, created = idea_service.add_idea_if_missing(
                    idea_id=str(candidate["idea_id"]),
                    name=str(candidate["name"]),
                    description=str(candidate["description"]),
                    potential_value=float(candidate["potential_value"]),
                    estimated_cost=float(candidate["estimated_cost"]),
                    open_questions=candidate.get("open_questions"),
                    interfaces=candidate.get("interfaces") or [],
                )
                derived_rows.append(
                    {
                        "idea_id": created_idea.id,
                        "created": created,
                        "estimated_roi": round(
                            float(created_idea.potential_value) / float(created_idea.estimated_cost), 4
                        )
                        if float(created_idea.estimated_cost) > 0
                        else 0.0,
                    }
                )

    return {
        "result": "completed",
        "selected_count": len(selected),
        "answered_count": len(answered_rows),
        "answered": answered_rows,
        "skipped": skipped_rows,
        "derived_ideas": derived_rows,
    }
