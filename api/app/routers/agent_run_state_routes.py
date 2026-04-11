"""Agent run-state and runner registry routes."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.models.agent import (
    AgentRunStateClaim,
    AgentRunStateHeartbeat,
    AgentRunStateSnapshot,
    AgentRunnerHeartbeat,
    AgentRunnerList,
    AgentRunnerSnapshot,
    AgentRunStateUpdate,
)
from app.routers.agent_telegram import format_task_alert
from app.services import (
    agent_execution_hooks,
    agent_run_state_service,
    agent_runner_registry_service,
    runner_orphan_recovery_service,
)

router = APIRouter()


@router.post("/run-state/claim", response_model=AgentRunStateSnapshot, summary="Claim or refresh an execution lease for task-level run ownership")
async def claim_run_state(data: AgentRunStateClaim) -> dict:
    """Claim or refresh an execution lease for task-level run ownership."""
    return agent_run_state_service.claim_run_state(
        task_id=data.task_id,
        run_id=data.run_id,
        worker_id=data.worker_id,
        lease_seconds=data.lease_seconds,
        attempt=data.attempt,
        branch=data.branch or "",
        repo_path=data.repo_path or "",
        metadata=data.metadata if isinstance(data.metadata, dict) else None,
    )


@router.post("/run-state/heartbeat", response_model=AgentRunStateSnapshot, summary="Heartbeat Run State")
async def heartbeat_run_state(data: AgentRunStateHeartbeat) -> dict:
    return agent_run_state_service.heartbeat_run_state(
        task_id=data.task_id,
        run_id=data.run_id,
        worker_id=data.worker_id,
        lease_seconds=data.lease_seconds,
    )


@router.post("/run-state/update", response_model=AgentRunStateSnapshot, summary="Update Run State")
async def update_run_state(data: AgentRunStateUpdate) -> dict:
    return agent_run_state_service.update_run_state(
        task_id=data.task_id,
        run_id=data.run_id,
        worker_id=data.worker_id,
        patch=data.patch if isinstance(data.patch, dict) else {},
        lease_seconds=data.lease_seconds,
        require_owner=bool(data.require_owner),
    )


@router.get("/run-state/{task_id}", response_model=AgentRunStateSnapshot, summary="Get Run State")
async def get_run_state(task_id: str) -> dict:
    state = agent_run_state_service.get_run_state(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run state not found")
    return state


@router.post("/runners/heartbeat", response_model=AgentRunnerSnapshot, summary="Heartbeat Runner")
async def heartbeat_runner(data: AgentRunnerHeartbeat, background_tasks: BackgroundTasks) -> dict:
    snapshot = agent_runner_registry_service.heartbeat_runner(
        runner_id=data.runner_id,
        status=data.status,
        lease_seconds=data.lease_seconds,
        host=data.host or "",
        pid=data.pid,
        version=data.version or "",
        active_task_id=data.active_task_id or "",
        active_run_id=data.active_run_id or "",
        last_error=data.last_error or "",
        capabilities=data.capabilities if isinstance(data.capabilities, dict) else None,
        metadata=data.metadata if isinstance(data.metadata, dict) else None,
    )
    await runner_orphan_recovery_service.maybe_recover_on_idle_heartbeat(
        snapshot=snapshot,
        background_tasks=background_tasks,
        alert_builder=lambda task: format_task_alert(task, runner_update=False),
    )
    return snapshot


@router.get("/runners", response_model=AgentRunnerList, summary="List Runners")
async def list_runners(
    include_stale: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
) -> AgentRunnerList:
    rows = agent_runner_registry_service.list_runners(include_stale=include_stale, limit=limit)
    return AgentRunnerList(
        runners=[AgentRunnerSnapshot(**row) for row in rows],
        total=len(rows),
    )


@router.get("/lifecycle/summary", summary="Agent Lifecycle Summary")
async def agent_lifecycle_summary(
    seconds: int = Query(3600, ge=60, le=2592000),
    limit: int = Query(500, ge=1, le=5000),
    task_id: Optional[str] = Query(None),
    source: str = Query("auto"),
) -> dict:
    return agent_execution_hooks.summarize_lifecycle_events(
        seconds=seconds,
        limit=limit,
        task_id=task_id,
        source=source,
    )
