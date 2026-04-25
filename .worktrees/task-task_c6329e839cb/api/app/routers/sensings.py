"""Sensings — the organism's moments of noticing, stored in the living graph.

A sensing is a first-class node in the same graph that holds concepts, ideas,
specs, and contributors. It has type="event" and carries a kind (breath,
skin, wandering, integration) plus whatever the organism noticed in that
moment. Sensings can be linked by `analogous-to` edges to the concepts,
ideas, and specs they touch, so the graph becomes the organism's continuous
journal of self-awareness.

There is no separate sensing storage, no markdown journal running alongside
the DB, no parallel system. One body, one source of truth. The breath at
/api/practice, the outer skin from the external signals sensing, and the
wandering reflection that comes back from a curious subagent all flow into
this same endpoint and live in the same graph.

Retrieval is emergent rather than scheduled. Callers ask for "what the
organism is holding right now" and the response is shaped by the natural
recency and relevance of the field, not by a fixed cadence.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import graph_service

router = APIRouter()

# Valid kinds the organism speaks in.
SensingKind = Literal["breath", "skin", "wandering", "integration"]
VALID_KINDS = {"breath", "skin", "wandering", "integration"}

# All sensings live as graph events; this property key marks them as sensings.
_SENSING_MARKER_KEY = "sensing_kind"


class SensingCreate(BaseModel):
    kind: SensingKind = Field(description="What form of sensing this moment is")
    summary: str = Field(
        description="One-line essence of what the organism noticed",
        min_length=1,
        max_length=500,
    )
    content: str = Field(
        description="The full reflection, pulse snapshot, or signal body",
        min_length=1,
    )
    source: str = Field(
        default="unknown",
        description="Tool, agent, or session that produced this sensing",
    )
    related_to: list[str] = Field(
        default_factory=list,
        description="IDs of concepts, ideas, or specs this sensing touches",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Kind-specific extra shape the sensing wants to carry",
    )


class SensingResponse(BaseModel):
    id: str
    kind: str
    summary: str
    content: str
    source: str
    observed_at: str
    related_to: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _node_to_sensing(node: dict) -> SensingResponse:
    # graph_service flattens properties onto the top level of the node dict,
    # so read them there rather than from a nested `properties` key.
    return SensingResponse(
        id=node.get("id", ""),
        kind=node.get(_SENSING_MARKER_KEY, ""),
        summary=node.get("summary", "") or node.get("name", ""),
        content=node.get("content", ""),
        source=node.get("source", "unknown"),
        observed_at=node.get("observed_at", "") or node.get("created_at", ""),
        related_to=list(node.get("related_to") or []),
        metadata=node.get("metadata") or {},
    )


def _is_sensing(node: dict) -> bool:
    return node.get("type") == "event" and bool(node.get(_SENSING_MARKER_KEY))


def _source_provenance_for_target(
    *,
    metadata: dict[str, Any],
    sensing_id: str,
    target_id: str,
) -> dict[str, Any]:
    rationales = metadata.get("edge_rationales") or {}
    rationale = ""
    if isinstance(rationales, dict):
        rationale = str(rationales.get(target_id) or "").strip()
    if not rationale:
        rationale = str(metadata.get("rationale") or "").strip()

    return {
        "source_artifact_id": metadata.get("source_artifact_id"),
        "sensing_id": sensing_id,
        "extraction_method": metadata.get("extraction_method"),
        "confidence": metadata.get("confidence"),
        "ingestion_policy": metadata.get("ingestion_policy"),
        "rationale": rationale,
        "quote_policy": metadata.get("quote_policy"),
    }


@router.post(
    "/sensings",
    response_model=SensingResponse,
    status_code=201,
    summary="Record a sensing in the graph",
    description=(
        "A sensing is any moment when the organism notices something about "
        "itself or the field it lives in. Breath sensings capture the state "
        "of the eight centers; skin sensings capture external signals from "
        "systems the organism lives inside; wandering sensings are the "
        "generative reflections from a curious walk through the field; "
        "integration sensings mark what was healed or built in response. "
        "All of them live in the same graph."
    ),
)
async def create_sensing(body: SensingCreate) -> SensingResponse:
    if body.kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown kind {body.kind!r}; expected one of {sorted(VALID_KINDS)}",
        )

    sensing_id = f"sensing-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    observed_at = datetime.now(timezone.utc).isoformat()
    metadata = dict(body.metadata or {})

    source_artifact_id = metadata.get("source_artifact_id")
    if source_artifact_id:
        for target in body.related_to:
            try:
                graph_service.validate_source_edge_provenance(
                    _source_provenance_for_target(
                        metadata=metadata,
                        sensing_id=sensing_id,
                        target_id=target,
                    )
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    properties = {
        _SENSING_MARKER_KEY: body.kind,
        "summary": body.summary,
        "content": body.content,
        "source": body.source,
        "observed_at": observed_at,
        "related_to": body.related_to,
        "metadata": metadata,
    }
    for key in ("source_artifact_id", "extraction_method", "ingestion_policy", "quote_policy"):
        if metadata.get(key):
            properties[key] = metadata[key]

    node = graph_service.create_node(
        id=sensing_id,
        type="event",
        name=body.summary[:120],
        description=body.summary,
        properties=properties,
    )

    # Grow synapses to any concepts/ideas/specs the sensing touches, so the
    # field holds the connection rather than forcing the caller to remember it.
    for target in body.related_to:
        try:
            if source_artifact_id:
                graph_service.create_provenance_edge(
                    from_id=sensing_id,
                    to_id=target,
                    type="analogous-to",
                    provenance=_source_provenance_for_target(
                        metadata=metadata,
                        sensing_id=sensing_id,
                        target_id=target,
                    ),
                )
            else:
                graph_service.create_edge(
                    from_id=sensing_id,
                    to_id=target,
                    type="analogous-to",
                    properties={"provenance": f"sensing:{body.kind}"},
                )
        except Exception:
            # A target that does not exist is a soft signal, not a failure.
            pass

    return _node_to_sensing(node)


@router.get(
    "/sensings",
    response_model=list[SensingResponse],
    summary="What the organism is holding right now",
    description=(
        "Returns recent sensings. By default the most recent across all kinds. "
        "Filter by kind to focus on one form of sensing. Retrieval is emergent "
        "rather than scheduled — the organism holds what feels recent to it."
    ),
)
async def list_sensings(
    kind: str | None = Query(default=None, description="breath | skin | wandering | integration"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[SensingResponse]:
    if kind and kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown kind {kind!r}; expected one of {sorted(VALID_KINDS)}",
        )

    # Pull a generous slice of event nodes and filter down to sensings.
    try:
        response = graph_service.list_nodes(type="event", limit=200)
        nodes = (
            response.get("items", [])
            if isinstance(response, dict)
            else (response or [])
        )
    except Exception:
        nodes = []

    sensings = [n for n in nodes if _is_sensing(n)]
    if kind:
        sensings = [
            n for n in sensings if (n.get("properties") or {}).get(_SENSING_MARKER_KEY) == kind
        ]

    sensings.sort(
        key=lambda n: (n.get("properties") or {}).get("observed_at", ""),
        reverse=True,
    )
    return [_node_to_sensing(n) for n in sensings[:limit]]


@router.get(
    "/sensings/{sensing_id}",
    response_model=SensingResponse,
    summary="A single sensing in full",
)
async def get_sensing(sensing_id: str) -> SensingResponse:
    node = graph_service.get_node(sensing_id)
    if not node or not _is_sensing(node):
        raise HTTPException(status_code=404, detail=f"sensing {sensing_id!r} not found")
    return _node_to_sensing(node)
