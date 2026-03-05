"""Public API: claim, update, heartbeat, get run state."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from app.services.agent_run_state import db, helpers, local_store, row_payload
from app.services.agent_run_state.models import AgentRunStateRecord


def claim_run_state(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int = 120,
    attempt: int = 1,
    branch: str = "",
    repo_path: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lease_seconds = helpers._normalize_lease_seconds(lease_seconds)
    if not db.get_database_url():
        return local_store.claim_local(
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            attempt=attempt,
            branch=branch,
            repo_path=repo_path,
            metadata=metadata,
        )

    db._ensure_schema()
    now = helpers._now()
    lease_until = now + timedelta(seconds=lease_seconds)
    with db._session() as session:
        row = session.get(AgentRunStateRecord, task_id)
        if row is not None:
            owner_active = helpers._aware(row.lease_expires_at) > now and not helpers._terminal_status(row.status)
            owner_same = row.run_id == run_id and row.worker_id == worker_id
            if owner_active and not owner_same:
                return row_payload._row_to_payload(row, claimed=False, detail="lease_owned_by_other_worker")

        if row is None:
            row = AgentRunStateRecord(
                task_id=task_id,
                run_id=run_id,
                worker_id=worker_id,
                status="running",
                attempt=max(1, int(attempt)),
                branch=branch,
                repo_path=repo_path,
                head_sha="",
                checkpoint_sha="",
                failure_class="",
                next_action="execute_command",
                metadata_json=json.dumps(metadata or {}),
                lease_expires_at=lease_until,
                last_heartbeat_at=now,
                started_at=now,
                updated_at=now,
                completed_at=None,
            )
            session.add(row)
        else:
            row.run_id = run_id
            row.worker_id = worker_id
            row.status = "running"
            row.attempt = max(1, int(attempt))
            row.branch = branch
            row.repo_path = repo_path
            row.metadata_json = json.dumps(metadata or {})
            row.lease_expires_at = lease_until
            row.last_heartbeat_at = now
            row.updated_at = now
            if row.started_at is None:
                row.started_at = now
        session.flush()
        return row_payload._row_to_payload(row, claimed=True)


def update_run_state(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    patch: dict[str, Any] | None = None,
    lease_seconds: int | None = None,
    require_owner: bool = True,
) -> dict[str, Any]:
    patch = patch or {}
    if not db.get_database_url():
        return local_store.update_local(
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch=patch,
            lease_seconds=lease_seconds,
            require_owner=require_owner,
        )

    db._ensure_schema()
    now = helpers._now()
    with db._session() as session:
        row = session.get(AgentRunStateRecord, task_id)
        if row is None:
            return {"claimed": False, "task_id": task_id, "detail": "run_state_not_found"}
        if require_owner and (row.run_id != run_id or row.worker_id != worker_id):
            return row_payload._row_to_payload(row, claimed=False, detail="lease_owner_mismatch")
        row_payload._patch_row(row, patch)
        row.updated_at = now
        row.last_heartbeat_at = now
        if lease_seconds is not None:
            row.lease_expires_at = now + timedelta(seconds=helpers._normalize_lease_seconds(lease_seconds))
        if helpers._terminal_status(row.status):
            row.lease_expires_at = now
            if row.completed_at is None:
                row.completed_at = now
        session.flush()
        return row_payload._row_to_payload(row, claimed=True)


def heartbeat_run_state(
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    lease_seconds: int = 120,
) -> dict[str, Any]:
    return update_run_state(
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        patch={"status": "running", "next_action": "execute_command", "last_heartbeat_at": helpers._iso(helpers._now())},
        lease_seconds=lease_seconds,
        require_owner=True,
    )


def get_run_state(task_id: str) -> dict[str, Any] | None:
    if not db.get_database_url():
        return local_store.get_local(task_id)

    db._ensure_schema()
    with db._session() as session:
        row = session.get(AgentRunStateRecord, task_id)
        if row is None:
            return None
        return row_payload._row_to_payload(row, claimed=True)
