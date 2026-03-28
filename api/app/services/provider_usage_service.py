"""Persistence for normalized Open Responses route and model evidence (operator audits)."""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.models.schemas import NormalizedResponseCall
from app.services import agent_routing_service as routing_service
from app.services.agent_service_task_derive import task_output_text

_lock = Lock()
_normalized_response_evidence: list[dict[str, Any]] = []


def clear_normalized_response_evidence_for_tests() -> None:
    """Reset stored evidence (tests only)."""
    global _normalized_response_evidence
    with _lock:
        _normalized_response_evidence = []


def list_normalized_response_evidence(*, limit: int = 500) -> list[dict[str, Any]]:
    """Return recent persisted normalized call records (newest-biased slice)."""
    with _lock:
        if limit <= 0:
            return []
        return list(_normalized_response_evidence[-limit:])


def _task_route_and_model(task: dict[str, Any]) -> tuple[str, str, str]:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    nrc = ctx.get("normalized_response_call") if isinstance(ctx.get("normalized_response_call"), dict) else {}
    rd = ctx.get("route_decision") if isinstance(ctx.get("route_decision"), dict) else {}
    task_id = str(task.get("id") or nrc.get("task_id") or "").strip() or "unknown"
    provider = str(nrc.get("provider") or rd.get("provider") or "").strip() or "unknown"
    model = str(
        nrc.get("model") or routing_service.normalize_open_responses_model(str(task.get("model") or ""))
    ).strip() or "unknown"
    return task_id, provider, model


def persist_normalized_call_from_task(task: dict[str, Any], *, phase: str) -> None:
    """Append route/model/output evidence for a normalized Open Responses call."""
    task_id, provider, model = _task_route_and_model(task)
    if phase == "completed":
        raw = task_output_text(task).strip() or "(empty)"
        if len(raw) > 9900:
            raw = raw[:9890] + "…(truncated)"
        output_text = raw
    else:
        output_text = "(pending)"

    record = NormalizedResponseCall(
        task_id=task_id,
        provider=provider,
        model=model,
        request_schema="open_responses_v1",
        output_text=output_text,
    )
    payload = {
        "phase": phase,
        "request_schema": record.request_schema,
        "record": record.model_dump(),
    }
    with _lock:
        _normalized_response_evidence.append(payload)
