"""Unified inventory service for ideas, questions, specs, implementations, and usage."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.agent import AgentTaskCreate, TaskType
from app.models.spec_registry import SpecRegistryCreate, SpecRegistryUpdate
from app.services import (
    agent_service,
    idea_lineage_service,
    idea_service,
    route_registry_service,
    runtime_service,
    spec_registry_service,
    value_lineage_service,
)


def _question_roi(value_to_whole: float, estimated_cost: float) -> float:
    if estimated_cost <= 0:
        return 0.0
    return round(float(value_to_whole) / float(estimated_cost), 4)


def _answer_roi(measured_delta: float | None, estimated_cost: float) -> float:
    if measured_delta is None or estimated_cost <= 0:
        return 0.0
    return round(float(measured_delta) / float(estimated_cost), 4)


IMPLEMENTATION_REQUEST_PATTERN = re.compile(
    r"\b(implement|implementation|build|create|add|fix|integrate|ship|expose|wire|develop)\b",
    re.IGNORECASE,
)

_FLOW_STAGE_ORDER: tuple[str, ...] = ("spec", "process", "implementation", "validation")
_FLOW_STAGE_ESTIMATED_COST: dict[str, float] = {
    "spec": 2.0,
    "process": 3.0,
    "implementation": 5.0,
    "validation": 2.0,
}
_FLOW_STAGE_TASK_TYPE: dict[str, TaskType] = {
    "spec": TaskType.SPEC,
    "process": TaskType.SPEC,
    "implementation": TaskType.IMPL,
    "validation": TaskType.TEST,
}
_TRACEABILITY_GAP_DEFAULT_IDEA_ID = "portfolio-governance"
_TRACEABILITY_GAP_CONTRIBUTOR_ID = "openai-codex"
_PROCESS_COMPLETENESS_TASK_TYPE_BY_CHECK: dict[str, TaskType] = {
    "ideas_have_standing_questions": TaskType.SPEC,
    "specs_linked_to_ideas": TaskType.SPEC,
    "specs_have_process_and_pseudocode": TaskType.SPEC,
    "ideas_have_specs": TaskType.SPEC,
    "endpoints_have_idea_mapping": TaskType.IMPL,
    "endpoints_have_spec_coverage": TaskType.SPEC,
    "endpoints_have_process_coverage": TaskType.IMPL,
    "endpoints_have_validation_coverage": TaskType.TEST,
    "all_endpoints_have_usage_events": TaskType.TEST,
    "canonical_route_registry_complete": TaskType.IMPL,
    "assets_are_modular_and_reusable": TaskType.SPEC,
}

_ASSET_MODULARITY_LIMITS: dict[str, int] = {
    "idea_description_sentences": 10,
    "idea_description_chars": 1800,
    "spec_summary_sentences": 10,
    "spec_summary_chars": 2000,
    "process_summary_sentences": 10,
    "process_summary_chars": 2000,
    "pseudocode_summary_sentences": 10,
    "pseudocode_summary_chars": 2200,
    "implementation_summary_sentences": 10,
    "implementation_summary_chars": 2200,
    "implementation_file_lines": 450,
}


def _is_implementation_request_question(question: str, answer: str | None = None) -> bool:
    text = f"{question or ''} {answer or ''}".strip()
    if not text:
        return False
    return IMPLEMENTATION_REQUEST_PATTERN.search(text) is not None


def _question_fingerprint(idea_id: str, question: str) -> str:
    payload = f"{idea_id.strip().lower()}::{question.strip().lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _flow_unblock_fingerprint(idea_id: str, blocking_stage: str) -> str:
    payload = f"flow-unblock::{idea_id.strip().lower()}::{blocking_stage.strip().lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _clamp_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(numeric, 1.0))


def _build_unblock_direction(
    idea_id: str,
    idea_name: str,
    blocking_stage: str,
    blocked_stages: list[str],
    spec_ids: list[str],
) -> str:
    blocked_text = ", ".join(blocked_stages) if blocked_stages else "flow completion"
    if blocking_stage == "spec":
        return (
            f"Unblock idea '{idea_id}' ({idea_name}) by adding/updating spec coverage. "
            f"This unlocks: {blocked_text}. Define acceptance checks and link to process and implementation."
        )
    if blocking_stage == "process":
        spec_hint = ", ".join(spec_ids[:5]) if spec_ids else "linked spec"
        return (
            f"Unblock idea '{idea_id}' ({idea_name}) by defining process and pseudocode grounded in {spec_hint}. "
            f"This unlocks: {blocked_text}."
        )
    if blocking_stage == "implementation":
        return (
            f"Unblock idea '{idea_id}' ({idea_name}) by implementing the tracked spec/process artifacts "
            f"and linking code references. This unlocks: {blocked_text}."
        )
    return (
        f"Unblock idea '{idea_id}' ({idea_name}) by validating the current implementation "
        "with local, CI, deploy, and e2e evidence updates."
    )


def _build_flow_interdependencies(
    *,
    idea_id: str,
    idea_name: str,
    spec_tracked: bool,
    process_tracked: bool,
    implementation_tracked: bool,
    validation_tracked: bool,
    spec_ids: list[str],
    idea_value_gap: float,
    idea_confidence: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    stage_tracked = {
        "spec": bool(spec_tracked),
        "process": bool(process_tracked),
        "implementation": bool(implementation_tracked),
        "validation": bool(validation_tracked),
    }
    missing = [stage for stage in _FLOW_STAGE_ORDER if not stage_tracked[stage]]
    if not missing:
        return (
            {
                "blocked": False,
                "blocking_stage": None,
                "upstream_required": [],
                "downstream_blocked": [],
                "estimated_unblock_cost": 0.0,
                "estimated_unblock_value": 0.0,
                "unblock_priority_score": 0.0,
                "task_fingerprint": None,
                "next_unblock_task": None,
            },
            None,
        )

    blocking_stage = missing[0]
    stage_index = _FLOW_STAGE_ORDER.index(blocking_stage)
    upstream_required = list(_FLOW_STAGE_ORDER[:stage_index])
    downstream_blocked = [stage for stage in _FLOW_STAGE_ORDER[stage_index + 1 :] if not stage_tracked[stage]]
    stage_cost = float(_FLOW_STAGE_ESTIMATED_COST.get(blocking_stage, 1.0))
    confidence = _clamp_confidence(idea_confidence)
    value_gap = max(float(idea_value_gap), 0.0)
    unlock_multiplier = (len(downstream_blocked) + 1) / max(1.0, float(len(_FLOW_STAGE_ORDER)))
    unlock_value = round(value_gap * confidence * unlock_multiplier, 4)
    priority_score = _question_roi(unlock_value, stage_cost)
    fingerprint = _flow_unblock_fingerprint(idea_id, blocking_stage)
    direction = _build_unblock_direction(
        idea_id=idea_id,
        idea_name=idea_name,
        blocking_stage=blocking_stage,
        blocked_stages=downstream_blocked,
        spec_ids=spec_ids,
    )
    task_type = _FLOW_STAGE_TASK_TYPE.get(blocking_stage, TaskType.IMPL)
    candidate = {
        "idea_id": idea_id,
        "idea_name": idea_name,
        "blocking_stage": blocking_stage,
        "upstream_required": upstream_required,
        "downstream_blocked": downstream_blocked,
        "estimated_unblock_cost": stage_cost,
        "estimated_unblock_value": unlock_value,
        "unblock_priority_score": priority_score,
        "task_fingerprint": fingerprint,
        "task_type": task_type.value,
        "direction": direction,
    }

    return (
        {
            "blocked": True,
            "blocking_stage": blocking_stage,
            "upstream_required": upstream_required,
            "downstream_blocked": downstream_blocked,
            "estimated_unblock_cost": stage_cost,
            "estimated_unblock_value": unlock_value,
            "unblock_priority_score": priority_score,
            "task_fingerprint": fingerprint,
            "next_unblock_task": {
                "task_type": task_type.value,
                "direction": direction,
            },
        },
        candidate,
    )


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

        direction = (
            f"Implementation request for idea '{idea_id}': {question} "
            "Produce a measurable artifact (spec->test->impl), link evidence, and update ROI signals."
        )
        if answer:
            direction += f" Use this answer as implementation contract: {answer}"

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


_SPEC_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": [], "source": "none"}
_SPEC_DISCOVERY_CACHE_TTL_SECONDS = 300.0
_EVIDENCE_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": [], "source": "none"}
_EVIDENCE_DISCOVERY_CACHE_TTL_SECONDS = 180.0
_ROUTE_PROBE_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "item": None, "source": "none"}
_ROUTE_PROBE_DISCOVERY_CACHE_TTL_SECONDS = 180.0
_ROUTE_PROBE_LATEST_FILE = "route_evidence_probe_latest.json"


def _project_root() -> Path:
    configured = os.getenv("COHERENCE_PROJECT_ROOT", "").strip()
    if configured:
        configured_path = Path(configured).expanduser().resolve()
        if configured_path.exists():
            return configured_path

    source_path = Path(__file__).resolve()
    for candidate in [source_path, *source_path.parents]:
        has_monorepo_layout = (candidate / "api" / "app").exists()
        has_api_service_layout = (candidate / "app").exists() and (candidate / "scripts").exists()
        if has_monorepo_layout or has_api_service_layout:
            return candidate
    return source_path.parents[3]


def _tracking_repository() -> str:
    return os.getenv("TRACKING_REPOSITORY", "seeker71/Coherence-Network")


def _tracking_ref() -> str:
    return os.getenv("TRACKING_REPOSITORY_REF", "main")


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _sort_spec_items(rows: list[dict]) -> list[dict]:
    def key(row: dict) -> tuple[int, int, str]:
        spec_id = str(row.get("spec_id") or "")
        if spec_id.isdigit():
            return (0, int(spec_id), "")
        return (1, 0, spec_id)

    return sorted(rows, key=key)


def _discover_specs_local(limit: int = 300) -> list[dict]:
    specs_dir = _project_root() / "specs"
    if not specs_dir.exists():
        return []
    files = sorted(specs_dir.glob("*.md"))
    out: list[dict] = []
    for path in files[: max(1, min(limit, 2000))]:
        stem = path.stem
        spec_id = stem.split("-", 1)[0] if "-" in stem else stem
        title = stem.replace("-", " ")
        try:
            for line in path.read_text(encoding="utf-8").splitlines()[:8]:
                if line.lstrip().startswith("#"):
                    title = line.lstrip("#").strip()
                    break
        except OSError:
            pass
        out.append(
            {
                "spec_id": spec_id,
                "title": title,
                "path": f"specs/{path.name}",
            }
        )
    return _sort_spec_items(out)


def _discover_specs_from_github(limit: int = 300, timeout: float = 8.0) -> list[dict]:
    now = time.time()
    cached = _SPEC_DISCOVERY_CACHE.get("items")
    if isinstance(cached, list) and _SPEC_DISCOVERY_CACHE.get("expires_at", 0.0) > now:
        return [item for item in cached if isinstance(item, dict)][: max(1, min(limit, 2000))]

    repository = _tracking_repository()
    ref = _tracking_ref()
    url = f"https://api.github.com/repos/{repository}/contents/specs"
    out: list[dict] = []
    try:
        with httpx.Client(timeout=timeout, headers=_github_headers()) as client:
            response = client.get(url, params={"ref": ref})
            response.raise_for_status()
            rows = response.json()
        if not isinstance(rows, list):
            return []
        for row in rows[: max(1, min(limit, 2000))]:
            if not isinstance(row, dict):
                continue
            path = row.get("path")
            if not isinstance(path, str) or not path.startswith("specs/") or not path.endswith(".md"):
                continue
            name = row.get("name") if isinstance(row.get("name"), str) else Path(path).name
            stem = Path(name).stem
            spec_id = stem.split("-", 1)[0] if "-" in stem else stem
            title = stem.replace("-", " ")
            out.append({"spec_id": spec_id, "title": title, "path": path})
    except httpx.HTTPError:
        return []

    out = _sort_spec_items(out)
    _SPEC_DISCOVERY_CACHE["items"] = out
    _SPEC_DISCOVERY_CACHE["expires_at"] = now + _SPEC_DISCOVERY_CACHE_TTL_SECONDS
    _SPEC_DISCOVERY_CACHE["source"] = "github"
    return out


def _discover_specs(limit: int = 300) -> tuple[list[dict], str]:
    local = _discover_specs_local(limit=limit)
    # If local checkout is sparse (e.g., deployment package without root specs), use GitHub source of truth.
    if len(local) >= 5:
        return local, "local"

    remote = _discover_specs_from_github(limit=limit)
    if remote:
        if local:
            by_path = {str(item.get("path")): item for item in remote}
            for item in local:
                path = str(item.get("path"))
                if path and path not in by_path:
                    by_path[path] = item
            return _sort_spec_items(list(by_path.values())), "local+github"
        return remote, "github"

    if local:
        return local, "local"
    return [], "none"


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
    spec_items, spec_source = _discover_specs()
    tracked_idea_ids = idea_service.list_tracked_idea_ids()
    runtime_events = runtime_service.list_events(limit=10000)

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
            "source": spec_source,
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
        "tracking": {
            "tracked_idea_ids_count": len(tracked_idea_ids),
            "tracked_idea_ids": tracked_idea_ids,
            "spec_discovery_source": spec_source,
            "runtime_events_count": len(runtime_events),
            "commit_evidence_local_available": (_project_root() / "docs" / "system_audit").exists(),
        },
    }


def next_highest_roi_task_from_answered_questions(create_task: bool = False) -> dict:
    sync_report = sync_implementation_request_question_tasks()
    inventory = build_system_lineage_inventory(runtime_window_seconds=86400)
    answered = inventory.get("questions", {}).get("answered", [])
    if not isinstance(answered, list) or not answered:
        return {
            "result": "no_answered_questions",
            "implementation_request_sync": sync_report,
        }

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
    question_fingerprint = _question_fingerprint(idea_id, question)
    question_roi = float(top.get("question_roi") or 0.0)
    answer_roi = float(top.get("answer_roi") or 0.0)

    existing_active = agent_service.find_active_task_by_fingerprint(question_fingerprint)

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
        "implementation_request_sync": sync_report,
        "task_fingerprint": question_fingerprint,
    }
    if existing_active is not None:
        report["active_task"] = {
            "id": existing_active.get("id"),
            "status": (
                existing_active["status"].value
                if hasattr(existing_active.get("status"), "value")
                else str(existing_active.get("status"))
            ),
            "claimed_by": existing_active.get("claimed_by"),
        }
        if create_task:
            report["result"] = "task_already_active"
            return report

    if not create_task:
        return report

    task = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.IMPL,
            context={
                "source": "inventory_high_roi",
                "idea_id": idea_id,
                "question": question,
                "question_fingerprint": question_fingerprint,
                "task_fingerprint": question_fingerprint,
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


def _commit_evidence_dir() -> Path:
    custom = os.getenv("IDEA_COMMIT_EVIDENCE_DIR")
    if custom:
        return Path(custom)
    return _project_root() / "docs" / "system_audit"


def _normalize_validation_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"pass", "fail", "pending"}:
        return status
    return "pending"


def _read_commit_evidence_records(limit: int = 400) -> list[dict[str, Any]]:
    evidence_dir = _commit_evidence_dir()
    files = []
    if evidence_dir.exists():
        files = sorted(evidence_dir.glob("commit_evidence_*.json"))[: max(1, min(limit, 3000))]
    out: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        payload["_evidence_file"] = str(path)
        out.append(payload)
    if out:
        return out

    now = time.time()
    cached = _EVIDENCE_DISCOVERY_CACHE.get("items")
    if isinstance(cached, list) and _EVIDENCE_DISCOVERY_CACHE.get("expires_at", 0.0) > now:
        return [item for item in cached if isinstance(item, dict)][: max(1, min(limit, 3000))]

    repository = _tracking_repository()
    ref = _tracking_ref()
    list_url = f"https://api.github.com/repos/{repository}/contents/docs/system_audit"
    remote_out: list[dict[str, Any]] = []
    has_token = bool(os.getenv("GITHUB_TOKEN"))
    try:
        with httpx.Client(timeout=8.0, headers=_github_headers()) as client:
            response = client.get(list_url, params={"ref": ref})
            response.raise_for_status()
            rows = response.json()
            if isinstance(rows, list):
                # Unauthenticated GitHub API calls are heavily rate-limited.
                remote_limit = min(limit, 200 if has_token else 20)
                evidence_rows = [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and isinstance(row.get("name"), str)
                    and row["name"].startswith("commit_evidence_")
                    and row["name"].endswith(".json")
                ]
                evidence_rows.sort(key=lambda row: str(row.get("name") or ""), reverse=True)
                evidence_rows = evidence_rows[: max(1, remote_limit)]
                for row in evidence_rows:
                    download_url = row.get("download_url")
                    if not isinstance(download_url, str) or not download_url:
                        continue
                    payload_resp = client.get(download_url)
                    if payload_resp.status_code != 200:
                        continue
                    try:
                        payload = payload_resp.json()
                    except ValueError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    payload["_evidence_file"] = str(row.get("path") or row.get("name") or "github")
                    remote_out.append(payload)
    except (httpx.HTTPError, TypeError):
        remote_out = []

    _EVIDENCE_DISCOVERY_CACHE["items"] = remote_out
    _EVIDENCE_DISCOVERY_CACHE["expires_at"] = now + _EVIDENCE_DISCOVERY_CACHE_TTL_SECONDS
    _EVIDENCE_DISCOVERY_CACHE["source"] = "github" if remote_out else "none"
    return remote_out


def _parse_record_datetime(record: dict[str, Any]) -> datetime:
    candidates = [
        record.get("updated_at"),
        record.get("created_at"),
        record.get("date"),
    ]
    for raw in candidates:
        if not isinstance(raw, str) or not raw.strip():
            continue
        value = raw.strip()
        try:
            if len(value) == 10 and value.count("-") == 2:
                return datetime.fromisoformat(f"{value}T00:00:00+00:00")
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return datetime.fromtimestamp(0, tz=timezone.utc)


def _latest_commit_evidence_records(limit: int = 20) -> list[dict[str, Any]]:
    requested = max(1, min(limit, 200))
    rows = _read_commit_evidence_records(limit=max(requested * 5, 200))
    sorted_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: (
            _parse_record_datetime(row),
            str(row.get("_evidence_file") or ""),
        ),
        reverse=True,
    )
    return sorted_rows[:requested]


def _route_evidence_probe_dir() -> Path:
    custom = os.getenv("ROUTE_EVIDENCE_PROBE_DIR")
    if custom:
        return Path(custom)
    return _project_root() / "docs" / "system_audit"


def _read_latest_route_evidence_probe() -> dict[str, Any] | None:
    probe_dir = _route_evidence_probe_dir()
    if not probe_dir.exists():
        local_payload = None
    else:
        files = sorted(probe_dir.glob("route_evidence_probe_*.json"))
        if not files:
            local_payload = None
        else:
            latest = max(files, key=lambda path: path.stat().st_mtime)
            try:
                payload = json.loads(latest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                local_payload = None
            else:
                if isinstance(payload, dict):
                    payload["_probe_file"] = str(latest)
                    local_payload = payload
                else:
                    local_payload = None
    if local_payload is not None:
        return local_payload

    now = time.time()
    cached = _ROUTE_PROBE_DISCOVERY_CACHE.get("item")
    if isinstance(cached, dict) and _ROUTE_PROBE_DISCOVERY_CACHE.get("expires_at", 0.0) > now:
        return dict(cached)

    repository = _tracking_repository()
    ref = _tracking_ref()
    raw_latest_url = (
        f"https://raw.githubusercontent.com/{repository}/{ref}/docs/system_audit/{_ROUTE_PROBE_LATEST_FILE}"
    )
    list_url = f"https://api.github.com/repos/{repository}/contents/docs/system_audit"
    remote_payload: dict[str, Any] | None = None
    try:
        with httpx.Client(timeout=8.0, headers=_github_headers()) as client:
            raw_latest = client.get(raw_latest_url)
            if raw_latest.status_code == 200:
                try:
                    payload = raw_latest.json()
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    payload["_probe_file"] = f"docs/system_audit/{_ROUTE_PROBE_LATEST_FILE}"
                    remote_payload = payload
            if remote_payload is not None:
                _ROUTE_PROBE_DISCOVERY_CACHE["item"] = dict(remote_payload)
                _ROUTE_PROBE_DISCOVERY_CACHE["expires_at"] = now + _ROUTE_PROBE_DISCOVERY_CACHE_TTL_SECONDS
                _ROUTE_PROBE_DISCOVERY_CACHE["source"] = "github-raw-latest"
                return remote_payload

            response = client.get(list_url, params={"ref": ref})
            response.raise_for_status()
            rows = response.json()
            if isinstance(rows, list):
                probes = [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and isinstance(row.get("name"), str)
                    and row["name"].startswith("route_evidence_probe_")
                    and row["name"].endswith(".json")
                ]
                probes.sort(key=lambda row: str(row.get("name") or ""), reverse=True)
                for row in probes[:5]:
                    download_url = row.get("download_url")
                    if not isinstance(download_url, str) or not download_url:
                        continue
                    payload_resp = client.get(download_url)
                    if payload_resp.status_code != 200:
                        continue
                    try:
                        payload = payload_resp.json()
                    except ValueError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    payload["_probe_file"] = str(row.get("path") or row.get("name") or "github")
                    remote_payload = payload
                    break
    except httpx.HTTPError:
        remote_payload = None

    _ROUTE_PROBE_DISCOVERY_CACHE["item"] = dict(remote_payload) if isinstance(remote_payload, dict) else None
    _ROUTE_PROBE_DISCOVERY_CACHE["expires_at"] = now + _ROUTE_PROBE_DISCOVERY_CACHE_TTL_SECONDS
    _ROUTE_PROBE_DISCOVERY_CACHE["source"] = "github" if remote_payload is not None else "none"
    return remote_payload


def _normalize_endpoint_path(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme else raw
    path = path.split("?", 1)[0].strip()
    if not path:
        return "/"
    if not path.startswith("/"):
        path = f"/{path}"
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def _path_template_matches(path_template: str, concrete_path: str) -> bool:
    template = _normalize_endpoint_path(path_template)
    concrete = _normalize_endpoint_path(concrete_path)
    if not template or not concrete:
        return False
    if template == concrete:
        return True
    escaped = re.escape(template)
    escaped = re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped)
    escaped = re.sub(r"\\\[[^\[\]]+\\\]", r"[^/]+", escaped)
    pattern = f"^{escaped}$"
    return re.match(pattern, concrete) is not None


def _public_endpoint_reference_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        e2e = record.get("e2e_validation")
        if not isinstance(e2e, dict):
            continue
        endpoints = e2e.get("public_endpoints")
        if not isinstance(endpoints, list):
            continue
        for endpoint in endpoints:
            normalized = _normalize_endpoint_path(str(endpoint))
            if not normalized:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _count_matching_public_references(path_template: str, reference_counts: dict[str, int]) -> int:
    if not reference_counts:
        return 0
    total = 0
    for path, count in reference_counts.items():
        if _path_template_matches(path_template, path):
            total += int(count)
    return total


def _probe_api_rows_by_key(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    rows = payload.get("api")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        method = str(row.get("method") or "").strip().upper()
        path = _normalize_endpoint_path(str(row.get("path_template") or row.get("path") or ""))
        if not method or not path:
            continue
        status = row.get("status_code")
        status_code = None
        try:
            status_code = int(status)
        except (TypeError, ValueError):
            status_code = None
        probe_method = str(row.get("probe_method") or ("GET" if method == "GET" else "OPTIONS")).strip().upper()
        data_present_raw = row.get("data_present")
        data_present = bool(data_present_raw) if isinstance(data_present_raw, bool) else None
        probe_ok = bool(row.get("probe_ok")) if isinstance(row.get("probe_ok"), bool) else False
        out[(method, path)] = {
            "status_code": status_code,
            "probe_method": probe_method,
            "data_present": data_present,
            "probe_ok": probe_ok,
        }
    return out


def _probe_web_rows_by_path(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = payload.get("web")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = _normalize_endpoint_path(str(row.get("path_template") or row.get("path") or ""))
        if not path:
            continue
        status = row.get("status_code")
        status_code = None
        try:
            status_code = int(status)
        except (TypeError, ValueError):
            status_code = None
        data_present_raw = row.get("data_present")
        data_present = bool(data_present_raw) if isinstance(data_present_raw, bool) else None
        probe_ok = bool(row.get("probe_ok")) if isinstance(row.get("probe_ok"), bool) else False
        out[path] = {
            "status_code": status_code,
            "data_present": data_present,
            "probe_ok": probe_ok,
        }
    return out


def _api_method_expects_real_data(method: str) -> bool:
    return str(method or "").strip().upper() == "GET"


def _is_probe_real_data_ok(expect_real_data: bool, probe_ok: bool, data_present: bool | None) -> bool:
    if not probe_ok:
        return False
    if not expect_real_data:
        return True
    return bool(data_present)


def _build_api_route_evidence_items(
    api_routes: list[dict[str, Any]],
    runtime_by_endpoint: dict[str, Any],
    public_reference_counts: dict[str, int],
    probe_api: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    api_items: list[dict[str, Any]] = []
    for row in api_routes:
        if not isinstance(row, dict):
            continue
        path_template = _normalize_endpoint_path(str(row.get("path") or ""))
        methods = [
            str(item).strip().upper()
            for item in (row.get("methods") if isinstance(row.get("methods"), list) else [])
            if str(item).strip()
        ]
        if not path_template or not methods:
            continue
        runtime_entry = runtime_by_endpoint.get(path_template)
        runtime_event_count = int(runtime_entry.event_count) if runtime_entry else 0
        public_refs = _count_matching_public_references(path_template, public_reference_counts)

        method_items: list[dict[str, Any]] = []
        has_evidence_for_route = False
        route_missing_real_data_count = 0
        for method in methods:
            probe_row = probe_api.get((method, path_template)) or {}
            probe_status = probe_row.get("status_code")
            probe_ok = bool(probe_row.get("probe_ok"))
            data_present = probe_row.get("data_present") if isinstance(probe_row.get("data_present"), bool) else None
            expect_real_data = _api_method_expects_real_data(method)
            probe_real_data_ok = _is_probe_real_data_ok(expect_real_data, probe_ok, data_present)
            has_evidence = runtime_event_count > 0 or public_refs > 0 or probe_real_data_ok
            missing_real_data = expect_real_data and probe_ok and not bool(data_present)
            if has_evidence:
                has_evidence_for_route = True
            if missing_real_data:
                route_missing_real_data_count += 1
            method_items.append(
                {
                    "method": method,
                    "probe_status_code": probe_status,
                    "probe_ok": probe_ok,
                    "expects_real_data": expect_real_data,
                    "probe_data_present": data_present,
                    "probe_real_data_ok": probe_real_data_ok,
                    "missing_real_data": missing_real_data,
                    "has_actual_evidence": has_evidence,
                }
            )

        api_items.append(
            {
                "path": path_template,
                "methods": methods,
                "idea_id": str(row.get("idea_id") or "").strip() or None,
                "purpose": str(row.get("purpose") or "").strip() or None,
                "runtime_event_count": runtime_event_count,
                "public_reference_count": public_refs,
                "methods_evidence": method_items,
                "missing_real_data_count": route_missing_real_data_count,
                "has_actual_evidence": has_evidence_for_route,
            }
        )
    api_items.sort(key=lambda item: (not item["has_actual_evidence"], item["path"]))
    return api_items


def _build_web_route_evidence_items(
    web_routes: list[dict[str, Any]],
    runtime_by_endpoint: dict[str, Any],
    public_reference_counts: dict[str, int],
    probe_web: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    web_items: list[dict[str, Any]] = []
    for row in web_routes:
        if not isinstance(row, dict):
            continue
        path_template = _normalize_endpoint_path(str(row.get("path") or ""))
        if not path_template:
            continue
        runtime_entry = runtime_by_endpoint.get(path_template)
        runtime_event_count = int(runtime_entry.event_count) if runtime_entry else 0
        public_refs = _count_matching_public_references(path_template, public_reference_counts)
        probe_row = probe_web.get(path_template) or {}
        probe_status = probe_row.get("status_code")
        probe_ok = bool(probe_row.get("probe_ok"))
        data_present = probe_row.get("data_present") if isinstance(probe_row.get("data_present"), bool) else None
        expect_real_data = True
        probe_real_data_ok = _is_probe_real_data_ok(expect_real_data, probe_ok, data_present)
        missing_real_data = expect_real_data and probe_ok and not bool(data_present)
        has_evidence = runtime_event_count > 0 or public_refs > 0 or probe_real_data_ok
        web_items.append(
            {
                "path": path_template,
                "idea_id": str(row.get("idea_id") or "").strip() or None,
                "purpose": str(row.get("purpose") or "").strip() or None,
                "runtime_event_count": runtime_event_count,
                "public_reference_count": public_refs,
                "probe_status_code": probe_status,
                "probe_ok": probe_ok,
                "expects_real_data": expect_real_data,
                "probe_data_present": data_present,
                "probe_real_data_ok": probe_real_data_ok,
                "missing_real_data": missing_real_data,
                "has_actual_evidence": has_evidence,
            }
        )
    web_items.sort(key=lambda item: (not item["has_actual_evidence"], item["path"]))
    return web_items


def _route_evidence_summary(api_items: list[dict[str, Any]], web_items: list[dict[str, Any]]) -> dict[str, int]:
    missing_api = sum(1 for item in api_items if not item["has_actual_evidence"])
    missing_web = sum(1 for item in web_items if not item["has_actual_evidence"])
    missing_real_data_api = sum(int(item.get("missing_real_data_count") or 0) for item in api_items)
    missing_real_data_web = sum(1 for item in web_items if bool(item.get("missing_real_data")))
    return {
        "api_total": len(api_items),
        "api_with_actual_evidence": len(api_items) - missing_api,
        "api_missing_actual_evidence": missing_api,
        "api_missing_real_data": missing_real_data_api,
        "web_total": len(web_items),
        "web_with_actual_evidence": len(web_items) - missing_web,
        "web_missing_actual_evidence": missing_web,
        "web_missing_real_data": missing_real_data_web,
    }


def build_route_evidence_inventory(runtime_window_seconds: int = 86400) -> dict[str, Any]:
    canonical = route_registry_service.get_canonical_routes()
    api_routes = canonical.get("api_routes") if isinstance(canonical.get("api_routes"), list) else []
    web_routes = canonical.get("web_routes") if isinstance(canonical.get("web_routes"), list) else []
    runtime_rows = runtime_service.summarize_by_endpoint(seconds=runtime_window_seconds)
    runtime_by_endpoint = {str(row.endpoint): row for row in runtime_rows}
    commit_records = _read_commit_evidence_records(limit=1200)
    public_reference_counts = _public_endpoint_reference_counts(commit_records)
    probe_payload = _read_latest_route_evidence_probe() or {}
    probe_api = _probe_api_rows_by_key(probe_payload)
    probe_web = _probe_web_rows_by_path(probe_payload)
    api_items = _build_api_route_evidence_items(api_routes, runtime_by_endpoint, public_reference_counts, probe_api)
    web_items = _build_web_route_evidence_items(web_routes, runtime_by_endpoint, public_reference_counts, probe_web)
    missing_api = [item for item in api_items if not bool(item.get("has_actual_evidence"))]
    missing_web = [item for item in web_items if not bool(item.get("has_actual_evidence"))]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_window_seconds": runtime_window_seconds,
        "probe": {
            "available": bool(probe_payload),
            "source_file": probe_payload.get("_probe_file"),
            "generated_at": probe_payload.get("generated_at"),
        },
        "summary": _route_evidence_summary(api_items, web_items),
        "api_routes": api_items,
        "web_routes": web_items,
        "missing": {
            "api_routes": missing_api[:200],
            "web_routes": missing_web[:200],
        },
    }


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


def _normalize_idea_ids_for_record(record: dict[str, Any], known_ids: set[str]) -> list[str]:
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
    if not out:
        out.append("portfolio-governance")

    normalized: list[str] = []
    for idea_id in out:
        normalized.append(idea_id if idea_id in known_ids else "portfolio-governance")

    deduped: list[str] = []
    seen: set[str] = set()
    for idea_id in normalized:
        if idea_id in seen:
            continue
        seen.add(idea_id)
        deduped.append(idea_id)
    return deduped


def derive_proactive_questions_from_recent_changes(limit: int = 20, top: int = 20) -> dict[str, Any]:
    records = _latest_commit_evidence_records(limit=limit)
    top_n = max(1, min(top, 200))
    known_idea_ids = {item.id for item in idea_service.list_ideas().ideas}

    intent_breakdown: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for record in records:
        change_intent = str(record.get("change_intent") or "unknown").strip().lower() or "unknown"
        intent_breakdown[change_intent] = intent_breakdown.get(change_intent, 0) + 1
        scope = str(record.get("commit_scope") or "").strip() or "recent feature/fix"
        template, base_value, base_cost = _proactive_question_template(change_intent)
        value = round(base_value + _scope_bonus(scope), 4)
        cost = round(max(base_cost, 0.1), 4)
        question_text = template.format(scope=scope)
        source_file = str(record.get("_evidence_file") or "")
        source_date = str(record.get("date") or "")

        for idea_id in _normalize_idea_ids_for_record(record, known_idea_ids):
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


def sync_proactive_questions_from_recent_changes(limit: int = 20, max_add: int = 20) -> dict[str, Any]:
    report = derive_proactive_questions_from_recent_changes(limit=limit, top=max_add * 3)
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


def _slugify_token(value: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    if not slug:
        slug = "item"
    return slug[: max(8, max_len)]


def _auto_idea_id_for_spec(spec_id: str) -> str:
    slug = _slugify_token(spec_id, max_len=36)
    fingerprint = hashlib.sha1(spec_id.encode("utf-8")).hexdigest()[:8]
    return f"spec-origin-{slug}-{fingerprint}"


def _auto_idea_id_for_endpoint(path: str, method: str) -> str:
    payload = f"{method.upper()}::{path}".encode("utf-8")
    slug = _slugify_token(path, max_len=28)
    fingerprint = hashlib.sha1(payload).hexdigest()[:8]
    return f"endpoint-lineage-{slug}-{fingerprint}"


def _auto_spec_id_for_endpoint(path: str, method: str) -> str:
    payload = f"{method.upper()}::{path}".encode("utf-8")
    slug = _slugify_token(path, max_len=28)
    fingerprint = hashlib.sha1(payload).hexdigest()[:8]
    return f"auto-{method.lower()}-{slug}-{fingerprint}"


def _usage_gap_fingerprint(path: str, method: str) -> str:
    payload = f"endpoint-usage-gap::{method.upper()}::{path}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _asset_modularity_fingerprint(asset_id: str, metric: str) -> str:
    payload = f"asset-modularity::{asset_id.strip().lower()}::{metric.strip().lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _all_task_fingerprints_for_source(source: str) -> set[str]:
    tasks, _ = agent_service.list_tasks(limit=100000, offset=0)
    out: set[str] = set()
    for task in tasks:
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if context.get("source") != source:
            continue
        fingerprint = context.get("task_fingerprint")
        if isinstance(fingerprint, str) and fingerprint.strip():
            out.add(fingerprint.strip())
    return out


def _sentence_count(text: str) -> int:
    value = str(text or "").strip()
    if not value:
        return 0
    parts = [chunk for chunk in re.split(r"[.!?]+", value) if chunk.strip()]
    return len(parts)


def _safe_file_line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def _estimate_split_effort_and_value(current: float, threshold: float, base_cost: float, base_value: float) -> tuple[float, float, float]:
    if threshold <= 0:
        threshold = 1.0
    over_ratio = max((float(current) / float(threshold)) - 1.0, 0.0)
    cost = round(max(base_cost, base_cost * (1.0 + over_ratio)), 2)
    value = round(base_value * (1.0 + min(over_ratio, 2.0)), 2)
    roi = _question_roi(value, cost)
    return cost, value, roi


def _ensure_gap_idea(
    idea_id: str,
    name: str,
    description: str,
    potential_value: float,
    estimated_cost: float,
    confidence: float,
    interfaces: list[str],
) -> tuple[bool, bool]:
    if idea_service.get_idea(idea_id) is not None:
        return True, False
    created = idea_service.create_idea(
        idea_id=idea_id,
        name=name,
        description=description,
        potential_value=max(1.0, float(potential_value)),
        estimated_cost=max(0.5, float(estimated_cost)),
        confidence=max(0.1, min(float(confidence), 1.0)),
        interfaces=interfaces,
    )
    if created is None:
        return idea_service.get_idea(idea_id) is not None, False
    return True, True


def sync_traceability_gap_artifacts(
    runtime_window_seconds: int = 86400,
    max_spec_idea_links: int = 150,
    max_missing_endpoint_specs: int = 200,
    max_spec_process_backfills: int = 500,
    max_usage_gap_tasks: int = 200,
) -> dict[str, Any]:
    traceability = build_endpoint_traceability_inventory(runtime_window_seconds=runtime_window_seconds)
    trace_items = traceability.get("items")
    items = [row for row in trace_items if isinstance(row, dict)] if isinstance(trace_items, list) else []

    specs = spec_registry_service.list_specs(limit=5000)
    spec_map = {entry.spec_id: entry for entry in specs}

    max_link = max(1, min(max_spec_idea_links, 1000))
    max_spec_create = max(1, min(max_missing_endpoint_specs, 2000))
    max_process_backfill = max(1, min(max_spec_process_backfills, 5000))
    max_usage_tasks = max(1, min(max_usage_gap_tasks, 2000))

    linked_specs_to_ideas: list[dict[str, Any]] = []
    created_ideas_for_specs: list[str] = []
    skipped_spec_idea_links_existing = 0

    for spec in specs:
        if len(linked_specs_to_ideas) >= max_link:
            break
        if isinstance(spec.idea_id, str) and spec.idea_id.strip():
            skipped_spec_idea_links_existing += 1
            continue

        derived_idea_id = _auto_idea_id_for_spec(spec.spec_id)
        ensured, created = _ensure_gap_idea(
            idea_id=derived_idea_id,
            name=f"Spec lineage: {spec.title}",
            description=(
                f"Derived from spec '{spec.spec_id}' that was missing an idea link. "
                "Tracks ROI, implementation path, and validation ownership for this spec."
            ),
            potential_value=max(float(spec.potential_value), 24.0),
            estimated_cost=max(float(spec.estimated_cost), 4.0),
            confidence=0.62,
            interfaces=["machine:api", "human:web", "machine:spec-registry"],
        )
        if created:
            created_ideas_for_specs.append(derived_idea_id)
        if not ensured:
            continue

        updated = spec_registry_service.update_spec(
            spec.spec_id,
            SpecRegistryUpdate(
                idea_id=derived_idea_id,
                updated_by_contributor_id=_TRACEABILITY_GAP_CONTRIBUTOR_ID,
            ),
        )
        if updated is None:
            continue
        linked_specs_to_ideas.append(
            {
                "spec_id": spec.spec_id,
                "idea_id": derived_idea_id,
            }
        )
        spec_map[updated.spec_id] = updated

    created_specs_for_endpoints: list[dict[str, Any]] = []
    skipped_existing_endpoint_specs = 0

    for row in items:
        if len(created_specs_for_endpoints) >= max_spec_create:
            break
        spec_section = row.get("spec")
        if isinstance(spec_section, dict) and bool(spec_section.get("tracked")):
            continue

        path = str(row.get("path") or "").strip()
        methods_raw = row.get("methods")
        methods = [m for m in methods_raw if isinstance(m, str) and m.strip()] if isinstance(methods_raw, list) else []
        method = str(methods[0]).upper() if methods else "GET"
        if not path:
            continue

        spec_id = _auto_spec_id_for_endpoint(path, method)
        if spec_id in spec_map:
            skipped_existing_endpoint_specs += 1
            continue

        idea_section = row.get("idea")
        selected_idea_id = ""
        if isinstance(idea_section, dict):
            selected_idea_id = str(idea_section.get("idea_id") or "").strip()
        if not selected_idea_id:
            selected_idea_id = _auto_idea_id_for_endpoint(path, method)
            _ensure_gap_idea(
                idea_id=selected_idea_id,
                name=f"Endpoint lineage: {method} {path}",
                description=(
                    f"Derived from endpoint '{method} {path}' that had no linked spec. "
                    "Tracks API behavior contract, process design, and implementation evidence."
                ),
                potential_value=22.0,
                estimated_cost=4.0,
                confidence=0.58,
                interfaces=["machine:api", "human:web", "machine:runtime"],
            )
        elif idea_service.get_idea(selected_idea_id) is None:
            selected_idea_id = _TRACEABILITY_GAP_DEFAULT_IDEA_ID

        created_spec = spec_registry_service.create_spec(
            SpecRegistryCreate(
                spec_id=spec_id,
                title=f"Auto spec: {method} {path}",
                summary=(
                    f"Auto-generated from endpoint traceability because code endpoint '{method} {path}' "
                    "had no linked spec artifact. Define acceptance tests and process/implementation evidence."
                ),
                idea_id=selected_idea_id or _TRACEABILITY_GAP_DEFAULT_IDEA_ID,
                process_summary=(
                    "Generated by traceability gap sync. Next: author process and pseudocode, then validate runtime path."
                ),
                created_by_contributor_id=_TRACEABILITY_GAP_CONTRIBUTOR_ID,
                potential_value=18.0,
                estimated_cost=3.0,
                actual_value=0.0,
                actual_cost=0.0,
            )
        )
        if created_spec is None:
            skipped_existing_endpoint_specs += 1
            continue

        spec_map[created_spec.spec_id] = created_spec
        created_specs_for_endpoints.append(
            {
                "path": path,
                "method": method,
                "spec_id": created_spec.spec_id,
                "idea_id": created_spec.idea_id,
            }
        )

    updated_spec_process_pseudocode: list[str] = []
    for spec in spec_registry_service.list_specs(limit=5000):
        if len(updated_spec_process_pseudocode) >= max_process_backfill:
            break
        process_summary = str(spec.process_summary or "").strip()
        pseudocode_summary = str(spec.pseudocode_summary or "").strip()
        if process_summary and pseudocode_summary:
            continue

        title_hint = str(spec.title or spec.spec_id).strip()
        path_hint = ""
        method_hint = ""
        if title_hint.lower().startswith("auto spec:"):
            payload = title_hint.split(":", 1)[1].strip()
            parts = payload.split(" ", 1)
            if len(parts) == 2:
                method_hint = parts[0].upper().strip()
                path_hint = parts[1].strip()

        generated_process_summary = process_summary or (
            f"Define contract for {title_hint}. Validate request, execute deterministic logic, "
            "record runtime telemetry, and verify deploy/e2e evidence."
        )
        generated_pseudocode_summary = pseudocode_summary or (
            (
                f"if request.method == '{method_hint}' and request.path == '{path_hint}': "
                "validate_input(); run_core_logic(); persist_outputs(); emit_runtime_event(); return_response()"
            )
            if method_hint and path_hint
            else (
                "validate_input(); run_core_logic(); persist_outputs(); "
                "emit_runtime_event(); return_response()"
            )
        )

        updated = spec_registry_service.update_spec(
            spec.spec_id,
            SpecRegistryUpdate(
                process_summary=generated_process_summary,
                pseudocode_summary=generated_pseudocode_summary,
                updated_by_contributor_id=_TRACEABILITY_GAP_CONTRIBUTOR_ID,
            ),
        )
        if updated is None:
            continue
        updated_spec_process_pseudocode.append(spec.spec_id)

    known_usage_fingerprints = _all_task_fingerprints_for_source("endpoint_usage_gap")
    created_usage_gap_tasks: list[dict[str, Any]] = []
    skipped_existing_usage_gap_tasks = 0

    for row in items:
        if len(created_usage_gap_tasks) >= max_usage_tasks:
            break
        usage = row.get("usage")
        event_count = int(usage.get("event_count") or 0) if isinstance(usage, dict) else 0
        if event_count > 0:
            continue

        path = str(row.get("path") or "").strip()
        methods_raw = row.get("methods")
        methods = [m for m in methods_raw if isinstance(m, str) and m.strip()] if isinstance(methods_raw, list) else []
        method = str(methods[0]).upper() if methods else "GET"
        if not path:
            continue
        fingerprint = _usage_gap_fingerprint(path, method)
        if fingerprint in known_usage_fingerprints:
            skipped_existing_usage_gap_tasks += 1
            continue

        idea_section = row.get("idea")
        idea_id = (
            str(idea_section.get("idea_id") or "").strip()
            if isinstance(idea_section, dict)
            else ""
        ) or _TRACEABILITY_GAP_DEFAULT_IDEA_ID

        direction = (
            f"Close endpoint usage tracking gap for {method} {path}. "
            "Execute a real request flow (no mocks), verify /api/runtime/events records the endpoint, "
            "and document evidence for CI/deploy/e2e gates."
        )
        task = agent_service.create_task(
            AgentTaskCreate(
                direction=direction,
                task_type=TaskType.TEST,
                context={
                    "source": "endpoint_usage_gap",
                    "endpoint_path": path,
                    "endpoint_method": method,
                    "idea_id": idea_id,
                    "task_fingerprint": fingerprint,
                    "runtime_window_seconds": runtime_window_seconds,
                },
            )
        )
        known_usage_fingerprints.add(fingerprint)
        created_usage_gap_tasks.append(
            {
                "task_id": task["id"],
                "path": path,
                "method": method,
                "idea_id": idea_id,
            }
        )

    return {
        "result": "traceability_gap_artifacts_synced",
        "runtime_window_seconds": runtime_window_seconds,
        "traceability_summary": traceability.get("summary", {}),
        "linked_specs_to_ideas_count": len(linked_specs_to_ideas),
        "created_ideas_for_specs_count": len(created_ideas_for_specs),
        "created_missing_endpoint_specs_count": len(created_specs_for_endpoints),
        "updated_spec_process_pseudocode_count": len(updated_spec_process_pseudocode),
        "created_usage_gap_tasks_count": len(created_usage_gap_tasks),
        "skipped_spec_idea_links_existing_count": skipped_spec_idea_links_existing,
        "skipped_existing_endpoint_specs_count": skipped_existing_endpoint_specs,
        "skipped_existing_usage_gap_tasks_count": skipped_existing_usage_gap_tasks,
        "linked_specs_to_ideas": linked_specs_to_ideas[:50],
        "created_missing_endpoint_specs": created_specs_for_endpoints[:50],
        "updated_spec_process_pseudocode": updated_spec_process_pseudocode[:50],
        "created_usage_gap_tasks": created_usage_gap_tasks[:50],
    }


def evaluate_process_completeness(
    runtime_window_seconds: int = 86400,
    auto_sync: bool = False,
    max_spec_idea_links: int = 150,
    max_missing_endpoint_specs: int = 200,
    max_spec_process_backfills: int = 500,
    max_usage_gap_tasks: int = 200,
) -> dict[str, Any]:
    sync_report: dict[str, Any] | None = None
    if auto_sync:
        sync_report = sync_traceability_gap_artifacts(
            runtime_window_seconds=runtime_window_seconds,
            max_spec_idea_links=max_spec_idea_links,
            max_missing_endpoint_specs=max_missing_endpoint_specs,
            max_spec_process_backfills=max_spec_process_backfills,
            max_usage_gap_tasks=max_usage_gap_tasks,
        )

    ideas_response = idea_service.list_ideas()
    ideas = list(ideas_response.ideas)
    specs = spec_registry_service.list_specs(limit=5000)
    endpoint_inventory = build_endpoint_traceability_inventory(runtime_window_seconds=runtime_window_seconds)
    endpoint_summary = endpoint_inventory.get("summary", {}) if isinstance(endpoint_inventory, dict) else {}

    standing_text = str(getattr(idea_service, "STANDING_QUESTION_TEXT", "")).strip()
    standing_missing_count = 0
    for idea in ideas:
        if not standing_text:
            continue
        has_standing = any(str(q.question).strip() == standing_text for q in idea.open_questions)
        if not has_standing:
            standing_missing_count += 1

    spec_missing_idea_link_count = sum(
        1
        for spec in specs
        if not (isinstance(spec.idea_id, str) and spec.idea_id.strip())
    )
    spec_missing_process_or_pseudocode_count = sum(
        1
        for spec in specs
        if not str(spec.process_summary or "").strip() or not str(spec.pseudocode_summary or "").strip()
    )
    ideas_with_specs = {
        str(spec.idea_id).strip()
        for spec in specs
        if isinstance(spec.idea_id, str) and str(spec.idea_id).strip()
    }
    ideas_without_specs_count = sum(1 for idea in ideas if idea.id not in ideas_with_specs)

    total_endpoints = int(endpoint_summary.get("total_endpoints") or 0)
    canonical_registered = int(endpoint_summary.get("canonical_registered") or 0)
    missing_usage_count = max(total_endpoints - int(endpoint_summary.get("with_usage_events") or 0), 0)
    missing_idea_count = int(endpoint_summary.get("missing_idea") or 0)
    missing_spec_count = int(endpoint_summary.get("missing_spec") or 0)
    missing_process_count = int(endpoint_summary.get("missing_process") or 0)
    missing_validation_count = int(endpoint_summary.get("missing_validation") or 0)
    modularity_report = evaluate_asset_modularity(runtime_window_seconds=runtime_window_seconds)
    modularity_summary = modularity_report.get("summary") if isinstance(modularity_report, dict) else {}
    modularity_blocking_assets = int(
        modularity_summary.get("blocking_assets") if isinstance(modularity_summary, dict) else 0
    )

    checks: list[dict[str, Any]] = [
        {
            "id": "ideas_have_standing_questions",
            "description": "Every idea has the standing improvement/measurability question.",
            "passed": standing_missing_count == 0,
            "current": {"missing_count": standing_missing_count, "total_ideas": len(ideas)},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Run idea backfill and ensure standing question enforcement.",
        },
        {
            "id": "specs_linked_to_ideas",
            "description": "Every spec is linked to an idea.",
            "passed": spec_missing_idea_link_count == 0,
            "current": {"missing_count": spec_missing_idea_link_count, "total_specs": len(specs)},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Run /api/inventory/gaps/sync-traceability to auto-link missing specs.",
        },
        {
            "id": "specs_have_process_and_pseudocode",
            "description": "Every spec has process summary and pseudocode summary.",
            "passed": spec_missing_process_or_pseudocode_count == 0,
            "current": {"missing_count": spec_missing_process_or_pseudocode_count, "total_specs": len(specs)},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Run /api/inventory/gaps/sync-traceability to backfill process/pseudocode gaps.",
        },
        {
            "id": "ideas_have_specs",
            "description": "Every idea is represented by at least one spec.",
            "passed": ideas_without_specs_count == 0,
            "current": {"missing_count": ideas_without_specs_count, "total_ideas": len(ideas)},
            "expected": {"missing_count": 0},
            "severity": "medium",
            "fix_hint": "Run /api/inventory/gaps/sync-traceability and add specs for strategic ideas.",
        },
        {
            "id": "endpoints_have_idea_mapping",
            "description": "All discovered endpoints map to an idea lineage.",
            "passed": missing_idea_count == 0,
            "current": {"missing_count": missing_idea_count, "total_endpoints": total_endpoints},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Extend canonical routes and runtime idea mapping.",
        },
        {
            "id": "endpoints_have_spec_coverage",
            "description": "All discovered endpoints are linked to at least one spec artifact.",
            "passed": missing_spec_count == 0,
            "current": {"missing_count": missing_spec_count, "total_endpoints": total_endpoints},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Run /api/inventory/gaps/sync-traceability to generate missing endpoint specs.",
        },
        {
            "id": "endpoints_have_process_coverage",
            "description": "All discovered endpoints have process evidence and tasks.",
            "passed": missing_process_count == 0,
            "current": {"missing_count": missing_process_count, "total_endpoints": total_endpoints},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Attach process evidence/task links to endpoint source files.",
        },
        {
            "id": "endpoints_have_validation_coverage",
            "description": "All discovered endpoints have validation evidence.",
            "passed": missing_validation_count == 0,
            "current": {"missing_count": missing_validation_count, "total_endpoints": total_endpoints},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Attach CI/deploy/e2e evidence to endpoint paths.",
        },
        {
            "id": "all_endpoints_have_usage_events",
            "description": "All discovered endpoints have at least one runtime usage event in the window.",
            "passed": missing_usage_count == 0,
            "current": {"missing_count": missing_usage_count, "total_endpoints": total_endpoints},
            "expected": {"missing_count": 0},
            "severity": "high",
            "fix_hint": "Run real endpoint flows; usage-gap tasks should be created via traceability sync.",
        },
        {
            "id": "canonical_route_registry_complete",
            "description": "All discovered endpoints are represented in canonical route registry.",
            "passed": total_endpoints > 0 and canonical_registered == total_endpoints,
            "current": {"canonical_registered": canonical_registered, "total_endpoints": total_endpoints},
            "expected": {"canonical_registered": total_endpoints},
            "severity": "medium",
            "fix_hint": "Update canonical route registry config/service.",
        },
        {
            "id": "assets_are_modular_and_reusable",
            "description": "Ideas/specs/pseudocode/implementations are split into maintainable reusable assets.",
            "passed": modularity_blocking_assets == 0,
            "current": {"blocking_assets": modularity_blocking_assets},
            "expected": {"blocking_assets": 0},
            "severity": "high",
            "fix_hint": "Run /api/inventory/gaps/sync-asset-modularity-tasks and split oversized assets by ROI.",
        },
    ]

    blockers = [
        {
            "check_id": check["id"],
            "severity": check["severity"],
            "description": check["description"],
            "current": check["current"],
            "expected": check["expected"],
            "fix_hint": check["fix_hint"],
        }
        for check in checks
        if not bool(check["passed"])
    ]
    blockers.sort(key=lambda row: ({"high": 0, "medium": 1, "low": 2}.get(str(row["severity"]), 3), row["check_id"]))

    passed_count = sum(1 for check in checks if bool(check["passed"]))
    failed_count = len(checks) - passed_count
    status = "pass" if failed_count == 0 else "fail"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "result": "process_complete" if status == "pass" else "process_gaps_detected",
        "auto_sync_applied": bool(auto_sync),
        "auto_sync_report": sync_report,
        "runtime_window_seconds": runtime_window_seconds,
        "summary": {
            "checks_total": len(checks),
            "checks_passed": passed_count,
            "checks_failed": failed_count,
            "blockers": len(blockers),
            "ideas_total": len(ideas),
            "specs_total": len(specs),
            "endpoints_total": total_endpoints,
            "asset_modularity_blocking_assets": modularity_blocking_assets,
        },
        "checks": checks,
        "blockers": blockers,
        "asset_modularity": modularity_report,
    }


def _process_completeness_gap_fingerprint(check_id: str) -> str:
    payload = f"process-completeness-gap::{check_id.strip().lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sync_process_completeness_gap_tasks(
    runtime_window_seconds: int = 86400,
    auto_sync: bool = True,
    max_tasks: int = 50,
    max_spec_idea_links: int = 150,
    max_missing_endpoint_specs: int = 200,
    max_spec_process_backfills: int = 500,
    max_usage_gap_tasks: int = 200,
) -> dict[str, Any]:
    report = evaluate_process_completeness(
        runtime_window_seconds=runtime_window_seconds,
        auto_sync=auto_sync,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )
    blockers = report.get("blockers")
    if not isinstance(blockers, list):
        blockers = []

    allowed = max(1, min(max_tasks, 500))
    created_tasks: list[dict[str, Any]] = []
    skipped_existing_count = 0

    for blocker in blockers:
        if len(created_tasks) >= allowed:
            break
        if not isinstance(blocker, dict):
            continue
        check_id = str(blocker.get("check_id") or "").strip()
        if not check_id:
            continue
        fingerprint = _process_completeness_gap_fingerprint(check_id)
        active = agent_service.find_active_task_by_fingerprint(fingerprint)
        if active is not None:
            skipped_existing_count += 1
            continue

        description = str(blocker.get("description") or check_id)
        fix_hint = str(blocker.get("fix_hint") or "").strip()
        severity = str(blocker.get("severity") or "medium").strip().lower() or "medium"
        current = blocker.get("current")
        expected = blocker.get("expected")
        current_text = json.dumps(current, sort_keys=True) if isinstance(current, dict) else str(current)
        expected_text = json.dumps(expected, sort_keys=True) if isinstance(expected, dict) else str(expected)

        direction = (
            f"Close process-completeness blocker '{check_id}' ({severity}). "
            f"{description} Current={current_text}. Expected={expected_text}. "
            f"Fix hint: {fix_hint}."
        )
        task_type = _PROCESS_COMPLETENESS_TASK_TYPE_BY_CHECK.get(check_id, TaskType.IMPL)
        task = agent_service.create_task(
            AgentTaskCreate(
                direction=direction,
                task_type=task_type,
                context={
                    "source": "process_completeness_gap",
                    "check_id": check_id,
                    "severity": severity,
                    "task_fingerprint": fingerprint,
                    "runtime_window_seconds": runtime_window_seconds,
                    "auto_sync": bool(auto_sync),
                },
            )
        )
        created_tasks.append(
            {
                "task_id": task["id"],
                "check_id": check_id,
                "task_type": task_type.value,
                "severity": severity,
            }
        )

    return {
        "result": "process_gap_tasks_synced",
        "status": report.get("status"),
        "process_result": report.get("result"),
        "blockers_count": len(blockers),
        "created_count": len(created_tasks),
        "skipped_existing_count": skipped_existing_count,
        "created_tasks": created_tasks,
        "process_summary": report.get("summary", {}),
        "process_auto_sync_applied": bool(report.get("auto_sync_applied")),
    }


def _build_asset_source_file_map(endpoint_rows: list[dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    source_file_map: dict[str, dict[str, set[str]]] = {}
    for row in endpoint_rows:
        source_files = row.get("source_files") if isinstance(row.get("source_files"), list) else []
        idea = row.get("idea") if isinstance(row.get("idea"), dict) else {}
        spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
        idea_id = str(idea.get("idea_id") or "").strip()
        spec_ids = [
            str(item).strip()
            for item in (spec.get("spec_ids") if isinstance(spec.get("spec_ids"), list) else [])
            if str(item).strip()
        ]
        for source_file in source_files:
            file_key = str(source_file).replace("\\", "/").strip()
            if not file_key:
                continue
            entry = source_file_map.setdefault(file_key, {"idea_ids": set(), "spec_ids": set()})
            if idea_id:
                entry["idea_ids"].add(idea_id)
            entry["spec_ids"].update(spec_ids)
    return source_file_map


def _collect_idea_modularity_blockers(ideas: list[Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for idea in ideas:
        description = str(idea.description or "").strip()
        if not description:
            continue
        sentence_count = _sentence_count(description)
        char_count = len(description)
        by_sentence = sentence_count > _ASSET_MODULARITY_LIMITS["idea_description_sentences"]
        by_char = char_count > _ASSET_MODULARITY_LIMITS["idea_description_chars"]
        if not (by_sentence or by_char):
            continue
        metric = "description_sentences" if by_sentence else "description_chars"
        current_value = sentence_count if by_sentence else char_count
        threshold = float(
            _ASSET_MODULARITY_LIMITS["idea_description_sentences"]
            if by_sentence
            else _ASSET_MODULARITY_LIMITS["idea_description_chars"]
        )
        cost, value, roi = _estimate_split_effort_and_value(
            current=max(sentence_count, char_count),
            threshold=threshold,
            base_cost=2.0,
            base_value=20.0,
        )
        blockers.append(
            {
                "asset_category": "idea",
                "asset_kind": "description",
                "asset_id": idea.id,
                "idea_id": idea.id,
                "spec_id": None,
                "path": None,
                "metric": metric,
                "current_value": current_value,
                "threshold": int(threshold),
                "severity": "high" if (float(current_value) / max(threshold, 1.0)) >= 1.8 else "medium",
                "estimated_split_cost_hours": cost,
                "estimated_value_to_whole": value,
                "estimated_roi": roi,
                "recommended_task_type": TaskType.SPEC.value,
                "split_plan": "Split into parent + child ideas, each with focused scope and linked specs.",
                "task_fingerprint": _asset_modularity_fingerprint(f"idea:{idea.id}:description", metric),
                "direction": (
                    f"Split oversized idea description for '{idea.id}' into modular idea assets. "
                    f"Current {metric}={current_value}, target <= {int(threshold)}. "
                    "Preserve ontology links and ROI traceability."
                ),
            }
        )
    return blockers


def _collect_spec_modularity_blockers(specs: list[Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    spec_text_fields = [
        ("summary", "spec_summary_sentences", "spec_summary_chars", "spec"),
        ("process_summary", "process_summary_sentences", "process_summary_chars", "process"),
        ("pseudocode_summary", "pseudocode_summary_sentences", "pseudocode_summary_chars", "pseudocode"),
        ("implementation_summary", "implementation_summary_sentences", "implementation_summary_chars", "implementation"),
    ]
    for spec in specs:
        for field_name, sentence_key, char_key, category in spec_text_fields:
            value_text = str(getattr(spec, field_name) or "").strip()
            if not value_text:
                continue
            sentence_count = _sentence_count(value_text)
            char_count = len(value_text)
            by_sentence = sentence_count > _ASSET_MODULARITY_LIMITS[sentence_key]
            by_char = char_count > _ASSET_MODULARITY_LIMITS[char_key]
            if not (by_sentence or by_char):
                continue
            metric = sentence_key if by_sentence else char_key
            current_value = sentence_count if by_sentence else char_count
            threshold = float(_ASSET_MODULARITY_LIMITS[sentence_key] if by_sentence else _ASSET_MODULARITY_LIMITS[char_key])
            base_cost = 2.0 if category in {"spec", "process", "pseudocode"} else 3.0
            base_value = 18.0 if category in {"spec", "process", "pseudocode"} else 22.0
            cost, value, roi = _estimate_split_effort_and_value(
                current=max(sentence_count, char_count),
                threshold=threshold,
                base_cost=base_cost,
                base_value=base_value,
            )
            blockers.append(
                {
                    "asset_category": category,
                    "asset_kind": field_name,
                    "asset_id": spec.spec_id,
                    "idea_id": str(spec.idea_id or _TRACEABILITY_GAP_DEFAULT_IDEA_ID),
                    "spec_id": spec.spec_id,
                    "path": f"/specs/{spec.spec_id}",
                    "metric": metric,
                    "current_value": current_value,
                    "threshold": int(threshold),
                    "severity": "high" if (float(current_value) / max(threshold, 1.0)) >= 1.8 else "medium",
                    "estimated_split_cost_hours": cost,
                    "estimated_value_to_whole": value,
                    "estimated_roi": roi,
                    "recommended_task_type": TaskType.SPEC.value,
                    "split_plan": (
                        "Break this section into linked sub-assets with explicit interfaces and validation checkpoints."
                    ),
                    "task_fingerprint": _asset_modularity_fingerprint(f"spec:{spec.spec_id}:{field_name}", metric),
                    "direction": (
                        f"Split oversized {field_name} for spec '{spec.spec_id}' into reusable modular assets. "
                        f"Current {metric}={current_value}, target <= {int(threshold)}."
                    ),
                }
            )
    return blockers


def _discover_implementation_files(root: Path, max_implementation_files: int) -> list[Path]:
    implementation_files: list[Path] = []
    max_files = max(1, min(max_implementation_files, 20000))
    seen_dirs: set[str] = set()
    directories = (
        root / "api" / "app",
        root / "app",
        root / "web" / "app",
        root / "web" / "components",
        root / "components",
    )
    for directory in directories:
        dir_key = directory.as_posix()
        if dir_key in seen_dirs:
            continue
        seen_dirs.add(dir_key)
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            implementation_files.append(path)
            if len(implementation_files) >= max_files:
                return implementation_files
    return implementation_files


def _collect_implementation_modularity_blockers(
    implementation_files: list[Path],
    root: Path,
    source_file_map: dict[str, dict[str, set[str]]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    line_limit = _ASSET_MODULARITY_LIMITS["implementation_file_lines"]
    for path in implementation_files:
        line_count = _safe_file_line_count(path)
        if line_count <= line_limit:
            continue
        rel_path = path.relative_to(root).as_posix()
        linked = source_file_map.get(rel_path) or source_file_map.get(rel_path.lstrip("/")) or {"idea_ids": set(), "spec_ids": set()}
        idea_ids = sorted(linked.get("idea_ids") or [])
        spec_ids = sorted(linked.get("spec_ids") or [])
        idea_id = idea_ids[0] if idea_ids else _TRACEABILITY_GAP_DEFAULT_IDEA_ID
        spec_id = spec_ids[0] if spec_ids else None
        cost, value, roi = _estimate_split_effort_and_value(
            current=line_count,
            threshold=float(line_limit),
            base_cost=3.0,
            base_value=24.0,
        )
        blockers.append(
            {
                "asset_category": "implementation",
                "asset_kind": "source_file",
                "asset_id": rel_path,
                "idea_id": idea_id,
                "spec_id": spec_id,
                "path": rel_path,
                "metric": "line_count",
                "current_value": line_count,
                "threshold": line_limit,
                "severity": "high" if line_count >= (line_limit * 2) else "medium",
                "estimated_split_cost_hours": cost,
                "estimated_value_to_whole": value,
                "estimated_roi": roi,
                "recommended_task_type": TaskType.IMPL.value,
                "split_plan": "Extract cohesive modules/components, keep API stable, and add explicit interfaces.",
                "task_fingerprint": _asset_modularity_fingerprint(f"implementation:{rel_path}", "line_count"),
                "direction": (
                    f"Split oversized implementation file '{rel_path}' into smaller reusable modules. "
                    f"Current line_count={line_count}, target <= {line_limit}. "
                    "Preserve behavior and validation coverage."
                ),
            }
        )
    return blockers


def _sort_asset_modularity_blockers(blockers: list[dict[str, Any]]) -> None:
    blockers.sort(
        key=lambda row: (
            -float(row.get("estimated_roi") or 0.0),
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("severity") or "medium"), 3),
            -float(row.get("current_value") or 0.0),
            str(row.get("asset_id") or ""),
        )
    )


def _asset_modularity_summary(
    blockers: list[dict[str, Any]],
    ideas_count: int,
    specs_count: int,
    implementation_files_count: int,
) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    for row in blockers:
        category = str(row.get("asset_category") or "unknown")
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "ideas_scanned": ideas_count,
        "specs_scanned": specs_count,
        "implementation_files_scanned": implementation_files_count,
        "blocking_assets": len(blockers),
        "by_category": dict(sorted(by_category.items(), key=lambda item: item[0])),
    }


def evaluate_asset_modularity(
    runtime_window_seconds: int = 86400,
    max_implementation_files: int = 5000,
) -> dict[str, Any]:
    ideas = idea_service.list_ideas().ideas
    specs = spec_registry_service.list_specs(limit=5000)
    endpoint_inventory = build_endpoint_traceability_inventory(runtime_window_seconds=runtime_window_seconds)
    endpoint_items = endpoint_inventory.get("items")
    endpoint_rows = [row for row in endpoint_items if isinstance(row, dict)] if isinstance(endpoint_items, list) else []
    source_file_map = _build_asset_source_file_map(endpoint_rows)

    root = _project_root()
    implementation_files = _discover_implementation_files(root, max_implementation_files)
    blockers = []
    blockers.extend(_collect_idea_modularity_blockers(ideas))
    blockers.extend(_collect_spec_modularity_blockers(specs))
    blockers.extend(_collect_implementation_modularity_blockers(implementation_files, root, source_file_map))
    _sort_asset_modularity_blockers(blockers)

    summary = _asset_modularity_summary(
        blockers=blockers,
        ideas_count=len(ideas),
        specs_count=len(specs),
        implementation_files_count=len(implementation_files),
    )

    has_blockers = len(blockers) > 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if has_blockers else "pass",
        "result": "asset_modularity_drift_detected" if has_blockers else "asset_modularity_ok",
        "runtime_window_seconds": runtime_window_seconds,
        "thresholds": _ASSET_MODULARITY_LIMITS,
        "summary": summary,
        "blockers": blockers,
    }


def sync_asset_modularity_tasks(
    runtime_window_seconds: int = 86400,
    max_tasks: int = 50,
) -> dict[str, Any]:
    report = evaluate_asset_modularity(runtime_window_seconds=runtime_window_seconds)
    blockers = report.get("blockers")
    rows = [row for row in blockers if isinstance(row, dict)] if isinstance(blockers, list) else []
    allowed = max(1, min(max_tasks, 500))
    known_fingerprints = _all_task_fingerprints_for_source("asset_modularity_drift")

    created_tasks: list[dict[str, Any]] = []
    skipped_existing_count = 0
    for row in rows:
        if len(created_tasks) >= allowed:
            break
        fingerprint = str(row.get("task_fingerprint") or "").strip()
        if not fingerprint:
            continue
        if fingerprint in known_fingerprints:
            skipped_existing_count += 1
            continue
        task_type_raw = str(row.get("recommended_task_type") or TaskType.SPEC.value)
        try:
            task_type = TaskType(task_type_raw)
        except ValueError:
            task_type = TaskType.SPEC
        task = agent_service.create_task(
            AgentTaskCreate(
                direction=str(row.get("direction") or "").strip(),
                task_type=task_type,
                context={
                    "source": "asset_modularity_drift",
                    "task_fingerprint": fingerprint,
                    "asset_category": row.get("asset_category"),
                    "asset_kind": row.get("asset_kind"),
                    "asset_id": row.get("asset_id"),
                    "idea_id": row.get("idea_id"),
                    "spec_id": row.get("spec_id"),
                    "metric": row.get("metric"),
                    "current_value": row.get("current_value"),
                    "threshold": row.get("threshold"),
                    "estimated_split_cost_hours": row.get("estimated_split_cost_hours"),
                    "estimated_value_to_whole": row.get("estimated_value_to_whole"),
                    "estimated_roi": row.get("estimated_roi"),
                    "runtime_window_seconds": runtime_window_seconds,
                },
            )
        )
        known_fingerprints.add(fingerprint)
        created_tasks.append(
            {
                "task_id": task["id"],
                "task_type": task_type.value,
                "asset_category": row.get("asset_category"),
                "asset_id": row.get("asset_id"),
                "estimated_roi": row.get("estimated_roi"),
            }
        )

    return {
        "result": "asset_modularity_tasks_synced",
        "status": report.get("status"),
        "blockers_count": len(rows),
        "created_count": len(created_tasks),
        "skipped_existing_count": skipped_existing_count,
        "created_tasks": created_tasks,
        "summary": report.get("summary", {}),
        "thresholds": report.get("thresholds", {}),
    }


def _join_path(prefix: str, subpath: str) -> str:
    if subpath == "/":
        return prefix or "/"
    if not prefix:
        return subpath
    if prefix.endswith("/") and subpath.startswith("/"):
        return f"{prefix[:-1]}{subpath}"
    return f"{prefix}{subpath}"


def _router_prefix_map() -> dict[str, str]:
    out: dict[str, str] = {}
    main_candidates = [
        _project_root() / "api" / "app" / "main.py",
        _project_root() / "app" / "main.py",
    ]
    tree = None
    for candidate in main_candidates:
        if not candidate.exists():
            continue
        try:
            tree = ast.parse(candidate.read_text(encoding="utf-8"))
            break
        except (OSError, SyntaxError):
            continue
    if tree is None:
        return out

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "include_router":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if (
            not isinstance(first_arg, ast.Attribute)
            or first_arg.attr != "router"
            or not isinstance(first_arg.value, ast.Name)
        ):
            continue
        prefix = ""
        for keyword in node.keywords:
            if keyword.arg != "prefix":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                prefix = keyword.value.value
        out[first_arg.value.id] = prefix
    return out


def _extract_decorated_routes(module_path: Path, decorator_owner: str) -> list[tuple[str, str]]:
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            owner = decorator.func.value
            if not isinstance(owner, ast.Name) or owner.id != decorator_owner:
                continue
            if not decorator.args:
                continue
            first_arg = decorator.args[0]
            if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
                continue
            out.append((method.upper(), first_arg.value))
    return out


def _source_path_aliases(file_path: str) -> set[str]:
    value = str(file_path or "").replace("\\", "/").strip().lstrip("/")
    # Deployed runtime stacks can resolve modules under duplicated segments (e.g. app/app/routers/*).
    while value.startswith("api/app/app/"):
        value = value.replace("api/app/app/", "api/app/", 1)
    while value.startswith("app/app/"):
        value = value.replace("app/app/", "app/", 1)
    value = value.replace("/api/app/app/", "/api/app/")
    value = value.replace("/app/app/", "/app/")
    if not value:
        return set()
    out = {value}

    if value.startswith("api/app/"):
        out.add(value.removeprefix("api/"))
    elif value.startswith("app/"):
        out.add(f"api/{value}")

    marker_api = "/api/app/"
    marker_app = "/app/"
    if marker_api in f"/{value}":
        suffix = f"/{value}".split(marker_api, 1)[1]
        out.add(f"api/app/{suffix}")
        out.add(f"app/{suffix}")
    elif marker_app in f"/{value}":
        suffix = f"/{value}".split(marker_app, 1)[1]
        out.add(f"app/{suffix}")
        out.add(f"api/app/{suffix}")
    return {item for item in out if item}


def _discover_api_endpoints_from_runtime() -> list[dict[str, Any]]:
    try:
        from fastapi.routing import APIRoute
        from app.main import app as main_app
    except Exception:
        return []

    grouped: dict[str, dict[str, Any]] = {}
    for route in main_app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = str(route.path or "")
        if not (path.startswith("/api") or path.startswith("/api")):
            continue
        methods = sorted(
            method
            for method in (route.methods or set())
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        )
        if not methods:
            continue

        source_files: set[str] = set()
        code = getattr(route.endpoint, "__code__", None)
        filename = getattr(code, "co_filename", "")
        if isinstance(filename, str) and filename.strip():
            source_files.update(_source_path_aliases(filename))

        row = grouped.setdefault(
            path,
            {
                "path": path,
                "methods": set(),
                "source_files": set(),
            },
        )
        row["methods"].update(methods)
        row["source_files"].update(source_files)

    out: list[dict[str, Any]] = []
    for path in sorted(grouped.keys()):
        row = grouped[path]
        out.append(
            {
                "path": path,
                "methods": sorted(row["methods"]),
                "source_files": sorted(row["source_files"]),
            }
        )
    return out


def _discover_api_endpoints_from_source() -> list[dict[str, Any]]:
    root = _project_root()
    router_candidates = [
        root / "api" / "app" / "routers",
        root / "app" / "routers",
    ]
    routers_dir = None
    for candidate in router_candidates:
        if candidate.exists():
            routers_dir = candidate
            break
    if routers_dir is None:
        return []
    prefix_map = _router_prefix_map()
    grouped: dict[str, dict[str, Any]] = {}

    for module_path in sorted(routers_dir.glob("*.py")):
        if module_path.name == "__init__.py":
            continue
        router_name = module_path.stem
        prefix = prefix_map.get(router_name, "")
        for method, subpath in _extract_decorated_routes(module_path, "router"):
            full_path = _join_path(prefix, subpath)
            if not (full_path.startswith("/api") or full_path.startswith("/api")):
                continue
            row = grouped.setdefault(
                full_path,
                {
                    "path": full_path,
                    "methods": set(),
                    "source_files": set(),
                },
            )
            row["methods"].add(method)
            row["source_files"].update(_source_path_aliases(str(module_path.relative_to(root))))

    main_path = root / "api" / "app" / "main.py"
    if not main_path.exists():
        main_path = root / "app" / "main.py"
    for method, subpath in _extract_decorated_routes(main_path, "app"):
        if not (subpath.startswith("/api") or subpath.startswith("/api")):
            continue
        row = grouped.setdefault(
            subpath,
            {
                "path": subpath,
                "methods": set(),
                "source_files": set(),
            },
        )
        row["methods"].add(method)
        row["source_files"].update(_source_path_aliases(str(main_path.relative_to(root))))

    out: list[dict[str, Any]] = []
    for path in sorted(grouped.keys()):
        row = grouped[path]
        out.append(
            {
                "path": path,
                "methods": sorted(row["methods"]),
                "source_files": sorted(row["source_files"]),
            }
        )
    return out


def _evidence_signals_by_source_file(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    signals: dict[str, dict[str, Any]] = {}
    for record in records:
        raw_files = record.get("change_files")
        if not isinstance(raw_files, list):
            continue
        files = [x.strip() for x in raw_files if isinstance(x, str) and x.strip()]
        if not files:
            continue
        spec_ids = {
            x.strip()
            for x in (record.get("spec_ids") if isinstance(record.get("spec_ids"), list) else [])
            if isinstance(x, str) and x.strip()
        }
        task_ids = {
            x.strip()
            for x in (record.get("task_ids") if isinstance(record.get("task_ids"), list) else [])
            if isinstance(x, str) and x.strip()
        }
        idea_ids = {
            x.strip()
            for x in (record.get("idea_ids") if isinstance(record.get("idea_ids"), list) else [])
            if isinstance(x, str) and x.strip()
        }
        local_status = _normalize_validation_status((record.get("local_validation") or {}).get("status"))
        ci_status = _normalize_validation_status((record.get("ci_validation") or {}).get("status"))
        deploy_status = _normalize_validation_status((record.get("deploy_validation") or {}).get("status"))
        e2e_status = _normalize_validation_status((record.get("e2e_validation") or {}).get("status"))

        for file_path in files:
            for alias in _source_path_aliases(file_path):
                signal = signals.setdefault(
                    alias,
                    {
                        "spec_ids": set(),
                        "task_ids": set(),
                        "idea_ids": set(),
                        "process_evidence_count": 0,
                        "validation_pass_counts": {
                            "local": 0,
                            "ci": 0,
                            "deploy": 0,
                            "e2e": 0,
                        },
                    },
                )
                signal["spec_ids"].update(spec_ids)
                signal["task_ids"].update(task_ids)
                signal["idea_ids"].update(idea_ids)
                signal["process_evidence_count"] += 1
                if local_status == "pass":
                    signal["validation_pass_counts"]["local"] += 1
                if ci_status == "pass":
                    signal["validation_pass_counts"]["ci"] += 1
                if deploy_status == "pass":
                    signal["validation_pass_counts"]["deploy"] += 1
                if e2e_status == "pass":
                    signal["validation_pass_counts"]["e2e"] += 1
    return signals


def build_endpoint_traceability_inventory(runtime_window_seconds: int = 86400) -> dict[str, Any]:
    endpoints = _discover_api_endpoints_from_runtime() or _discover_api_endpoints_from_source()
    canonical = route_registry_service.get_canonical_routes().get("api_routes", [])
    canonical_by_path = {
        row.get("path"): row
        for row in canonical
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    evidence_by_file = _evidence_signals_by_source_file(_read_commit_evidence_records(limit=1200))
    ideas_summary = idea_service.list_ideas().summary
    specs, spec_source = _discover_specs(limit=2000)
    registry_specs = spec_registry_service.list_specs(limit=5000)
    discovered_spec_ids = {
        str(row.get("spec_id") or "").strip()
        for row in specs
        if isinstance(row, dict) and str(row.get("spec_id") or "").strip()
    }
    discovered_spec_ids.update(
        str(spec.spec_id).strip()
        for spec in registry_specs
        if isinstance(getattr(spec, "spec_id", None), str) and str(spec.spec_id).strip()
    )
    usage_rows = runtime_service.summarize_by_endpoint(seconds=runtime_window_seconds)
    usage_by_endpoint = {row.endpoint: row for row in usage_rows}

    items: list[dict[str, Any]] = []
    for endpoint in endpoints:
        path = endpoint["path"]
        methods = endpoint["methods"]
        source_files = endpoint["source_files"]
        canonical_row = canonical_by_path.get(path)
        canonical_methods = []
        canonical_idea_id = ""
        if isinstance(canonical_row, dict):
            raw_methods = canonical_row.get("methods")
            if isinstance(raw_methods, list):
                canonical_methods = sorted(
                    [m.strip().upper() for m in raw_methods if isinstance(m, str) and m.strip()]
                )
            canonical_idea_id = str(canonical_row.get("idea_id") or "").strip()

        spec_ids: set[str] = set()
        task_ids: set[str] = set()
        evidence_idea_ids: set[str] = set()
        process_evidence_count = 0
        validation_pass_counts = {"local": 0, "ci": 0, "deploy": 0, "e2e": 0}
        for source_file in source_files:
            signal = evidence_by_file.get(source_file)
            if not signal:
                continue
            spec_ids.update(signal["spec_ids"])
            task_ids.update(signal["task_ids"])
            evidence_idea_ids.update(signal["idea_ids"])
            process_evidence_count += int(signal["process_evidence_count"])
            for key in validation_pass_counts:
                validation_pass_counts[key] += int(signal["validation_pass_counts"][key])

        # Deterministic endpoint->spec link: if an auto-generated endpoint spec exists,
        # treat it as a real spec link for this endpoint even without commit evidence.
        for method in methods or ["GET"]:
            derived_spec_id = _auto_spec_id_for_endpoint(path, method)
            if derived_spec_id in discovered_spec_ids:
                spec_ids.add(derived_spec_id)

        usage = usage_by_endpoint.get(path)
        runtime_idea_id = str(usage.idea_id if usage else "").strip()

        idea_ids = set(evidence_idea_ids)
        source_parts: list[str] = []
        if canonical_idea_id:
            idea_ids.add(canonical_idea_id)
            source_parts.append("canonical")
        if evidence_idea_ids:
            source_parts.append("evidence")
        if runtime_idea_id:
            idea_ids.add(runtime_idea_id)
            source_parts.append("runtime")

        derived_idea_id = runtime_service.resolve_idea_id(
            endpoint=path,
            method=methods[0] if methods else None,
        )
        if derived_idea_id and derived_idea_id != "unmapped":
            idea_ids.add(derived_idea_id)
            if "derived" not in source_parts:
                source_parts.append("derived")

        primary_idea_id = canonical_idea_id or runtime_idea_id
        if not primary_idea_id and len(idea_ids) == 1:
            primary_idea_id = next(iter(idea_ids))
        if not primary_idea_id and derived_idea_id and derived_idea_id != "unmapped":
            primary_idea_id = derived_idea_id

        origin_idea_id = (
            idea_lineage_service.resolve_origin_idea_id(primary_idea_id) if primary_idea_id else None
        )
        idea_source = "+".join(source_parts) if source_parts else "missing"
        idea_tracked = bool(primary_idea_id)
        spec_tracked = len(spec_ids) > 0
        process_tracked = process_evidence_count > 0 or len(task_ids) > 0
        validation_tracked = any(validation_pass_counts.values())
        fully_traced = idea_tracked and spec_tracked and process_tracked and validation_tracked

        gaps: list[str] = []
        if not idea_tracked:
            gaps.append("idea")
        if not spec_tracked:
            gaps.append("spec")
        if not process_tracked:
            gaps.append("process")
        if not validation_tracked:
            gaps.append("validation")
        if canonical_row is None:
            gaps.append("canonical_route")
        elif canonical_methods and canonical_methods != methods:
            gaps.append("canonical_method_mismatch")

        items.append(
            {
                "path": path,
                "methods": methods,
                "source_files": source_files,
                "canonical_route": {
                    "registered": canonical_row is not None,
                    "methods": canonical_methods,
                    "method_match": not canonical_methods or canonical_methods == methods,
                },
                "idea": {
                    "tracked": idea_tracked,
                    "idea_id": primary_idea_id or None,
                    "origin_idea_id": origin_idea_id,
                    "idea_ids": sorted(idea_ids),
                    "source": idea_source,
                },
                "usage": {
                    "tracked": True,
                    "window_seconds": runtime_window_seconds,
                    "event_count": int(usage.event_count) if usage else 0,
                    "methods": usage.methods if usage else [],
                    "total_runtime_ms": float(usage.total_runtime_ms) if usage else 0.0,
                    "average_runtime_ms": float(usage.average_runtime_ms) if usage else 0.0,
                    "runtime_cost_estimate": float(usage.runtime_cost_estimate) if usage else 0.0,
                    "status_counts": usage.status_counts if usage else {},
                    "by_source": usage.by_source if usage else {},
                },
                "spec": {
                    "tracked": spec_tracked,
                    "spec_ids": sorted(spec_ids),
                },
                "process": {
                    "tracked": process_tracked,
                    "evidence_count": process_evidence_count,
                    "task_ids": sorted(task_ids),
                },
                "validation": {
                    "tracked": validation_tracked,
                    "pass_counts": validation_pass_counts,
                },
                "traceability": {
                    "fully_traced": fully_traced,
                    "gaps": gaps,
                },
            }
        )

    summary = {
        "total_endpoints": len(items),
        "canonical_registered": sum(1 for row in items if row["canonical_route"]["registered"]),
        "with_idea": sum(1 for row in items if row["idea"]["tracked"]),
        "with_origin_idea": sum(1 for row in items if bool(row["idea"].get("origin_idea_id"))),
        "with_usage_events": sum(1 for row in items if int(row["usage"]["event_count"]) > 0),
        "with_spec": sum(1 for row in items if row["spec"]["tracked"]),
        "with_process": sum(1 for row in items if row["process"]["tracked"]),
        "with_validation": sum(1 for row in items if row["validation"]["tracked"]),
        "fully_traced": sum(1 for row in items if row["traceability"]["fully_traced"]),
        "missing_idea": sum(1 for row in items if not row["idea"]["tracked"]),
        "missing_spec": sum(1 for row in items if not row["spec"]["tracked"]),
        "missing_process": sum(1 for row in items if not row["process"]["tracked"]),
        "missing_validation": sum(1 for row in items if not row["validation"]["tracked"]),
    }

    missing_items = [row for row in items if not row["traceability"]["fully_traced"]]
    missing_items.sort(key=lambda row: (len(row["traceability"]["gaps"]), row["path"]), reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": {
            "idea_count": ideas_summary.total_ideas,
            "spec_count": len(discovered_spec_ids),
            "spec_source": spec_source,
            "canonical_route_count": len(canonical_by_path),
            "runtime_window_seconds": runtime_window_seconds,
        },
        "summary": summary,
        "top_gaps": missing_items[:25],
        "items": items,
    }


def _new_flow_row(idea_id: str, idea_name: str) -> dict[str, Any]:
    return {
        "idea_id": idea_id,
        "idea_name": idea_name,
        "_spec_ids": set(),
        "_task_ids": set(),
        "_thread_branches": set(),
        "_change_intents": set(),
        "_evidence_refs": set(),
        "_implementation_refs": set(),
        "_lineage_ids": set(),
        "_source_files": set(),
        "_public_endpoints": set(),
        "_contributors_all": set(),
        "_contributors_by_role": {},
        "_contributor_registry_ids": set(),
        "_contribution_ids": set(),
        "_asset_ids": set(),
        "process_evidence_count": 0,
        "usage_events_count": 0,
        "measured_value_total": 0.0,
        "runtime_events_count": 0,
        "runtime_total_ms": 0.0,
        "runtime_cost_estimate": 0.0,
        "validation_counts": {
            "local": {"pass": 0, "fail": 0, "pending": 0},
            "ci": {"pass": 0, "fail": 0, "pending": 0},
            "deploy": {"pass": 0, "fail": 0, "pending": 0},
            "e2e": {"pass": 0, "fail": 0, "pending": 0},
        },
        "phase_gate": {"pass_count": 0, "blocked_count": 0},
    }


def _add_contributor(flow: dict[str, Any], contributor_id: str, roles: list[str]) -> None:
    cid = str(contributor_id or "").strip()
    if not cid:
        return
    flow["_contributors_all"].add(cid)
    role_map = flow["_contributors_by_role"]
    for role in roles:
        normalized = str(role or "").strip().lower()
        if not normalized:
            continue
        if normalized not in role_map:
            role_map[normalized] = set()
        role_map[normalized].add(cid)


def _normalize_contributor_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _direct_idea_ids_from_contribution_metadata(metadata: Any) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    out: set[str] = set()
    raw_single = metadata.get("idea_id")
    if isinstance(raw_single, str) and raw_single.strip():
        out.add(raw_single.strip())
    raw_multi = metadata.get("idea_ids")
    if isinstance(raw_multi, list):
        for item in raw_multi:
            if isinstance(item, str) and item.strip():
                out.add(item.strip())
    return sorted(out)


def build_spec_process_implementation_validation_flow(
    idea_id: str | None = None,
    runtime_window_seconds: int = 86400,
    contributor_rows: list[dict[str, Any]] | None = None,
    contribution_rows: list[dict[str, Any]] | None = None,
    asset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    portfolio = idea_service.list_ideas()
    idea_name_map = {item.id: item.name for item in portfolio.ideas}
    idea_signal_map = {
        item.id: {
            "value_gap": float(item.value_gap),
            "confidence": float(item.confidence),
            "estimated_cost": float(item.estimated_cost),
            "potential_value": float(item.potential_value),
            "actual_value": float(item.actual_value),
        }
        for item in portfolio.ideas
    }

    runtime_rows = runtime_service.summarize_by_idea(seconds=runtime_window_seconds)
    runtime_by_idea = {row.idea_id: row for row in runtime_rows}

    lineage_links = value_lineage_service.list_links(limit=1000)
    usage_events = value_lineage_service.list_usage_events(limit=5000)

    usage_by_lineage_count: dict[str, int] = {}
    usage_by_lineage_value: dict[str, float] = {}
    for event in usage_events:
        usage_by_lineage_count[event.lineage_id] = usage_by_lineage_count.get(event.lineage_id, 0) + 1
        usage_by_lineage_value[event.lineage_id] = usage_by_lineage_value.get(event.lineage_id, 0.0) + float(event.value)

    contributor_rows = contributor_rows or []
    contribution_rows = contribution_rows or []
    asset_rows = asset_rows or []
    known_asset_ids = {
        str(row.get("id")).strip()
        for row in asset_rows
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }

    contributor_id_by_token: dict[str, set[str]] = {}
    for contributor in contributor_rows:
        if not isinstance(contributor, dict):
            continue
        contributor_id = str(contributor.get("id") or "").strip()
        if not contributor_id:
            continue
        token_candidates = {
            _normalize_contributor_token(contributor_id),
            _normalize_contributor_token(str(contributor.get("name") or "")),
            _normalize_contributor_token(str(contributor.get("email") or "")),
        }
        email = str(contributor.get("email") or "").strip().lower()
        if "@" in email:
            token_candidates.add(_normalize_contributor_token(email.split("@", 1)[0]))
        for token in token_candidates:
            if not token:
                continue
            contributor_id_by_token.setdefault(token, set()).add(contributor_id)

    evidence_records = _read_commit_evidence_records(limit=800)

    discovered_ids: set[str] = set(idea_name_map.keys())
    discovered_ids.update(link.idea_id for link in lineage_links if link.idea_id)
    for record in evidence_records:
        raw_ids = record.get("idea_ids")
        if isinstance(raw_ids, list):
            for candidate in raw_ids:
                if isinstance(candidate, str) and candidate.strip():
                    discovered_ids.add(candidate.strip())

    filtered_ids = sorted(discovered_ids)
    if idea_id:
        filtered_ids = [item for item in filtered_ids if item == idea_id]

    flows: dict[str, dict[str, Any]] = {}
    for current_idea_id in filtered_ids:
        flows[current_idea_id] = _new_flow_row(
            current_idea_id,
            idea_name_map.get(current_idea_id, current_idea_id),
        )

    def ensure(idea_key: str) -> dict[str, Any]:
        if idea_key not in flows:
            flows[idea_key] = _new_flow_row(idea_key, idea_name_map.get(idea_key, idea_key))
        return flows[idea_key]

    for link in lineage_links:
        if idea_id and link.idea_id != idea_id:
            continue
        flow = ensure(link.idea_id)
        flow["_spec_ids"].add(link.spec_id)
        flow["_lineage_ids"].add(link.id)
        for ref in link.implementation_refs:
            if isinstance(ref, str) and ref.strip():
                flow["_implementation_refs"].add(ref.strip())
        _add_contributor(flow, str(link.contributors.idea or ""), ["idea"])
        _add_contributor(flow, str(link.contributors.spec or ""), ["spec"])
        _add_contributor(flow, str(link.contributors.implementation or ""), ["implementation"])
        _add_contributor(flow, str(link.contributors.review or ""), ["review"])
        flow["usage_events_count"] += int(usage_by_lineage_count.get(link.id, 0))
        flow["measured_value_total"] += float(usage_by_lineage_value.get(link.id, 0.0))

    for record in evidence_records:
        raw_idea_ids = record.get("idea_ids")
        if not isinstance(raw_idea_ids, list):
            continue
        record_idea_ids = [
            item.strip()
            for item in raw_idea_ids
            if isinstance(item, str) and item.strip() and (not idea_id or item.strip() == idea_id)
        ]
        if not record_idea_ids:
            continue

        raw_spec_ids = record.get("spec_ids")
        spec_ids = [s.strip() for s in raw_spec_ids if isinstance(s, str) and s.strip()] if isinstance(raw_spec_ids, list) else []

        raw_task_ids = record.get("task_ids")
        task_ids = [s.strip() for s in raw_task_ids if isinstance(s, str) and s.strip()] if isinstance(raw_task_ids, list) else []

        raw_change_files = record.get("change_files")
        change_files = [
            item.strip()
            for item in raw_change_files
            if isinstance(item, str) and item.strip()
        ] if isinstance(raw_change_files, list) else []

        raw_evidence_refs = record.get("evidence_refs")
        evidence_refs = [
            item.strip()
            for item in raw_evidence_refs
            if isinstance(item, str) and item.strip()
        ] if isinstance(raw_evidence_refs, list) else []

        contributors = record.get("contributors") if isinstance(record.get("contributors"), list) else []
        local_status = _normalize_validation_status((record.get("local_validation") or {}).get("status"))
        ci_status = _normalize_validation_status((record.get("ci_validation") or {}).get("status"))
        deploy_status = _normalize_validation_status((record.get("deploy_validation") or {}).get("status"))
        e2e_status = _normalize_validation_status((record.get("e2e_validation") or {}).get("status"))
        phase_gate = record.get("phase_gate") if isinstance(record.get("phase_gate"), dict) else {}
        phase_pass = bool(phase_gate.get("can_move_next_phase"))

        thread_branch = str(record.get("thread_branch") or "").strip()
        change_intent = str(record.get("change_intent") or "").strip().lower()
        public_endpoints = (
            record.get("e2e_validation", {}).get("public_endpoints")
            if isinstance(record.get("e2e_validation"), dict)
            else []
        )

        for current_idea_id in record_idea_ids:
            flow = ensure(current_idea_id)
            flow["process_evidence_count"] += 1
            flow["validation_counts"]["local"][local_status] += 1
            flow["validation_counts"]["ci"][ci_status] += 1
            flow["validation_counts"]["deploy"][deploy_status] += 1
            flow["validation_counts"]["e2e"][e2e_status] += 1
            if phase_pass:
                flow["phase_gate"]["pass_count"] += 1
            else:
                flow["phase_gate"]["blocked_count"] += 1
            if thread_branch:
                flow["_thread_branches"].add(thread_branch)
            if change_intent:
                flow["_change_intents"].add(change_intent)
            for spec_id_value in spec_ids:
                flow["_spec_ids"].add(spec_id_value)
            for task_id_value in task_ids:
                flow["_task_ids"].add(task_id_value)
            for file_path in change_files:
                flow["_source_files"].add(file_path)
            for evidence_ref in evidence_refs:
                flow["_evidence_refs"].add(evidence_ref)
            if isinstance(public_endpoints, list):
                for endpoint in public_endpoints:
                    if isinstance(endpoint, str) and endpoint.strip():
                        flow["_public_endpoints"].add(endpoint.strip())
            for contributor in contributors:
                if not isinstance(contributor, dict):
                    continue
                cid = str(contributor.get("contributor_id") or "").strip()
                raw_roles = contributor.get("roles")
                roles = [role for role in raw_roles if isinstance(role, str)] if isinstance(raw_roles, list) else []
                _add_contributor(flow, cid, roles)

    for current_idea_id, runtime in runtime_by_idea.items():
        if idea_id and current_idea_id != idea_id:
            continue
        flow = ensure(current_idea_id)
        flow["runtime_events_count"] = int(runtime.event_count)
        flow["runtime_total_ms"] = float(runtime.total_runtime_ms)
        flow["runtime_cost_estimate"] = float(runtime.runtime_cost_estimate)

    contribution_by_id: dict[str, dict[str, Any]] = {}
    contributions_by_contributor_id: dict[str, list[dict[str, Any]]] = {}
    direct_contribs_by_idea: dict[str, list[dict[str, Any]]] = {}
    for row in contribution_rows:
        if not isinstance(row, dict):
            continue
        contribution_id = str(row.get("id") or "").strip()
        if contribution_id:
            contribution_by_id[contribution_id] = row
        contributor_id = str(row.get("contributor_id") or "").strip()
        if contributor_id:
            contributions_by_contributor_id.setdefault(contributor_id, []).append(row)
        for direct_idea_id in _direct_idea_ids_from_contribution_metadata(row.get("metadata")):
            direct_contribs_by_idea.setdefault(direct_idea_id, []).append(row)

    # Direct mapping: contribution metadata explicitly references idea ids.
    for current_idea_id, rows in direct_contribs_by_idea.items():
        if idea_id and current_idea_id != idea_id:
            continue
        flow = ensure(current_idea_id)
        for row in rows:
            contribution_id = str(row.get("id") or "").strip()
            if contribution_id:
                flow["_contribution_ids"].add(contribution_id)
            contributor_id = str(row.get("contributor_id") or "").strip()
            if contributor_id:
                flow["_contributor_registry_ids"].add(contributor_id)
                _add_contributor(flow, contributor_id, ["contribution"])
            asset_id = str(row.get("asset_id") or "").strip()
            if asset_id and (not known_asset_ids or asset_id in known_asset_ids):
                flow["_asset_ids"].add(asset_id)

    # Alias-based fallback: match evidence/lineage contributor handles to registry contributors.
    for flow in flows.values():
        for alias in list(flow["_contributors_all"]):
            token = _normalize_contributor_token(alias)
            if not token:
                continue
            resolved_ids = contributor_id_by_token.get(token, set())
            if not resolved_ids:
                continue
            for contributor_id in resolved_ids:
                flow["_contributor_registry_ids"].add(contributor_id)
                for row in contributions_by_contributor_id.get(contributor_id, []):
                    contribution_id = str(row.get("id") or "").strip()
                    if contribution_id:
                        flow["_contribution_ids"].add(contribution_id)
                    asset_id = str(row.get("asset_id") or "").strip()
                    if asset_id and (not known_asset_ids or asset_id in known_asset_ids):
                        flow["_asset_ids"].add(asset_id)

    items: list[dict[str, Any]] = []
    unblock_queue: list[dict[str, Any]] = []
    active_task_cache: dict[str, dict[str, Any] | None] = {}
    for current_idea_id in sorted(flows.keys()):
        flow = flows[current_idea_id]
        spec_count = len(flow["_spec_ids"])
        spec_ids = sorted(flow["_spec_ids"])
        process_tracked = bool(flow["process_evidence_count"] > 0 or flow["_task_ids"] or flow["_evidence_refs"])
        implementation_tracked = bool(flow["_lineage_ids"] or flow["_implementation_refs"])
        validation_tracked = bool(
            flow["validation_counts"]["local"]["pass"]
            or flow["validation_counts"]["ci"]["pass"]
            or flow["validation_counts"]["deploy"]["pass"]
            or flow["validation_counts"]["e2e"]["pass"]
            or flow["usage_events_count"] > 0
        )
        contributors_tracked = bool(flow["_contributors_all"])
        registry_contribution_count = len(flow["_contribution_ids"])
        registry_cost_total = round(
            sum(
                float((contribution_by_id.get(contribution_id) or {}).get("cost_amount") or 0.0)
                for contribution_id in flow["_contribution_ids"]
            ),
            4,
        )
        contributions_tracked = bool(
            flow["usage_events_count"] > 0
            or flow["measured_value_total"] > 0
            or registry_contribution_count > 0
        )
        idea_signals = idea_signal_map.get(
            current_idea_id,
            {"value_gap": 0.0, "confidence": 0.0, "estimated_cost": 0.0, "potential_value": 0.0, "actual_value": 0.0},
        )
        interdependencies, queue_candidate = _build_flow_interdependencies(
            idea_id=current_idea_id,
            idea_name=flow["idea_name"],
            spec_tracked=spec_count > 0,
            process_tracked=process_tracked,
            implementation_tracked=implementation_tracked,
            validation_tracked=validation_tracked,
            spec_ids=spec_ids,
            idea_value_gap=float(idea_signals.get("value_gap", 0.0)),
            idea_confidence=float(idea_signals.get("confidence", 0.0)),
        )
        if queue_candidate is not None:
            fingerprint = str(queue_candidate.get("task_fingerprint") or "")
            active_task = active_task_cache.get(fingerprint)
            if fingerprint and fingerprint not in active_task_cache:
                active_task = agent_service.find_active_task_by_fingerprint(fingerprint)
                active_task_cache[fingerprint] = active_task
            queue_candidate["active_task"] = (
                {
                    "id": active_task.get("id"),
                    "status": (
                        active_task["status"].value
                        if hasattr(active_task.get("status"), "value")
                        else str(active_task.get("status"))
                    ),
                    "claimed_by": active_task.get("claimed_by"),
                }
                if isinstance(active_task, dict)
                else None
            )
            unblock_queue.append(queue_candidate)

        items.append(
            {
                "idea_id": current_idea_id,
                "idea_name": flow["idea_name"],
                "spec": {
                    "count": spec_count,
                    "spec_ids": spec_ids,
                    "tracked": spec_count > 0,
                },
                "process": {
                    "tracked": process_tracked,
                    "evidence_count": flow["process_evidence_count"],
                    "task_ids": sorted(flow["_task_ids"]),
                    "thread_branches": sorted(flow["_thread_branches"]),
                    "change_intents": sorted(flow["_change_intents"]),
                    "evidence_refs": sorted(flow["_evidence_refs"]),
                    "source_files": sorted(flow["_source_files"]),
                },
                "implementation": {
                    "tracked": implementation_tracked,
                    "lineage_link_count": len(flow["_lineage_ids"]),
                    "lineage_ids": sorted(flow["_lineage_ids"]),
                    "implementation_refs": sorted(flow["_implementation_refs"]),
                    "runtime_events_count": flow["runtime_events_count"],
                    "runtime_total_ms": round(float(flow["runtime_total_ms"]), 4),
                    "runtime_cost_estimate": round(float(flow["runtime_cost_estimate"]), 8),
                },
                "validation": {
                    "tracked": validation_tracked,
                    "local": flow["validation_counts"]["local"],
                    "ci": flow["validation_counts"]["ci"],
                    "deploy": flow["validation_counts"]["deploy"],
                    "e2e": flow["validation_counts"]["e2e"],
                    "phase_gate": flow["phase_gate"],
                    "public_endpoints": sorted(flow["_public_endpoints"]),
                },
                "contributors": {
                    "tracked": contributors_tracked,
                    "total_unique": len(flow["_contributors_all"]),
                    "all": sorted(flow["_contributors_all"]),
                    "registry_ids": sorted(flow["_contributor_registry_ids"]),
                    "by_role": {
                        role: sorted(ids)
                        for role, ids in sorted(flow["_contributors_by_role"].items(), key=lambda item: item[0])
                    },
                },
                "contributions": {
                    "tracked": contributions_tracked,
                    "usage_events_count": int(flow["usage_events_count"]),
                    "measured_value_total": round(float(flow["measured_value_total"]), 4),
                    "registry_contribution_count": registry_contribution_count,
                    "registry_total_cost": registry_cost_total,
                    "contribution_ids": sorted(flow["_contribution_ids"]),
                },
                "assets": {
                    "tracked": len(flow["_asset_ids"]) > 0,
                    "count": len(flow["_asset_ids"]),
                    "asset_ids": sorted(flow["_asset_ids"]),
                },
                "chain": {
                    "spec": "tracked" if spec_count > 0 else "missing",
                    "process": "tracked" if process_tracked else "missing",
                    "implementation": "tracked" if implementation_tracked else "missing",
                    "validation": "tracked" if validation_tracked else "missing",
                    "contributors": "tracked" if contributors_tracked else "missing",
                    "contributions": "tracked" if contributions_tracked else "missing",
                    "assets": "tracked" if len(flow["_asset_ids"]) > 0 else "missing",
                },
                "interdependencies": interdependencies,
                "idea_signals": {
                    "value_gap": round(float(idea_signals.get("value_gap", 0.0)), 4),
                    "confidence": round(float(idea_signals.get("confidence", 0.0)), 4),
                    "estimated_cost": round(float(idea_signals.get("estimated_cost", 0.0)), 4),
                    "potential_value": round(float(idea_signals.get("potential_value", 0.0)), 4),
                    "actual_value": round(float(idea_signals.get("actual_value", 0.0)), 4),
                },
            }
        )

    unblock_queue.sort(
        key=lambda row: (
            -float(row.get("unblock_priority_score") or 0.0),
            -len(row.get("downstream_blocked") or []),
            -float(row.get("estimated_unblock_value") or 0.0),
            str(row.get("idea_id") or ""),
        )
    )

    summary = {
        "ideas": len(items),
        "with_spec": sum(1 for row in items if row["spec"]["tracked"]),
        "with_process": sum(1 for row in items if row["process"]["tracked"]),
        "with_implementation": sum(1 for row in items if row["implementation"]["tracked"]),
        "with_validation": sum(1 for row in items if row["validation"]["tracked"]),
        "with_contributors": sum(1 for row in items if row["contributors"]["tracked"]),
        "with_contributions": sum(1 for row in items if row["contributions"]["tracked"]),
        "with_assets": sum(1 for row in items if row["assets"]["tracked"]),
        "blocked_ideas": sum(1 for row in items if row["interdependencies"]["blocked"]),
        "queue_items": len(unblock_queue),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_window_seconds": runtime_window_seconds,
        "filter": {"idea_id": idea_id},
        "summary": summary,
        "unblock_queue": unblock_queue,
        "items": items,
    }


def next_unblock_task_from_flow(
    create_task: bool = False,
    idea_id: str | None = None,
    runtime_window_seconds: int = 86400,
) -> dict[str, Any]:
    flow = build_spec_process_implementation_validation_flow(
        idea_id=idea_id,
        runtime_window_seconds=runtime_window_seconds,
    )
    queue = flow.get("unblock_queue")
    if not isinstance(queue, list) or not queue:
        return {
            "result": "no_blocking_items",
            "flow_summary": flow.get("summary", {}),
            "filter": {"idea_id": idea_id},
        }

    top = queue[0] if isinstance(queue[0], dict) else None
    if top is None:
        return {
            "result": "no_blocking_items",
            "flow_summary": flow.get("summary", {}),
            "filter": {"idea_id": idea_id},
        }

    task_fingerprint = str(top.get("task_fingerprint") or "").strip()
    existing_active = (
        agent_service.find_active_task_by_fingerprint(task_fingerprint)
        if task_fingerprint
        else None
    )

    report: dict[str, Any] = {
        "result": "task_suggested",
        "idea_id": str(top.get("idea_id") or ""),
        "idea_name": str(top.get("idea_name") or ""),
        "blocking_stage": str(top.get("blocking_stage") or ""),
        "upstream_required": list(top.get("upstream_required") or []),
        "downstream_blocked": list(top.get("downstream_blocked") or []),
        "estimated_unblock_cost": float(top.get("estimated_unblock_cost") or 0.0),
        "estimated_unblock_value": float(top.get("estimated_unblock_value") or 0.0),
        "unblock_priority_score": float(top.get("unblock_priority_score") or 0.0),
        "task_type": str(top.get("task_type") or TaskType.IMPL.value),
        "direction": str(top.get("direction") or ""),
        "task_fingerprint": task_fingerprint,
        "flow_summary": flow.get("summary", {}),
        "filter": {"idea_id": idea_id},
    }

    if isinstance(existing_active, dict):
        report["active_task"] = {
            "id": existing_active.get("id"),
            "status": (
                existing_active["status"].value
                if hasattr(existing_active.get("status"), "value")
                else str(existing_active.get("status"))
            ),
            "claimed_by": existing_active.get("claimed_by"),
        }
        if create_task:
            report["result"] = "task_already_active"
            return report

    if not create_task:
        return report

    task_type_raw = str(top.get("task_type") or TaskType.IMPL.value)
    try:
        task_type = TaskType(task_type_raw)
    except ValueError:
        task_type = TaskType.IMPL

    created = agent_service.create_task(
        AgentTaskCreate(
            direction=str(top.get("direction") or ""),
            task_type=task_type,
            context={
                "source": "flow_unblock_task",
                "idea_id": str(top.get("idea_id") or ""),
                "blocking_stage": str(top.get("blocking_stage") or ""),
                "task_fingerprint": task_fingerprint,
                "unblock_priority_score": float(top.get("unblock_priority_score") or 0.0),
                "estimated_unblock_value": float(top.get("estimated_unblock_value") or 0.0),
                "estimated_unblock_cost": float(top.get("estimated_unblock_cost") or 0.0),
                "runtime_window_seconds": runtime_window_seconds,
            },
        )
    )
    report["created_task"] = {
        "id": created["id"],
        "status": created["status"].value if hasattr(created.get("status"), "value") else str(created.get("status")),
        "task_type": (
            created["task_type"].value if hasattr(created.get("task_type"), "value") else str(created.get("task_type"))
        ),
    }
    return report
