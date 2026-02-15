from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.adapters.graph_store import InMemoryGraphStore
from app.adapters.postgres_store import PostgresGraphStore, Base
from app.routers import (
    assets,
    contributions,
    contributors,
    distributions,
    friction,
    gates,
    health,
    ideas,
    inventory,
    runtime,
    value_lineage,
)
from app.models.runtime import RuntimeEventCreate
from app.services import runtime_service

app = FastAPI(title="Coherence Contribution Network API", version="1.0.0")

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

# Resource routers
app.include_router(contributors.router, prefix="/v1", tags=["contributors"])
app.include_router(assets.router, prefix="/v1", tags=["assets"])
app.include_router(contributions.router, prefix="/v1", tags=["contributions"])
app.include_router(distributions.router, prefix="/v1", tags=["distributions"])
app.include_router(ideas.router, prefix="/api", tags=["ideas"])
app.include_router(friction.router, prefix="/api", tags=["friction"])
app.include_router(gates.router, prefix="/api", tags=["gates"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(value_lineage.router, prefix="/api", tags=["value-lineage"])
app.include_router(runtime.router, prefix="/api", tags=["runtime"])
app.include_router(inventory.router, prefix="/api", tags=["inventory"])


@app.middleware("http")
async def capture_runtime_metrics(request, call_next):
    if os.getenv("RUNTIME_TELEMETRY_ENABLED", "1").strip() in {"0", "false", "False"}:
        return await call_next(request)

    import time

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    path = request.url.path
    if path.startswith("/api") or path.startswith("/v1"):
        try:
            runtime_service.record_event(
                RuntimeEventCreate(
                    source="api",
                    endpoint=path,
                    method=request.method,
                    status_code=response.status_code,
                    runtime_ms=max(0.1, elapsed_ms),
                    idea_id=request.headers.get("x-idea-id"),
                    metadata={},
                )
            )
        except Exception:
            # Telemetry should not affect request success.
            pass
    return response
