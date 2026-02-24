from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.adapters.graph_store import InMemoryGraphStore
from app.adapters.postgres_store import PostgresGraphStore, Base
from app.routers import (
    agent,
    automation_usage,
    assets,
    contributions,
    contributors,
    distributions,
    friction,
    gates,
    governance,
    health,
    ideas,
    inventory,
    spec_registry,
    runtime,
    value_lineage,
)
from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service

app = FastAPI(title="Coherence Contribution Network API", version="1.0.0")
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
    raw = os.getenv("API_SLOW_REQUEST_MS", "1500").strip()
    try:
        return max(25.0, float(raw))
    except ValueError:
        return 1500.0


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


def _should_capture_runtime_metrics(request_path: str, raw_path: str) -> bool:
    capture_path = request_path.startswith("/api") or request_path.startswith("/v1")
    capture_raw = raw_path.startswith("/api") or raw_path.startswith("/v1")
    if not (capture_path or capture_raw):
        return False
    if request_path == "/api/runtime/change-token":
        # Live refresh polling must remain lightweight and should not self-generate runtime events.
        return False
    return True


def _content_length_bytes(request: Request) -> int:
    value = request.headers.get("content-length")
    if not value:
        return 0
    return _safe_int_or_none(value) or 0


def _runtime_event_metadata(
    *,
    request: Request,
    method: str,
    route_label: str,
    query_count: int,
    raw_query_rows: list[dict[str, str]],
    heavy_query_rows: dict[str, str],
    body_size: int,
    reasons: list[str],
    exc_name: str | None,
) -> dict[str, str | int]:
    return {
        "method": method,
        "route": route_label,
        "query_count": query_count,
        "query_samples": ",".join(f"{row.get('k')}={row.get('v')}" for row in raw_query_rows[:6]),
        "heavy_query_keys": ",".join(sorted(heavy_query_rows.keys())),
        "body_bytes": body_size,
        "client": _client_identity(request),
        "req_id": _correlation_id(request),
        "page_view_id": (request.headers.get("x-page-view-id") or "").strip(),
        "page_route": (request.headers.get("x-page-route") or "").strip(),
        "slow_reasons": ", ".join(reasons),
        "exception": exc_name or "",
    }


def _append_exposed_headers(existing: str | None, extra: list[str]) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for chunk in ((existing or "").split(","), extra):
        for value in chunk:
            item = str(value).strip()
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return ", ".join(merged)


def _apply_runtime_response_headers(response: Response, request: Request, elapsed_ms: float) -> None:
    runtime_ms = max(0.1, float(elapsed_ms))
    response.headers["x-coherence-runtime-ms"] = f"{runtime_ms:.4f}"
    response.headers["x-coherence-runtime-cost-estimate"] = (
        f"{runtime_service.estimate_runtime_cost(runtime_ms):.8f}"
    )
    correlation_id = _correlation_id(request)
    if correlation_id and correlation_id != "none":
        response.headers["x-coherence-request-id"] = correlation_id
    response.headers["access-control-expose-headers"] = _append_exposed_headers(
        response.headers.get("access-control-expose-headers"),
        [
            "x-coherence-runtime-ms",
            "x-coherence-runtime-cost-estimate",
            "x-coherence-request-id",
        ],
    )


def _record_runtime_event(
    *,
    request: Request,
    method: str,
    request_path: str,
    raw_path: str,
    status_code: int,
    elapsed_ms: float,
    route_label: str,
    query_count: int,
    raw_query_rows: list[dict[str, str]],
    heavy_query_rows: dict[str, str],
    reasons: list[str],
    body_size: int,
    exc_name: str | None,
) -> None:
    metadata = _runtime_event_metadata(
        request=request,
        method=method,
        route_label=route_label,
        query_count=query_count,
        raw_query_rows=raw_query_rows,
        heavy_query_rows=heavy_query_rows,
        body_size=body_size,
        reasons=reasons,
        exc_name=exc_name,
    )
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


def _log_slow_request(
    *,
    request: Request,
    method: str,
    request_path: str,
    route_label: str,
    raw_path: str,
    status_code: int,
    elapsed_ms: float,
    query_count: int,
    raw_query_rows: list[dict[str, str]],
    heavy_query_rows: dict[str, str],
    body_size: int,
    reasons: list[str],
    exc_name: str | None,
    exc_message: str | None,
) -> None:
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

# Configure CORS
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Resource routers (canonical)
app.include_router(contributors.router, prefix="/api", tags=["contributors"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(contributions.router, prefix="/api", tags=["contributions"])
app.include_router(distributions.router, prefix="/api", tags=["distributions"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(automation_usage.router, prefix="/api", tags=["automation-usage"])
app.include_router(ideas.router, prefix="/api", tags=["ideas"])
app.include_router(spec_registry.router, prefix="/api", tags=["spec-registry"])
app.include_router(governance.router, prefix="/api", tags=["governance"])
app.include_router(friction.router, prefix="/api", tags=["friction"])
app.include_router(gates.router, prefix="/api", tags=["gates"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(value_lineage.router, prefix="/api", tags=["value-lineage"])
app.include_router(runtime.router, prefix="/api", tags=["runtime"])
app.include_router(inventory.router, prefix="/api", tags=["inventory"])

# Backward compatibility for legacy clients; hidden from OpenAPI.
app.include_router(contributors.router, prefix="/v1", include_in_schema=False)
app.include_router(assets.router, prefix="/v1", include_in_schema=False)
app.include_router(contributions.router, prefix="/v1", include_in_schema=False)
app.include_router(distributions.router, prefix="/v1", include_in_schema=False)


@app.on_event("startup")
async def _prime_hot_caches() -> None:
    try:
        # Prevent first-user-request spikes from service bootstrap + first-load cache hydration.
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
        if store is not None:
            contributor_payload_rows = [item.model_dump(mode="json") for item in store.list_contributors(limit=300)]
            contribution_payload_rows = [item.model_dump(mode="json") for item in store.list_contributions(limit=600)]
            asset_payload_rows = [item.model_dump(mode="json") for item in store.list_assets(limit=300)]
            contributor_rows = len(contributor_payload_rows)
            contribution_rows = len(contribution_payload_rows)
            asset_rows = len(asset_payload_rows)
        try:
            # Warm the expensive flow cache used by web to avoid first-user cold path.
            flow_payload = inventory_service.build_spec_process_implementation_validation_flow(
                runtime_window_seconds=86400,
                contributor_rows=contributor_payload_rows,
                contribution_rows=contribution_payload_rows,
                asset_rows=asset_payload_rows,
                spec_registry_limit=160,
                lineage_link_limit=180,
                usage_event_limit=350,
                commit_evidence_limit=200,
                runtime_event_limit=600,
                list_item_limit=12,
            )
            if not isinstance(flow_payload, dict):
                flow_payload = {}
            flow_items = len(flow_payload.get("items", []))
        except Exception:
            logger.debug("api_startup_flow_cache_failed", exc_info=True)
            flow_items = 0
        startup_ms = (time.perf_counter() - startup_begin) * 1000.0
        logger.info(
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
    except Exception:
        logger.warning("api_startup_cache_warm_failed", exc_info=True)


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
    should_capture = _should_capture_runtime_metrics(request_path, raw_path)
    slow_threshold_ms = _slow_request_ms_threshold()
    log_all_requests = _env_flag("API_LOG_ALL_REQUESTS", False)
    response = None
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
        if should_capture:
            body_size = _content_length_bytes(request)
            reasons = _slow_route_reasons(
                path=request_path,
                status_code=status_code,
                reasons=[],
                method=method,
                query_summary=heavy_query_rows,
            )
            try:
                _record_runtime_event(
                    request=request,
                    method=method,
                    request_path=request_path,
                    raw_path=raw_path,
                    status_code=status_code,
                    elapsed_ms=elapsed_ms,
                    route_label=route_label,
                    query_count=query_count,
                    raw_query_rows=raw_query_rows,
                    heavy_query_rows=heavy_query_rows,
                    reasons=reasons,
                    body_size=body_size,
                    exc_name=exc_name,
                )
            except Exception:
                # Telemetry should not affect request success.
                pass

            if response is not None:
                _apply_runtime_response_headers(response, request, elapsed_ms)

            if elapsed_ms >= slow_threshold_ms or log_all_requests or status_code >= 500:
                _log_slow_request(
                    request=request,
                    method=method,
                    request_path=request_path,
                    route_label=route_label,
                    raw_path=raw_path,
                    status_code=status_code,
                    elapsed_ms=elapsed_ms,
                    query_count=query_count,
                    raw_query_rows=raw_query_rows,
                    heavy_query_rows=heavy_query_rows,
                    body_size=body_size,
                    reasons=reasons,
                    exc_name=exc_name,
                    exc_message=exc_message,
                )
