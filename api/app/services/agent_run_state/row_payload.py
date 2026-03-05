"""Row-to-payload conversion and row patching for agent run state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.services.agent_run_state.helpers import _aware, _iso, _safe_metadata
from app.services.agent_run_state.models import AgentRunStateRecord


def _row_to_payload(row: AgentRunStateRecord, *, claimed: bool, detail: str | None = None) -> dict[str, Any]:
    return {
        "claimed": bool(claimed),
        "task_id": row.task_id,
        "run_id": row.run_id,
        "worker_id": row.worker_id,
        "status": row.status,
        "attempt": int(row.attempt),
        "branch": row.branch or "",
        "repo_path": row.repo_path or "",
        "head_sha": row.head_sha or "",
        "checkpoint_sha": row.checkpoint_sha or "",
        "failure_class": row.failure_class or "",
        "next_action": row.next_action or "",
        "lease_expires_at": _iso(_aware(row.lease_expires_at)),
        "last_heartbeat_at": _iso(_aware(row.last_heartbeat_at)),
        "updated_at": _iso(_aware(row.updated_at)),
        "detail": detail,
    }


def _patch_row(row: AgentRunStateRecord, patch: dict[str, Any]) -> None:
    if "status" in patch:
        row.status = str(patch.get("status") or "").strip() or row.status
    if "attempt" in patch:
        try:
            row.attempt = max(1, int(patch.get("attempt")))
        except Exception:
            pass
    if "branch" in patch:
        row.branch = str(patch.get("branch") or "").strip()
    if "repo_path" in patch:
        row.repo_path = str(patch.get("repo_path") or "").strip()
    if "head_sha" in patch:
        row.head_sha = str(patch.get("head_sha") or "").strip()
    if "checkpoint_sha" in patch:
        row.checkpoint_sha = str(patch.get("checkpoint_sha") or "").strip()
    if "failure_class" in patch:
        row.failure_class = str(patch.get("failure_class") or "").strip()
    if "next_action" in patch:
        row.next_action = str(patch.get("next_action") or "").strip()
    if "metadata" in patch:
        row.metadata_json = json.dumps(_safe_metadata(patch.get("metadata")))
    if "started_at" in patch and isinstance(patch.get("started_at"), str):
        try:
            row.started_at = datetime.fromisoformat(str(patch.get("started_at")))
        except Exception:
            pass
    if "completed_at" in patch and isinstance(patch.get("completed_at"), str):
        try:
            row.completed_at = datetime.fromisoformat(str(patch.get("completed_at")))
        except Exception:
            pass
    if "last_heartbeat_at" in patch and isinstance(patch.get("last_heartbeat_at"), str):
        try:
            row.last_heartbeat_at = datetime.fromisoformat(str(patch.get("last_heartbeat_at")))
        except Exception:
            pass
