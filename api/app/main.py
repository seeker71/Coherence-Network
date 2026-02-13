from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from app.adapters.graph_store import InMemoryGraphStore
from app.routers import assets, contributions, contributors, distributions

app = FastAPI(title="Coherence Contribution Network API", version="1.0.0")

# Default in-memory store (tests can override app.state.graph_store per test)
app.state.graph_store = InMemoryGraphStore()

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

# Resource routers
app.include_router(contributors.router, prefix="/v1", tags=["contributors"])
app.include_router(assets.router, prefix="/v1", tags=["assets"])
app.include_router(contributions.router, prefix="/v1", tags=["contributions"])
app.include_router(distributions.router, prefix="/v1", tags=["distributions"])
