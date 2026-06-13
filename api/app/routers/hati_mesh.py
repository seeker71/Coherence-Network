"""Hati mesh sensing-organ presence routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service

router = APIRouter()

OrganKind = Literal[
    "android-phone",
    "host-kernel",
    "camera",
    "microphone",
    "speaker",
    "sensor",
    "agent",
    "hardware-device",
]

ChannelStatus = Literal["offered", "accepted", "open", "paused", "closed", "refused"]


class OrganAnnounceIn(BaseModel):
    organ_id: str = Field(..., min_length=8, max_length=160)
    organ_kind: OrganKind
    app: str = Field(default="hati-os", min_length=1, max_length=80)
    app_version: str = Field(default="0.1", min_length=1, max_length=40)
    target: str = Field(default="unknown", min_length=1, max_length=80)
    steward_cell_id: str | None = Field(default=None, max_length=160)
    steward_label: str | None = Field(default=None, max_length=160)
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    lanes: list[str] = Field(default_factory=list, max_length=32)
    public_key: str | None = Field(default=None, max_length=256)


class ChannelOfferIn(BaseModel):
    from_organ_id: str = Field(..., min_length=8, max_length=160)
    to_organ_id: str = Field(..., min_length=8, max_length=160)
    protocol: str = Field(..., min_length=1, max_length=80)
    interface: str = Field(..., min_length=1, max_length=120)
    capability: str = Field(..., min_length=1, max_length=120)
    codec: str = Field(default="json", min_length=1, max_length=80)
    status: ChannelStatus = "offered"
    sample_rate_hz: float = Field(default=0.0, ge=0.0, le=192000.0)
    bytes_per_second: float = Field(default=0.0, ge=0.0)


class OrganHeartbeatIn(BaseModel):
    organ_id: str = Field(..., min_length=8, max_length=160)
    listening: bool = True
    active_channels: list[str] = Field(default_factory=list, max_length=32)
    sample_rate_hz: float = Field(default=0.0, ge=0.0, le=192000.0)
    bytes_per_second: float = Field(default=0.0, ge=0.0)


def _join(values: list[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return ",".join(cleaned[:32])


def _event_for(payload: OrganAnnounceIn) -> RuntimeEventCreate:
    metadata: dict[str, str | float | int | bool] = {
        "mesh": "hati.mesh",
        "organ_id": payload.organ_id,
        "organ_kind": payload.organ_kind,
        "app": payload.app,
        "app_version": payload.app_version,
        "target": payload.target,
        "capabilities": _join(payload.capabilities),
        "lanes": _join(payload.lanes),
        "has_public_key": bool(payload.public_key),
    }
    if payload.steward_cell_id:
        metadata["steward_cell_id"] = payload.steward_cell_id
    if payload.steward_label:
        metadata["steward_label"] = payload.steward_label
    return RuntimeEventCreate(
        source="api",
        endpoint="/api/hati/mesh/organs/announce",
        raw_endpoint="/api/hati/mesh/organs/announce",
        method="POST",
        status_code=201,
        runtime_ms=1.0,
        idea_id="hati-mesh-sensing-organs",
        metadata=metadata,
    )


def _event_for_offer(payload: ChannelOfferIn) -> RuntimeEventCreate:
    return RuntimeEventCreate(
        source="api",
        endpoint="/api/hati/mesh/channels/offer",
        raw_endpoint="/api/hati/mesh/channels/offer",
        method="POST",
        status_code=201,
        runtime_ms=1.0,
        idea_id="hati-mesh-sensing-organs",
        metadata={
            "mesh": "hati.mesh",
            "from_organ_id": payload.from_organ_id,
            "to_organ_id": payload.to_organ_id,
            "protocol": payload.protocol,
            "interface": payload.interface,
            "capability": payload.capability,
            "codec": payload.codec,
            "status": payload.status,
            "sample_rate_hz": payload.sample_rate_hz,
            "bytes_per_second": payload.bytes_per_second,
        },
    )


def _event_for_heartbeat(payload: OrganHeartbeatIn) -> RuntimeEventCreate:
    return RuntimeEventCreate(
        source="api",
        endpoint="/api/hati/mesh/organs/heartbeat",
        raw_endpoint="/api/hati/mesh/organs/heartbeat",
        method="POST",
        status_code=201,
        runtime_ms=1.0,
        idea_id="hati-mesh-sensing-organs",
        metadata={
            "mesh": "hati.mesh",
            "organ_id": payload.organ_id,
            "listening": payload.listening,
            "active_channels": _join(payload.active_channels),
            "sample_rate_hz": payload.sample_rate_hz,
            "bytes_per_second": payload.bytes_per_second,
        },
    )


@router.post(
    "/hati/mesh/organs/announce",
    status_code=201,
    summary="Announce a Hati mesh sensing organ",
)
async def announce_organ(payload: OrganAnnounceIn) -> dict[str, Any]:
    event = runtime_service.record_event(_event_for(payload))
    now = datetime.now(timezone.utc).isoformat()
    return {
        "mesh": "hati.mesh",
        "status": "announced",
        "announced_at": now,
        "organ": payload.model_dump(),
        "identity": {
            "organ_id": payload.organ_id,
            "organ_kind": payload.organ_kind,
            "steward_cell_id": payload.steward_cell_id or "unbound",
            "identity_floor": "stable-install-id",
            "identity_north_star": "signed self-sovereign organ identity bound to a steward/cell relation and revocable capabilities",
        },
        "receipt": {
            "runtime_event_id": event.id,
            "endpoint": event.endpoint,
            "recorded_at": event.recorded_at.isoformat(),
        },
    }


@router.post(
    "/hati/mesh/organs/heartbeat",
    status_code=201,
    summary="Heartbeat from a listening Hati mesh organ",
)
async def heartbeat_organ(payload: OrganHeartbeatIn) -> dict[str, Any]:
    event = runtime_service.record_event(_event_for_heartbeat(payload))
    return {
        "mesh": "hati.mesh",
        "status": "listening" if payload.listening else "not-listening",
        "organ_id": payload.organ_id,
        "active_channels": payload.active_channels,
        "flow": {
            "sample_rate_hz": payload.sample_rate_hz,
            "bytes_per_second": payload.bytes_per_second,
        },
        "receipt": {
            "runtime_event_id": event.id,
            "endpoint": event.endpoint,
            "recorded_at": event.recorded_at.isoformat(),
        },
    }


@router.get(
    "/hati/mesh/organs",
    summary="List recently announced Hati mesh sensing organs",
)
async def list_organs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    rows = runtime_service.list_events(limit=max(limit * 4, 100), source="api")
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        if row.endpoint not in {
            "/api/hati/mesh/organs/announce",
            "/api/hati/mesh/organs/heartbeat",
        }:
            continue
        organ_id = str(row.metadata.get("organ_id") or "")
        if not organ_id:
            continue
        if organ_id not in by_id:
            order.append(organ_id)
            by_id[organ_id] = {
                "organ_id": organ_id,
                "organ_kind": "unknown",
                "steward_cell_id": "unbound",
                "capabilities": [],
                "lanes": [],
                "listening": False,
                "active_channels": [],
                "sample_rate_hz": 0.0,
                "bytes_per_second": 0.0,
                "last_seen_at": row.recorded_at.isoformat(),
                "receipt_id": row.id,
            }
        item = by_id[organ_id]
        item["last_seen_at"] = row.recorded_at.isoformat()
        item["receipt_id"] = row.id
        if row.endpoint == "/api/hati/mesh/organs/announce":
            item["organ_kind"] = row.metadata.get("organ_kind", item["organ_kind"])
            item["steward_cell_id"] = row.metadata.get("steward_cell_id", item["steward_cell_id"])
            item["capabilities"] = str(row.metadata.get("capabilities", "")).split(",") if row.metadata.get("capabilities") else item["capabilities"]
            item["lanes"] = str(row.metadata.get("lanes", "")).split(",") if row.metadata.get("lanes") else item["lanes"]
        else:
            item["listening"] = bool(row.metadata.get("listening", False))
            item["active_channels"] = str(row.metadata.get("active_channels", "")).split(",") if row.metadata.get("active_channels") else []
            item["sample_rate_hz"] = row.metadata.get("sample_rate_hz", 0.0)
            item["bytes_per_second"] = row.metadata.get("bytes_per_second", 0.0)
    items = [by_id[organ_id] for organ_id in order[:limit]]
    return {"mesh": "hati.mesh", "count": len(items), "items": items}


@router.post(
    "/hati/mesh/channels/offer",
    status_code=201,
    summary="Offer a communication channel between Hati mesh organs",
)
async def offer_channel(payload: ChannelOfferIn) -> dict[str, Any]:
    event = runtime_service.record_event(_event_for_offer(payload))
    return {
        "mesh": "hati.mesh",
        "status": payload.status,
        "channel": payload.model_dump(),
        "receipt": {
            "runtime_event_id": event.id,
            "endpoint": event.endpoint,
            "recorded_at": event.recorded_at.isoformat(),
        },
    }


@router.get(
    "/hati/mesh/channels",
    summary="List recent Hati mesh channel offers and open lanes",
)
async def list_channels(
    organ_id: str | None = Query(default=None, min_length=8, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    rows = runtime_service.list_events(limit=max(limit * 4, 100), source="api")
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.endpoint != "/api/hati/mesh/channels/offer":
            continue
        from_id = str(row.metadata.get("from_organ_id") or "")
        to_id = str(row.metadata.get("to_organ_id") or "")
        if organ_id and organ_id not in {from_id, to_id}:
            continue
        items.append(
            {
                "from_organ_id": from_id,
                "to_organ_id": to_id,
                "protocol": row.metadata.get("protocol"),
                "interface": row.metadata.get("interface"),
                "capability": row.metadata.get("capability"),
                "codec": row.metadata.get("codec"),
                "status": row.metadata.get("status"),
                "sample_rate_hz": row.metadata.get("sample_rate_hz", 0.0),
                "bytes_per_second": row.metadata.get("bytes_per_second", 0.0),
                "last_seen_at": row.recorded_at.isoformat(),
                "receipt_id": row.id,
            }
        )
        if len(items) >= limit:
            break
    return {"mesh": "hati.mesh", "count": len(items), "items": items}
