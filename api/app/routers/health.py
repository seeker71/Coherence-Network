"""Health check endpoint (spec 001)."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()

# Spec 001: exactly status, version, timestamp; all strings; no extra keys
HEALTH_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    """GET /api/health response — status, version, timestamp only (spec 001)."""
    model_config = ConfigDict(extra="forbid")
    status: Annotated[str, Field(description="Always 'ok'")]
    version: Annotated[str, Field(description="Semver MAJOR.MINOR.PATCH")]
    timestamp: Annotated[str, Field(description="ISO8601 UTC")]


@router.get("/version")
async def version():
    """Return API version (lightweight, for dashboards)."""
    return {"version": "0.1.0"}


@router.get("/ready")
async def ready():
    """Readiness probe for k8s/deploy. Returns 200 when API can serve traffic."""
    return {"status": "ready"}


@router.get("/health", response_model=HealthResponse)
async def health():
    """Return API health status (spec 001)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return HealthResponse(status="ok", version=HEALTH_VERSION, timestamp=ts)
