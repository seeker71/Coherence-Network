"""Tests for import stack API — spec 022."""

import json

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


def _lockfile_v3():
    """Minimal package-lock.json v3 structure."""
    return {
        "name": "test",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "packages": {
            "": {
                "name": "test",
                "version": "1.0.0",
                "dependencies": {"react": "^18.0.0"},
            },
            "node_modules/react": {
                "version": "18.2.0",
                "dependencies": {"loose-envify": "1.4.0"},
            },
            "node_modules/loose-envify": {"version": "1.4.0"},
        },
    }


@pytest.mark.asyncio
async def test_import_stack_returns_200_with_packages_and_risk(client, graph_store):
    """POST /api/import/stack with valid package-lock.json returns 200 — spec 022."""
    graph_store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.2.0",
            description="React",
            dependency_count=2,
        )
    )
    lockfile = _lockfile_v3()
    content = json.dumps(lockfile).encode("utf-8")
    response = await client.post(
        "/api/import/stack",
        files={"file": ("package-lock.json", content, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "packages" in data
    assert "risk_summary" in data
    assert len(data["packages"]) >= 2
    pkg_names = {p["name"] for p in data["packages"]}
    assert "react" in pkg_names
    risk = data["risk_summary"]
    assert "unknown" in risk
    assert "high_risk" in risk
    assert "medium_risk" in risk
    assert "low_risk" in risk


@pytest.mark.asyncio
async def test_import_stack_known_package_has_coherence(client, graph_store):
    """Known package in GraphStore gets coherence score."""
    graph_store.upsert_project(
        Project(
            name="react",
            ecosystem="npm",
            version="18.2.0",
            description="React",
            dependency_count=2,
        )
    )
    lockfile = {"lockfileVersion": 3, "packages": {"node_modules/react": {"version": "18.2.0"}}}
    content = json.dumps(lockfile).encode("utf-8")
    response = await client.post(
        "/api/import/stack",
        files={"file": ("package-lock.json", content, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    react_pkg = next((p for p in data["packages"] if p["name"] == "react"), None)
    assert react_pkg is not None
    assert react_pkg["status"] == "known"
    assert react_pkg["coherence"] is not None
    assert 0.0 <= react_pkg["coherence"] <= 1.0


@pytest.mark.asyncio
async def test_import_stack_unknown_package_has_unknown_status(client):
    """Unknown package gets status unknown."""
    lockfile = {"lockfileVersion": 3, "packages": {"node_modules/unknown-pkg": {"version": "1.0.0"}}}
    content = json.dumps(lockfile).encode("utf-8")
    response = await client.post(
        "/api/import/stack",
        files={"file": ("package-lock.json", content, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    pkg = next((p for p in data["packages"] if p["name"] == "unknown-pkg"), None)
    assert pkg is not None
    assert pkg["status"] == "unknown"
    assert pkg["coherence"] is None
    assert data["risk_summary"]["unknown"] >= 1


@pytest.mark.asyncio
async def test_import_stack_invalid_json_returns_400(client):
    """POST with invalid JSON returns 400."""
    response = await client.post(
        "/api/import/stack",
        files={"file": ("package-lock.json", b"not json", "application/json")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_import_stack_no_file_returns_400(client):
    """POST without file returns 400."""
    response = await client.post("/api/import/stack")
    assert response.status_code == 400  # Our handler raises 400 when no file


@pytest.mark.asyncio
async def test_import_stack_requirements_txt_returns_200(client, graph_store):
    """POST with requirements.txt returns 200 — spec 025."""
    graph_store.upsert_project(
        Project(
            name="requests",
            ecosystem="pypi",
            version="2.28.0",
            description="HTTP library",
            dependency_count=2,
        )
    )
    content = b"requests==2.28.0\ndjango>=4.0\nflask\n"
    response = await client.post(
        "/api/import/stack",
        files={"file": ("requirements.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "packages" in data
    assert "risk_summary" in data
    assert len(data["packages"]) >= 2
    pkg_names = {p["name"] for p in data["packages"]}
    assert "requests" in pkg_names
    requests_pkg = next((p for p in data["packages"] if p["name"] == "requests"), None)
    assert requests_pkg is not None
    assert requests_pkg["status"] == "known"
    assert requests_pkg["coherence"] is not None


@pytest.mark.asyncio
async def test_import_stack_requirements_unknown_package(client):
    """requirements.txt with unknown package gets status unknown — spec 025."""
    content = b"unknown-pypi-pkg==1.0.0\n"
    response = await client.post(
        "/api/import/stack",
        files={"file": ("requirements.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    pkg = next((p for p in data["packages"] if "unknown" in p["name"].lower()), None)
    assert pkg is not None
    assert pkg["status"] == "unknown"
