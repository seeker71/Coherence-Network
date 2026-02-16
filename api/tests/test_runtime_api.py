from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_runtime_event_ingest_and_summary(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    (tmp_path / "idea_lineage.json").write_text(
        json.dumps({"origin_map": {"oss-interface-alignment": "portfolio-governance"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_LINEAGE_MAP_PATH", str(tmp_path / "idea_lineage.json"))

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
        assert row["origin_idea_id"] == "portfolio-governance"
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
        for endpoint in ("/api/health-proxy", "/api/unknown-route", "/api/contributors", "/some-web-route"):
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


@pytest.mark.asyncio
async def test_runtime_endpoint_summary_includes_origin_idea_lineage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    (tmp_path / "idea_lineage.json").write_text(
        json.dumps({"origin_map": {"portfolio-governance": "system-root"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_LINEAGE_MAP_PATH", str(tmp_path / "idea_lineage.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/spec-registry/abc-spec",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 17.5,
            },
        )
        assert created.status_code == 201
        event = created.json()
        assert event["endpoint"] == "/api/spec-registry/{spec_id}"
        assert event["idea_id"] == "portfolio-governance"
        assert event["origin_idea_id"] == "system-root"

        summary = await client.get("/api/runtime/endpoints/summary", params={"seconds": 3600})
        assert summary.status_code == 200
        data = summary.json()
        assert data["window_seconds"] == 3600
        row = next(
            entry for entry in data["endpoints"] if entry["endpoint"] == "/api/spec-registry/{spec_id}"
        )
        assert row["idea_id"] == "portfolio-governance"
        assert row["origin_idea_id"] == "system-root"
        assert row["event_count"] >= 1


@pytest.mark.asyncio
async def test_runtime_get_endpoint_exerciser_runs_safe_calls_and_reports_coverage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run = await client.post(
            "/api/runtime/exerciser/run",
            params={"cycles": 1, "max_endpoints": 30, "delay_ms": 0, "timeout_seconds": 8.0},
        )
        assert run.status_code == 200
        payload = run.json()
        assert payload["result"] == "runtime_get_endpoint_exerciser_completed"
        assert payload["summary"]["discovered_get_endpoints"] >= 1
        assert payload["summary"]["total_calls"] >= 1
        assert payload["coverage"]["after_with_usage_events"] >= payload["coverage"]["before_with_usage_events"]
        assert isinstance(payload["calls"], list)
        assert len(payload["calls"]) >= 1
        first = payload["calls"][0]
        assert str(first["path_template"]).startswith("/api/")
        assert int(first["runtime_ms"]) > 0
