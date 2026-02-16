from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app
from app.models.project import Project


@pytest.mark.asyncio
async def test_search_and_project_endpoints_work_with_inmemory_store() -> None:
    store = InMemoryGraphStore()
    store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.0.0",
            description="A JavaScript library for building user interfaces",
            dependency_count=0,
        )
    )
    store.upsert_project(
        Project(
            name="fastapi",
            ecosystem="pypi",
            version="0.110.0",
            description="FastAPI framework, high performance, easy to learn",
            dependency_count=0,
        )
    )
    store.add_dependency("npm", "react", "npm", "loose-envify")
    app.state.graph_store = store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search", params={"q": "react"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body.get("results"), list)
        assert body.get("total") == len(body["results"])
        assert any(r["name"] == "react" and r["ecosystem"] == "npm" for r in body["results"])

        got = await client.get("/api/projects/npm/react")
        assert got.status_code == 200
        assert got.json()["name"] == "react"
        assert got.json()["dependency_count"] >= 1

        missing = await client.get("/api/projects/npm/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Project not found"


@pytest.mark.asyncio
async def test_project_coherence_endpoint_returns_components() -> None:
    store = InMemoryGraphStore()
    store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.0.0",
            description="",
            dependency_count=0,
        )
    )
    app.state.graph_store = store

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/projects/npm/react/coherence")
        assert resp.status_code == 200
        data = resp.json()
        assert 0.0 <= float(data["score"]) <= 1.0
        assert isinstance(data.get("components"), dict)
        assert len(data["components"]) == 8
        assert "downstream_impact" in data["components"]
        assert "dependency_health" in data["components"]

        missing = await client.get("/api/projects/npm/does-not-exist/coherence")
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Project not found"

