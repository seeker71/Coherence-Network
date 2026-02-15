"""Unified inventory service for ideas, questions, specs, implementations, and usage."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from app.services import (
    idea_service,
    page_lineage_service,
    route_registry_service,
    runtime_service,
    value_lineage_service,
)


def _roi_estimator_path() -> Path:
    configured = os.getenv("ROI_ESTIMATOR_PATH")
    if configured:
        return Path(configured)
    return _project_root() / "api" / "data" / "roi_estimator.json"


def _default_roi_estimator_state() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": 1,
        "updated_at": now,
        "weights": {
            "idea_multiplier": 1.0,
            "question_multiplier": 1.0,
            "answer_multiplier": 1.0,
        },
        "measurement_events": [],
        "calibration_runs": [],
    }


def _read_roi_estimator_state() -> dict:
    path = _roi_estimator_path()
    if not path.exists():
        return _default_roi_estimator_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_roi_estimator_state()
    if not isinstance(payload, dict):
        return _default_roi_estimator_state()
    out = _default_roi_estimator_state()
    out["weights"].update(payload.get("weights") or {})
    out["measurement_events"] = [
        row for row in (payload.get("measurement_events") or []) if isinstance(row, dict)
    ][-2000:]
    out["calibration_runs"] = [
        row for row in (payload.get("calibration_runs") or []) if isinstance(row, dict)
    ][-200:]
    out["updated_at"] = str(payload.get("updated_at") or out["updated_at"])
    return out


def _write_roi_estimator_state(state: dict) -> None:
    path = _roi_estimator_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "measurement_events": [row for row in (state.get("measurement_events") or []) if isinstance(row, dict)][-2000:],
        "calibration_runs": [row for row in (state.get("calibration_runs") or []) if isinstance(row, dict)][-200:],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _roi_weights() -> dict[str, float]:
    state = _read_roi_estimator_state()
    raw = state.get("weights") if isinstance(state.get("weights"), dict) else {}
    return {
        "idea_multiplier": float(raw.get("idea_multiplier") or 1.0),
        "question_multiplier": float(raw.get("question_multiplier") or 1.0),
        "answer_multiplier": float(raw.get("answer_multiplier") or 1.0),
    }


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    denom = float(denominator)
    if denom <= 0.0:
        return None
    return round(float(numerator) / denom, 6)


def _median(values: list[float]) -> float | None:
    rows = sorted([float(v) for v in values if isinstance(v, (int, float)) and float(v) > 0.0])
    if not rows:
        return None
    n = len(rows)
    if n % 2 == 1:
        return rows[n // 2]
    return round((rows[n // 2 - 1] + rows[n // 2]) / 2.0, 6)


def _extract_roi_observations(inventory: dict) -> dict[str, list[dict]]:
    idea_rows = inventory.get("roi_insights", {}).get("most_estimated_roi")
    all_idea_rows = inventory.get("ideas", {}).get("items")
    by_id = {
        str(row.get("id") or "").strip(): row
        for row in (all_idea_rows if isinstance(all_idea_rows, list) else [])
        if isinstance(row, dict)
    }
    idea_obs: list[dict] = []
    if isinstance(idea_rows, list):
        seen_ids: set[str] = set()
        for row in idea_rows:
            if not isinstance(row, dict):
                continue
            idea_id = str(row.get("idea_id") or "").strip()
            if not idea_id or idea_id in seen_ids:
                continue
            source = by_id.get(idea_id, {})
            base_estimated = _safe_ratio(
                float(source.get("potential_value") or 0.0) * float(source.get("confidence") or 0.0),
                float(source.get("estimated_cost") or 0.0) + float(source.get("resistance_risk") or 0.0),
            )
            realized = _safe_ratio(
                float(source.get("actual_value") or 0.0),
                float(source.get("actual_cost") or 0.0),
            )
            if base_estimated is None or realized is None:
                continue
            seen_ids.add(idea_id)
            idea_obs.append(
                {
                    "kind": "idea",
                    "subject_id": idea_id,
                    "estimated_base": base_estimated,
                    "actual_roi": realized,
                    "error": round(realized - base_estimated, 6),
                    "ratio": round(realized / base_estimated, 6) if base_estimated > 0 else None,
                    "source": "inventory",
                }
            )

    question_rows = inventory.get("questions", {}).get("answered")
    question_obs: list[dict] = []
    if isinstance(question_rows, list):
        for row in question_rows:
            if not isinstance(row, dict):
                continue
            estimated_cost = float(row.get("estimated_cost") or 0.0)
            value_to_whole = float(row.get("value_to_whole") or 0.0)
            measured_delta = row.get("measured_delta")
            if estimated_cost <= 0.0 or measured_delta is None:
                continue
            base_estimated = _safe_ratio(value_to_whole, estimated_cost)
            actual = _safe_ratio(float(measured_delta), estimated_cost)
            if base_estimated is None or actual is None:
                continue
            question_obs.append(
                {
                    "kind": "question",
                    "subject_id": str(row.get("question_id") or row.get("question") or "").strip(),
                    "idea_id": str(row.get("idea_id") or "").strip(),
                    "estimated_base": base_estimated,
                    "actual_roi": actual,
                    "error": round(actual - base_estimated, 6),
                    "ratio": round(actual / base_estimated, 6) if base_estimated > 0 else None,
                    "source": "inventory",
                }
            )
    return {"ideas": idea_obs, "questions": question_obs}


def _extract_manual_observations(state: dict) -> dict[str, list[dict]]:
    events = state.get("measurement_events")
    if not isinstance(events, list):
        return {"ideas": [], "questions": []}
    ideas: list[dict] = []
    questions: list[dict] = []
    for row in events:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("subject_type") or "").strip().lower()
        estimated_base = _safe_ratio(
            float(row.get("estimated_base") or 0.0),
            1.0,
        )
        actual_roi = _safe_ratio(
            float(row.get("actual_roi") or 0.0),
            1.0,
        )
        if estimated_base is None or actual_roi is None:
            continue
        obs = {
            "kind": kind,
            "subject_id": str(row.get("subject_id") or "").strip(),
            "idea_id": str(row.get("idea_id") or "").strip() or None,
            "estimated_base": estimated_base,
            "actual_roi": actual_roi,
            "error": round(actual_roi - estimated_base, 6),
            "ratio": round(actual_roi / estimated_base, 6) if estimated_base > 0 else None,
            "source": "manual",
        }
        if kind == "idea":
            ideas.append(obs)
        elif kind == "question":
            questions.append(obs)
    return {"ideas": ideas, "questions": questions}


def _suggested_multipliers(idea_obs: list[dict], question_obs: list[dict]) -> dict:
    idea_ratios = [float(row.get("ratio")) for row in idea_obs if isinstance(row.get("ratio"), (int, float))]
    question_ratios = [float(row.get("ratio")) for row in question_obs if isinstance(row.get("ratio"), (int, float))]
    idea_suggested = _median(idea_ratios)
    question_suggested = _median(question_ratios)
    if idea_suggested is None:
        idea_suggested = 1.0
    if question_suggested is None:
        question_suggested = 1.0
    idea_suggested = min(max(float(idea_suggested), 0.2), 5.0)
    question_suggested = min(max(float(question_suggested), 0.2), 5.0)
    return {
        "idea_multiplier": round(idea_suggested, 6),
        "question_multiplier": round(question_suggested, 6),
        "answer_multiplier": round(question_suggested, 6),
        "idea_samples": len(idea_ratios),
        "question_samples": len(question_ratios),
    }


def _question_roi(value_to_whole: float, estimated_cost: float) -> float:
    if estimated_cost <= 0:
        return 0.0
    weights = _roi_weights()
    base = float(value_to_whole) / float(estimated_cost)
    return round(base * float(weights.get("question_multiplier") or 1.0), 4)


def _answer_roi(measured_delta: float | None, estimated_cost: float) -> float:
    if measured_delta is None or estimated_cost <= 0:
        return 0.0
    weights = _roi_weights()
    base = float(measured_delta) / float(estimated_cost)
    return round(base * float(weights.get("answer_multiplier") or 1.0), 4)


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


def _normalize_interface_path(path: str) -> str:
    out = (path or "").strip()
    if not out:
        return ""
    if "?" in out:
        out = out.split("?", 1)[0]
    out = re.sub(r"\$\{[^}]+\}", "{param}", out)
    out = re.sub(r"\[[^\]]+\]", "{param}", out)
    out = re.sub(r"/{2,}", "/", out)
    if not out.startswith("/"):
        out = "/" + out
    return out.rstrip("/") or "/"


def _discover_api_routes_from_source() -> list[dict]:
    routers_dir = _project_root() / "api" / "app" / "routers"
    if not routers_dir.exists():
        return []
    main_py = _project_root() / "api" / "app" / "main.py"
    prefix_by_router: dict[str, str] = {}
    if main_py.exists():
        try:
            main_content = main_py.read_text(encoding="utf-8")
            for router_name, prefix in re.findall(
                r'app\.include_router\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\.router\s*,\s*prefix="([^"]+)"',
                main_content,
            ):
                prefix_by_router[router_name] = prefix
        except OSError:
            prefix_by_router = {}
    pattern = re.compile(r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']')
    rows: list[dict] = []
    for path in sorted(routers_dir.glob("*.py")):
        router_name = path.stem
        prefix = prefix_by_router.get(router_name, "/api")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in pattern.finditer(content):
            method = match.group(1).upper()
            route_path = _normalize_interface_path(f"{prefix}{match.group(2)}")
            rows.append({"path": route_path, "method": method, "source_file": str(path)})
    uniq: dict[tuple[str, str], dict] = {}
    for row in rows:
        uniq[(row["path"], row["method"])] = row
    return sorted(uniq.values(), key=lambda row: (row["path"], row["method"]))


def _discover_web_api_usage_paths() -> list[str]:
    web_dir = _project_root() / "web"
    if not web_dir.exists():
        return []
    path_pattern = re.compile(r"/(?:api|v1)/[A-Za-z0-9_./${}\-\[\]]+")
    rows: list[str] = []
    for path in sorted(web_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if ".next" in path.parts or "node_modules" in path.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in path_pattern.findall(content):
            normalized = _normalize_interface_path(match)
            if normalized.startswith("/api/") or normalized.startswith("/v1/"):
                rows.append(normalized)
    return sorted(set(rows))


def _api_route_matches_web_usage(api_path: str, web_path: str) -> bool:
    if api_path == web_path:
        return True
    pattern = "^" + re.escape(api_path).replace(r"\{", "{").replace(r"\}", "}") + "$"
    pattern = re.sub(r"\{[^/]+\}", r"[^/]+", pattern)
    if re.match(pattern, web_path):
        return True
    if "{param}" in web_path:
        wildcard_web = "^" + re.escape(web_path).replace(r"\{param\}", r"[^/]+") + "$"
        if re.match(wildcard_web, api_path):
            return True
    return False


def _api_web_gap_rows() -> tuple[list[dict], list[str], int]:
    api_routes = _discover_api_routes_from_source()
    web_paths = _discover_web_api_usage_paths()
    gaps: list[dict] = []
    for route in api_routes:
        api_path = str(route.get("path") or "")
        matched = any(_api_route_matches_web_usage(api_path, web_path) for web_path in web_paths)
        if matched:
            continue
        gaps.append(
            {
                "path": api_path,
                "method": route.get("method"),
                "source_file": route.get("source_file"),
                "gap_type": "api_not_used_in_web_ui",
                "impact": "machine_only_availability",
            }
        )
    return gaps, web_paths, len(api_routes)


def _build_asset_registry(
    *,
    ideas: list[dict],
    spec_items: list[dict],
    api_routes_total: int,
    web_usage_paths_total: int,
    interface_gaps: list[dict],
) -> dict:
    assets: list[dict] = []
    for item in ideas:
        idea_id = str(item.get("id") or "").strip()
        if not idea_id:
            continue
        assets.append(
            {
                "asset_id": f"idea:{idea_id}",
                "asset_type": "idea",
                "name": str(item.get("name") or idea_id),
                "linked_id": idea_id,
                "status": str(item.get("manifestation_status") or "none"),
                "estimated_value": float(item.get("potential_value") or 0.0),
                "estimated_cost": float(item.get("estimated_cost") or 0.0),
                "machine_path": f"/api/ideas/{idea_id}",
                "human_path": "/portfolio",
            }
        )
    for item in spec_items:
        spec_id = str(item.get("spec_id") or "").strip()
        spec_path = str(item.get("path") or "").strip()
        if not spec_id:
            continue
        assets.append(
            {
                "asset_id": f"spec:{spec_id}",
                "asset_type": "spec",
                "name": str(item.get("title") or spec_id),
                "linked_id": spec_id,
                "status": "tracked",
                "estimated_value": 0.0,
                "estimated_cost": 0.0,
                "machine_path": "/api/inventory/system-lineage",
                "human_path": spec_path or "specs/",
            }
        )

    lineage = page_lineage_service.get_page_lineage()
    entries = lineage.get("entries") if isinstance(lineage.get("entries"), list) else []
    for row in entries:
        if not isinstance(row, dict):
            continue
        page_path = str(row.get("page_path") or "").strip()
        if not page_path:
            continue
        assets.append(
            {
                "asset_id": f"page:{page_path}",
                "asset_type": "page",
                "name": str(row.get("page_title") or page_path),
                "linked_id": page_path,
                "status": "mapped",
                "estimated_value": 0.0,
                "estimated_cost": 0.0,
                "machine_path": f"/api/inventory/page-lineage?page_path={page_path}",
                "human_path": page_path,
            }
        )

    assets.append(
        {
            "asset_id": "runtime:api-route-surface",
            "asset_type": "api_surface",
            "name": "API route surface",
            "linked_id": "api_routes",
            "status": "tracked",
            "estimated_value": float(api_routes_total),
            "estimated_cost": float(len(interface_gaps)),
            "machine_path": "/api/inventory/availability/scan",
            "human_path": "/gates",
        }
    )
    assets.append(
        {
            "asset_id": "runtime:web-api-usage-surface",
            "asset_type": "web_usage_surface",
            "name": "Web API usage surface",
            "linked_id": "web_api_usage_paths",
            "status": "tracked",
            "estimated_value": float(web_usage_paths_total),
            "estimated_cost": 0.0,
            "machine_path": "/api/inventory/availability/scan",
            "human_path": "/portfolio",
        }
    )

    counts: dict[str, int] = {}
    for row in assets:
        key = str(row.get("asset_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {
        "total": len(assets),
        "by_type": counts,
        "coverage": {
            "api_routes_total": api_routes_total,
            "web_api_usage_paths_total": web_usage_paths_total,
            "api_web_gap_count": len(interface_gaps),
        },
        "items": assets,
    }


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


def _traceability_maturity_assessment(
    *,
    specs_count: int,
    link_rows: list[dict],
    ideas_count: int,
) -> dict:
    """Calculate traceability maturity metrics for idea→spec→impl lineage.

    Tracks maturity dimensions:
    - Lineage coverage: % of specs with lineage links
    - Completeness: % of lineage links with all required fields
    - Evidence freshness: % of links with recent activity

    Spec: 061-traceability-maturity-governance.md
    """
    lineage_count = len(link_rows)

    # Count specs with lineage (from spec_id in links)
    specs_with_lineage = set()
    complete_links = 0
    incomplete_links = []

    for link in link_rows:
        spec_id = link.get("spec_id")
        if spec_id:
            specs_with_lineage.add(spec_id)

        # Check completeness
        idea_id = link.get("idea_id")
        contributors = link.get("contributors", {})
        impl_refs = link.get("implementation_refs", [])

        required_roles = ["idea", "spec", "implementation", "review"]
        missing_roles = [role for role in required_roles if not contributors.get(role)]

        is_complete = (
            bool(idea_id) and
            bool(spec_id) and
            len(missing_roles) == 0 and
            len(impl_refs) > 0
        )

        if is_complete:
            complete_links += 1
        else:
            errors = []
            if not idea_id:
                errors.append("missing_idea_id")
            if not spec_id:
                errors.append("missing_spec_id")
            if missing_roles:
                errors.extend([f"missing_contributor_{role}" for role in missing_roles])
            if not impl_refs:
                errors.append("missing_implementation_refs")

            incomplete_links.append({
                "lineage_id": link.get("id"),
                "spec_id": spec_id or "unknown",
                "errors": errors
            })

    # Calculate metrics
    lineage_coverage = round(len(specs_with_lineage) / specs_count, 4) if specs_count > 0 else 0.0
    completeness = round(complete_links / lineage_count, 4) if lineage_count > 0 else 0.0

    # Overall maturity score (0.0-1.0)
    # Weighted: 60% coverage + 40% completeness
    maturity_score = round((lineage_coverage * 0.6) + (completeness * 0.4), 4)

    # Maturity level
    if maturity_score >= 0.9:
        maturity_level = "excellent"
    elif maturity_score >= 0.75:
        maturity_level = "good"
    elif maturity_score >= 0.5:
        maturity_level = "fair"
    else:
        maturity_level = "needs_improvement"

    return {
        "principle": "Every spec must be traceable to an idea with complete contributor attribution.",
        "maturity_score": maturity_score,
        "maturity_level": maturity_level,
        "metrics": {
            "lineage_coverage": lineage_coverage,
            "lineage_coverage_pct": f"{lineage_coverage * 100:.1f}%",
            "completeness": completeness,
            "completeness_pct": f"{completeness * 100:.1f}%",
        },
        "counts": {
            "total_specs": specs_count,
            "specs_with_lineage": len(specs_with_lineage),
            "specs_without_lineage": specs_count - len(specs_with_lineage),
            "total_lineage_links": lineage_count,
            "complete_links": complete_links,
            "incomplete_links": len(incomplete_links),
        },
        "gaps": incomplete_links[:10] if incomplete_links else [],
        "enforcement": {
            "merge_time_gate": "active",
            "gate_spec": "061-traceability-maturity-governance.md",
            "workflow": ".github/workflows/spec-lineage-enforcement.yml",
            "validation_script": "scripts/validate_spec_lineage.py"
        },
        "improvement_targets": {
            "next_milestone": {
                "coverage": 0.95,
                "completeness": 0.98,
                "target_maturity": 0.96
            }
        }
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
    weights = _roi_weights()
    idea_multiplier = float(weights.get("idea_multiplier") or 1.0)
    estimated_roi_by_idea: dict[str, float] = {}
    for item in ideas:
        idea_id = str(item.get("id") or "")
        estimated_cost = float(item.get("estimated_cost") or 0.0)
        potential_value = float(item.get("potential_value") or 0.0)
        estimated_roi_by_idea[idea_id] = round((potential_value / estimated_cost) * idea_multiplier, 4) if estimated_cost > 0 else 0.0

    answered_questions: list[dict] = []
    unanswered_questions: list[dict] = []
    for idea in ideas_response.ideas:
        for q in idea.open_questions:
            row = {
                "idea_id": idea.id,
                "idea_name": idea.name,
                "question": q.question,
                "question_id": q.question_id,
                "parent_idea_id": q.parent_idea_id,
                "parent_question_id": q.parent_question_id,
                "evolved_from_answer_of": q.evolved_from_answer_of,
                "asked_by": q.asked_by,
                "answered_by": q.answered_by,
                "evidence_refs": q.evidence_refs,
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
    valid_idea_ids = {
        str(row.get("id") or "").strip()
        for row in ideas
        if isinstance(row, dict)
    }
    question_id_set = {
        str(row.get("question_id") or "").strip()
        for row in all_questions
        if isinstance(row, dict) and str(row.get("question_id") or "").strip()
    }
    linked_to_idea = [
        row
        for row in all_questions
        if isinstance(row, dict)
        and str(row.get("parent_idea_id") or "").strip() in valid_idea_ids
    ]
    linked_to_parent_question = [
        row
        for row in all_questions
        if isinstance(row, dict)
        and str(row.get("parent_question_id") or "").strip() in question_id_set
    ]
    unlinked_questions = [
        row
        for row in all_questions
        if isinstance(row, dict)
        and str(row.get("parent_idea_id") or "").strip() not in valid_idea_ids
        and str(row.get("parent_question_id") or "").strip() not in question_id_set
    ]
    answered_without_provenance = [
        row
        for row in answered_questions
        if isinstance(row, dict)
        and not str(row.get("answered_by") or "").strip()
    ]
    evolution_edges = [
        {
            "from_question_id": str(row.get("parent_question_id") or row.get("evolved_from_answer_of") or "").strip(),
            "to_question_id": str(row.get("question_id") or "").strip(),
            "idea_id": str(row.get("idea_id") or "").strip(),
        }
        for row in all_questions
        if isinstance(row, dict)
        and (
            str(row.get("parent_question_id") or "").strip()
            or str(row.get("evolved_from_answer_of") or "").strip()
        )
        and str(row.get("question_id") or "").strip()
    ]

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
        estimated_roi = round((potential_value / estimated_cost) * idea_multiplier, 4) if estimated_cost > 0 else 0.0
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
    traceability_maturity = _traceability_maturity_assessment(
        specs_count=len(spec_items),
        link_rows=link_rows,
        ideas_count=len(ideas),
    )
    interface_gaps, web_usage_paths, api_routes_total = _api_web_gap_rows()
    assets = _build_asset_registry(
        ideas=ideas,
        spec_items=spec_items,
        api_routes_total=api_routes_total,
        web_usage_paths_total=len(web_usage_paths),
        interface_gaps=interface_gaps,
    )
    estimator_state = _read_roi_estimator_state()

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
        "question_ontology": {
            "principle": "Every question/answer is linked to an idea or higher-level parent question.",
            "total_questions": len(all_questions),
            "linked_to_idea_count": len(linked_to_idea),
            "linked_to_parent_question_count": len(linked_to_parent_question),
            "unlinked_count": len(unlinked_questions),
            "answered_without_provenance_count": len(answered_without_provenance),
            "evolution_edges_count": len(evolution_edges),
            "unlinked": unlinked_questions[:50],
            "answered_without_provenance": answered_without_provenance[:50],
            "evolution_edges": evolution_edges[:200],
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
        "assets": assets,
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
        "roi_estimator": {
            "weights": estimator_state.get("weights", {}),
            "measurement_events_count": len(estimator_state.get("measurement_events") or []),
            "calibration_runs_count": len(estimator_state.get("calibration_runs") or []),
            "updated_at": estimator_state.get("updated_at"),
            "api": {
                "estimator": "/api/inventory/roi/estimator",
                "measurements": "/api/inventory/roi/estimator/measurements",
                "calibrate": "/api/inventory/roi/estimator/calibrate",
                "weights": "/api/inventory/roi/estimator/weights",
            },
        },
        "next_roi_work": {
            "selection_basis": "highest_idea_estimated_roi_then_question_roi",
            "item": next_question,
        },
        "operating_console": operating_console_status,
        "evidence_contract": evidence_contract,
        "tracking_mechanism": tracking_mechanism,
        "traceability_maturity": traceability_maturity,
        "availability_gaps": {
            "principle": "No gap between machine API and human web availability.",
            "why_previously_missed": (
                "Prior workflow tracked canonical milestone routes and runtime telemetry, but lacked "
                "automated full API-route to web-usage parity scanning."
            ),
            "api_routes_total": api_routes_total,
            "web_api_usage_paths_total": len(web_usage_paths),
            "unavailable_in_web_count": len(interface_gaps),
            "unavailable_in_web": interface_gaps[:100],
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


def get_roi_estimator(runtime_window_seconds: int = 86400) -> dict:
    state = _read_roi_estimator_state()
    inventory = build_system_lineage_inventory(runtime_window_seconds=runtime_window_seconds)
    live = _extract_roi_observations(inventory)
    manual = _extract_manual_observations(state)
    merged_ideas = [*live["ideas"], *manual["ideas"]]
    merged_questions = [*live["questions"], *manual["questions"]]
    suggestions = _suggested_multipliers(merged_ideas, merged_questions)

    def _mae(rows: list[dict]) -> float | None:
        errors = [abs(float(row.get("error") or 0.0)) for row in rows if isinstance(row.get("error"), (int, float))]
        if not errors:
            return None
        return round(sum(errors) / float(len(errors)), 6)

    return {
        "version": state.get("version", 1),
        "updated_at": state.get("updated_at"),
        "formula": {
            "idea_estimated_roi": "((potential_value * confidence) / (estimated_cost + resistance_risk)) * idea_multiplier",
            "question_estimated_roi": "(value_to_whole / estimated_cost) * question_multiplier",
            "answer_measured_roi": "(measured_delta / estimated_cost) * answer_multiplier",
        },
        "weights": state.get("weights", {}),
        "observations": {
            "idea_samples": len(merged_ideas),
            "question_samples": len(merged_questions),
            "idea_mae": _mae(merged_ideas),
            "question_mae": _mae(merged_questions),
            "latest_manual_measurements": (state.get("measurement_events") or [])[-10:],
        },
        "suggested_weights": suggestions,
        "calibration_runs": (state.get("calibration_runs") or [])[-20:],
    }


def update_roi_estimator_weights(
    *,
    idea_multiplier: float | None = None,
    question_multiplier: float | None = None,
    answer_multiplier: float | None = None,
    updated_by: str | None = None,
) -> dict:
    state = _read_roi_estimator_state()
    weights = state.get("weights") if isinstance(state.get("weights"), dict) else {}
    if idea_multiplier is not None:
        weights["idea_multiplier"] = round(float(idea_multiplier), 6)
    if question_multiplier is not None:
        weights["question_multiplier"] = round(float(question_multiplier), 6)
    if answer_multiplier is not None:
        weights["answer_multiplier"] = round(float(answer_multiplier), 6)
    state["weights"] = weights
    runs = state.get("calibration_runs") if isinstance(state.get("calibration_runs"), list) else []
    runs.append(
        {
            "type": "manual_update",
            "applied": True,
            "updated_by": str(updated_by or "unknown"),
            "applied_weights": weights,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    state["calibration_runs"] = runs[-200:]
    _write_roi_estimator_state(state)
    return get_roi_estimator()


def record_roi_measurement(
    *,
    subject_type: str,
    subject_id: str,
    idea_id: str | None = None,
    estimated_roi: float | None = None,
    actual_roi: float | None = None,
    actual_value: float | None = None,
    actual_cost: float | None = None,
    measured_delta: float | None = None,
    estimated_cost: float | None = None,
    source: str = "api",
    measured_by: str | None = None,
    evidence_refs: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    normalized_subject_type = str(subject_type or "").strip().lower()
    normalized_subject_id = str(subject_id or "").strip()
    if normalized_subject_type not in {"idea", "question"}:
        return {"result": "invalid_subject_type"}
    if not normalized_subject_id:
        return {"result": "invalid_subject_id"}

    inferred_estimated = estimated_roi
    inferred_actual = actual_roi
    inferred_idea_id = str(idea_id or "").strip() or None
    inferred_estimated_cost = estimated_cost

    if normalized_subject_type == "idea":
        roi_rows = inventory.get("roi_insights", {}).get("most_estimated_roi")
        if isinstance(roi_rows, list):
            match = next(
                (
                    row for row in roi_rows
                    if isinstance(row, dict) and str(row.get("idea_id") or "").strip() == normalized_subject_id
                ),
                None,
            )
            if isinstance(match, dict):
                if inferred_estimated is None:
                    inferred_estimated = float(match.get("estimated_roi") or 0.0)
                if inferred_actual is None and isinstance(match.get("actual_roi"), (int, float)):
                    inferred_actual = float(match.get("actual_roi") or 0.0)
                if inferred_estimated_cost is None:
                    inferred_estimated_cost = float(match.get("estimated_cost") or 0.0)
    else:
        answered = inventory.get("questions", {}).get("answered")
        unanswered = inventory.get("questions", {}).get("unanswered")
        candidates = [*(answered if isinstance(answered, list) else []), *(unanswered if isinstance(unanswered, list) else [])]
        match = next(
            (
                row
                for row in candidates
                if isinstance(row, dict)
                and (
                    str(row.get("question_id") or "").strip() == normalized_subject_id
                    or str(row.get("question") or "").strip() == normalized_subject_id
                )
            ),
            None,
        )
        if isinstance(match, dict):
            inferred_idea_id = inferred_idea_id or str(match.get("idea_id") or "").strip() or None
            if inferred_estimated is None:
                inferred_estimated = float(match.get("question_roi") or 0.0)
            if inferred_estimated_cost is None:
                inferred_estimated_cost = float(match.get("estimated_cost") or 0.0)
            if inferred_actual is None and match.get("measured_delta") is not None:
                candidate_actual = _safe_ratio(float(match.get("measured_delta") or 0.0), float(match.get("estimated_cost") or 0.0))
                if candidate_actual is not None:
                    inferred_actual = candidate_actual

    if inferred_actual is None:
        candidate_actual = _safe_ratio(actual_value, actual_cost)
        if candidate_actual is not None:
            inferred_actual = candidate_actual
    if inferred_actual is None:
        candidate_actual = _safe_ratio(measured_delta, inferred_estimated_cost)
        if candidate_actual is not None:
            inferred_actual = candidate_actual
    if inferred_estimated is None and inferred_estimated_cost is not None:
        candidate_estimated = _safe_ratio(actual_value, inferred_estimated_cost)
        if candidate_estimated is not None:
            inferred_estimated = candidate_estimated

    if inferred_estimated is None or inferred_actual is None:
        return {
            "result": "insufficient_measurement_data",
            "required": [
                "estimated_roi or inferable estimate from idea/question",
                "actual_roi or pair (actual_value,actual_cost) or (measured_delta,estimated_cost)",
            ],
        }

    base_estimated = float(inferred_estimated)
    event = {
        "subject_type": normalized_subject_type,
        "subject_id": normalized_subject_id,
        "idea_id": inferred_idea_id,
        "estimated_base": round(base_estimated, 6),
        "actual_roi": round(float(inferred_actual), 6),
        "error": round(float(inferred_actual) - base_estimated, 6),
        "ratio": round(float(inferred_actual) / base_estimated, 6) if base_estimated > 0 else None,
        "source": str(source or "api"),
        "measured_by": str(measured_by or "unknown"),
        "evidence_refs": [str(x) for x in (evidence_refs or []) if str(x).strip()],
        "notes": str(notes or "").strip() or None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    state = _read_roi_estimator_state()
    events = state.get("measurement_events") if isinstance(state.get("measurement_events"), list) else []
    events.append(event)
    state["measurement_events"] = events[-2000:]
    _write_roi_estimator_state(state)
    return {
        "result": "measurement_recorded",
        "measurement": event,
        "estimator": get_roi_estimator(),
    }


def calibrate_roi_estimator(
    *,
    apply: bool = True,
    min_samples: int = 3,
    calibrated_by: str | None = None,
) -> dict:
    state = _read_roi_estimator_state()
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    live = _extract_roi_observations(inventory)
    manual = _extract_manual_observations(state)
    idea_obs = [*live["ideas"], *manual["ideas"]]
    question_obs = [*live["questions"], *manual["questions"]]
    suggested = _suggested_multipliers(idea_obs, question_obs)

    can_apply = (
        int(suggested.get("idea_samples") or 0) >= int(min_samples)
        or int(suggested.get("question_samples") or 0) >= int(min_samples)
    )
    applied = bool(apply and can_apply)
    if applied:
        state["weights"] = {
            "idea_multiplier": float(suggested["idea_multiplier"]),
            "question_multiplier": float(suggested["question_multiplier"]),
            "answer_multiplier": float(suggested["answer_multiplier"]),
        }

    runs = state.get("calibration_runs") if isinstance(state.get("calibration_runs"), list) else []
    run = {
        "type": "auto_calibration",
        "applied": applied,
        "can_apply": can_apply,
        "calibrated_by": str(calibrated_by or "system"),
        "min_samples": int(min_samples),
        "sample_counts": {
            "idea_samples": int(suggested.get("idea_samples") or 0),
            "question_samples": int(suggested.get("question_samples") or 0),
        },
        "suggested_weights": {
            "idea_multiplier": float(suggested["idea_multiplier"]),
            "question_multiplier": float(suggested["question_multiplier"]),
            "answer_multiplier": float(suggested["answer_multiplier"]),
        },
        "applied_weights": state.get("weights"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    runs.append(run)
    state["calibration_runs"] = runs[-200:]
    _write_roi_estimator_state(state)
    return {
        "result": "calibrated" if applied else "calibration_suggested_only",
        "run": run,
        "estimator": get_roi_estimator(),
    }


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


def scan_api_web_availability_gaps(create_tasks: bool = False) -> dict:
    gap_rows, web_usage_paths, api_routes_total = _api_web_gap_rows()
    generated_tasks: list[dict] = []
    if create_tasks:
        for gap in gap_rows:
            method = str(gap.get("method") or "GET")
            path = str(gap.get("path") or "")
            signature = f"api_web_gap::{method}::{path}"
            direction = (
                f"API/web availability gap: {method} {path} has machine availability but no web UI usage path. "
                "Implement or wire a human web UI flow, add tests, and verify parity in availability scan."
            )
            task = _create_or_reuse_issue_task(
                condition="api_web_availability_gap",
                signature=signature,
                direction=direction,
                context={
                    "path": path,
                    "method": method,
                    "source_file": gap.get("source_file"),
                    "gap_type": gap.get("gap_type"),
                },
            )
            generated_tasks.append({"path": path, "method": method, "task": task})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "principle": "No gap between machine API and human web availability.",
        "why_previously_missed": (
            "Canonical route tracking and runtime checks covered only milestone surfaces; no automated scanner compared "
            "all API route declarations against web UI API usage paths."
        ),
        "api_routes_total": api_routes_total,
        "web_api_usage_paths_total": len(web_usage_paths),
        "gaps_count": len(gap_rows),
        "gaps": gap_rows,
        "create_tasks": create_tasks,
        "generated_tasks": generated_tasks,
    }


def list_assets_inventory(asset_type: str | None = None, limit: int = 500) -> dict:
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    assets = inventory.get("assets", {}).get("items")
    rows = [row for row in (assets if isinstance(assets, list) else []) if isinstance(row, dict)]
    if asset_type:
        token = asset_type.strip().lower()
        rows = [row for row in rows if str(row.get("asset_type") or "").strip().lower() == token]
    rows = rows[: max(1, min(limit, 5000))]
    return {
        "generated_at": inventory.get("generated_at"),
        "total": len(rows),
        "asset_type": asset_type,
        "items": rows,
        "coverage": inventory.get("assets", {}).get("coverage"),
        "by_type": inventory.get("assets", {}).get("by_type"),
    }


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
