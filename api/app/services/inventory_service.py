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

import httpx

from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service, idea_service, route_registry_service, runtime_service, value_lineage_service


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

_SPEC_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": [], "source": "fallback"}
_SPEC_DISCOVERY_CACHE_TTL_SECONDS = 300.0
_EVIDENCE_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": [], "source": "none"}
_EVIDENCE_DISCOVERY_CACHE_TTL_SECONDS = 180.0


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
    return FALLBACK_SPECS[: max(1, min(limit, 2000))], "fallback"


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
    try:
        with httpx.Client(timeout=8.0, headers=_github_headers()) as client:
            response = client.get(list_url, params={"ref": ref})
            response.raise_for_status()
            rows = response.json()
            if isinstance(rows, list):
                evidence_rows = [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and isinstance(row.get("name"), str)
                    and row["name"].startswith("commit_evidence_")
                    and row["name"].endswith(".json")
                ][: max(1, min(limit, 1200))]
                for row in evidence_rows:
                    download_url = row.get("download_url")
                    if not isinstance(download_url, str) or not download_url:
                        continue
                    payload_resp = client.get(download_url)
                    if payload_resp.status_code != 200:
                        continue
                    payload = payload_resp.json()
                    if not isinstance(payload, dict):
                        continue
                    payload["_evidence_file"] = str(row.get("path") or row.get("name") or "github")
                    remote_out.append(payload)
    except (httpx.HTTPError, ValueError, TypeError):
        remote_out = []

    _EVIDENCE_DISCOVERY_CACHE["items"] = remote_out
    _EVIDENCE_DISCOVERY_CACHE["expires_at"] = now + _EVIDENCE_DISCOVERY_CACHE_TTL_SECONDS
    _EVIDENCE_DISCOVERY_CACHE["source"] = "github" if remote_out else "none"
    return remote_out


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
        if not (path.startswith("/api") or path.startswith("/v1")):
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
            if not (full_path.startswith("/api") or full_path.startswith("/v1")):
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
        if not (subpath.startswith("/api") or subpath.startswith("/v1")):
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


def build_endpoint_traceability_inventory() -> dict[str, Any]:
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

        idea_ids = set(evidence_idea_ids)
        if canonical_idea_id:
            idea_ids.add(canonical_idea_id)
        idea_source = "missing"
        if canonical_idea_id and evidence_idea_ids:
            idea_source = "canonical+evidence"
        elif canonical_idea_id:
            idea_source = "canonical"
        elif evidence_idea_ids:
            idea_source = "evidence"

        primary_idea_id = canonical_idea_id
        if not primary_idea_id and len(idea_ids) == 1:
            primary_idea_id = next(iter(idea_ids))

        idea_tracked = len(idea_ids) > 0
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
                    "idea_ids": sorted(idea_ids),
                    "source": idea_source,
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
            "spec_count": len(specs),
            "spec_source": spec_source,
            "canonical_route_count": len(canonical_by_path),
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


def build_spec_process_implementation_validation_flow(
    idea_id: str | None = None,
    runtime_window_seconds: int = 86400,
) -> dict[str, Any]:
    portfolio = idea_service.list_ideas()
    idea_name_map = {item.id: item.name for item in portfolio.ideas}

    runtime_rows = runtime_service.summarize_by_idea(seconds=runtime_window_seconds)
    runtime_by_idea = {row.idea_id: row for row in runtime_rows}

    lineage_links = value_lineage_service.list_links(limit=1000)
    usage_events = value_lineage_service.list_usage_events(limit=5000)

    usage_by_lineage_count: dict[str, int] = {}
    usage_by_lineage_value: dict[str, float] = {}
    for event in usage_events:
        usage_by_lineage_count[event.lineage_id] = usage_by_lineage_count.get(event.lineage_id, 0) + 1
        usage_by_lineage_value[event.lineage_id] = usage_by_lineage_value.get(event.lineage_id, 0.0) + float(event.value)

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

    items: list[dict[str, Any]] = []
    for current_idea_id in sorted(flows.keys()):
        flow = flows[current_idea_id]
        spec_count = len(flow["_spec_ids"])
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
        contributions_tracked = bool(flow["usage_events_count"] > 0 or flow["measured_value_total"] > 0)

        items.append(
            {
                "idea_id": current_idea_id,
                "idea_name": flow["idea_name"],
                "spec": {
                    "count": spec_count,
                    "spec_ids": sorted(flow["_spec_ids"]),
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
                    "by_role": {
                        role: sorted(ids)
                        for role, ids in sorted(flow["_contributors_by_role"].items(), key=lambda item: item[0])
                    },
                },
                "contributions": {
                    "tracked": contributions_tracked,
                    "usage_events_count": int(flow["usage_events_count"]),
                    "measured_value_total": round(float(flow["measured_value_total"]), 4),
                },
                "chain": {
                    "spec": "tracked" if spec_count > 0 else "missing",
                    "process": "tracked" if process_tracked else "missing",
                    "implementation": "tracked" if implementation_tracked else "missing",
                    "validation": "tracked" if validation_tracked else "missing",
                    "contributors": "tracked" if contributors_tracked else "missing",
                    "contributions": "tracked" if contributions_tracked else "missing",
                },
            }
        )

    summary = {
        "ideas": len(items),
        "with_spec": sum(1 for row in items if row["spec"]["tracked"]),
        "with_process": sum(1 for row in items if row["process"]["tracked"]),
        "with_implementation": sum(1 for row in items if row["implementation"]["tracked"]),
        "with_validation": sum(1 for row in items if row["validation"]["tracked"]),
        "with_contributors": sum(1 for row in items if row["contributors"]["tracked"]),
        "with_contributions": sum(1 for row in items if row["contributions"]["tracked"]),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_window_seconds": runtime_window_seconds,
        "filter": {"idea_id": idea_id},
        "summary": summary,
        "items": items,
    }
