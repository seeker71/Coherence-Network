"""Health check endpoint (spec 001)."""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()
_log = logging.getLogger("coherence.api.perf")

HEALTH_VERSION = "1.0.0"
SERVICE_STARTED_AT = datetime.now(timezone.utc)


def _iso_utc(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uptime_seconds(now: datetime) -> int:
    return max(0, int((now - SERVICE_STARTED_AT).total_seconds()))


def _uptime_human(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m {secs}s"
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class HealthResponse(BaseModel):
    """GET /api/health response."""

    model_config = ConfigDict(extra="forbid")
    status: Annotated[str, Field(description="Always 'ok'")]
    version: Annotated[str, Field(description="Semver MAJOR.MINOR.PATCH")]
    timestamp: Annotated[str, Field(description="ISO8601 UTC")]
    started_at: Annotated[str, Field(description="ISO8601 UTC when service process started")]
    uptime_seconds: Annotated[int, Field(description="Seconds service has been up")]
    uptime_human: Annotated[str, Field(description="Human readable uptime")]


class ReadyResponse(BaseModel):
    """GET /api/ready response."""

    model_config = ConfigDict(extra="forbid")
    status: Annotated[str, Field(description="Always 'ready'")]
    version: Annotated[str, Field(description="Semver MAJOR.MINOR.PATCH")]
    timestamp: Annotated[str, Field(description="ISO8601 UTC")]
    started_at: Annotated[str, Field(description="ISO8601 UTC when service process started")]
    uptime_seconds: Annotated[int, Field(description="Seconds service has been up")]
    uptime_human: Annotated[str, Field(description="Human readable uptime")]


@router.get("/version")
async def version():
    """Return API version (lightweight, for dashboards)."""
    return {"version": HEALTH_VERSION}


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request):
    """Readiness probe for k8s/deploy. Returns 200 when API can serve traffic."""
    is_ready = getattr(request.app.state, "graph_store", None) is not None
    if not is_ready:
        raise HTTPException(status_code=503, detail="not ready")
    now = datetime.now(timezone.utc)
    up = _uptime_seconds(now)
    return ReadyResponse(
        status="ready",
        version=HEALTH_VERSION,
        timestamp=_iso_utc(now),
        started_at=_iso_utc(SERVICE_STARTED_AT),
        uptime_seconds=up,
        uptime_human=_uptime_human(up),
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    """Return API health status."""
    debug = "/api/health" in {
        part.strip()
        for part in (os.getenv("PERF_DEBUG_ENDPOINTS", "") or "").split(",")
        if part.strip()
    }
    t0 = time.perf_counter()
    now = datetime.now(timezone.utc)
    t1 = time.perf_counter()
    up = _uptime_seconds(now)
    t2 = time.perf_counter()
    resp = HealthResponse(
        status="ok",
        version=HEALTH_VERSION,
        timestamp=_iso_utc(now),
        started_at=_iso_utc(SERVICE_STARTED_AT),
        uptime_seconds=up,
        uptime_human=_uptime_human(up),
    )
    t3 = time.perf_counter()
    if debug:
        _log.info(
            "perf_health steps_ms now=%.3f uptime=%.3f construct=%.3f total=%.3f",
            (t1 - t0) * 1000.0,
            (t2 - t1) * 1000.0,
            (t3 - t2) * 1000.0,
            (t3 - t0) * 1000.0,
        )
    return resp
