from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.adapters.graph_store import InMemoryGraphStore
from app.adapters.postgres_store import PostgresGraphStore, Base
from app.config_loader import get_float
from app.routers import (
    agent,
    automation_usage,
    assets,
    audit,
    coherence,
    contributions,
    contributor_identity,
    contributors,
    distributions,
    federation,
    friction,
    gates,
    governance,
    health,
    ideas,
    inventory,
    news,
    providers,
    spec_registry,
    runtime,
    auth_keys,
    traceability,
    treasury,
    value_lineage,
)
from app.routers import concepts
from app.routers import graph
from app.routers import agent_grounded_metrics_routes
from app.routers import provider_stats
from app.routers import service_registry_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_duration import RequestDurationMiddleware
from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service

_startup_logger = logging.getLogger("coherence.api.slow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # -- L1: CORS production warning --
    _ao = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    _db = os.getenv("DATABASE_URL", "")
    if _ao == "http://localhost:3000" and "postgres" in _db:
        _startup_logger.warning(
            "CORS_DEFAULT_IN_PRODUCTION ALLOWED_ORIGINS is still 'http://localhost:3000' "
            "but DATABASE_URL contains 'postgres', indicating a production database. "
            "Set ALLOWED_ORIGINS to your production domain(s)."
        )

    # -- Ensure all DB tables exist (non-destructive) --
    try:
        from app.services.unified_models import Base as _UnifiedBase
        from app.services.unified_db import engine as _get_engine
        _eng = _get_engine()
        if _eng:
            _UnifiedBase.metadata.create_all(_eng, checkfirst=True)
            _startup_logger.info("DB tables ensured via unified_models.Base")
    except Exception:
        _startup_logger.warning("DB table creation skipped", exc_info=True)

    # -- Prime hot caches (migrated from @app.on_event('startup')) --
    try:
        startup_begin = time.perf_counter()
        from app.services import (
            commit_evidence_service,
            inventory_service,
            idea_service,
            spec_registry_service,
            runtime_service as runtime_cache_service,
        )

        idea_rows = idea_service.list_ideas().ideas
        spec_rows = spec_registry_service.list_specs(limit=1000)
        evidence_rows = commit_evidence_service.list_records(limit=2000)
        runtime_rows = runtime_cache_service.list_events(
            limit=2000,
            since=datetime.now(timezone.utc) - timedelta(hours=24),
        )
        store = getattr(app.state, "graph_store", None)
        contributor_rows = 0
        contribution_rows = 0
        asset_rows = 0
        contributor_payload_rows: list[dict] = []
        contribution_payload_rows: list[dict] = []
        asset_payload_rows: list[dict] = []
        startup_errors: list[str] = []
        if store is not None:
            try:
                contributor_payload_rows = [item.model_dump(mode="json") for item in store.list_contributors(limit=2000)]
                contributor_rows = len(contributor_payload_rows)
            except Exception:
                _startup_logger.error("startup: contributors table missing or unreadable", exc_info=True)
                startup_errors.append("contributors_table_missing")
            try:
                contribution_payload_rows = [item.model_dump(mode="json") for item in store.list_contributions(limit=2000)]
                contribution_rows = len(contribution_payload_rows)
            except Exception:
                _startup_logger.error("startup: contributions table missing or unreadable", exc_info=True)
                startup_errors.append("contributions_table_missing")
            try:
                asset_payload_rows = [item.model_dump(mode="json") for item in store.list_assets(limit=2000)]
                asset_rows = len(asset_payload_rows)
            except Exception:
                _startup_logger.error("startup: assets table missing or unreadable", exc_info=True)
                startup_errors.append("assets_table_missing")
        try:
            flow_payload = inventory_service.build_spec_process_implementation_validation_flow(
                runtime_window_seconds=86400,
                contributor_rows=contributor_payload_rows,
                contribution_rows=contribution_payload_rows,
                asset_rows=asset_payload_rows,
                spec_registry_limit=200,
                lineage_link_limit=300,
                usage_event_limit=1200,
                commit_evidence_limit=500,
                runtime_event_limit=2000,
            )
            if not isinstance(flow_payload, dict):
                flow_payload = {}
            flow_items = len(flow_payload.get("items", []))
        except Exception:
            _startup_logger.debug("api_startup_flow_cache_failed", exc_info=True)
            flow_items = 0
        startup_ms = (time.perf_counter() - startup_begin) * 1000.0
        _startup_logger.info(
            "api_startup_cache_warm elapsed_ms=%.2f idea_count=%s spec_count=%s evidence_count=%s runtime_events=%s contributors=%s contributions=%s assets=%s flow_items=%s",
            startup_ms,
            len(idea_rows),
            len(spec_rows),
            len(evidence_rows),
            len(runtime_rows),
            contributor_rows,
            contribution_rows,
            asset_rows,
            flow_items,
        )
        # Record friction events for any DB table failures detected at startup
        if startup_errors:
            try:
                from app.models.friction import FrictionEvent as _FE
                from app.services import friction_service as _fs
                for err_label in startup_errors:
                    evt = _FE(
                        id=f"fric_{uuid4().hex[:12]}",
                        timestamp=datetime.now(timezone.utc),
                        stage="startup",
                        block_type="missing_table",
                        severity="high",
                        owner="api_startup",
                        unblock_condition=f"Ensure {err_label.replace('_', ' ')} exists; run DB migrations or restart.",
                        energy_loss_estimate=1.0,
                        cost_of_delay=0.0,
                        status="open",
                        notes=f"Startup detected: {err_label}",
                    )
                    _fs.append_event(evt)
            except Exception:
                _startup_logger.warning("Failed to record startup friction events", exc_info=True)
    except Exception:
        _startup_logger.warning("api_startup_cache_warm_failed", exc_info=True)

    # -- Service Registry: discover, register, and initialize contracts --
    try:
        from app.services.service_registry import ServiceRegistry
        from app.services.contracts.idea_contract import IdeaServiceContract
        from app.services.contracts.agent_contract import AgentServiceContract
        from app.services.contracts.runtime_contract import RuntimeServiceContract
        from app.services.contracts.inventory_contract import InventoryServiceContract
        from app.services.contracts.federation_contract import FederationServiceContract

        registry = ServiceRegistry()
        registry.register(IdeaServiceContract())
        registry.register(AgentServiceContract())
        registry.register(RuntimeServiceContract())
        registry.register(InventoryServiceContract())
        registry.register(FederationServiceContract())

        await registry.initialize_all()

        missing = registry.validate_dependencies()
        if missing:
            _startup_logger.warning("service_registry_missing_deps: %s", missing)

        app.state.service_registry = registry
        metrics = registry.startup_metrics()
        _startup_logger.info(
            "service_registry_ready discovered=%d registered=%d initialized=%d failed=%d",
            metrics["discovered"],
            metrics["registered"],
            metrics["initialized"],
            metrics["failed"],
        )
    except Exception:
        _startup_logger.warning("service_registry_setup_failed", exc_info=True)

    yield
    # shutdown: nothing needed currently


app = FastAPI(
    title="Coherence Contribution Network API",
    version=health.HEALTH_VERSION,
    description=(
        "Open intelligence platform that traces every idea from inception to payout — "
        "with fair attribution, coherence scoring, and federated trust.\n\n"
        "**Ecosystem:** "
        "[Web](https://coherencycoin.com) · "
        "[API Docs](https://api.coherencycoin.com/docs) · "
        "[CLI (`npm i -g coherence-cli`)](https://www.npmjs.com/package/coherence-cli) · "
        "[MCP Server](https://www.npmjs.com/package/coherence-mcp-server) · "
        "[GitHub](https://github.com/seeker71/Coherence-Network) · "
        "[OpenClaw Skill](https://clawhub.com/skills/coherence-network)"
    ),
    contact={"name": "Coherence Network", "url": "https://github.com/seeker71/Coherence-Network"},
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Liveness and readiness probes"},
        {"name": "contributors", "description": "Contributor registry CRUD"},
        {"name": "assets", "description": "Asset inventory CRUD"},
        {"name": "contributions", "description": "Contribution tracking with coherence scoring"},
        {"name": "distributions", "description": "Value distribution calculations"},
        {"name": "ideas", "description": "Idea portfolio and ROI analysis"},
        {"name": "spec-registry", "description": "Feature specification tracking"},
        {"name": "agent", "description": "Task orchestration and agent execution"},
        {"name": "gates", "description": "Release gate validation"},
        {"name": "runtime", "description": "Runtime telemetry and event tracking"},
        {"name": "inventory", "description": "System lineage aggregation"},
        {"name": "governance", "description": "Change approval workflows"},
        {"name": "friction", "description": "Pipeline friction signals"},
        {"name": "automation-usage", "description": "Provider readiness and usage tracking"},
        {"name": "value-lineage", "description": "Value attribution tracing"},
        {"name": "identity", "description": "Contributor identity linking and verification"},
    ],
)
logger = logging.getLogger("coherence.api.slow")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
logger.propagate = False
logger.setLevel(logging.INFO)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _slow_request_ms_threshold() -> float:
    raw = os.getenv("API_SLOW_REQUEST_MS")
    if raw is not None:
        try:
            return max(25.0, float(raw.strip()))
        except ValueError:
            pass
    return max(25.0, get_float("api", "slow_request_ms", 1500.0))


def _build_route_signature(request) -> tuple[str, str, str]:
    route = request.scope.get("route")
    route_path = ""
    route_name = ""
    if route is not None:
        route_path = str(getattr(route, "path", "") or "")
        route_name = str(getattr(route, "name", "") or "")
    raw_path = request.url.path
    request_path = route_path if route_path else raw_path
    return request_path, route_name, raw_path


def _query_summary(query_params) -> tuple[int, list[dict[str, str]], dict[str, str]]:
    items = []
    heavy_keys = {
        "limit",
        "top",
        "runtime_window_seconds",
        "contributor_limit",
        "contribution_limit",
        "asset_limit",
        "spec_limit",
        "lineage_link_limit",
        "usage_event_limit",
        "runtime_event_limit",
        "max_implementation_files",
        "cycles",
        "max_endpoints",
        "delay_ms",
    }
    summary: dict[str, str] = {}
    for key, value in query_params.multi_items():
        if key in heavy_keys:
            summary[key] = value
        if len(items) < 8:
            items.append({"k": key, "v": value})
    return len(query_params), items, summary


def _client_identity(request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",", 1)[0].strip()
    remote = request.client.host if request.client and request.client.host else ""
    if remote:
        return remote
    return "unknown"


def _correlation_id(request) -> str:
    for key in (
        "x-request-id",
        "x-vercel-id",
        "x-railway-request-id",
        "x-amzn-trace-id",
        "cf-ray",
    ):
        value = request.headers.get(key)
        if value:
            return value
    return "none"


def _safe_int_or_none(value: str | None) -> int | None:
    if not value or not value.isdigit():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _slow_route_reasons(
    path: str,
    status_code: int | None,
    reasons: list[str],
    method: str,
    query_summary: dict[str, str],
) -> list[str]:
    observed = list(reasons)
    status_code = status_code or 0

    if "/api/inventory/flow" in path:
        observed.append("inventory/flow performs multi-source aggregation")
    if "/api/inventory/system-lineage" in path:
        observed.append("system-lineage computes lineage + commit evidence + runtime summary")
    if "/api/inventory/commit-evidence" in path:
        observed.append("commit-evidence sorts and traverses recent records")
    if "/api/runtime/ideas/summary" in path:
        observed.append("runtime summary computes windowed event rollup")
    if "/api/runtime/exerciser/run" in path:
        observed.append("runtime exerciser performs batched endpoint hits")
    if status_code and status_code >= 500:
        observed.append("server error path")
    runtime_window_seconds = query_summary.get("runtime_window_seconds")
    if runtime_window_seconds and runtime_window_seconds.isdigit():
        if int(runtime_window_seconds) > 86400:
            observed.append("large runtime_window_seconds window")
    for key in ("contributor_limit", "contribution_limit", "asset_limit", "spec_limit"):
        value = query_summary.get(key)
        if value and value.isdigit() and int(value) >= 2000:
            observed.append(f"high request load key={key} value={value}")
    for key in ("lineage_link_limit", "usage_event_limit", "runtime_event_limit"):
        value = query_summary.get(key)
        if value and value.isdigit() and int(value) >= 2000:
            observed.append(f"high request load key={key} value={value}")

    if method == "POST" and any(key in query_summary for key in ("delay_ms", "runtime_window_seconds")):
        observed.append("POST with latency-affecting query modifiers")
    if status_code >= 500:
        observed.append("server error path")
    if status_code == 404:
        observed.append("route miss")
    if not query_summary:
        observed.append("no heavy query params")

    seen: set[str] = set()
    ordered: list[str] = []
    for reason in observed:
        if reason in seen:
            continue
        seen.add(reason)
        ordered.append(reason)
    return ordered

# Configure CORS
from app.services.config_service import get_cors_origins
allowed_origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Agent-Execute-Token", "X-Admin-Key", "X-API-Key", "X-Idea-ID"],
    expose_headers=["X-Request-ID", "X-Coherence-Runtime-Ms", "X-Coherence-Runtime-Cost-Estimate"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses per OWASP best practices."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if os.getenv("ENABLE_HSTS", "").strip().lower() in {"1", "true", "yes"}:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Request-ID for tracing across services."""

    async def dispatch(self, request: Request, call_next):
        request_id = None
        for key in ("x-request-id", "x-vercel-id", "x-railway-request-id", "x-amzn-trace-id", "cf-ray"):
            value = request.headers.get(key)
            if value:
                request_id = value
                break
        if not request_id:
            request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestDurationMiddleware, threshold_seconds=1.0)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# Initialize graph store based on environment
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Production: Use PostgreSQL
    app.state.graph_store = PostgresGraphStore(database_url)
else:
    # Development/Testing: Use in-memory store with optional JSON persistence
    persist_path = os.getenv("GRAPH_STORE_PATH")
    app.state.graph_store = InMemoryGraphStore(persist_path=persist_path)

# Operational endpoints
@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation."""
    return RedirectResponse(url="/docs")

@app.post("/api/admin/reset-database")
async def reset_database(x_admin_key: str = Header(None)):
    """Drop and recreate all database tables. DESTRUCTIVE - use with caution!"""
    admin_key = os.getenv("ADMIN_API_KEY") or os.getenv("COHERENCE_API_KEY")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")

    store = app.state.graph_store
    if not isinstance(store, PostgresGraphStore):
        raise HTTPException(status_code=400, detail="Only PostgreSQL databases can be reset")

    # Drop all tables
    with store.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS contributions CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS assets CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS contributors CASCADE;"))
        conn.commit()

    # Recreate with new schema
    Base.metadata.create_all(bind=store.engine)

    return {
        "status": "success",
        "message": "Database tables dropped and recreated with new schema",
        "changes": [
            "contributors: added type, wallet_address, hourly_rate",
            "assets: changed from name/asset_type to description/type",
            "contributions: unchanged"
        ]
    }

# ---------------------------------------------------------------------------
# API Versioning Strategy
# ---------------------------------------------------------------------------
# Current state:
#   - All canonical routes are mounted at the /api/ prefix.
#   - Legacy /v1/ aliases exist for contributors, assets, contributions, and
#     distributions (see "Backward compatibility" block below). These aliases
#     are hidden from the OpenAPI schema (include_in_schema=False).
#
# Future versioning:
#   - Breaking changes will be introduced under a /v2/ prefix. The /v1/ and
#     /api/ routes will remain unchanged until the deprecation window closes.
#
# Deprecation policy:
#   - Old API versions are supported for a minimum of 6 months after the
#     successor version reaches general availability.
#   - Deprecation will be communicated via Deprecation / Sunset response
#     headers on affected endpoints before removal.
# ---------------------------------------------------------------------------

# Resource routers (canonical)
app.include_router(contributors.router, prefix="/api", tags=["contributors"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(contributions.router, prefix="/api", tags=["contributions"])
app.include_router(distributions.router, prefix="/api", tags=["distributions"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(automation_usage.router, prefix="/api", tags=["automation-usage"])
app.include_router(ideas.router, prefix="/api", tags=["ideas"])
app.include_router(spec_registry.router, prefix="/api", tags=["spec-registry"])
app.include_router(coherence.router, prefix="/api", tags=["coherence"])
app.include_router(governance.router, prefix="/api", tags=["governance"])
app.include_router(federation.router, prefix="/api", tags=["federation"])
app.include_router(friction.router, prefix="/api", tags=["friction"])
app.include_router(gates.router, prefix="/api", tags=["gates"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(value_lineage.router, prefix="/api", tags=["value-lineage"])
app.include_router(runtime.router, prefix="/api", tags=["runtime"])
app.include_router(inventory.router, prefix="/api", tags=["inventory"])
app.include_router(auth_keys.router, prefix="/api", tags=["auth"])
app.include_router(news.router, prefix="/api", tags=["news"])
app.include_router(traceability.router, prefix="/api", tags=["traceability"])
app.include_router(providers.router, prefix="/api", tags=["agent"])
app.include_router(agent_grounded_metrics_routes.router, prefix="/api", tags=["ideas"])
app.include_router(treasury.router, prefix="/api", tags=["treasury"])
app.include_router(contributor_identity.router, tags=["identity"])
app.include_router(provider_stats.router)
app.include_router(service_registry_router.router, prefix="/api", tags=["services"])
app.include_router(concepts.router, prefix="/api", tags=["concepts"])
app.include_router(graph.router, prefix="/api", tags=["graph"])

# Backward compatibility for legacy clients; hidden from OpenAPI.
# These /v1/ aliases map to the same routers as /api/ and will be maintained
# for at least 6 months after any future /v2/ release (see versioning strategy above).
app.include_router(contributors.router, prefix="/v1", include_in_schema=False)
app.include_router(assets.router, prefix="/v1", include_in_schema=False)
app.include_router(contributions.router, prefix="/v1", include_in_schema=False)
app.include_router(distributions.router, prefix="/v1", include_in_schema=False)


@app.middleware("http")
async def capture_runtime_metrics(request: Request, call_next):
    if os.getenv("RUNTIME_TELEMETRY_ENABLED", "1").strip() in {"0", "false", "False"}:
        return await call_next(request)

    start = time.perf_counter()
    status_code: int | None = None
    exc_name: str | None = None
    exc_message: str | None = None
    method = request.method
    request_path, route_name, raw_path = _build_route_signature(request)
    query_count, raw_query_rows, heavy_query_rows = _query_summary(request.query_params)
    route_label = route_name or "unknown"
    response = None
    excluded_paths = {"/api/runtime/change-token"}
    should_capture = request_path.startswith("/api") or request_path.startswith("/v1") or raw_path.startswith("/api") or raw_path.startswith("/v1")
    if request_path in excluded_paths or raw_path in excluded_paths:
        should_capture = False
    slow_threshold_ms = _slow_request_ms_threshold()
    log_all_requests = _env_flag("API_LOG_ALL_REQUESTS", False)
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        status_code = 500
        exc_name = exc.__class__.__name__
        exc_message = str(exc)
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if status_code is None:
            status_code = 500
        if response is not None:
            response.headers["x-coherence-runtime-ms"] = f"{max(0.0, elapsed_ms):.3f}"
            response.headers["x-coherence-runtime-cost-estimate"] = (
                f"{runtime_service.estimate_runtime_cost(max(0.0, elapsed_ms)):.8f}"
            )
            existing_exposed = str(response.headers.get("access-control-expose-headers") or "")
            required_exposed = {
                "x-request-id",
                "x-coherence-runtime-ms",
                "x-coherence-runtime-cost-estimate",
            }
            if existing_exposed:
                current = {part.strip().lower() for part in existing_exposed.split(",") if part.strip()}
            else:
                current = set()
            merged = sorted(current | required_exposed)
            response.headers["access-control-expose-headers"] = ", ".join(merged)
        if should_capture:
            if request.headers.get("content-length"):
                body_size = _safe_int_or_none(request.headers.get("content-length")) or 0
            else:
                body_size = 0
            reasons = _slow_route_reasons(
                path=request_path,
                status_code=status_code,
                reasons=[],
                method=method,
                query_summary=heavy_query_rows,
            )
            try:
                metadata = {
                    "method": method,
                    "route": route_label,
                    "query_count": query_count,
                    "query_samples": ",".join(
                        f"{row.get('k')}={row.get('v')}" for row in raw_query_rows[:6]
                    ),
                    "heavy_query_keys": ",".join(sorted(heavy_query_rows.keys())),
                    "body_bytes": body_size,
                    "client": _client_identity(request),
                    "req_id": _correlation_id(request),
                    "slow_reasons": ", ".join(reasons),
                    "exception": exc_name or "",
                    "page_view_id": str(request.headers.get("x-page-view-id") or "").strip(),
                    "page_route": str(request.headers.get("x-page-route") or "").strip(),
                }
                runtime_service.record_event(
                    RuntimeEventCreate(
                        source="api",
                        endpoint=request_path,
                        raw_endpoint=raw_path,
                        method=method,
                        status_code=status_code,
                        runtime_ms=max(0.1, elapsed_ms),
                        idea_id=request.headers.get("x-idea-id"),
                        metadata=metadata,
                    )
                )
            except Exception:
                # Telemetry should not affect request success.
                logger.debug("Telemetry recording failed", exc_info=True)

            if elapsed_ms >= slow_threshold_ms or log_all_requests or status_code >= 500:
                    reason_text = ", ".join(reasons) if reasons else "unspecified"
                    logger.warning(
                        "slow_api_request method=%s path=%s route=%s raw_path=%s status=%s elapsed_ms=%.2f "
                    "query_count=%s query_samples=%s heavy_queries=%s body_bytes=%s reasons=%s correlation=%s client=%s exception=%s",
                    method,
                    request_path,
                    route_label,
                    raw_path,
                    status_code,
                    elapsed_ms,
                    query_count,
                    raw_query_rows,
                    heavy_query_rows,
                    body_size,
                    reason_text,
                        _correlation_id(request),
                        _client_identity(request),
                        f"{exc_name or 'none'}{':' + exc_message if exc_message else ''}",
                    )
