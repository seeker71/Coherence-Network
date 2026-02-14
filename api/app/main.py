from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.adapters.graph_store import InMemoryGraphStore
from app.adapters.postgres_store import PostgresGraphStore, Base
from app.routers import assets, contributions, contributors, distributions

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

@app.get("/api/health")
async def health():
    """Liveness check - is process up?"""
    return {
        "status": "ok",
        "service": "coherence-contribution-network",
        "version": app.version,
    }

@app.get("/api/ready")
async def ready():
    """Readiness check - can handle traffic?"""
    ready = getattr(app.state, "graph_store", None) is not None
    if not ready:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready"}

@app.post("/api/admin/reset-database")
async def reset_database(x_admin_key: str = Header(None)):
    """Drop and recreate all database tables. DESTRUCTIVE - use with caution!"""
    # Temporary migration key - will be removed after migration
    admin_key = os.getenv("ADMIN_API_KEY") or os.getenv("COHERENCE_API_KEY") or "migrate-2024-02-14"
    if not x_admin_key or x_admin_key != admin_key:
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
