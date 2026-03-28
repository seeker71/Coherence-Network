from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import pipeline


@pytest.mark.asyncio
async def test_pipeline_status_200(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(pipeline.router, prefix="/api")
    monkeypatch.setattr(
        "app.services.pipeline_service.get_status",
        lambda: {
            "running": True,
            "uptime_seconds": 42,
            "current_idea_id": "idea-1",
            "cycle_count": 7,
            "ideas_advanced": 3,
            "tasks_completed": 5,
            "tasks_failed": 1,
            "last_cycle_at": "2026-03-21T14:30:00Z",
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/status")

    assert response.status_code == 200
    assert response.json()["running"] is True


@pytest.mark.asyncio
async def test_pipeline_status_503_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(pipeline.router, prefix="/api")
    monkeypatch.setattr(
        "app.services.pipeline_service.get_status",
        lambda: {
            "running": False,
            "uptime_seconds": 0,
            "current_idea_id": None,
            "cycle_count": 0,
            "ideas_advanced": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_cycle_at": None,
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/status")

    assert response.status_code == 503
    assert response.json()["running"] is False


@pytest.mark.asyncio
async def test_pipeline_summary_always_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Summary endpoint returns 200 even when the runner is not running."""
    app = FastAPI()
    app.include_router(pipeline.router, prefix="/api")
    monkeypatch.setattr(
        "app.services.pipeline_service.get_status",
        lambda: {
            "running": False,
            "uptime_seconds": 0,
            "current_idea_id": None,
            "cycle_count": 0,
            "ideas_advanced": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_cycle_at": None,
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/summary")

    assert response.status_code == 200
    assert response.json()["running"] is False


@pytest.mark.asyncio
async def test_pipeline_summary_200_when_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """Summary endpoint returns 200 with full status when runner is active."""
    app = FastAPI()
    app.include_router(pipeline.router, prefix="/api")
    monkeypatch.setattr(
        "app.services.pipeline_service.get_status",
        lambda: {
            "running": True,
            "uptime_seconds": 120,
            "current_idea_id": "idea-42",
            "cycle_count": 15,
            "ideas_advanced": 8,
            "tasks_completed": 12,
            "tasks_failed": 2,
            "last_cycle_at": "2026-03-28T06:00:00Z",
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["running"] is True
    assert data["tasks_completed"] == 12
    assert data["current_idea_id"] == "idea-42"
