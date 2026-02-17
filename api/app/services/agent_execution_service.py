"""Server-side execution for agent tasks.

This is intentionally conservative:
- default-deny for paid providers (can be overridden via env for emergencies)
- records runtime events for diagnostics and usage visibility
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from app.models.agent import TaskStatus
from app.models.runtime import RuntimeEventCreate
from app.services import agent_service, metrics_service, runtime_service
from app.services.openrouter_client import OpenRouterError, chat_completion


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _paid_providers_allowed() -> bool:
    # Default: paid providers NOT allowed.
    return _truthy(os.getenv("AGENT_ALLOW_PAID_PROVIDERS", "0"))


def _extract_underlying_model(task_model: str) -> str:
    cleaned = (task_model or "").strip()
    if cleaned.startswith("openclaw/"):
        return cleaned.split("/", 1)[1].strip()
    if cleaned.startswith("cursor/"):
        return cleaned.split("/", 1)[1].strip()
    return cleaned


def _write_task_log(task_id: str, lines: list[str]) -> None:
    try:
        api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logs_dir = os.path.join(api_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        path = os.path.join(logs_dir, f"task_{task_id}.log")
        with open(path, "a", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln.rstrip() + "\n")
    except Exception:
        # Logging must never break execution.
        return


def _claim_task(task_id: str, worker_id: str) -> tuple[bool, str | None]:
    try:
        agent_service.update_task(task_id, status=TaskStatus.RUNNING, worker_id=worker_id)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _task_route_is_paid(task: dict[str, Any]) -> bool:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = ctx.get("route_decision") if isinstance(ctx.get("route_decision"), dict) else {}
    return bool(route_decision.get("is_paid_provider"))


def _finish_task(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    status: TaskStatus,
    output: str,
    model_for_metrics: str,
    elapsed_ms: int,
) -> None:
    agent_service.update_task(task_id, status=status, output=output, worker_id=worker_id)
    metrics_service.record_task(
        task_id=task_id,
        task_type=str(task.get("task_type") or "unknown"),
        model=model_for_metrics,
        duration_seconds=max(0.0, float(elapsed_ms) / 1000.0),
        status="completed" if status == TaskStatus.COMPLETED else "failed",
    )


def _record_openrouter_tool_event(
    *,
    task_id: str,
    model: str,
    elapsed_ms: int,
    ok: bool,
    provider_request_id: str | None = None,
    response_id: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    usage_json: str = "{}",
    error: str | None = None,
) -> None:
    status_code = 200 if ok else 500
    metadata: dict[str, str | float | int | bool] = {
        "tracking_kind": "agent_tool_call",
        "task_id": task_id,
        "model": model,
        "provider": "openrouter",
        "is_paid_provider": False,
    }
    if ok:
        metadata.update(
            {
                "usage_prompt_tokens": int(prompt_tokens),
                "usage_completion_tokens": int(completion_tokens),
                "usage_total_tokens": int(total_tokens),
                "usage_json": str(usage_json)[:2000],
                "provider_request_id": (provider_request_id or "")[:200],
                "response_id": (response_id or "")[:200],
            }
        )
    else:
        metadata["error"] = (error or "unknown")[:800]

    runtime_service.record_event(
        RuntimeEventCreate(
            source="worker",
            endpoint="tool:openrouter.chat_completion",
            method="RUN",
            status_code=status_code,
            runtime_ms=float(max(1, int(elapsed_ms))),
            idea_id="coherence-network-agent-pipeline",
            metadata=metadata,
        )
    )


def _run_openrouter(
    *,
    task_id: str,
    model: str,
    prompt: str,
    started_perf: float,
) -> dict[str, Any]:
    try:
        content, usage, meta = chat_completion(model=model, prompt=prompt)
        elapsed_ms = max(1, int(meta.get("elapsed_ms") or int(round((time.perf_counter() - started_perf) * 1000))))
        usage_dict = usage if isinstance(usage, dict) else {}
        prompt_tokens = int(usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens") or 0)
        completion_tokens = int(usage_dict.get("completion_tokens") or usage_dict.get("output_tokens") or 0)
        total_tokens = int(usage_dict.get("total_tokens") or (prompt_tokens + completion_tokens))
        usage_json = json.dumps(usage_dict, sort_keys=True)[:2000]
        _record_openrouter_tool_event(
            task_id=task_id,
            model=model,
            elapsed_ms=elapsed_ms,
            ok=True,
            provider_request_id=str(meta.get("provider_request_id") or ""),
            response_id=str(meta.get("response_id") or ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_json=usage_json,
        )
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "content": content,
            "usage_json": usage_json,
            "provider_request_id": str(meta.get("provider_request_id") or ""),
        }
    except OpenRouterError as exc:
        elapsed_ms = max(1, int(round((time.perf_counter() - started_perf) * 1000)))
        _record_openrouter_tool_event(task_id=task_id, model=model, elapsed_ms=elapsed_ms, ok=False, error=str(exc))
        return {"ok": False, "elapsed_ms": elapsed_ms, "error": f"Execution failed (OpenRouter): {exc}"}


def _resolve_openrouter_model(task: dict[str, Any], default: str) -> str:
    model = _extract_underlying_model(str(task.get("model") or ""))
    return model or default


def _resolve_prompt(task: dict[str, Any]) -> str:
    return str(task.get("direction") or "").strip()


def _complete_success(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    elapsed_ms: int,
    content: str,
    usage_json: str,
    request_id: str,
) -> dict[str, Any]:
    _write_task_log(
        task_id,
        [
            f"[openrouter] status=200 elapsed_ms={elapsed_ms} request_id={request_id}",
            f"[usage] {usage_json}",
            "[output]",
            content,
        ],
    )
    _finish_task(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        status=TaskStatus.COMPLETED,
        output=content,
        model_for_metrics=str(task.get("model") or model or "unknown"),
        elapsed_ms=elapsed_ms,
    )
    return {"ok": True, "status": "completed", "elapsed_ms": elapsed_ms, "model": model}


def _complete_failure(
    *,
    task_id: str,
    task: dict[str, Any],
    worker_id: str,
    model: str,
    elapsed_ms: int,
    msg: str,
) -> dict[str, Any]:
    _write_task_log(task_id, [msg])
    _finish_task(
        task_id=task_id,
        task=task,
        worker_id=worker_id,
        status=TaskStatus.FAILED,
        output=msg,
        model_for_metrics=str(task.get("model") or model or "unknown"),
        elapsed_ms=elapsed_ms,
    )
    return {"ok": False, "status": "failed", "elapsed_ms": elapsed_ms, "model": model}


def execute_task(
    task_id: str,
    *,
    worker_id: str = "openclaw-worker:server",
) -> dict[str, Any]:
    """Execute a task using OpenRouter (free model by default).

    Returns a small summary dict (also useful for unit tests). This is safe to
    call from FastAPI BackgroundTasks.
    """
    task = agent_service.get_task(task_id)
    if task is None:
        return {"ok": False, "error": "task_not_found"}

    claimed, claim_error = _claim_task(task_id, worker_id)
    if not claimed:
        return {"ok": False, "error": f"claim_failed:{claim_error}"}

    task = agent_service.get_task(task_id) or {}

    if _task_route_is_paid(task) and not _paid_providers_allowed():
        msg = "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled."
        _write_task_log(task_id, [msg])
        _finish_task(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            status=TaskStatus.FAILED,
            output=msg,
            model_for_metrics=str(task.get("model") or "unknown"),
            elapsed_ms=1,
        )
        return {"ok": False, "error": "paid_provider_blocked"}

    default_model = os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free").strip() or "openrouter/free"
    model = _resolve_openrouter_model(task, default_model)

    prompt = _resolve_prompt(task)
    if not prompt:
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=1,
            msg="Empty direction",
        )

    started = time.perf_counter()
    _write_task_log(task_id, [f"[execute] worker_id={worker_id} model={model}", f"[prompt]\n{prompt}"])

    try:
        result = _run_openrouter(task_id=task_id, model=model, prompt=prompt, started_perf=started)
        elapsed_ms = int(result.get("elapsed_ms") or 1)
        if result.get("ok") is True:
            content = str(result.get("content") or "")
            usage_json = str(result.get("usage_json") or "{}")
            request_id = str(result.get("provider_request_id") or "")
            return _complete_success(
                task_id=task_id,
                task=task,
                worker_id=worker_id,
                model=model,
                elapsed_ms=elapsed_ms,
                content=content,
                usage_json=usage_json,
                request_id=request_id,
            )

        msg = str(result.get("error") or "Execution failed (OpenRouter)")
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            msg=msg,
        )
    except Exception as exc:
        elapsed_ms = max(1, int(round((time.perf_counter() - started) * 1000)))
        msg = f"Execution failed: {exc}"
        return _complete_failure(
            task_id=task_id,
            task=task,
            worker_id=worker_id,
            model=model,
            elapsed_ms=elapsed_ms,
            msg=msg,
        )
