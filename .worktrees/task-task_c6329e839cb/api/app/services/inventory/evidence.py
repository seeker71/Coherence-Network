"""Commit evidence: read from files/Github/DB, latest records, inventory."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config_loader import get_str
from app.services import commit_evidence_service
from app.services.inventory.spec_discovery import (
    _github_headers,
    _project_root,
    _tracking_ref,
    _tracking_repository,
)

_EVIDENCE_DISCOVERY_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": [], "source": "none"}
_EVIDENCE_DISCOVERY_CACHE_TTL_SECONDS = 180.0
_DB_EVIDENCE_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": []}
_DB_EVIDENCE_CACHE_TTL_SECONDS = 60.0


def _commit_evidence_dir() -> Path:
    custom = get_str("commit_evidence", "directory", default="")
    if custom:
        return Path(custom)
    return _project_root() / "docs" / "system_audit"


def _normalize_validation_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"pass", "fail", "pending"}:
        return status
    return "pending"


def _read_commit_evidence_records_from_files(evidence_dir: Path, limit: int) -> list[dict[str, Any]]:
    files: list[Path] = []
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
    return out


def _read_commit_evidence_records_from_github(limit: int) -> list[dict[str, Any]]:
    now = time.time()
    cached = _EVIDENCE_DISCOVERY_CACHE.get("items")
    if isinstance(cached, list) and _EVIDENCE_DISCOVERY_CACHE.get("expires_at", 0.0) > now:
        return [item for item in cached if isinstance(item, dict)][: max(1, min(limit, 3000))]

    repository = _tracking_repository()
    ref = _tracking_ref()
    list_url = f"https://api.github.com/repos/{repository}/contents/docs/system_audit"
    remote_out: list[dict[str, Any]] = []
    has_token = bool(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))
    try:
        with httpx.Client(timeout=8.0, headers=_github_headers()) as client:
            response = client.get(list_url, params={"ref": ref})
            response.raise_for_status()
            rows = response.json()
            if isinstance(rows, list):
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


def _read_commit_evidence_records(limit: int = 400) -> list[dict[str, Any]]:
    """Read commit evidence from the unified DB (single source of truth).

    Falls back to file/github discovery only if the DB has no records,
    to bootstrap initial data.
    """
    from app.services import unified_db as _udb

    db_url = _udb.database_url()
    source_key = f"db:{db_url}"
    now = time.time()
    cached_source = str(_DB_EVIDENCE_CACHE.get("source_key", ""))
    if (
        cached_source == source_key
        and _DB_EVIDENCE_CACHE.get("expires_at", 0.0) > now
        and isinstance(_DB_EVIDENCE_CACHE.get("items"), list)
    ):
        requested_limit = max(1, min(int(limit), 5000))
        return [row for row in _DB_EVIDENCE_CACHE["items"][:requested_limit]]

    try:
        requested_limit = max(1, min(int(limit), 5000))
        rows = commit_evidence_service.list_records(limit=requested_limit)
        _DB_EVIDENCE_CACHE["expires_at"] = now + _DB_EVIDENCE_CACHE_TTL_SECONDS
        _DB_EVIDENCE_CACHE["items"] = rows
        _DB_EVIDENCE_CACHE["source_key"] = source_key
        if rows:
            return rows
    except Exception:
        pass

    # Bootstrap: no DB records yet — try files then github
    evidence_dir = _commit_evidence_dir()
    out = _read_commit_evidence_records_from_files(evidence_dir, limit)
    if out:
        return out
    return _read_commit_evidence_records_from_github(limit)


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


def build_commit_evidence_inventory(limit: int = 50) -> dict[str, Any]:
    requested = max(1, min(limit, 500))
    items = _latest_commit_evidence_records(limit=requested)
    info = commit_evidence_service.backend_info()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limit": requested,
        "storage": info,
        "items": items,
    }
