"""Agent task execute and pickup-and-execute routes."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from app.models.agent import TaskStatus, TaskType
from app.models.error import ErrorDetail
from app.routers.agent_helpers import (
    coerce_force_paid_override,
    force_paid_override,
    require_execute_token,
    require_execute_token_when_unset,
    requeue_terminal_task_for_execute,
    task_to_item,
    truthy,
)
from app.services import agent_service

router = APIRouter()


@router.post(
    "/tasks/pickup-and-execute",
    responses={
        403: {"description": "Forbidden (missing or invalid execute token)", "model": ErrorDetail},
        404: {"description": "No pending task found", "model": ErrorDetail},
        409: {"description": "Task already claimed/running by another worker", "model": ErrorDetail},
    },
)
async def pickup_and_execute_task(
    request: Request,
    background_tasks: BackgroundTasks,
    task_id: Optional[str] = Query(None),
    task_type: Optional[TaskType] = Query(None),
    x_agent_execute_token: Optional[str] = Header(None, alias="X-Agent-Execute-Token"),
    x_force_paid_providers: Optional[str] = Header(None, alias="X-Force-Paid-Providers"),
    force_paid_providers: str | None = Query(None),
    force_paid_provider: str | None = Query(None),
    force_allow_paid_providers: str | None = Query(None),
    allow_paid_providers: str | None = Query(None),
    allow_paid_provider: str | None = Query(None),
    max_cost_usd: float | None = Query(None, ge=0.0),
    estimated_cost_usd: float | None = Query(None, ge=0.0),
    cost_slack_ratio: float | None = Query(None, ge=1.0),
) -> dict:
    """Pick a pending task (oldest-first fallback) and execute it via Codex/API worker flow."""
    require_execute_token(
        "pickup_and_execute_task",
        x_agent_execute_token,
        require_when_token_not_configured=True,
    )

    if task_id:
        task = agent_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        task = requeue_terminal_task_for_execute(task_id, task)
    else:
        pending, _ = agent_service.list_tasks(status=TaskStatus.PENDING, task_type=task_type, limit=200, offset=0)
        if not pending:
            return {"ok": False, "picked": False, "reason": "No pending tasks"}
        task = pending[-1]

    task_ctx = task.get("context")
    selected_task_id = str(task.get("id") or "").strip()
    if not selected_task_id:
        raise HTTPException(status_code=404, detail="Task id missing")

    force_paid_override_val = force_paid_override(
        request,
        x_force_paid_providers=x_force_paid_providers,
        force_paid_providers=force_paid_providers,
        force_paid_provider=force_paid_provider,
        force_allow_paid_providers=force_allow_paid_providers,
        allow_paid_providers=allow_paid_providers,
        allow_paid_provider=allow_paid_provider,
    )
    if force_paid_override_val:
        ctx: dict = task_ctx if isinstance(task_ctx, dict) else {}
        if not truthy(str(ctx.get("force_paid_providers") or "")):
            agent_service.update_task(
                selected_task_id,
                context={
                    "force_paid_providers": True,
                    "force_paid_override_source": "query",
                },
            )

    from app.services import agent_execution_service

    background_tasks.add_task(
        agent_execution_service.execute_task,
        selected_task_id,
        force_paid_providers=force_paid_override_val,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    return {"ok": True, "picked": True, "task": task_to_item(task)}


@router.post(
    "/tasks/{task_id}/execute",
    responses={
        403: {"description": "Forbidden (missing or invalid execute token)", "model": ErrorDetail},
        404: {"description": "Task not found", "model": ErrorDetail},
    },
)
async def execute_task(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_agent_execute_token: Optional[str] = Header(None, alias="X-Agent-Execute-Token"),
    x_force_paid_providers: Optional[str] = Header(None, alias="X-Force-Paid-Providers"),
    force_paid_providers: str | None = Query(None),
    force_paid_provider: str | None = Query(None),
    force_allow_paid_providers: str | None = Query(None),
    allow_paid_providers: str | None = Query(None),
    allow_paid_provider: str | None = Query(None),
    max_cost_usd: float | None = Query(None, ge=0.0),
    estimated_cost_usd: float | None = Query(None, ge=0.0),
    cost_slack_ratio: float | None = Query(None, ge=1.0),
) -> dict:
    """Execute a task server-side (background).

    If AGENT_EXECUTE_TOKEN is set, callers must provide header X-Agent-Execute-Token.
    """
    require_execute_token(
        "execute_task",
        x_agent_execute_token,
        require_when_token_not_configured=require_execute_token_when_unset(),
    )

    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task = requeue_terminal_task_for_execute(task_id, task)

    from app.services import agent_execution_service

    force_paid_override_val = force_paid_override(
        request,
        x_force_paid_providers=x_force_paid_providers,
        force_paid_providers=force_paid_providers,
        force_paid_provider=force_paid_provider,
        force_allow_paid_providers=force_allow_paid_providers,
        allow_paid_providers=allow_paid_providers,
        allow_paid_provider=allow_paid_provider,
    )
    if force_paid_override_val:
        task_ctx = task.get("context")
        ctx: dict = task_ctx if isinstance(task_ctx, dict) else {}
        if not truthy(str(ctx.get("force_paid_providers") or "")):
            agent_service.update_task(
                task_id,
                context={
                    "force_paid_providers": True,
                    "force_paid_override_source": "query"
                    if coerce_force_paid_override(request)
                    else "header",
                },
            )

    background_tasks.add_task(
        agent_execution_service.execute_task,
        task_id,
        force_paid_providers=force_paid_override_val,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    return {"ok": True, "task_id": task_id}
