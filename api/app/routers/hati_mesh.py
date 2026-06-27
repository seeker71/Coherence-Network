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
ChannelDirection = Literal["bidirectional", "send", "receive", "presence", "install-only"]
DiscoveryState = Literal["declared", "seen", "paired", "trusted", "streaming", "training"]


class OrganAnnounceIn(BaseModel):
    organ_id: str = Field(..., min_length=8, max_length=160)
    organ_kind: OrganKind
    app: str = Field(default="hati-os", min_length=1, max_length=80)
    app_version: str = Field(default="0.1", min_length=1, max_length=40)
    target: str = Field(default="unknown", min_length=1, max_length=80)
    steward_cell_id: str | None = Field(default=None, max_length=160)
    steward_label: str | None = Field(default=None, max_length=160)
    display_name: str | None = Field(default=None, max_length=160)
    dwelling_name: str | None = Field(default=None, max_length=160)
    location_label: str | None = Field(default=None, max_length=160)
    map_x: float | None = Field(default=None, ge=0.0, le=100.0)
    map_y: float | None = Field(default=None, ge=0.0, le=100.0)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    discovery_state: DiscoveryState = "declared"
    trust_score_ppm: int = Field(default=0, ge=0, le=1000000)
    signal_strength_ppm: int = Field(default=0, ge=0, le=1000000)
    battery_level_ppm: int = Field(default=0, ge=0, le=1000000)
    power_cost_ppm: int = Field(default=0, ge=0, le=1000000)
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
    data_type: str = Field(default="event", min_length=1, max_length=80)
    direction: ChannelDirection = "bidirectional"
    status: ChannelStatus = "offered"
    sample_rate_hz: float = Field(default=0.0, ge=0.0, le=192000.0)
    bytes_per_second: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    error_rate_ppm: int = Field(default=0, ge=0, le=1000000)
    packet_loss_ppm: int = Field(default=0, ge=0, le=1000000)
    branch_success_rate_ppm: int = Field(default=0, ge=0, le=1000000)
    infer_error_rate_ppm: int = Field(default=0, ge=0, le=1000000)
    signal_strength_ppm: int = Field(default=0, ge=0, le=1000000)
    power_cost_ppm: int = Field(default=0, ge=0, le=1000000)
    trust_score_ppm: int = Field(default=0, ge=0, le=1000000)
    route_quality_ppm: int = Field(default=0, ge=0, le=1000000)
    model_id: str | None = Field(default=None, max_length=160)


class OrganHeartbeatIn(BaseModel):
    organ_id: str = Field(..., min_length=8, max_length=160)
    listening: bool = True
    active_channels: list[str] = Field(default_factory=list, max_length=32)
    sample_rate_hz: float = Field(default=0.0, ge=0.0, le=192000.0)
    bytes_per_second: float = Field(default=0.0, ge=0.0)
    discovery_state: DiscoveryState = "seen"
    trust_score_ppm: int = Field(default=0, ge=0, le=1000000)
    signal_strength_ppm: int = Field(default=0, ge=0, le=1000000)
    battery_level_ppm: int = Field(default=0, ge=0, le=1000000)
    power_cost_ppm: int = Field(default=0, ge=0, le=1000000)


def _join(values: list[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return ",".join(cleaned[:32])


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _organ_state(payload: dict[str, Any]) -> str:
    state = str(payload.get("discovery_state") or "declared")
    if state in {"training", "streaming", "trusted", "paired"}:
        return state
    if _as_float(payload.get("bytes_per_second")) > 0 or payload.get("listening"):
        return "streaming"
    if _as_int(payload.get("trust_score_ppm")) >= 700000:
        return "trusted"
    if payload.get("active_channels"):
        return "paired"
    return state


def _event_for(payload: OrganAnnounceIn) -> RuntimeEventCreate:
    metadata: dict[str, str | float | int | bool] = {
        "mesh": "hati.mesh",
        "organ_id": payload.organ_id,
        "organ_kind": payload.organ_kind,
        "app": payload.app,
        "app_version": payload.app_version,
        "target": payload.target,
        "discovery_state": payload.discovery_state,
        "trust_score_ppm": payload.trust_score_ppm,
        "signal_strength_ppm": payload.signal_strength_ppm,
        "battery_level_ppm": payload.battery_level_ppm,
        "power_cost_ppm": payload.power_cost_ppm,
        "capabilities": _join(payload.capabilities),
        "lanes": _join(payload.lanes),
        "has_public_key": bool(payload.public_key),
    }
    if payload.steward_cell_id:
        metadata["steward_cell_id"] = payload.steward_cell_id
    if payload.steward_label:
        metadata["steward_label"] = payload.steward_label
    for key in ("display_name", "dwelling_name", "location_label"):
        value = getattr(payload, key)
        if value:
            metadata[key] = value
    for key in ("map_x", "map_y", "latitude", "longitude"):
        value = getattr(payload, key)
        if value is not None:
            metadata[key] = value
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
            "data_type": payload.data_type,
            "direction": payload.direction,
            "status": payload.status,
            "sample_rate_hz": payload.sample_rate_hz,
            "bytes_per_second": payload.bytes_per_second,
            "latency_ms": payload.latency_ms,
            "error_rate_ppm": payload.error_rate_ppm,
            "packet_loss_ppm": payload.packet_loss_ppm,
            "branch_success_rate_ppm": payload.branch_success_rate_ppm,
            "infer_error_rate_ppm": payload.infer_error_rate_ppm,
            "signal_strength_ppm": payload.signal_strength_ppm,
            "power_cost_ppm": payload.power_cost_ppm,
            "trust_score_ppm": payload.trust_score_ppm,
            "route_quality_ppm": payload.route_quality_ppm,
            "model_id": payload.model_id or "",
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
            "discovery_state": payload.discovery_state,
            "trust_score_ppm": payload.trust_score_ppm,
            "signal_strength_ppm": payload.signal_strength_ppm,
            "battery_level_ppm": payload.battery_level_ppm,
            "power_cost_ppm": payload.power_cost_ppm,
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
    rows = runtime_service.list_events(
        limit=max(limit * 4, 100),
        source="api",
        endpoint_prefix="/api/hati/mesh/organs",
    )
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
                "display_name": "",
                "dwelling_name": "",
                "location_label": "",
                "map_x": None,
                "map_y": None,
                "latitude": None,
                "longitude": None,
                "discovery_state": "declared",
                "trust_score_ppm": 0,
                "signal_strength_ppm": 0,
                "battery_level_ppm": 0,
                "power_cost_ppm": 0,
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
            item["display_name"] = row.metadata.get("display_name", item["display_name"])
            item["dwelling_name"] = row.metadata.get("dwelling_name", item["dwelling_name"])
            item["location_label"] = row.metadata.get("location_label", item["location_label"])
            item["map_x"] = row.metadata.get("map_x", item["map_x"])
            item["map_y"] = row.metadata.get("map_y", item["map_y"])
            item["latitude"] = row.metadata.get("latitude", item["latitude"])
            item["longitude"] = row.metadata.get("longitude", item["longitude"])
            item["discovery_state"] = row.metadata.get("discovery_state", item["discovery_state"])
            item["trust_score_ppm"] = _as_int(row.metadata.get("trust_score_ppm", item["trust_score_ppm"]))
            item["signal_strength_ppm"] = _as_int(row.metadata.get("signal_strength_ppm", item["signal_strength_ppm"]))
            item["battery_level_ppm"] = _as_int(row.metadata.get("battery_level_ppm", item["battery_level_ppm"]))
            item["power_cost_ppm"] = _as_int(row.metadata.get("power_cost_ppm", item["power_cost_ppm"]))
            item["steward_cell_id"] = row.metadata.get("steward_cell_id", item["steward_cell_id"])
            item["capabilities"] = str(row.metadata.get("capabilities", "")).split(",") if row.metadata.get("capabilities") else item["capabilities"]
            item["lanes"] = str(row.metadata.get("lanes", "")).split(",") if row.metadata.get("lanes") else item["lanes"]
        else:
            item["listening"] = bool(row.metadata.get("listening", False))
            item["active_channels"] = str(row.metadata.get("active_channels", "")).split(",") if row.metadata.get("active_channels") else []
            item["sample_rate_hz"] = _as_float(row.metadata.get("sample_rate_hz", 0.0))
            item["bytes_per_second"] = _as_float(row.metadata.get("bytes_per_second", 0.0))
            item["discovery_state"] = row.metadata.get("discovery_state", item["discovery_state"])
            item["trust_score_ppm"] = _as_int(row.metadata.get("trust_score_ppm", item["trust_score_ppm"]))
            item["signal_strength_ppm"] = _as_int(row.metadata.get("signal_strength_ppm", item["signal_strength_ppm"]))
            item["battery_level_ppm"] = _as_int(row.metadata.get("battery_level_ppm", item["battery_level_ppm"]))
            item["power_cost_ppm"] = _as_int(row.metadata.get("power_cost_ppm", item["power_cost_ppm"]))
        item["discovery_state"] = _organ_state(item)
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
    rows = runtime_service.list_events(
        limit=max(limit * 4, 100),
        source="api",
        endpoint_prefix="/api/hati/mesh/channels",
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.endpoint != "/api/hati/mesh/channels/offer":
            continue
        from_id = str(row.metadata.get("from_organ_id") or "")
        to_id = str(row.metadata.get("to_organ_id") or "")
        protocol = str(row.metadata.get("protocol") or "")
        if not from_id or not to_id or not protocol:
            continue
        if organ_id and organ_id not in {from_id, to_id}:
            continue
        items.append(
            {
                "from_organ_id": from_id,
                "to_organ_id": to_id,
                "protocol": protocol,
                "interface": str(row.metadata.get("interface") or ""),
                "capability": str(row.metadata.get("capability") or ""),
                "codec": str(row.metadata.get("codec") or ""),
                "data_type": str(row.metadata.get("data_type") or "event"),
                "direction": str(row.metadata.get("direction") or "bidirectional"),
                "status": str(row.metadata.get("status") or "offered"),
                "sample_rate_hz": row.metadata.get("sample_rate_hz", 0.0),
                "bytes_per_second": row.metadata.get("bytes_per_second", 0.0),
                "latency_ms": row.metadata.get("latency_ms", 0.0),
                "error_rate_ppm": row.metadata.get("error_rate_ppm", 0),
                "packet_loss_ppm": row.metadata.get("packet_loss_ppm", 0),
                "branch_success_rate_ppm": row.metadata.get("branch_success_rate_ppm", 0),
                "infer_error_rate_ppm": row.metadata.get("infer_error_rate_ppm", 0),
                "signal_strength_ppm": _as_int(row.metadata.get("signal_strength_ppm", 0)),
                "power_cost_ppm": _as_int(row.metadata.get("power_cost_ppm", 0)),
                "trust_score_ppm": _as_int(row.metadata.get("trust_score_ppm", 0)),
                "route_quality_ppm": _as_int(row.metadata.get("route_quality_ppm", 0)),
                "model_id": row.metadata.get("model_id", ""),
                "last_seen_at": row.recorded_at.isoformat(),
                "receipt_id": row.id,
            }
        )
        if len(items) >= limit:
            break
    return {"mesh": "hati.mesh", "count": len(items), "items": items}
