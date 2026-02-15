from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_runtime_event_ingest_and_summary(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "web",
                "endpoint": "/gates",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 84.2,
            },
        )
        assert created.status_code == 201
        row = created.json()
        assert row["source"] == "web"
        assert row["idea_id"] == "oss-interface-alignment"
        assert row["runtime_cost_estimate"] > 0

        summary = await client.get("/api/runtime/ideas/summary", params={"seconds": 3600})
        assert summary.status_code == 200
        data = summary.json()
        assert data["window_seconds"] == 3600
        assert isinstance(data["ideas"], list)
        assert any(item["idea_id"] == "oss-interface-alignment" for item in data["ideas"])


@pytest.mark.asyncio
async def test_runtime_middleware_records_api_calls(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas")
        assert resp.status_code == 200

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        assert any(row["source"] == "api" and row["endpoint"] == "/api/ideas" for row in rows)


@pytest.mark.asyncio
async def test_runtime_default_mapping_avoids_unmapped_for_known_surfaces(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for endpoint in ("/api/health-proxy", "/api/unknown-route", "/v1/contributors", "/some-web-route"):
            created = await client.post(
                "/api/runtime/events",
                json={
                    "source": "web",
                    "endpoint": endpoint,
                    "method": "GET",
                    "status_code": 200,
                    "runtime_ms": 11.0,
                },
            )
            assert created.status_code == 201
            assert created.json()["idea_id"] != "unmapped"
