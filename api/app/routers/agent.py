"""Agent orchestration API routes."""

import logging
import os

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


@router.post("/agent/tasks", status_code=201)
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
    """List tasks with status needs_decision or failed only."""
    items, total = agent_service.get_attention_tasks(limit=limit)
    return {
        "tasks": [_task_to_item(t) for t in items],
        "total": total,
    }


@router.get("/agent/tasks/count")
async def get_task_count() -> dict:
    """Lightweight task counts for dashboards (total, by_status)."""
    return agent_service.get_task_count()


@router.get("/agent/tasks/{task_id}")
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


@router.patch("/agent/tasks/{task_id}")
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
    if user_id is not None and not telegram_adapter.is_user_allowed(user_id):
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


@router.get("/agent/metrics")
async def get_metrics() -> dict:
    """Task metrics: success rate, execution time, by task_type, by model. Spec 027."""
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
                status["running"][0]["live_tail"] = [ln.rstrip() for ln in lines[-25:] if ln.strip()]
            except Exception:
                status["running"][0]["live_tail"] = None
        else:
            status["running"][0]["live_tail"] = None
    return status


@router.get("/agent/tasks/{task_id}/log")
async def get_task_log(task_id: str) -> dict:
    """Full task log (prompt, command, output). File is streamed during execution, complete on finish."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", f"task_{task_id}.log")
    if not os.path.isfile(log_path):
        return {"task_id": task_id, "log": None, "command": task.get("command"), "output": task.get("output")}
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
async def telegram_test_send(text: str = "Test from diagnostics") -> dict:
    """Send a test message to TELEGRAM_CHAT_IDS. Returns raw Telegram API response for debugging."""
    import httpx

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids = [s.strip() for s in (os.environ.get("TELEGRAM_CHAT_IDS") or "").split(",") if s.strip()]
    if not token or not chat_ids:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS not set"}

    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for cid in chat_ids[:3]:
            r = await client.post(url, json={"chat_id": cid, "text": text})
            results.append({
                "chat_id": cid,
                "status_code": r.status_code,
                "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
            })
    return {"ok": all(r["status_code"] == 200 for r in results), "results": results}
