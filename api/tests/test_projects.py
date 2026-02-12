"""Tests for project and search API — spec 008, 019."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app
from app.models.project import Project


@pytest.fixture
def graph_store():
    """Fresh in-memory store per test."""
    return InMemoryGraphStore(persist_path=None)


@pytest.fixture
async def client(graph_store):
    """Client with graph_store injected into app state."""
    app.state.graph_store = graph_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_project_returns_200_when_exists(client: AsyncClient, graph_store):
    """GET /api/projects/npm/react returns 200 when project exists."""
    graph_store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.2.0",
            description="React is a JavaScript library",
            dependency_count=3,
        )
    )
    response = await client.get("/api/projects/npm/react")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "react"
    assert data["ecosystem"] == "npm"
    assert data["version"] == "18.2.0"
    assert "React" in data["description"]


@pytest.mark.asyncio
async def test_get_project_returns_404_when_missing(client: AsyncClient):
    """GET /api/projects/npm/nonexistent returns 404."""
    response = await client.get("/api/projects/npm/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


@pytest.mark.asyncio
async def test_get_project_pypi_returns_200_when_exists(
    client: AsyncClient, graph_store
):
    """GET /api/projects/pypi/requests returns 200 when pypi project exists — spec 024."""
    graph_store.upsert_project(
        Project(
            name="requests",
            ecosystem="pypi",
            version="2.32.0",
            description="Python HTTP library",
            dependency_count=2,
        )
    )
    response = await client.get("/api/projects/pypi/requests")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "requests"
    assert data["ecosystem"] == "pypi"


@pytest.mark.asyncio
async def test_search_returns_matching_results(client: AsyncClient, graph_store):
    """GET /api/search?q=react returns matching results."""
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
            name="react-dom",
            ecosystem="npm",
            version="18.2.0",
            description="React DOM",
            dependency_count=0,
        )
    )
    graph_store.upsert_project(
        Project(
            name="lodash",
            ecosystem="npm",
            version="4.17.0",
            description="Utility library",
            dependency_count=0,
        )
    )
    response = await client.get("/api/search?q=react")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert data["total"] >= 2
    names = [r["name"] for r in data["results"]]
    assert "react" in names
    assert "react-dom" in names


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(client: AsyncClient, graph_store):
    """GET /api/search?q= returns empty results."""
    graph_store.upsert_project(
        Project(name="a", ecosystem="npm", version="1", description="x", dependency_count=0)
    )
    response = await client.get("/api/search?q=")
    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.asyncio
async def test_get_coherence_returns_200_with_score_and_components(
    client: AsyncClient, graph_store
):
    """GET /api/projects/npm/react/coherence returns 200 with score and components — spec 020."""
    graph_store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.2.0",
            description="React library",
            dependency_count=2,
        )
    )
    response = await client.get("/api/projects/npm/react/coherence")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "components" in data
    assert 0.0 <= data["score"] <= 1.0
    for k, v in data["components"].items():
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_get_coherence_returns_404_when_missing(client: AsyncClient):
    """GET /api/projects/npm/nonexistent/coherence returns 404 — spec 020."""
    response = await client.get("/api/projects/npm/nonexistent/coherence")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
