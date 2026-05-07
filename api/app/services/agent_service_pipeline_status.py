"""Agent pipeline status: running, pending, completed with attention and diagnostics."""

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from app.models.agent import (
    ControlPlaneExecution,
    ControlPlaneProof,
    ControlPlaneSource,
    ControlPlaneTask,
    ControlPlaneWorkspace,
)
from app.services.agent_service_store import _ensure_store_loaded, _store
from app.services.agent_service_task_derive import (
    failure_classification,
    status_value,
    task_output_text,
    task_type_name,
)


def _pipeline_task_status_item(task: dict[str, Any], now: datetime) -> tuple[str, dict[str, Any]]:
    created = task.get("created_at")
    updated = task.get("updated_at")
    started = task.get("started_at")
    st = task.get("status")
    st_val = st.value if hasattr(st, "value") else str(st)

    def _ts(obj: Any) -> str:
        return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)

    def _seconds_ago(ts: Any) -> int | None:
        if ts is None:
            return None
        try:
            return int((now - ts).total_seconds())
        except Exception:
            return None

    def _duration(start_ts: Any, end_ts: Any) -> int | None:
        if start_ts is None or end_ts is None:
            return None
        try:
            return int((end_ts - start_ts).total_seconds())
        except Exception:
            return None

    item = {
        "id": task.get("id"),
        "status": st_val,
        "task_type": task.get("task_type"),
        "model": task.get("model"),
        "direction": (task.get("direction") or "")[:100],
        "claimed_by": task.get("claimed_by"),
        "created_at": _ts(created),
        "updated_at": _ts(updated),
        "wait_seconds": _seconds_ago(created) if st_val == "pending" else None,
        "running_seconds": _seconds_ago(started) if st_val == "running" and started else None,
        "duration_seconds": _duration(started, updated)
        if st_val in ("completed", "failed") and started and updated
        else None,
    }
    return st_val, item


def normalize_task_to_control_plane(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize an internal agent task into the Symphony-aligned task shape."""
    task_id = str(task.get("id") or "").strip()
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    source = context.get("source") if isinstance(context.get("source"), dict) else {}
    workspace = context.get("workspace") if isinstance(context.get("workspace"), dict) else {}
    proof = context.get("proof") if isinstance(context.get("proof"), dict) else {}
    execution = context.get("execution") if isinstance(context.get("execution"), dict) else {}
    followthrough_blockers = proof.get("followthrough_blockers")
    if not isinstance(followthrough_blockers, list):
        followthrough_blockers = []

    def _string_list(key: str) -> list[str]:
        value = context.get(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    task_type = task_type_name(task.get("task_type")) or "unknown"
    model = str(task.get("model") or execution.get("model") or "").strip() or None
    claimed_by = str(task.get("claimed_by") or execution.get("claimed_by") or "").strip() or None
    control_task = ControlPlaneTask(
        id=task_id,
        source=ControlPlaneSource(
            kind=str(source.get("kind") or context.get("source_kind") or "internal_api"),
            external_id=source.get("external_id") or context.get("external_id"),
            url=source.get("url") or context.get("url"),
        ),
        title=str(context.get("title") or task.get("direction") or task_id)[:160],
        description=str(task.get("direction") or ""),
        state=status_value(task.get("status")) or "pending",
        priority=context.get("priority") if isinstance(context.get("priority"), int) else None,
        labels=_string_list("labels"),
        blocked_by=_string_list("blocked_by"),
        task_type=task_type,
        files_allowed=_string_list("files_allowed"),
        done_when=_string_list("done_when"),
        commands=_string_list("commands"),
        constraints=_string_list("constraints"),
        workspace=ControlPlaneWorkspace(
            branch=workspace.get("branch") or context.get("branch"),
            path=workspace.get("path") or context.get("workspace_path"),
            key=workspace.get("key") or context.get("workspace_key"),
        ),
        execution=ControlPlaneExecution(
            executor=execution.get("executor") or context.get("executor"),
            model=model,
            claimed_by=claimed_by,
            claimed_at=task.get("claimed_at") or execution.get("claimed_at"),
            attempts=int(execution.get("attempts") or context.get("attempts") or 0),
            max_attempts=int(execution.get("max_attempts") or context.get("max_attempts") or 1),
            next_retry_at=execution.get("next_retry_at") or context.get("next_retry_at"),
        ),
        proof=ControlPlaneProof(
            local_validation=str(proof.get("local_validation") or "pending"),
            evidence_file=proof.get("evidence_file") or context.get("evidence_file"),
            pr_url=proof.get("pr_url") or context.get("pr_url"),
            ci_status=str(proof.get("ci_status") or "pending"),
            deploy_status=str(proof.get("deploy_status") or "not_required"),
            followthrough_status=str(proof.get("followthrough_status") or "clear"),
            followthrough_blockers=followthrough_blockers,
        ),
    )
    return control_task.model_dump(mode="json")


def _collect_pipeline_status_items(now: datetime) -> tuple[list[dict], list[dict], list[dict]]:
    running, pending, completed = [], [], []
    for t in _store.values():
        st_val, item = _pipeline_task_status_item(t, now=now)
        if st_val == "running":
            running.append(item)
        elif st_val == "pending":
            pending.append(item)
        else:
            completed.append(item)
    return running, pending, completed


def _parse_github_time(value: str) -> datetime | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _minutes_since_github_time(value: str, now: datetime) -> float:
    parsed = _parse_github_time(value)
    if parsed is None:
        return 0.0
    return max(0.0, (now - parsed).total_seconds() / 60.0)


_FOLLOWTHROUGH_CACHE: dict[tuple[str, float], tuple[float, dict[str, Any]]] = {}
_FOLLOWTHROUGH_CACHE_TTL_SECONDS, _FOLLOWTHROUGH_GH_TIMEOUT_SECONDS = 30.0, 0.75


def _gh_json(args: list[str], *, timeout: float = 5) -> Any:
    out = subprocess.check_output(["gh", *args], text=True, timeout=timeout)
    return json.loads(out or "null")


def _status_rollup_errors(rollup: Any) -> list[str]:
    if not isinstance(rollup, list):
        return []
    errors: list[str] = []
    for row in rollup:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("context") or "unknown").strip()
        row_type = str(row.get("__typename") or "").strip()
        if row_type == "CheckRun":
            status = str(row.get("status") or "").strip().upper()
            conclusion = str(row.get("conclusion") or "").strip().upper()
            if status != "COMPLETED":
                errors.append(f"{name}:status={status or 'UNKNOWN'}")
            elif conclusion not in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
                errors.append(f"{name}:conclusion={conclusion or 'UNKNOWN'}")
        elif row_type == "StatusContext":
            state = str(row.get("state") or "").strip().upper()
            if state != "SUCCESS":
                errors.append(f"{name}:state={state or 'UNKNOWN'}")
    return errors


def _followthrough_action(detail: dict[str, Any], check_errors: list[str]) -> tuple[str, str]:
    if bool(detail.get("isDraft")):
        return "draft_pr", "finish or close draft PR before starting new work"
    merge_state = str(detail.get("mergeStateStatus") or "").strip().upper()
    if check_errors:
        return "failing_check", "inspect failing checks and rerun after repair"
    if merge_state == "CLEAN":
        return "stale_pr", "merge or close stale green PR"
    return "stale_pr", f"rebase or resolve merge state {merge_state or 'UNKNOWN'}"


def _followthrough_blocker_from_pr(
    row: dict[str, Any],
    *,
    repo: str,
    now: datetime,
    stale_minutes: float,
) -> dict[str, Any] | None:
    head = str(row.get("headRefName") or "").strip()
    if not head.startswith("codex/") or bool(row.get("isDraft")):
        return None
    age_minutes = _minutes_since_github_time(str(row.get("updatedAt") or ""), now)
    if age_minutes < stale_minutes:
        return None
    number = int(row.get("number") or 0)
    detail: dict[str, Any] = {}
    if number > 0:
        try:
            payload = _gh_json(
                [
                    "pr",
                    "view",
                    str(number),
                    "--repo",
                    repo,
                    "--json",
                    "isDraft,mergeStateStatus,statusCheckRollup",
                ]
            )
            detail = payload if isinstance(payload, dict) else {}
        except Exception:
            detail = {}
    check_errors = _status_rollup_errors(detail.get("statusCheckRollup"))
    kind, action = _followthrough_action(detail, check_errors)
    url = str(row.get("url") or "").strip()
    command = (
        f"gh pr merge {number} --repo {repo} --merge --delete-branch"
        if kind == "stale_pr" and action.startswith("merge")
        else f"gh pr checks {number} --repo {repo}"
    )
    return {
        "kind": kind,
        "url": url,
        "owner": "codex",
        "command": command,
        "reason": action,
        "pr_number": number,
        "head": head,
        "age_minutes": round(age_minutes, 1),
        "check_errors": check_errors,
    }


def collect_followthrough_status(
    *,
    now: datetime,
    repo: str = "seeker71/Coherence-Network",
    stale_minutes: float = 90.0,
) -> dict[str, Any]:
    """Best-effort live follow-through view for open Codex PRs."""
    cache_key = (repo, float(stale_minutes))
    now_monotonic = time.monotonic()
    cached = _FOLLOWTHROUGH_CACHE.get(cache_key)
    if cached and now_monotonic - cached[0] <= _FOLLOWTHROUGH_CACHE_TTL_SECONDS:
        return dict(cached[1])

    if shutil.which("gh") is None:
        return {"status": "unknown", "collector_available": False, "reason": "gh_not_available", "blockers": []}
    try:
        payload = _gh_json(
            ["pr", "list", "--repo", repo, "--state", "open", "--limit", "200", "--json",
             "number,title,headRefName,updatedAt,url,isDraft"],
            timeout=_FOLLOWTHROUGH_GH_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        result = {"status": "unknown", "collector_available": False,
                  "reason": f"gh_query_failed:{type(exc).__name__}", "blockers": []}
        _FOLLOWTHROUGH_CACHE[cache_key] = (now_monotonic, dict(result))
        return result
    rows = payload if isinstance(payload, list) else []
    blockers = [
        blocker
        for row in rows
        if isinstance(row, dict)
        for blocker in [_followthrough_blocker_from_pr(row, repo=repo, now=now, stale_minutes=stale_minutes)]
        if blocker is not None
    ]
    codex_open_count = len([
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("headRefName") or "").startswith("codex/")
        and not bool(row.get("isDraft"))
    ])
    result = {
        "status": "blocked" if blockers else "clear",
        "collector_available": True,
        "repo": repo,
        "stale_minutes": stale_minutes,
        "codex_open_prs": codex_open_count,
        "blockers": blockers,
    }
    _FOLLOWTHROUGH_CACHE[cache_key] = (now_monotonic, dict(result))
    return result


def _orchestration_tissue(
    running: list[dict],
    pending: list[dict],
    attention: dict[str, Any],
    followthrough: dict[str, Any],
) -> dict[str, Any]:
    blocker_count = len(followthrough.get("blockers") or [])
    stale_tissue = blocker_count + (1 if attention.get("stuck") else 0)
    hardened_tissue = 0
    if attention.get("repeated_failures"):
        hardened_tissue += 1
    if attention.get("executor_fail"):
        hardened_tissue += 1
    if attention.get("low_success_rate"):
        hardened_tissue += 1
    circulation_score = max(0, 100 - stale_tissue * 25 - hardened_tissue * 15)
    vitality_score = max(0, circulation_score - (10 if pending and not running else 0))
    if followthrough.get("status") == "unknown":
        circulation = "unverified"
    elif stale_tissue or hardened_tissue:
        circulation = "constricted"
    else:
        circulation = "flowing"
    signals: list[str] = []
    if blocker_count:
        signals.append(f"{blocker_count} stale follow-through blocker(s)")
    if attention.get("stuck"):
        signals.append("pending work is waiting without active circulation")
    if attention.get("repeated_failures"):
        signals.append("repeated failures indicate hardened execution tissue")
    if not signals:
        signals.append("no stale follow-through or hardened execution signals detected")
    return {
        "vitality_score": vitality_score,
        "circulation": circulation,
        "circulation_score": circulation_score,
        "stale_tissue_count": stale_tissue,
        "hardened_tissue_count": hardened_tissue,
        "signals": signals,
    }


def _pipeline_latest_activity(
    running: list[dict], completed: list[dict]
) -> tuple[dict | None, dict | None]:
    latest_request = latest_response = None
    if running:
        task = _store.get(running[0]["id"])
        if task:
            latest_request = {
                "task_id": task.get("id"),
                "status": "running",
                "direction": task.get("direction"),
                "prompt_preview": (task.get("command") or "")[:500],
            }
    if completed:
        task = _store.get(completed[0]["id"])
        if task:
            if not latest_request:
                latest_request = {
                    "task_id": task.get("id"),
                    "status": task.get("status"),
                    "direction": task.get("direction"),
                    "prompt_preview": (task.get("command") or "")[:500],
                }
            out = task_output_text(task)
            latest_response = {
                "task_id": task.get("id"),
                "status": task.get("status"),
                "output_preview": out[:2000],
                "output_len": len(out),
            }
    return latest_request, latest_response


def _pipeline_attention_summary(
    running: list[dict], pending: list[dict], completed: list[dict]
) -> dict[str, Any]:
    attention_flags = []
    stuck = False
    if pending and not running:
        wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
        if wait_secs and max(wait_secs) > 600:
            stuck = True
            attention_flags.append("stuck")
    repeated_failures = False
    if len(completed) >= 3:
        last_three = completed[:3]
        if all(status_value((_store.get(c["id"]) or {}).get("status")) == "failed" for c in last_three):
            repeated_failures = True
            attention_flags.append("repeated_failures")
    output_empty = False
    for completed_item in completed[:5]:
        t = _store.get(completed_item["id"]) or {}
        if len(task_output_text(t)) == 0 and status_value(t.get("status")) == "completed":
            output_empty = True
            attention_flags.append("output_empty")
            break
    executor_fail = False
    for completed_item in completed[:5]:
        t = _store.get(completed_item["id"]) or {}
        if len(task_output_text(t)) == 0 and status_value(t.get("status")) == "failed":
            executor_fail = True
            attention_flags.append("executor_fail")
            break
    low_success_rate = False
    try:
        from app.services.metrics_service import get_aggregates
        agg = get_aggregates()
        sr = agg.get("success_rate", {}) or {}
        total = sr.get("total", 0) or 0
        rate = float(sr.get("rate", 0) or 0)
        if total >= 10 and rate < 0.8:
            low_success_rate = True
            attention_flags.append("low_success_rate")
    except Exception:
        pass
    by_phase = {"spec": 0, "impl": 0, "test": 0, "review": 0}
    for item in running + pending:
        tt = item.get("task_type")
        tt_val = tt.value if hasattr(tt, "value") else str(tt)
        if tt_val in by_phase:
            by_phase[tt_val] += 1
    return {
        "stuck": stuck,
        "repeated_failures": repeated_failures,
        "output_empty": output_empty,
        "executor_fail": executor_fail,
        "low_success_rate": low_success_rate,
        "flags": attention_flags,
        "by_phase": by_phase,
    }


def _pipeline_queue_diagnostics(
    running: list[dict], pending: list[dict], completed: list[dict]
) -> dict[str, Any]:
    pending_by_task_type = {}
    running_by_task_type = {}
    for item in pending:
        key = task_type_name(item.get("task_type")) or "unknown"
        pending_by_task_type[key] = pending_by_task_type.get(key, 0) + 1
    for item in running:
        key = task_type_name(item.get("task_type")) or "unknown"
        running_by_task_type[key] = running_by_task_type.get(key, 0) + 1
    reason_counts: dict[str, int] = {}
    signature_counts: dict[str, int] = {}
    recent_failed: list[dict[str, Any]] = []
    recent_zero_output_resolved: list[dict[str, Any]] = []
    for item in completed[:20]:
        task = _store.get(item.get("id")) or {}
        st = status_value(task.get("status"))
        if st not in {"completed", "failed"}:
            continue
        if len(task_output_text(task).strip()) > 0:
            continue
        recent_zero_output_resolved.append(
            {
                "task_id": task.get("id"),
                "task_type": task_type_name(task.get("task_type")) or "unknown",
                "status": st,
            }
        )
    for task in _recent_failed_tasks(limit=12):
        classified = failure_classification(task)
        reason = classified["bucket"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        ctx = task.get("context") or {}
        failure_signature = str(ctx.get("failure_signature") or "").strip() if isinstance(ctx, dict) else ""
        signature = classified.get("signature") or failure_signature
        if signature:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
        recent_failed.append({
            "task_id": task.get("id"),
            "task_type": task_type_name(task.get("task_type")) or "unknown",
            "reason": reason,
            "signature": signature,
        })
    recent_failed_reasons = [
        {"reason": r, "count": c} for r, c in sorted(reason_counts.items(), key=lambda row: (-row[1], row[0]))
    ]
    recent_failed_signatures = [
        {"signature": r, "count": c} for r, c in sorted(signature_counts.items(), key=lambda row: (-row[1], row[0]))
    ]
    total_pending = sum(pending_by_task_type.values())
    dominant_pending_type = ""
    dominant_pending_share = 0.0
    if total_pending > 0:
        dominant_pending_type, dominant_count = max(pending_by_task_type.items(), key=lambda row: row[1])
        dominant_pending_share = round(float(dominant_count) / float(total_pending), 4)
    queue_mix_warning = bool(total_pending >= 5 and dominant_pending_share >= 0.8)
    return {
        "pending_by_task_type": pending_by_task_type,
        "running_by_task_type": running_by_task_type,
        "recent_failed_count": len(recent_failed),
        "recent_failed": recent_failed[:5],
        "recent_failed_reasons": recent_failed_reasons,
        "recent_failed_signatures": recent_failed_signatures,
        "recent_zero_output_resolved_count": len(recent_zero_output_resolved),
        "recent_zero_output_resolved": recent_zero_output_resolved[:5],
        "queue_mix_warning": queue_mix_warning,
        "dominant_pending_task_type": dominant_pending_type,
        "dominant_pending_share": dominant_pending_share,
    }


def _task_updated_timestamp(task: dict[str, Any]) -> float:
    value = task.get("updated_at") or task.get("created_at")
    if hasattr(value, "timestamp"):
        try:
            return float(value.timestamp())
        except Exception:
            return 0.0
    return 0.0


def _recent_failed_tasks(*, limit: int) -> list[dict[str, Any]]:
    failed = [task for task in _store.values() if status_value(task.get("status")) == "failed"]
    failed.sort(key=_task_updated_timestamp, reverse=True)
    return failed[:limit]


def get_pipeline_status(now_utc=None) -> dict[str, Any]:
    """Pipeline visibility: running, pending with wait times, recent completed with duration."""
    _ensure_store_loaded(include_output=False)
    now = now_utc or datetime.now(timezone.utc)
    running, pending, completed = _collect_pipeline_status_items(now)
    completed.sort(key=lambda x: x.get("updated_at") or x.get("created_at", ""), reverse=True)
    latest_request, latest_response = _pipeline_latest_activity(running, completed)
    attention = _pipeline_attention_summary(running, pending, completed)
    diagnostics = _pipeline_queue_diagnostics(running, pending, completed)
    followthrough = collect_followthrough_status(now=now)
    if followthrough.get("status") == "blocked":
        attention.setdefault("flags", []).append("followthrough_blocked")
    normalized_control_plane = [
        normalize_task_to_control_plane(_store.get(item["id"]) or {})
        for item in [*running[:5], *pending[:5]]
        if item.get("id") in _store
    ]
    tissue = _orchestration_tissue(running, pending, attention, followthrough)
    return {
        "running": running[:10],
        "pending": sorted(pending, key=lambda x: x.get("created_at", ""))[:20],
        "running_by_phase": attention.pop("by_phase"),
        "recent_completed": [
            {**c, "output_len": len(task_output_text(_store.get(c["id"]) or {}))}
            for c in completed[:10]
        ],
        "latest_request": latest_request,
        "latest_response": latest_response,
        "attention": {
            "stuck": attention["stuck"],
            "repeated_failures": attention["repeated_failures"],
            "output_empty": attention["output_empty"],
            "executor_fail": attention["executor_fail"],
            "low_success_rate": attention["low_success_rate"],
                "flags": attention["flags"],
        },
        "diagnostics": diagnostics,
        "followthrough": followthrough,
        "orchestration_tissue": tissue,
        "control_plane": {
            "normalized_active": normalized_control_plane,
            "normalized_active_count": len(normalized_control_plane),
        },
    }
