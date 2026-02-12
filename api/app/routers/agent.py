"""Agent orchestration API routes."""

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query

from typing import Optional

logger = logging.getLogger(__name__)

from app.models.agent import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskList,
    AgentTaskListItem,
    AgentTaskUpdate,
    RouteResponse,
    TaskStatus,
    TaskType,
)
from app.models.error import ErrorDetail
from app.services import agent_service

router = APIRouter()


def _task_to_item(task: dict) -> dict:
    """Convert stored task to list item (no command/output)."""
    return {
        "id": task["id"],
        "direction": task["direction"],
        "task_type": task["task_type"],
        "status": task["status"],
        "model": task["model"],
        "progress_pct": task.get("progress_pct"),
        "current_step": task.get("current_step"),
        "decision_prompt": task.get("decision_prompt"),
        "decision": task.get("decision"),
        "created_at": task["created_at"],
        "updated_at": task.get("updated_at"),
    }


def _task_to_attention_item(task: dict) -> dict:
    """Like _task_to_item but includes output (spec 003: GET /attention)."""
    out = _task_to_item(task)
    out["output"] = task.get("output")
    return out


def _task_to_full(task: dict) -> dict:
    """Convert stored task to full response."""
    return {
        "id": task["id"],
        "direction": task["direction"],
        "task_type": task["task_type"],
        "status": task["status"],
        "model": task["model"],
        "command": task["command"],
        "output": task.get("output"),
        "context": task.get("context"),
        "progress_pct": task.get("progress_pct"),
        "current_step": task.get("current_step"),
        "decision_prompt": task.get("decision_prompt"),
        "decision": task.get("decision"),
        "created_at": task["created_at"],
        "updated_at": task.get("updated_at"),
    }


@router.post(
    "/agent/tasks",
    status_code=201,
    responses={422: {"description": "Invalid task_type, empty direction, or validation error (detail: list of {loc, msg, type})"}},
)
async def create_task(data: AgentTaskCreate) -> AgentTask:
    """Submit a task and get routed model + command."""
    task = agent_service.create_task(data)
    return AgentTask(**_task_to_full(task))


@router.get("/agent/tasks")
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    task_type: Optional[TaskType] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentTaskList:
    """List tasks with optional filters. Pagination: limit, offset."""
    items, total = agent_service.list_tasks(
        status=status, task_type=task_type, limit=limit, offset=offset
    )
    return AgentTaskList(
        tasks=[AgentTaskListItem(**_task_to_item(t)) for t in items],
        total=total,
    )


@router.get("/agent/tasks/attention")
async def get_attention_tasks(limit: int = Query(20, ge=1, le=100)) -> dict:
    """List tasks with status needs_decision or failed only (spec 003: includes output, decision_prompt)."""
    items, total = agent_service.get_attention_tasks(limit=limit)
    return {
        "tasks": [_task_to_attention_item(t) for t in items],
        "total": total,
    }


@router.get("/agent/tasks/count")
async def get_task_count() -> dict:
    """Lightweight task counts for dashboards (total, by_status)."""
    return agent_service.get_task_count()


@router.get(
    "/agent/tasks/{task_id}",
    responses={404: {"description": "Task not found", "model": ErrorDetail}},
)
async def get_task(task_id: str) -> AgentTask:
    """Get task by id."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTask(**_task_to_full(task))


def _format_alert(task: dict) -> str:
    """Format task for Telegram alert. Includes decision_prompt when set."""
    status = task.get("status", "?")
    status_str = status.value if hasattr(status, "value") else str(status)
    direction = (task.get("direction") or "")[:80]
    msg = f"⚠️ *{status_str}*\n\n{direction}\n\nTask: `{task.get('id', '')}`"
    if task.get("decision_prompt"):
        msg += f"\n\n{task['decision_prompt']}"
    return msg


@router.patch(
    "/agent/tasks/{task_id}",
    responses={
        400: {"description": "At least one field required", "model": ErrorDetail},
        404: {"description": "Task not found", "model": ErrorDetail},
    },
)
async def update_task(
    task_id: str,
    data: AgentTaskUpdate,
    background_tasks: BackgroundTasks,
) -> AgentTask:
    """Update task. Supports status, output, progress_pct, current_step, decision_prompt, decision.
    Sends Telegram alert for needs_decision/failed. When decision present and task needs_decision, sets status→running.
    """
    if all(
        getattr(data, f) is None
        for f in ("status", "output", "progress_pct", "current_step", "decision_prompt", "decision")
    ):
        raise HTTPException(status_code=400, detail="At least one field required")
    task = agent_service.update_task(
        task_id,
        status=data.status,
        output=data.output,
        progress_pct=data.progress_pct,
        current_step=data.current_step,
        decision_prompt=data.decision_prompt,
        decision=data.decision,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if data.status in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED):
        from app.services import telegram_adapter

        if telegram_adapter.is_configured():
            msg = _format_alert(task)
            if data.output:
                msg += f"\n\nOutput: {data.output[:200]}"
            background_tasks.add_task(telegram_adapter.send_alert, msg)
    if data.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        try:
            from app.services.metrics_service import record_task

            created = task.get("created_at")
            updated = task.get("updated_at")
            end_ts = updated if updated is not None else datetime.now(timezone.utc)
            if created is not None:
                if hasattr(created, "timestamp") and hasattr(end_ts, "timestamp"):
                    duration_seconds = (end_ts - created).total_seconds()
                else:
                    created_dt = created if isinstance(created, datetime) else datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    updated_dt = end_ts if isinstance(end_ts, datetime) else datetime.fromisoformat(str(end_ts).replace("Z", "+00:00"))
                    duration_seconds = (updated_dt - created_dt).total_seconds()
                duration_seconds = max(0.0, duration_seconds)
            else:
                duration_seconds = 0.0
            task_type_str = task["task_type"].value if hasattr(task["task_type"], "value") else str(task["task_type"])
            status_str = task["status"].value if hasattr(task["status"], "value") else str(task["status"])
            record_task(
                task_id=task_id,
                task_type=task_type_str,
                model=task.get("model", "unknown"),
                duration_seconds=round(duration_seconds, 1),
                status=status_str,
            )
        except ImportError:
            pass
    return AgentTask(**_task_to_full(task))


@router.post("/agent/telegram/webhook")
async def telegram_webhook(update: dict = Body(...)) -> dict:
    """Receive Telegram updates. Parse commands and reply.

    Commands: /status, /tasks [status], /task {id}, /direction "..." or plain text.
    Requires TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS.
    """
    from app.services import telegram_adapter
    from app.services import telegram_diagnostics

    telegram_diagnostics.record_webhook(update)
    logger.info("Telegram webhook received: %s", list(update.keys()))
    if not telegram_adapter.has_token():
        logger.warning("Telegram webhook: no token configured")
        return {"ok": True}
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        logger.info("Telegram webhook: no message in update")
        return {"ok": True}
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()
    user_id = (msg.get("from") or {}).get("id")
    logger.info("Telegram webhook: user_id=%s chat_id=%s text=%r", user_id, chat_id, text[:50])
    # When TELEGRAM_ALLOWED_USER_IDS is set, require a known user (reject missing from / unauthenticated)
    if not telegram_adapter.is_user_allowed(user_id):
        if user_id is None:
            logger.warning("Telegram webhook: message has no 'from' (reject when TELEGRAM_ALLOWED_USER_IDS set)")
        else:
            logger.warning("Telegram webhook: user %s not allowed (check TELEGRAM_ALLOWED_USER_IDS)", user_id)
        return {"ok": True}
    cmd, arg = telegram_adapter.parse_command(text)
    reply = ""
    if cmd == "status":
        summary = agent_service.get_review_summary()
        needs = summary["needs_attention"]
        reply = f"*Agent status*\nTasks: {summary['total']}\n"
        reply += "\n".join(f"  {k}: {v}" for k, v in summary["by_status"].items())
        if needs:
            reply += f"\n\n⚠️ *{len(needs)} need attention*"
    elif cmd == "usage":
        usage = agent_service.get_usage_summary()
        reply = "*Usage by model*\n"
        for model, u in usage.get("by_model", {}).items():
            reply += f"\n`{model}`: {u.get('count', 0)} tasks"
            if u.get("by_status"):
                reply += " " + ", ".join(f"{k}:{v}" for k, v in u["by_status"].items())
        reply += "\n\n*Routing*: " + ", ".join(
            f"{t}={d['model']}" for t, d in usage.get("routing", {}).items()
        )
    elif cmd == "tasks":
        status_filter = arg if arg in ("pending", "running", "completed", "failed", "needs_decision") else None
        status_enum = TaskStatus(status_filter) if status_filter else None
        items, total = agent_service.list_tasks(status=status_enum, limit=10)
        reply = f"*Tasks* ({total} total)\n"
        for t in items:
            reply += f"\n`{t['id']}` {t['status']} — {str(t['direction'])[:50]}..."
    elif cmd == "task":
        if not arg:
            reply = "Usage: /task {id}"
        else:
            task = agent_service.get_task(arg.strip())
            if not task:
                reply = f"Task `{arg}` not found"
            else:
                reply = _format_alert(task) if task.get("status") in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED) else f"*Task* `{task['id']}`\n{task['status']}\n{task.get('direction', '')[:200]}"
    elif cmd == "reply":
        # /reply {task_id} {decision}
        parts = (arg or "").split(maxsplit=1)
        task_id = (parts[0] or "").strip()
        decision = (parts[1] or "").strip() if len(parts) > 1 else ""
        if not task_id or not decision:
            reply = "Usage: /reply {task_id} {decision}"
        else:
            task = agent_service.update_task(task_id, decision=decision)
            if not task:
                reply = f"Task `{task_id}` not found"
            else:
                reply = f"Decision recorded for `{task_id}`"
    elif cmd == "attention":
        items, total = agent_service.get_attention_tasks(limit=10)
        reply = f"*Attention* ({total} need action)\n"
        for t in items:
            reply += f"\n`{t['id']}` {t['status']} — {str(t.get('direction', ''))[:40]}..."
            if t.get("decision_prompt"):
                reply += f"\n  _{t['decision_prompt'][:60]}_"
    elif cmd == "direction" or (not cmd and text):
        direction = arg if cmd == "direction" else text
        if not direction:
            reply = "Send a direction: e.g. /direction Add GET /api/projects"
        else:
            created = agent_service.create_task(AgentTaskCreate(direction=direction, task_type=TaskType.IMPL))
            reply = f"✅ Task `{created['id']}`\n\nRun:\n`{created['command']}`"
    else:
        reply = "Commands: /status, /tasks [status], /task {id}, /reply {id} {decision}, /attention, /usage, /direction \"...\" or just type your direction"
    if reply:
        ok = await telegram_adapter.send_reply(chat_id, reply)
        logger.info("Telegram reply sent: %s", ok)
        if not ok:
            logger.warning("Telegram send_reply failed — check bot token and that user has /start with bot")
    return {"ok": True}


@router.get("/agent/usage")
async def get_usage() -> dict:
    """Per-model usage and routing. For /usage bot command and dashboards."""
    return agent_service.get_usage_summary()


@router.get("/agent/fatal-issues")
async def get_fatal_issues() -> dict:
    """Unrecoverable failures. Check when autonomous; no user interaction needed until fatal."""
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    path = os.path.join(logs_dir, "fatal_issues.json")
    if not os.path.isfile(path):
        return {"fatal": False}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {"fatal": True, **data}
    except Exception:
        return {"fatal": False}


@router.get("/agent/monitor-issues")
async def get_monitor_issues() -> dict:
    """Monitor issues from automated pipeline check. Checkable; use to react and improve. Spec 027."""
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    path = os.path.join(logs_dir, "monitor_issues.json")
    if not os.path.isfile(path):
        return {"issues": [], "last_check": None}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"issues": [], "last_check": None}


@router.get("/agent/metrics")
async def get_metrics() -> dict:
    """Task metrics: success rate, execution time, by task_type, by model. Spec 026 Phase 1."""
    try:
        from app.services.metrics_service import get_aggregates

        return get_aggregates()
    except ImportError:
        return {
            "success_rate": {"completed": 0, "failed": 0, "total": 0, "rate": 0.0},
            "execution_time": {"p50_seconds": 0, "p95_seconds": 0},
            "by_task_type": {},
            "by_model": {},
        }


@router.get("/agent/effectiveness")
async def get_effectiveness() -> dict:
    """Pipeline effectiveness: throughput, success rate, issue tracking, progress, goal proximity.
    Use to measure and improve the pipeline, agents, and progress toward overall goal."""
    try:
        from app.services.effectiveness_service import get_effectiveness as _get

        return _get()
    except ImportError:
        return {
            "throughput": {"completed_7d": 0, "tasks_per_day": 0},
            "success_rate": 0.0,
            "issues": {"open": 0, "resolved_7d": 0},
            "progress": {},
            "goal_proximity": 0.0,
            "heal_resolved_count": 0,
            "top_issues_by_priority": [],
        }


def _agent_logs_dir() -> str:
    """Logs directory for status-report and meta_questions; overridable in tests."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")


def _merge_meta_questions_into_report(report: dict, logs_dir: str) -> dict:
    """If report lacks meta_questions but api/logs/meta_questions.json exists, merge it (surface unanswered/failed)."""
    if "meta_questions" in report:
        return report
    mq_path = os.path.join(logs_dir, "meta_questions.json")
    if not os.path.isfile(mq_path):
        return report
    try:
        with open(mq_path, encoding="utf-8") as f:
            mq = json.load(f)
    except Exception:
        return report
    summary = mq.get("summary") or {}
    unanswered = summary.get("unanswered") or []
    failed = summary.get("failed") or []
    mq_status = "ok" if not unanswered and not failed else "needs_attention"
    report["meta_questions"] = {
        "status": mq_status,
        "last_run": mq.get("run_at"),
        "unanswered": unanswered,
        "failed": failed,
    }
    if mq_status == "needs_attention":
        report.setdefault("overall", {})
        report["overall"].setdefault("needs_attention", [])
        if "meta_questions" not in report["overall"]["needs_attention"]:
            report["overall"]["needs_attention"] = report["overall"]["needs_attention"] + ["meta_questions"]
        report["overall"]["status"] = "needs_attention"
    return report


@router.get("/agent/status-report")
async def get_status_report() -> dict:
    """Hierarchical pipeline status (Layer 0 Goal → 1 Orchestration → 2 Execution → 3 Attention).
    Machine and human readable. Written by monitor each check. Includes meta_questions (unanswered/failed) when present."""
    logs_dir = _agent_logs_dir()
    path = os.path.join(logs_dir, "pipeline_status_report.json")
    if not os.path.isfile(path):
        out = {
            "generated_at": None,
            "overall": {"status": "unknown", "going_well": [], "needs_attention": []},
            "layer_0_goal": {"status": "unknown", "summary": "Report not yet generated by monitor"},
            "layer_1_orchestration": {"status": "unknown", "summary": ""},
            "layer_2_execution": {"status": "unknown", "summary": ""},
            "layer_3_attention": {"status": "unknown", "summary": ""},
        }
        return _merge_meta_questions_into_report(out, logs_dir)
    try:
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        return _merge_meta_questions_into_report(report, logs_dir)
    except Exception:
        out = {"generated_at": None, "overall": {"status": "unknown", "going_well": [], "needs_attention": []}, "error": "Could not read report"}
        return _merge_meta_questions_into_report(out, logs_dir)


@router.get("/agent/pipeline-status")
async def get_pipeline_status() -> dict:
    """Pipeline visibility: running task, pending with wait times, recent completed with duration.
    Includes project manager state when available. For running tasks, includes live_tail (last 20 lines of streamed log)."""
    status = agent_service.get_pipeline_status()
    # Add PM state from file if present (prefer overnight state when running overnight)
    import json
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    state_file = os.path.join(logs_dir, "project_manager_state.json")
    overnight_file = os.path.join(logs_dir, "project_manager_state_overnight.json")
    if os.path.isfile(overnight_file) and (
        not os.path.isfile(state_file) or os.path.getmtime(overnight_file) > os.path.getmtime(state_file)
    ):
        state_file = overnight_file
    if os.path.isfile(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                status["project_manager"] = json.load(f)
        except Exception:
            status["project_manager"] = None
    else:
        status["project_manager"] = None
    # Add live tail from running task's log (streamed during execution)
    running = status.get("running") or []
    if running:
        rid = running[0].get("id")
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", f"task_{rid}.log")
        if os.path.isfile(log_path):
            try:
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()
                status["running"][0]["live_tail"] = [ln.rstrip() for ln in lines[-20:] if ln.strip()]
            except Exception:
                status["running"][0]["live_tail"] = None
        else:
            status["running"][0]["live_tail"] = None
    return status


@router.get(
    "/agent/tasks/{task_id}/log",
    responses={404: {"description": "Task not found or task log not found", "model": ErrorDetail}},
)
async def get_task_log(task_id: str) -> dict:
    """Full task log (prompt, command, output). File is streamed during execution, complete on finish."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", f"task_{task_id}.log")
    if not os.path.isfile(log_path):
        raise HTTPException(status_code=404, detail="Task log not found")
    with open(log_path, encoding="utf-8") as f:
        log_content = f.read()
    return {"task_id": task_id, "log": log_content, "command": task.get("command"), "output": task.get("output")}


@router.get("/agent/route", response_model=RouteResponse)
async def route(
    task_type: TaskType = Query(...),
    executor: Optional[str] = Query("claude", description="Executor: claude (default) or cursor"),
) -> RouteResponse:
    """Get routing for a task type (no persistence). Use executor=cursor for Cursor CLI."""
    return RouteResponse(**agent_service.get_route(task_type, executor=executor or "claude"))


@router.get("/agent/telegram/diagnostics")
async def telegram_diagnostics() -> dict:
    """Diagnostics: last webhook events, send results, config (masked). For debugging."""
    from app.services import telegram_adapter
    from app.services import telegram_diagnostics as diag

    token = (
        (os.environ.get("TELEGRAM_BOT_TOKEN") or "")[:8] + "..." if os.environ.get("TELEGRAM_BOT_TOKEN") else None
    )
    return {
        "config": {
            "has_token": telegram_adapter.has_token(),
            "token_prefix": token,
            "chat_ids": os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if os.environ.get("TELEGRAM_CHAT_IDS") else [],
            "allowed_user_ids": (
                os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
                if os.environ.get("TELEGRAM_ALLOWED_USER_IDS") else []
            ),
        },
        "webhook_events": diag.get_webhook_events(),
        "send_results": diag.get_send_results(),
    }


@router.post("/agent/telegram/test-send")
async def telegram_test_send(
    text: Optional[str] = Query(None, description="Optional message text"),
) -> dict:
    """Send a test message to TELEGRAM_CHAT_IDS. Returns raw Telegram API response for debugging."""
    import httpx

    message_text = text or "Test from diagnostics"
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids = [s.strip() for s in (os.environ.get("TELEGRAM_CHAT_IDS") or "").split(",") if s.strip()]
    if not token or not chat_ids:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS not set"}

    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for cid in chat_ids[:3]:
            r = await client.post(url, json={"chat_id": cid, "text": message_text})
            results.append({
                "chat_id": cid,
                "status_code": r.status_code,
                "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
            })
    return {"ok": all(r["status_code"] == 200 for r in results), "results": results}
