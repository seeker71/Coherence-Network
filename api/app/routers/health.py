"""Health check endpoint (spec 001)."""

from datetime import datetime, timezone
import logging
import os
import ast
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.middleware.request_outcomes import recent_outcomes_snapshot
from app.services import persistence_contract_service
from app.services import unified_db
from app.services import audit_ledger_service
from app.services.config_service import get_config

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
    """Get deployed SHA from runtime environment or config."""
    for key in _DEPLOY_SHA_ENV_KEYS:
        value = str(os.getenv(key, "")).strip()
        if value:
            return value, key
    config = get_config()
    sha = config.get("deployed_sha")
    if sha:
        return str(sha), "config:deployed_sha"
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
    integrity_compromised: Annotated[
        bool,
        Field(description="True if audit ledger hash chain verification fails"),
    ] = False


class HealthResponse(_BaseHealthResponse):
    """GET /api/health response."""
    schema_ok: Annotated[
        bool,
        Field(description="True if core tables (contributions, contributors, assets) exist"),
    ] = True
    opencode_enabled: Annotated[
        bool,
        Field(description="True if opencode integration is enabled"),
    ] = True
    smart_reap_available: Annotated[
        bool,
        Field(description="True if smart_reap_service module is importable"),
    ] = True
    smart_reap_import_error: Annotated[
        str | None,
        Field(description="Import error message if smart_reap_service failed to load"),
    ] = None
    recent_outcomes: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Real-user traffic outcome snapshot from "
                "RequestOutcomesMiddleware: rolling per-status-class counts "
                "over the last 1 and 5 minutes. Read by pulse to flag the "
                "api organ as strained when recent_outcomes.last_1m.5xx > 0."
            )
        ),
    ] = None


class ReadyResponse(_BaseHealthResponse):
    """GET /api/ready response."""
    db_connected: Annotated[bool, Field(description="Whether the database is reachable")] = False


class PingResponse(BaseModel):
    """GET /api/ping response."""

    model_config = ConfigDict(extra="forbid")
    pong: Annotated[bool, Field(description="Always true when API is reachable")]
    timestamp: Annotated[str, Field(description="ISO8601 UTC")]


@router.get("/version", summary="Return API version (lightweight, for dashboards)")
async def version():
    """Return API version (lightweight, for dashboards)."""
    return {"version": HEALTH_VERSION}


@router.get("/ping", response_model=PingResponse, summary="Lightweight liveness ping with current UTC timestamp")
async def ping():
    """Lightweight liveness ping with current UTC timestamp."""
    now = datetime.now(timezone.utc)
    return PingResponse(pong=True, timestamp=_iso_utc(now))


@router.get("/ready", response_model=ReadyResponse, summary="Readiness probe for k8s/deploy. Returns 200 when API can serve traffic")
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

    # Check audit ledger integrity (spec 123)
    integrity_compromised = False
    try:
        # We only check the last 100 entries for the health check to keep it fast
        # Full verification is available at /api/audit/verify
        res = audit_ledger_service.verify_chain()
        integrity_compromised = not res.verified
    except Exception:
        logger.warning("Integrity check failed", exc_info=True)

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
        integrity_compromised=integrity_compromised,
    )


@router.get("/health/persistence", summary="Return global persistence contract status for core domain data")
async def persistence_contract(request: Request):
    """Return global persistence contract status for core domain data."""
    return persistence_contract_service.evaluate(request.app)


def _check_schema() -> bool:
    """Validate that core tables (contributions, contributors, assets) exist."""
    try:
        from sqlalchemy import text as _text
        with unified_db.session() as sess:
            for table in ("contributions", "contributors", "assets"):
                sess.execute(_text(f"SELECT 1 FROM {table} LIMIT 1"))
        return True
    except Exception:
        logger.warning("Schema check: one or more core tables missing", exc_info=True)
        return False


@router.get("/health", response_model=HealthResponse, summary="Return API health status")
async def health():
    """Return API health status."""
    now = datetime.now(timezone.utc)
    up = _uptime_seconds(now)
    deployed_sha, deployed_sha_source = _deployed_sha()

    # Check audit ledger integrity (spec 123)
    integrity_compromised = False
    try:
        res = audit_ledger_service.verify_chain()
        integrity_compromised = not res.verified
    except Exception:
        logger.warning("Integrity check failed", exc_info=True)

    schema_ok = _check_schema()

    # Gap 1: Check if smart_reap_service is importable
    smart_reap_available = True
    smart_reap_import_error = None
    try:
        import importlib
        importlib.import_module("app.services.smart_reaper_service")
    except ImportError as _e:
        smart_reap_available = False
        smart_reap_import_error = str(_e)

    # Real-user traffic outcome snapshot. If the middleware isn't wired
    # (e.g. during a test client run without the full stack), this fails
    # softly and the field is None.
    try:
        recent_outcomes = recent_outcomes_snapshot()
    except Exception:
        recent_outcomes = None

    return HealthResponse(
        status="ok",
        version=HEALTH_VERSION,
        timestamp=_iso_utc(now),
        started_at=_iso_utc(SERVICE_STARTED_AT),
        uptime_seconds=up,
        uptime_human=_uptime_human(up),
        deployed_sha=deployed_sha,
        deployed_sha_source=deployed_sha_source,
        integrity_compromised=integrity_compromised,
        schema_ok=schema_ok,
        smart_reap_available=smart_reap_available,
        smart_reap_import_error=smart_reap_import_error,
        recent_outcomes=recent_outcomes,
    )
