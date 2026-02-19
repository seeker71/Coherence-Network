"""Railway management command handlers for Telegram webhook."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.services import release_gate_service

logger = logging.getLogger(__name__)

_DEFAULT_REPOSITORY = "seeker71/Coherence-Network"
_DEFAULT_BRANCH = "main"
_DEFAULT_API_BASE = "https://coherence-network-production.up.railway.app"
_DEFAULT_WEB_BASE = "https://coherence-web-production.up.railway.app"
_JOB_LIST_LIMIT = 8


def _escape_markdown(text: str) -> str:
    out = text or ""
    for ch in ("\\", "`", "*", "_", "[", "]"):
        out = out.replace(ch, f"\\{ch}")
    return out


def _github_token() -> str | None:
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    return token or None


def _short_sha(value: Any) -> str:
    raw = str(value or "").strip()
    return raw[:12] if raw else "unknown"


def _inline_code_list(values: list[Any], *, limit: int = 6) -> str:
    items = [str(value).strip() for value in values if str(value).strip()]
    if not items:
        return "none"
    shown = items[:limit]
    out = ", ".join(f"`{item}`" for item in shown)
    if len(items) > limit:
        out += f", +{len(items) - limit} more"
    return out


def _now_utc_label() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def railway_help_reply() -> str:
    return (
        "*Railway commands*\n"
        "`/railway head`\n"
        "`/railway status`\n"
        "`/railway jobs`\n"
        "`/railway schedule [max_attempts]`\n"
        "`/railway verify`\n"
        "`/railway tick due`\n"
        "`/railway tick all`\n"
        "`/railway tick {job_id}`"
    )


def _format_status_reply(report: dict[str, Any]) -> str:
    result = str(report.get("result") or "unknown")
    reason = str(report.get("reason") or "").strip()
    failing = report.get("failing_checks")
    warnings = report.get("warnings")
    reply = (
        "*Railway status*\n"
        f"Checked: `{_now_utc_label()}`\n"
        f"Repository: `{report.get('repository', _DEFAULT_REPOSITORY)}`\n"
        f"Branch: `{report.get('branch', _DEFAULT_BRANCH)}`\n"
        f"Result: `{result}`\n"
        f"Expected SHA: `{_short_sha(report.get('expected_sha'))}`"
    )
    if isinstance(failing, list):
        reply += f"\nFailing: {_inline_code_list(failing)}"
    if isinstance(warnings, list) and warnings:
        reply += f"\nWarnings: {_inline_code_list(warnings)}"
    if reason:
        reply += f"\nReason: {_escape_markdown(reason[:200])}"
    if result == "public_contract_passed":
        reply += "\nNext: `/railway schedule 8` to monitor future deploy checks"
    else:
        reply += "\nNext: `/railway verify` to create+run a verification job"
    return reply


def _format_jobs_reply(jobs: list[dict[str, Any]]) -> str:
    if not jobs:
        return (
            "*Railway jobs*\n"
            f"Checked: `{_now_utc_label()}`\n"
            "No verification jobs found."
        )
    reply = (
        f"*Railway jobs* ({len(jobs)} total)\n"
        f"Checked: `{_now_utc_label()}`"
    )
    latest = list(reversed(jobs))[:_JOB_LIST_LIMIT]
    for job in latest:
        job_id = str(job.get("job_id") or "?")
        status = str(job.get("status") or "unknown")
        attempts = int(job.get("attempts") or 0)
        max_attempts = int(job.get("max_attempts") or 0)
        if max_attempts > 0:
            reply += f"\n`{job_id}` {status} ({attempts}/{max_attempts})"
        else:
            reply += f"\n`{job_id}` {status} ({attempts})"
    return reply


def _format_verify_reply(created: dict[str, Any], ticked: dict[str, Any]) -> str:
    job_id = str(ticked.get("job_id") or created.get("job_id") or "?")
    status = str(ticked.get("status") or created.get("status") or "unknown")
    attempts = int(ticked.get("attempts") or created.get("attempts") or 0)
    max_attempts = int(ticked.get("max_attempts") or created.get("max_attempts") or 0)
    last_result = ticked.get("last_result")
    result = (
        str(last_result.get("result") or "unknown")
        if isinstance(last_result, dict)
        else "unknown"
    )
    reason = (
        str(last_result.get("reason") or "").strip()
        if isinstance(last_result, dict)
        else ""
    )
    reply = (
        "*Railway verify*\n"
        f"Checked: `{_now_utc_label()}`\n"
        f"Job: `{job_id}`\n"
        f"Status: `{status}`\n"
        f"Attempts: `{attempts}/{max_attempts or '?'}`\n"
        f"Result: `{result}`"
    )
    if reason:
        reply += f"\nReason: {_escape_markdown(reason[:200])}"
    if status == "retrying":
        reply += f"\nNext: `/railway tick {job_id}`"
    elif status == "failed":
        reply += f"\nNext: inspect `/railway status` then retry `/railway tick {job_id}`"
    elif status == "completed":
        reply += "\nNext: `/railway status`"
    return reply


def _format_tick_reply(job: dict[str, Any]) -> str:
    status = str(job.get("status") or "unknown")
    job_id = str(job.get("job_id") or "?")
    if status == "not_found":
        return f"Railway job `{job_id}` not found"
    attempts = int(job.get("attempts") or 0)
    max_attempts = int(job.get("max_attempts") or 0)
    last_result = job.get("last_result")
    result = (
        str(last_result.get("result") or "unknown")
        if isinstance(last_result, dict)
        else "unknown"
    )
    reason = (
        str(last_result.get("reason") or "").strip()
        if isinstance(last_result, dict)
        else str(job.get("last_error") or "").strip()
    )
    reply = (
        "*Railway tick*\n"
        f"Checked: `{_now_utc_label()}`\n"
        f"Job: `{job_id}`\n"
        f"Status: `{status}`\n"
        f"Attempts: `{attempts}/{max_attempts or '?'}`\n"
        f"Result: `{result}`"
    )
    if reason:
        reply += f"\nReason: {_escape_markdown(reason[:200])}"
    if status == "retrying":
        reply += f"\nNext: `/railway tick {job_id}`"
    elif status == "failed":
        reply += "\nNext: `/railway status` and `/railway verify`"
    elif status == "completed":
        reply += "\nNext: `/railway jobs`"
    return reply


def _format_tick_many_reply(result: dict[str, Any], *, due_only: bool) -> str:
    jobs = result.get("jobs") if isinstance(result.get("jobs"), list) else []
    mode = "due" if due_only else "all"
    if not jobs:
        return (
            f"*Railway tick {mode}*\n"
            f"Checked: `{_now_utc_label()}`\n"
            "No jobs were updated."
        )
    reply = (
        f"*Railway tick {mode}* ({len(jobs)} updated)\n"
        f"Checked: `{_now_utc_label()}`"
    )
    for job in jobs[:_JOB_LIST_LIMIT]:
        job_id = str(job.get("job_id") or "?")
        status = str(job.get("status") or "unknown")
        attempts = int(job.get("attempts") or 0)
        max_attempts = int(job.get("max_attempts") or 0)
        result_obj = job.get("last_result")
        result_name = (
            str(result_obj.get("result") or "unknown")
            if isinstance(result_obj, dict)
            else "unknown"
        )
        reply += f"\n`{job_id}` {status} ({attempts}/{max_attempts or '?'}) `{result_name}`"
    reply += "\nNext: `/railway jobs`"
    return reply


def _format_schedule_reply(created: dict[str, Any]) -> str:
    job_id = str(created.get("job_id") or "?")
    status = str(created.get("status") or "unknown")
    attempts = int(created.get("attempts") or 0)
    max_attempts = int(created.get("max_attempts") or 0)
    return (
        "*Railway schedule*\n"
        f"Checked: `{_now_utc_label()}`\n"
        f"Job: `{job_id}`\n"
        f"Status: `{status}`\n"
        f"Attempts: `{attempts}/{max_attempts or '?'}`\n"
        "Next: `/railway tick due`"
    )


def _parse_max_attempts(rest: list[str]) -> int | None:
    if not rest:
        return None
    raw = rest[0].strip()
    if not raw.isdigit():
        return None
    return max(1, min(200, int(raw)))


async def _command_head(token: str | None) -> str:
    sha = await asyncio.to_thread(
        release_gate_service.get_branch_head_sha,
        _DEFAULT_REPOSITORY,
        _DEFAULT_BRANCH,
        token,
        8.0,
    )
    if not sha:
        return (
            "*Railway head*\n"
            f"Repository: `{_DEFAULT_REPOSITORY}`\n"
            f"Branch: `{_DEFAULT_BRANCH}`\n"
            "SHA: `unavailable`"
        )
    return (
        "*Railway head*\n"
        f"Repository: `{_DEFAULT_REPOSITORY}`\n"
        f"Branch: `{_DEFAULT_BRANCH}`\n"
        f"SHA: `{_short_sha(sha)}`"
    )


async def _command_status(token: str | None) -> str:
    report = await asyncio.to_thread(
        release_gate_service.evaluate_public_deploy_contract_report,
        repository=_DEFAULT_REPOSITORY,
        branch=_DEFAULT_BRANCH,
        api_base=_DEFAULT_API_BASE,
        web_base=_DEFAULT_WEB_BASE,
        timeout=8.0,
        github_token=token,
    )
    return _format_status_reply(report if isinstance(report, dict) else {})


async def _command_jobs() -> str:
    jobs = await asyncio.to_thread(release_gate_service.list_public_deploy_verification_jobs)
    return _format_jobs_reply(jobs if isinstance(jobs, list) else [])


async def _create_job(token: str | None, *, max_attempts: int | None) -> dict[str, Any]:
    created = await asyncio.to_thread(
        release_gate_service.create_public_deploy_verification_job,
        repository=_DEFAULT_REPOSITORY,
        branch=_DEFAULT_BRANCH,
        api_base=_DEFAULT_API_BASE,
        web_base=_DEFAULT_WEB_BASE,
        max_attempts=max_attempts,
        timeout=8.0,
        poll_seconds=30.0,
        github_token=token,
    )
    return created if isinstance(created, dict) else {}


async def _command_schedule(token: str | None, rest: list[str]) -> str:
    created = await _create_job(token, max_attempts=_parse_max_attempts(rest))
    if not created:
        return "Railway schedule failed: unable to create verification job"
    return _format_schedule_reply(created)


async def _command_verify(token: str | None, rest: list[str]) -> str:
    created = await _create_job(token, max_attempts=_parse_max_attempts(rest))
    if not created:
        return "Railway verify failed: unable to create verification job"
    job_id = str(created.get("job_id") or "").strip()
    if not job_id:
        return "Railway verify failed: missing job id"
    ticked = await asyncio.to_thread(
        release_gate_service.tick_public_deploy_verification_job,
        job_id=job_id,
        github_token=token,
    )
    return _format_verify_reply(created, ticked if isinstance(ticked, dict) else {})


async def _command_tick(token: str | None, rest: list[str]) -> str:
    if not rest:
        return "Usage: /railway tick {job_id}"
    target = rest[0].strip().lower()
    if target in {"due", "all"}:
        due_only = target != "all"
        ticked_many = await asyncio.to_thread(
            release_gate_service.tick_public_deploy_verification_jobs,
            github_token=token,
            due_only=due_only,
        )
        if not isinstance(ticked_many, dict):
            return "Railway tick failed: unable to update verification jobs"
        return _format_tick_many_reply(ticked_many, due_only=due_only)

    job_id = rest[0].strip()
    if not job_id:
        return "Usage: /railway tick {job_id}"
    ticked = await asyncio.to_thread(
        release_gate_service.tick_public_deploy_verification_job,
        job_id=job_id,
        github_token=token,
    )
    return _format_tick_reply(ticked if isinstance(ticked, dict) else {})


async def handle_railway_command(arg: str) -> str:
    args = (arg or "").split()
    action = args[0].lower() if args else "help"
    rest = args[1:] if len(args) > 1 else []
    token = _github_token()
    handlers = {
        "head": lambda: _command_head(token),
        "status": lambda: _command_status(token),
        "jobs": _command_jobs,
        "schedule": lambda: _command_schedule(token, rest),
        "create": lambda: _command_schedule(token, rest),
        "verify": lambda: _command_verify(token, rest),
        "tick": lambda: _command_tick(token, rest),
    }
    if action in {"help", "h", "?"}:
        return railway_help_reply()
    if action not in handlers:
        return railway_help_reply()

    try:
        return await handlers[action]()
    except Exception as exc:
        logger.exception("Telegram railway command failed: action=%s", action)
        msg = str(exc).strip() or "unknown error"
        return f"Railway command failed: {_escape_markdown(msg[:240])}"
