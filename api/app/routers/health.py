"""Health check endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter()


@router.get("/version")
async def version():
    """Return API version (lightweight, for dashboards)."""
    return {"version": "0.1.0"}


@router.get("/ready")
async def ready():
    """Readiness probe for k8s/deploy. Returns 200 when API can serve traffic."""
    return {"status": "ready"}


@router.get("/health")
async def health():
    """Return API health status."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
