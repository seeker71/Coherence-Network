"""Agent task log route."""

import os

from fastapi import APIRouter, HTTPException

from app.models.error import ErrorDetail
from app.services import agent_service

router = APIRouter()


@router.get(
    "/tasks/{task_id}/log",
    responses={404: {"description": "Task not found or task log not found", "model": ErrorDetail}},
)
async def get_task_log(task_id: str) -> dict:
    """Full task log (prompt, command, output). File is streamed during execution, complete on finish."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    log_path = os.path.join(base_dir, f"task_{task_id}.log")
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as f:
            log_content = f.read()
        return {
            "task_id": task_id,
            "log": log_content,
            "command": task.get("command"),
            "output": task.get("output"),
            "log_source": "file",
        }

    fallback_lines: list[str] = []
    status = task.get("status")
    current_step = task.get("current_step")
    updated_at = task.get("updated_at")
    if status is not None:
        fallback_lines.append(f"status: {status}")
    if current_step:
        fallback_lines.append(f"current_step: {current_step}")
    if updated_at:
        fallback_lines.append(f"updated_at: {updated_at}")
    output = str(task.get("output") or "").strip()
    if output:
        fallback_lines.append("")
        fallback_lines.append("output:")
        fallback_lines.append(output[:5000])
    fallback = "\n".join(fallback_lines).strip() or "No task log file is available for this task yet."

    return {
        "task_id": task_id,
        "log": fallback,
        "command": task.get("command"),
        "output": task.get("output"),
        "log_source": "task_snapshot",
    }
