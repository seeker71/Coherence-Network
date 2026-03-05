"""Local JSON file storage for agent run state (no-DB fallback)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any

from app.services.agent_run_state.helpers import (
    _fallback_path,
    _local_file_lock,
    _now,
    _iso,
    _normalize_lease_seconds,
    _terminal_status,
    get_local_lock,
)


def _read_local() -> dict[str, Any]:
    path = _fallback_path()
    if not path.exists():
        return {"tasks": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": {}}
    if not isinstance(payload, dict):
        return {"tasks": {}}
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        payload["tasks"] = {}
    return payload


def _write_local(payload: dict[str, Any]) -> None:
    path = _fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(payload, tmp, indent=2)
            tmp.flush()
            try:
                os.fsync(tmp.fileno())
            except OSError:
                pass
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def _claim_local(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int,
    attempt: int,
    branch: str,
    repo_path: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    now = _now()
    lease_until = now + timedelta(seconds=lease_seconds)
    lock = get_local_lock()
    with lock, _local_file_lock():
        payload = _read_local()
        tasks = payload.setdefault("tasks", {})
        current = tasks.get(task_id)
        if isinstance(current, dict):
            owner_run = str(current.get("run_id") or "")
            owner_worker = str(current.get("worker_id") or "")
            owner_status = str(current.get("status") or "")
            expires_raw = str(current.get("lease_expires_at") or "")
            try:
                expires_at = datetime.fromisoformat(expires_raw) if expires_raw else now - timedelta(seconds=1)
            except Exception:
                expires_at = now - timedelta(seconds=1)
            active_owner = expires_at > now and not _terminal_status(owner_status)
            if active_owner and (owner_run != run_id or owner_worker != worker_id):
                return {
                    "claimed": False,
                    "task_id": task_id,
                    "run_id": owner_run,
                    "worker_id": owner_worker,
                    "status": owner_status,
                    "attempt": int(current.get("attempt") or 0) or None,
                    "branch": str(current.get("branch") or ""),
                    "repo_path": str(current.get("repo_path") or ""),
                    "head_sha": str(current.get("head_sha") or ""),
                    "checkpoint_sha": str(current.get("checkpoint_sha") or ""),
                    "failure_class": str(current.get("failure_class") or ""),
                    "next_action": str(current.get("next_action") or ""),
                    "lease_expires_at": _iso(expires_at),
                    "last_heartbeat_at": str(current.get("last_heartbeat_at") or ""),
                    "updated_at": str(current.get("updated_at") or ""),
                    "detail": "lease_owned_by_other_worker",
                }

        row = {
            "task_id": task_id,
            "run_id": run_id,
            "worker_id": worker_id,
            "status": "running",
            "attempt": int(attempt),
            "branch": branch,
            "repo_path": repo_path,
            "head_sha": "",
            "checkpoint_sha": "",
            "failure_class": "",
            "next_action": "execute_command",
            "metadata": metadata or {},
            "lease_expires_at": _iso(lease_until),
            "last_heartbeat_at": _iso(now),
            "started_at": _iso(now),
            "updated_at": _iso(now),
            "completed_at": None,
        }
        tasks[task_id] = row
        _write_local(payload)
        return {**row, "claimed": True, "detail": None}


def _update_local(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    patch: dict[str, Any],
    lease_seconds: int | None,
    require_owner: bool,
) -> dict[str, Any]:
    now = _now()
    lock = get_local_lock()
    with lock, _local_file_lock():
        payload = _read_local()
        tasks = payload.setdefault("tasks", {})
        row = tasks.get(task_id)
        if not isinstance(row, dict):
            return {"claimed": False, "task_id": task_id, "detail": "run_state_not_found"}
        owner_ok = str(row.get("run_id") or "") == run_id and str(row.get("worker_id") or "") == worker_id
        if require_owner and not owner_ok:
            return {"claimed": False, "task_id": task_id, "detail": "lease_owner_mismatch"}
        if "status" in patch:
            row["status"] = str(patch.get("status") or row.get("status") or "").strip() or row.get("status", "")
        for key in ("attempt", "branch", "repo_path", "head_sha", "checkpoint_sha", "failure_class", "next_action"):
            if key in patch:
                row[key] = patch.get(key)
        if "metadata" in patch and isinstance(patch.get("metadata"), dict):
            row["metadata"] = patch.get("metadata")
        if "completed_at" in patch:
            row["completed_at"] = patch.get("completed_at")
        row["last_heartbeat_at"] = _iso(now)
        if lease_seconds is not None:
            row["lease_expires_at"] = _iso(now + timedelta(seconds=_normalize_lease_seconds(lease_seconds)))
        if _terminal_status(str(row.get("status") or "")):
            row["lease_expires_at"] = _iso(now)
        row["updated_at"] = _iso(now)
        tasks[task_id] = row
        _write_local(payload)
        return {**row, "claimed": True, "detail": None}


def claim_local(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int,
    attempt: int,
    branch: str,
    repo_path: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    return _claim_local(
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        attempt=attempt,
        branch=branch,
        repo_path=repo_path,
        metadata=metadata,
    )


def update_local(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    patch: dict[str, Any],
    lease_seconds: int | None,
    require_owner: bool,
) -> dict[str, Any]:
    return _update_local(
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        patch=patch,
        lease_seconds=lease_seconds,
        require_owner=require_owner,
    )


def get_local(task_id: str) -> dict[str, Any] | None:
    lock = get_local_lock()
    with lock, _local_file_lock():
        payload = _read_local()
        tasks = payload.get("tasks")
        if not isinstance(tasks, dict):
            return None
        row = tasks.get(task_id)
        if not isinstance(row, dict):
            return None
        return {"claimed": True, **row}
