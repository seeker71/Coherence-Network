"""Health check endpoint (spec 001)."""

from datetime import datetime, timezone
import logging
import os
import ast
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
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
    """Get deployed SHA from the live file-backed configuration."""
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
        Field(description="File-backed configuration source for deployed_sha"),
    ] = None
    integrity_compromised: Annotated[
        bool,
        Field(description="True if audit ledger hash chain verification fails"),
    ] = False
    integrity_verified: Annotated[
        bool,
        Field(
            description=(
                "True only when audit-ledger verification completed without error"
            )
        ),
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
    kernel_runtime: Annotated[
        str,
        Field(
            description=(
                "Which form-kernel path would serve a transmuted endpoint "
                "in this container right now — 'inline' (PyO3 extension), "
                "'subprocess' (form-kernel-rust binary), or 'unavailable' "
                "(no kernel carrier reachable). Lets the witness see at a "
                "glance whether a deploy lost the hot path."
            )
        ),
    ] = "unavailable"
    native_runtime_observation: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Behavioral kernel known-answer and form-cli nonce/digest "
                "challenge, including current executable/table identities"
            )
        ),
    ] = None
    observation_schema: Annotated[str | None, Field()] = None
    observation_nonce_sha256: Annotated[str | None, Field()] = None
    kernel_challenge: Annotated[dict[str, Any] | None, Field()] = None
    form_cli_challenge: Annotated[dict[str, Any] | None, Field()] = None
    deployment_witness_node_id: Annotated[
        str | None,
        Field(description="Latest persisted deployment WITNESS NamedCell REF"),
    ] = None
    deployment_witness_content_node_id: Annotated[
        str | None,
        Field(description="Content CTOR bound to the latest deployment WITNESS"),
    ] = None
    deployment_observed_at: Annotated[
        str | None,
        Field(description="UTC time of the independent post-deploy health read"),
    ] = None
    deployment_observation_expires_at: Annotated[
        str | None,
        Field(description="UTC expiry of the latest deployment WITNESS"),
    ] = None
    deployment_observation_fresh: Annotated[
        bool,
        Field(description="True only while the latest WITNESS verifies and is unexpired"),
    ] = False


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
    integrity_verified = False
    try:
        # We only check the last 100 entries for the health check to keep it fast
        # Full verification is available at /api/audit/verify
        res = audit_ledger_service.verify_chain()
        integrity_verified = True
        integrity_compromised = not res.verified
    except Exception:
        logger.warning("Integrity check failed", exc_info=True)
    if not integrity_verified or integrity_compromised:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "integrity_verification_failed",
                "integrity_verified": integrity_verified,
                "integrity_compromised": integrity_compromised,
            },
        )

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
        integrity_verified=integrity_verified,
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
async def health(
    observation_nonce: Annotated[
        str | None,
        Query(pattern=r"^[A-Za-z0-9_-]{43}$"),
    ] = None,
):
    """Return API health status."""
    now = datetime.now(timezone.utc)
    up = _uptime_seconds(now)
    deployed_sha, deployed_sha_source = _deployed_sha()

    # Check audit ledger integrity (spec 123)
    integrity_compromised = False
    integrity_verified = False
    try:
        res = audit_ledger_service.verify_chain()
        integrity_verified = True
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

    # Execute both native carriers. Availability flags alone are not evidence
    # that the deployed executable can answer or that its source stamp matches.
    observation_schema = None
    observation_nonce_sha256 = None
    kernel_challenge = None
    form_cli_challenge = None
    try:
        if observation_nonce is None:
            from app.services.native_runtime_observation import observe_native_runtime

            native_runtime_observation = observe_native_runtime()
            kernel_runtime = str(
                native_runtime_observation.get("kernel", {}).get(
                    "runtime", "unavailable"
                )
            )
        else:
            from app.services.deployment_observer_service import (
                active_challenge_for_nonce,
                carrier_challenge_input_sha256,
                nonce_sha256,
            )
            from app.services.native_runtime_observation import (
                observe_native_runtime_challenge,
            )

            with unified_db.session() as sess:
                challenge = active_challenge_for_nonce(
                    sess, nonce=observation_nonce
                )
            if deployed_sha != challenge.target_sha:
                raise RuntimeError("observer challenge deployment SHA drift")
            challenge_input = carrier_challenge_input_sha256(observation_nonce)
            native_runtime_observation = observe_native_runtime_challenge(
                challenge_input
            )
            kernel = native_runtime_observation["kernel"]
            form_cli = native_runtime_observation["form_cli"]
            observation_schema = "native-carrier-observation-v1"
            observation_nonce_sha256 = nonce_sha256(observation_nonce)
            kernel_runtime = str(kernel["runtime"])
            kernel_challenge = {
                "input_sha256": challenge_input,
                "result": str(kernel["result"]),
                "verified": True,
                "runtime": kernel_runtime,
                "binary_sha256": kernel["binary_sha256"],
            }
            form_cli_challenge = {
                "input_sha256": challenge_input,
                "result": form_cli["challenge_response_sha256"],
                "verified": True,
                "protocol": "form-cli-v2",
                "binary_sha256": form_cli["binary_sha256"],
                "wrapper_sha256": form_cli["wrapper_sha256"],
                "source_sha256": form_cli["source_stamp"],
                "table_sha256": form_cli["table_sha256"],
                "stamp_sha256": form_cli["stamp_sha256"],
            }
    except Exception as exc:
        if observation_nonce is not None:
            raise HTTPException(
                status_code=503,
                detail="native observer challenge failed",
            ) from exc
        native_runtime_observation = None
        kernel_runtime = "unavailable"

    witness = None
    witness_fresh = False
    try:
        from app.services.deployment_observation import (
            latest_deployment_observation,
            verify_deployment_observation,
        )
        with unified_db.session() as sess:
            witness = latest_deployment_observation(sess, now=now, allow_expired=True)
            if witness is not None:
                verify_deployment_observation(
                    sess,
                    witness["node_id"],
                    expected_answer_key=witness["answer_key"],
                    now=now,
                )
                witness_fresh = True
    except Exception:
        witness_fresh = False

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
        integrity_verified=integrity_verified,
        schema_ok=schema_ok,
        smart_reap_available=smart_reap_available,
        smart_reap_import_error=smart_reap_import_error,
        recent_outcomes=recent_outcomes,
        kernel_runtime=kernel_runtime,
        native_runtime_observation=native_runtime_observation,
        observation_schema=observation_schema,
        observation_nonce_sha256=observation_nonce_sha256,
        kernel_challenge=kernel_challenge,
        form_cli_challenge=form_cli_challenge,
        deployment_witness_node_id=(witness or {}).get("node_id"),
        deployment_witness_content_node_id=(witness or {}).get("content_node_id"),
        deployment_observed_at=(witness or {}).get("observed_at"),
        deployment_observation_expires_at=(witness or {}).get("expires_at"),
        deployment_observation_fresh=witness_fresh,
    )


@router.get(
    "/health/db-contention",
    summary="Leading indicator of DB write-lane contention (oldest txn age + lock-waiters)",
)
async def db_contention():
    """A leading indicator of write-lane lock contention — wedge prevention.

    On 2026-07-02 the substrate write lane wedged three times on a long-held
    `UPDATE substrate_nodes SET count = ...`, each needing a manual
    pg_terminate_backend. The DB now fails such waits fast (lock_timeout) and
    reaps idle transactions; this probe lets a monitor SEE contention building
    *before* it bites — the oldest open transaction's age and the number of
    statements waiting on a lock. Postgres only; sqlite has no pg_stat_activity
    and returns nulls with backend='sqlite'.
    """
    from sqlalchemy import text as _text

    now = datetime.now(timezone.utc)
    out: dict[str, Any] = {
        "timestamp": _iso_utc(now),
        "backend": None,
        "max_txn_age_seconds": None,
        "lock_waiters": None,
        "healthy": True,
    }
    try:
        with unified_db.session() as sess:
            backend = sess.bind.dialect.name if sess.bind is not None else None
            out["backend"] = backend
            if backend == "postgresql":
                row = sess.execute(
                    _text(
                        "SELECT "
                        "COALESCE(EXTRACT(EPOCH FROM (now() - min(xact_start))), 0) "
                        "  AS max_age, "
                        "COUNT(*) FILTER (WHERE wait_event_type = 'Lock') "
                        "  AS lock_waiters "
                        "FROM pg_stat_activity WHERE xact_start IS NOT NULL"
                    )
                ).one()
                max_age = float(row.max_age)
                waiters = int(row.lock_waiters)
                out["max_txn_age_seconds"] = round(max_age, 2)
                out["lock_waiters"] = waiters
                # With lock_timeout=5s and idle_in_transaction=30s in force, a
                # transaction older than ~25s or waiters piling up means the
                # write lane is under real strain — surface it before it wedges.
                out["healthy"] = max_age < 25.0 and waiters <= 2
    except Exception:
        logger.warning("db-contention probe failed", exc_info=True)
        out["healthy"] = None  # unknown, not asserted-healthy
    return out
