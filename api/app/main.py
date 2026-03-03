from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Header
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
_reqlog = logging.getLogger("coherence.api.request")

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


@app.middleware("http")
async def capture_runtime_metrics(request, call_next):
    if os.getenv("RUNTIME_TELEMETRY_ENABLED", "1").strip() in {"0", "false", "False"}:
        return await call_next(request)

    import time
    import asyncio
    from uuid import uuid4

    log_enabled = os.getenv("REQUEST_LOG_ENABLED", "1").strip() not in {"0", "false", "False"}
    async_telemetry = os.getenv("RUNTIME_TELEMETRY_ASYNC", "1").strip() not in {"0", "false", "False"}

    rid = request.headers.get("x-request-id") or request.headers.get("x-railway-request-id") or ""
    rid = str(rid).strip() if rid else ""
    if not rid:
        rid = f"req_{uuid4().hex[:12]}"
    request.state.request_id = rid

    start = time.perf_counter()
    response = await call_next(request)
    handler_ms = (time.perf_counter() - start) * 1000.0

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    path = route_path if isinstance(route_path, str) and route_path.strip() else request.url.path
    if path.startswith("/api") or path.startswith("/v1"):
        # Safe metadata only: no query values or request bodies.
        query_keys = list(request.query_params.keys())
        ua = str(request.headers.get("user-agent") or "").strip()
        if len(ua) > 180:
            ua = ua[:180]
        content_length = request.headers.get("content-length")
        cl_val: int | None = None
        if content_length:
            try:
                cl_val = int(content_length)
            except Exception:
                cl_val = None

        slow_threshold = runtime_service.slow_threshold_ms()
        slow = float(handler_ms) >= float(slow_threshold)

        telemetry_ms = 0.0
        try:
            t0 = time.perf_counter()
            payload = RuntimeEventCreate(
                source="api",
                endpoint=path,
                raw_endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                runtime_ms=max(0.1, handler_ms),
                idea_id=request.headers.get("x-idea-id"),
                metadata={
                    "request_id": rid,
                    "query_keys": ",".join([k for k in query_keys if k])[:300],
                    "user_agent": ua,
                    "content_length": int(cl_val) if isinstance(cl_val, int) else 0,
                    "slow": bool(slow),
                    "slow_threshold_ms": int(slow_threshold),
                    "telemetry_ms": 0.0,
                    "telemetry_async": bool(async_telemetry),
                },
            )
            if async_telemetry:
                # Never block the request on DB writes or other sync telemetry work.
                task = asyncio.create_task(asyncio.to_thread(runtime_service.record_event, payload))
                task.add_done_callback(lambda t: t.exception())  # swallow exceptions
                telemetry_ms = 0.0
            else:
                runtime_service.record_event(payload)
                telemetry_ms = (time.perf_counter() - t0) * 1000.0
        except Exception:
            # Telemetry should not affect request success.
            telemetry_ms = 0.0

        # Emit request logs into container logs so Railway can be used as an "APM-lite".
        if log_enabled:
            total_ms = float(handler_ms) + float(telemetry_ms)
            _reqlog.info(
                "api_request method=%s path=%s status=%s handler_ms=%.1f telemetry_ms=%.1f total_ms=%.1f request_id=%s",
                request.method,
                path,
                response.status_code,
                handler_ms,
                telemetry_ms,
                total_ms,
                rid,
            )
            if slow:
                _reqlog.warning(
                    "api_slow_request method=%s path=%s status=%s handler_ms=%.1f request_id=%s query_keys=%s route=%s",
                    request.method,
                    path,
                    response.status_code,
                    handler_ms,
                    rid,
                    ",".join([k for k in query_keys if k])[:300],
                    route_path or "",
                )

    # Propagate request id for client-side correlation.
    try:
        response.headers.setdefault("x-request-id", rid)
    except Exception:
        pass
    return response
