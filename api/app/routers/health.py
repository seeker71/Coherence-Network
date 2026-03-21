"""Health check endpoint (spec 001)."""

from datetime import datetime, timezone
import logging
import os
import ast
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services import persistence_contract_service
from app.services import unified_db

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_api_version() -> str:
    """Read API version from setup.py in the api directory."""
    try:
        # Resolve the path to setup.py relative to this file
        setup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "setup.py")
        if os.path.exists(setup_path):
            with open(setup_path, "r") as f:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setup":
                        for keyword in node.keywords:
                            if keyword.arg == "version":
                                return str(ast.literal_eval(keyword.value))
    except Exception as e:
        logger.warning(f"Failed to load version from setup.py: {e}")
    
    return "1.0.0"  # Fallback


HEALTH_VERSION = _get_api_version()
SERVICE_STARTED_AT = datetime.now(timezone.utc)
_DEPLOY_SHA_ENV_KEYS = (
    "RAILWAY_GIT_COMMIT_SHA",
    "RAILWAY_GIT_SHA",
    "GIT_COMMIT_SHA",
    "COMMIT_SHA",
    "SOURCE_VERSION",
)


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


def _deployed_sha() -> tuple[str | None, str | None]:
    for env_key in _DEPLOY_SHA_ENV_KEYS:
        value = str(os.getenv(env_key, "")).strip()
        if value:
            return value, env_key
    return None, None


class _BaseHealthResponse(BaseModel):
    """Shared fields for health and readiness responses."""

    model_config = ConfigDict(extra="forbid")
    status: Annotated[str, Field(description="Service status")]
    version: Annotated[str, Field(description="Semver MAJOR.MINOR.PATCH")]
    timestamp: Annotated[str, Field(description="ISO8601 UTC")]
    started_at: Annotated[str, Field(description="ISO8601 UTC when service process started")]
    uptime_seconds: Annotated[int, Field(description="Seconds service has been up")]
    uptime_human: Annotated[str, Field(description="Human readable uptime")]
    deployed_sha: Annotated[
        str | None,
        Field(description="Deployed commit SHA when available from runtime environment"),
    ] = None
    deployed_sha_source: Annotated[
        str | None,
        Field(description="Environment variable source for deployed_sha"),
    ] = None


class HealthResponse(_BaseHealthResponse):
    """GET /api/health response."""
    pass


class ReadyResponse(_BaseHealthResponse):
    """GET /api/ready response."""
    db_connected: Annotated[bool, Field(description="Whether the database is reachable")] = False


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
    persistence_report = persistence_contract_service.evaluate(request.app)
    if persistence_report.get("required") and not persistence_report.get("pass_contract"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "persistence_contract_failed",
                "failures": persistence_report.get("failures", []),
                "domains": persistence_report.get("domains", {}),
            },
        )
    now = datetime.now(timezone.utc)
    up = _uptime_seconds(now)
    deployed_sha, deployed_sha_source = _deployed_sha()
    db_connected = False
    try:
        from sqlalchemy import text as _text
        with unified_db.session() as sess:
            sess.execute(_text("SELECT 1"))
        db_connected = True
    except Exception:
        logger.warning("DB connectivity check failed", exc_info=True)
    return ReadyResponse(
        status="ready",
        version=HEALTH_VERSION,
        timestamp=_iso_utc(now),
        started_at=_iso_utc(SERVICE_STARTED_AT),
        uptime_seconds=up,
        uptime_human=_uptime_human(up),
        deployed_sha=deployed_sha,
        deployed_sha_source=deployed_sha_source,
        db_connected=db_connected,
    )


@router.get("/health/persistence")
async def persistence_contract(request: Request):
    """Return global persistence contract status for core domain data."""
    return persistence_contract_service.evaluate(request.app)


@router.get("/health", response_model=HealthResponse)
async def health():
    """Return API health status."""
    now = datetime.now(timezone.utc)
    up = _uptime_seconds(now)
    deployed_sha, deployed_sha_source = _deployed_sha()
    return HealthResponse(
        status="ok",
        version=HEALTH_VERSION,
        timestamp=_iso_utc(now),
        started_at=_iso_utc(SERVICE_STARTED_AT),
        uptime_seconds=up,
        uptime_human=_uptime_human(up),
        deployed_sha=deployed_sha,
        deployed_sha_source=deployed_sha_source,
    )
