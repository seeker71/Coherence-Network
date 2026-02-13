from __future__ import annotations

from fastapi import FastAPI

from app.adapters.graph_store import InMemoryGraphStore
from app.routers import assets, contributions, contributors, distributions

app = FastAPI(title="Coherence Contribution Network API", version="1.0.0")

# Default in-memory store (tests can override app.state.graph_store per test)
app.state.graph_store = InMemoryGraphStore()

app.include_router(contributors.router, prefix="/v1", tags=["contributors"])
app.include_router(assets.router, prefix="/v1", tags=["assets"])
app.include_router(contributions.router, prefix="/v1", tags=["contributions"])
app.include_router(distributions.router, prefix="/v1", tags=["distributions"])
