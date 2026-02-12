"""Holdout tests — excluded from agent context. See README.md.

These verify behavior agents must not game (e.g. returning constant values).
CI runs full suite including holdout. Agent runs use: pytest --ignore=tests/holdout/
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app
from app.models.project import Project


@pytest.fixture
def graph_store():
    return InMemoryGraphStore(persist_path=None)


@pytest.fixture
async def client(graph_store):
    app.state.graph_store = graph_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_project_dependency_count_derived_from_edges(client, graph_store):
    """Holdout: dependency_count must be computed from actual edges, not a constant.

    An implementation that returns dependency_count=0 for all projects would fail here.
    """
    graph_store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.2.0",
            description="React library",
            dependency_count=0,
        )
    )
    graph_store.upsert_project(
        Project(
            name="lodash",
            ecosystem="npm",
            version="4.17.0",
            description="Utility",
            dependency_count=0,
        )
    )
    graph_store.upsert_project(
        Project(
            name="scheduler",
            ecosystem="npm",
            version="0.23.0",
            description="Scheduler",
            dependency_count=0,
        )
    )
    graph_store.add_dependency("npm", "react", "npm", "lodash")
    graph_store.add_dependency("npm", "react", "npm", "scheduler")

    response = await client.get("/api/projects/npm/react")
    assert response.status_code == 200
    data = response.json()
    assert data["dependency_count"] == 2, "dependency_count must reflect actual edges"
