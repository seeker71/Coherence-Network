"""External agent encounter records.

These routes join an outside agent's returned trace with task-engine routing
when a response task exists. The returned trace can be recorded first, so an
encounter is not lost when task creation is slow or unavailable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import agent_service, graph_service

router = APIRouter()

_MARKER_KEY = "external_agent_encounter"


class ExternalAgentEncounterCreate(BaseModel):
    external_agent: str = Field(min_length=1, max_length=80)
    directed_by: str = Field(min_length=1, max_length=300)
    returned_trace_url: str | None = Field(default=None, max_length=1000)
    returned_trace_summary: str = Field(min_length=1, max_length=2000)
    response_task_id: str | None = Field(default=None, min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalAgentEncounterTaskLink(BaseModel):
    response_task_id: str = Field(min_length=1, max_length=120)


class ExternalAgentEncounterResponse(BaseModel):
    id: str
    external_agent: str
    directed_by: str
    returned_trace_url: str | None = None
    returned_trace_summary: str
    response_task_id: str | None = None
    response_task_snapshot: dict[str, Any] | None = None
    encountered_at: str
    evidence_status: str
    trace_completeness: dict[str, bool]
    metadata: dict[str, Any] = Field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encounter_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"external-encounter-{stamp}-{uuid.uuid4().hex[:6]}"


def _task_snapshot(task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    task = agent_service.get_task(task_id)
    if not task:
        return None
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    route = context.get("route_decision") if isinstance(context.get("route_decision"), dict) else {}
    status = task.get("status")
    status_value = status.value if hasattr(status, "value") else str(status or "")
    return {
        "task_id": task.get("id"),
        "task_type": task.get("task_type"),
        "status": status_value,
        "executor": context.get("executor") or route.get("executor"),
        "model_override": context.get("model_override"),
        "route_model": route.get("model") or task.get("model"),
        "provider": route.get("provider"),
        "billing_provider": route.get("billing_provider"),
        "is_paid_provider": route.get("is_paid_provider"),
        "created_at": str(task.get("created_at") or ""),
        "updated_at": str(task.get("updated_at") or "") if task.get("updated_at") else None,
    }


def _status(*, returned_trace_url: str | None, response_task_id: str | None, snapshot: dict[str, Any] | None) -> tuple[str, dict[str, bool]]:
    completeness = {
        "has_returned_trace": bool(returned_trace_url),
        "has_response_task": bool(response_task_id),
        "has_route_snapshot": bool(snapshot),
    }
    if snapshot:
        return "trace_recorded_task_linked", completeness
    if response_task_id:
        return "trace_recorded_task_missing", completeness
    return "trace_recorded_task_unlinked", completeness


def _node_to_response(node: dict[str, Any]) -> ExternalAgentEncounterResponse:
    snapshot = node.get("response_task_snapshot")
    status, completeness = _status(
        returned_trace_url=node.get("returned_trace_url"),
        response_task_id=node.get("response_task_id"),
        snapshot=snapshot if isinstance(snapshot, dict) else None,
    )
    return ExternalAgentEncounterResponse(
        id=str(node.get("id") or ""),
        external_agent=str(node.get("external_agent") or ""),
        directed_by=str(node.get("directed_by") or ""),
        returned_trace_url=node.get("returned_trace_url"),
        returned_trace_summary=str(node.get("returned_trace_summary") or node.get("summary") or ""),
        response_task_id=node.get("response_task_id"),
        response_task_snapshot=snapshot if isinstance(snapshot, dict) else None,
        encountered_at=str(node.get("encountered_at") or node.get("created_at") or ""),
        evidence_status=status,
        trace_completeness=completeness,
        metadata=node.get("metadata") if isinstance(node.get("metadata"), dict) else {},
    )


def _is_encounter(node: dict[str, Any]) -> bool:
    return node.get("type") == "event" and bool(node.get(_MARKER_KEY))


@router.post(
    "/external-encounters",
    response_model=ExternalAgentEncounterResponse,
    status_code=201,
    summary="Record an outside agent returned trace and optional response task link",
)
async def create_external_agent_encounter(body: ExternalAgentEncounterCreate) -> ExternalAgentEncounterResponse:
    response_task_snapshot = _task_snapshot(body.response_task_id)
    encountered_at = _now_iso()
    properties = {
        _MARKER_KEY: True,
        "external_agent": body.external_agent.strip().lower(),
        "directed_by": body.directed_by.strip(),
        "returned_trace_url": body.returned_trace_url,
        "returned_trace_summary": body.returned_trace_summary.strip(),
        "response_task_id": body.response_task_id,
        "response_task_snapshot": response_task_snapshot,
        "encountered_at": encountered_at,
        "metadata": dict(body.metadata or {}),
    }
    node = graph_service.create_node(
        id=_encounter_id(),
        type="event",
        name=f"{properties['external_agent']} returned trace",
        description=body.returned_trace_summary[:500],
        properties=properties,
    )
    return _node_to_response(node)


@router.get(
    "/external-encounters",
    response_model=list[ExternalAgentEncounterResponse],
    summary="List recent outside agent encounter records",
)
async def list_external_agent_encounters(
    external_agent: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ExternalAgentEncounterResponse]:
    response = graph_service.list_nodes(type="event", limit=300)
    nodes = [node for node in response.get("items", []) if _is_encounter(node)]
    if external_agent:
        wanted = external_agent.strip().lower()
        nodes = [node for node in nodes if str(node.get("external_agent") or "").lower() == wanted]
    nodes.sort(key=lambda node: str(node.get("encountered_at") or node.get("created_at") or ""), reverse=True)
    return [_node_to_response(node) for node in nodes[:limit]]


@router.get(
    "/external-encounters/{encounter_id}",
    response_model=ExternalAgentEncounterResponse,
    summary="Fetch one outside agent encounter record",
)
async def get_external_agent_encounter(encounter_id: str) -> ExternalAgentEncounterResponse:
    node = graph_service.get_node(encounter_id)
    if not node or not _is_encounter(node):
        raise HTTPException(status_code=404, detail=f"external encounter {encounter_id!r} not found")
    return _node_to_response(node)


@router.patch(
    "/external-encounters/{encounter_id}/response-task",
    response_model=ExternalAgentEncounterResponse,
    summary="Attach or refresh the task-engine response link for an encounter",
)
async def link_external_agent_encounter_task(
    encounter_id: str,
    body: ExternalAgentEncounterTaskLink,
) -> ExternalAgentEncounterResponse:
    node = graph_service.get_node(encounter_id)
    if not node or not _is_encounter(node):
        raise HTTPException(status_code=404, detail=f"external encounter {encounter_id!r} not found")

    snapshot = _task_snapshot(body.response_task_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"response task {body.response_task_id!r} not found")

    updated = graph_service.update_node(
        encounter_id,
        properties={
            "response_task_id": body.response_task_id,
            "response_task_snapshot": snapshot,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"external encounter {encounter_id!r} not found")
    return _node_to_response(updated)
