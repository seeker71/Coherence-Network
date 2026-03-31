"""Spec discovery: project root, GitHub/local specs, spec coverage, implementation gap tasks."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service, spec_registry_service


def _project_root() -> Path:
    configured = os.getenv("COHERENCE_PROJECT_ROOT", "").strip()
    if configured:
        configured_path = Path(configured).expanduser().resolve()
        if configured_path.exists():
            return configured_path

    source_path = Path(__file__).resolve()
    for candidate in [source_path, *source_path.parents]:
        if (candidate / "api" / "app").exists():
            return candidate
    for candidate in [source_path, *source_path.parents]:
        if (candidate / "app").exists() and (candidate / "scripts").exists():
            return candidate
    return source_path.parents[3]


_SPEC_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": [], "source": "none"}
_SPEC_DISCOVERY_CACHE_TTL_SECONDS = 300.0
_SPEC_COVERAGE_FILE = "docs/SPEC-COVERAGE.md"
_SPEC_COVERAGE_SKIP_HINTS = (
    "backlog",
    "placeholder",
    "template",
    "test-backlog",
    "sprint0-graph-foundation-indexer-api",
)


def _tracking_repository() -> str:
    return os.getenv("TRACKING_REPOSITORY", "seeker71/Coherence-Network")


def _tracking_ref() -> str:
    return os.getenv("TRACKING_REPOSITORY_REF", "main")


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _idea_api_path(idea_id: str) -> str:
    return f"/api/ideas/{quote(str(idea_id), safe='')}"


def _spec_api_path(spec_id: str) -> str:
    return f"/api/spec-registry/{quote(str(spec_id), safe='')}"


def _sort_spec_items(rows: list[dict]) -> list[dict]:
    def key(row: dict) -> tuple[int, int, str]:
        spec_id = str(row.get("spec_id") or "")
        if spec_id.isdigit():
            return (0, int(spec_id), "")
        return (1, 0, spec_id)

    return sorted(rows, key=key)


def _normalize_spec_item(row: dict[str, Any]) -> dict[str, Any]:
    spec_id = str(row.get("spec_id") or "").strip()
    path_value = str(row.get("path") or "").strip()
    api_path = str(row.get("api_path") or "").strip()
    source_path = str(row.get("source_path") or "").strip()
    if path_value.startswith("specs/") and not source_path:
        source_path = path_value
    if not api_path and spec_id:
        api_path = _spec_api_path(spec_id)
    normalized = dict(row)
    if api_path:
        normalized["api_path"] = api_path
        normalized["path"] = api_path
    if source_path:
        normalized["source_path"] = source_path
    return normalized


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
            _normalize_spec_item(
                {"spec_id": spec_id, "title": title, "path": f"specs/{path.name}"}
            )
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
            out.append(
                _normalize_spec_item({"spec_id": spec_id, "title": title, "path": path})
            )
    except httpx.HTTPError:
        return []

    out = _sort_spec_items(out)
    _SPEC_DISCOVERY_CACHE["items"] = out
    _SPEC_DISCOVERY_CACHE["expires_at"] = now + _SPEC_DISCOVERY_CACHE_TTL_SECONDS
    _SPEC_DISCOVERY_CACHE["source"] = "github"
    return out


def _discover_specs(limit: int = 300) -> tuple[list[dict], str]:
    local = [_normalize_spec_item(item) for item in _discover_specs_local(limit=limit)]
    if len(local) >= 5:
        return local, "local"
    remote = [_normalize_spec_item(item) for item in _discover_specs_from_github(limit=limit)]
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


def _spec_registry_roi_by_prefix(limit: int = 5000) -> dict[str, float]:
    roi_by_prefix: dict[str, float] = {}
    try:
        rows = spec_registry_service.list_specs(limit=max(1, min(limit, 10000)))
    except Exception:
        return roi_by_prefix
    for row in rows:
        raw_spec_id = str(getattr(row, "spec_id", "") or "").strip()
        match = re.match(r"^(\d{3})", raw_spec_id)
        if not match:
            continue
        prefix = match.group(1)
        try:
            estimated_roi = float(getattr(row, "estimated_roi", 0.0) or 0.0)
        except (TypeError, ValueError):
            estimated_roi = 0.0
        previous = roi_by_prefix.get(prefix)
        if previous is None or estimated_roi > previous:
            roi_by_prefix[prefix] = round(estimated_roi, 4)
    return roi_by_prefix


def _spec_source_path_for_id(spec_id: str) -> str:
    root = _project_root()
    specs_dir = root / "specs"
    if not specs_dir.exists():
        return ""
    matches = sorted(specs_dir.glob(f"{spec_id}-*.md"))
    if not matches:
        return ""
    try:
        return matches[0].relative_to(root).as_posix()
    except ValueError:
        return matches[0].as_posix()


def _parse_spec_coverage_status_summary(limit: int = 500) -> list[dict[str, Any]]:
    root = _project_root()
    coverage_path = root / _SPEC_COVERAGE_FILE
    if not coverage_path.exists():
        return []
    try:
        lines = coverage_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    in_status_summary = False
    in_table = False
    rows: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not in_status_summary:
            if line.startswith("## Status Summary"):
                in_status_summary = True
            continue
        if line.startswith("## ") and not line.startswith("## Status Summary"):
            break
        if line.startswith("| Spec |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            if rows:
                break
            continue
        parts = [part.strip() for part in raw_line.split("|")[1:-1]]
        if len(parts) < 4:
            continue
        if parts[0].lower() == "spec" or set(parts[0]) == {"-"}:
            continue
        spec_cell = parts[0]
        match = re.match(r"^(\d{3})\s+(.+)$", spec_cell)
        if not match:
            continue
        spec_id = match.group(1)
        title = match.group(2).strip()
        present = parts[1] if len(parts) > 1 else ""
        specd = parts[2] if len(parts) > 2 else ""
        tested = parts[3] if len(parts) > 3 else ""
        notes = parts[4] if len(parts) > 4 else ""
        source_path = _spec_source_path_for_id(spec_id)
        rows.append(
            {
                "spec_id": spec_id,
                "title": title,
                "present": present,
                "specd": specd,
                "tested": tested,
                "notes": notes,
                "source_path": source_path,
            }
        )
        if len(rows) >= max(1, min(limit, 5000)):
            break
    return rows


def _should_skip_spec_gap_task(row: dict[str, Any]) -> bool:
    present = str(row.get("present") or "")
    if "—" in present:
        return True
    source_path = str(row.get("source_path") or "").lower()
    title = str(row.get("title") or "").lower()
    check = f"{source_path} {title}"
    return any(hint in check for hint in _SPEC_COVERAGE_SKIP_HINTS)


def _spec_implementation_gap_candidates(limit: int = 200) -> list[dict[str, Any]]:
    rows = _parse_spec_coverage_status_summary(limit=max(limit * 3, 200))
    roi_by_prefix = _spec_registry_roi_by_prefix(limit=5000)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        present = str(row.get("present") or "")
        specd = str(row.get("specd") or "")
        if "✓" in present:
            continue
        if "✓" not in specd:
            continue
        if _should_skip_spec_gap_task(row):
            continue
        spec_id = str(row.get("spec_id") or "").strip()
        if not spec_id:
            continue
        estimated_roi = round(float(roi_by_prefix.get(spec_id, 0.0) or 0.0), 4)
        source_path = str(row.get("source_path") or "").strip()
        candidates.append(
            {
                "spec_id": spec_id,
                "title": str(row.get("title") or "").strip(),
                "source_path": source_path,
                "present": present,
                "specd": specd,
                "tested": str(row.get("tested") or ""),
                "notes": str(row.get("notes") or ""),
                "estimated_roi": estimated_roi,
                "roi_source": "spec_registry.estimated_roi" if estimated_roi > 0 else "default_zero",
                "task_fingerprint": f"spec_implementation_gap::{spec_id}",
            }
        )
    candidates.sort(
        key=lambda item: (-float(item.get("estimated_roi") or 0.0), str(item.get("spec_id") or "")),
    )
    return candidates[: max(1, min(limit, 500))]


def sync_spec_implementation_gap_tasks(create_task: bool = False, limit: int = 200) -> dict[str, Any]:
    candidates = _spec_implementation_gap_candidates(limit=max(1, min(limit, 500)))
    if not candidates:
        return {
            "result": "no_spec_implementation_gaps",
            "gaps_count": 0,
            "created_count": 0,
            "skipped_existing_count": 0,
            "ordered_gaps": [],
            "created_tasks": [],
        }
    ordered_gaps: list[dict[str, Any]] = []
    created_tasks: list[dict[str, Any]] = []
    skipped_existing_count = 0
    for candidate in candidates:
        row = dict(candidate)
        fingerprint = str(row.get("task_fingerprint") or "").strip()
        active = agent_service.find_active_task_by_fingerprint(fingerprint) if fingerprint else None
        if isinstance(active, dict):
            row["active_task"] = {
                "id": active.get("id"),
                "status": (
                    active["status"].value
                    if hasattr(active.get("status"), "value")
                    else str(active.get("status"))
                ),
                "claimed_by": active.get("claimed_by"),
            }
            if create_task:
                skipped_existing_count += 1
        ordered_gaps.append(row)
        if not create_task or isinstance(active, dict):
            continue
        spec_id = str(row.get("spec_id") or "").strip()
        title = str(row.get("title") or "").strip()
        source_path = str(row.get("source_path") or "").strip()
        direction = (
            f"Implement spec {spec_id} ({title}) from {source_path or 'spec file'}. "
            "Follow the spec verification contract, add/update tests for behavior, and run local validation. "
            "Do not modify tests only to force pass."
        )
        task = agent_service.create_task(
            AgentTaskCreate(
                direction=direction,
                task_type=TaskType.IMPL,
                context={
                    "source": "spec_implementation_gap",
                    "spec_id": spec_id,
                    "spec_title": title,
                    "spec_path": source_path,
                    "estimated_roi": float(row.get("estimated_roi") or 0.0),
                    "task_fingerprint": fingerprint,
                },
            )
        )
        created_tasks.append(
            {
                "task_id": task["id"],
                "spec_id": spec_id,
                "estimated_roi": float(row.get("estimated_roi") or 0.0),
            }
        )
    return {
        "result": "spec_implementation_gap_tasks_synced",
        "gaps_count": len(ordered_gaps),
        "created_count": len(created_tasks),
        "skipped_existing_count": skipped_existing_count,
        "ordered_gaps": ordered_gaps,
        "created_tasks": created_tasks,
    }
