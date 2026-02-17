from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import runtime_service


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


@pytest.mark.asyncio
async def test_runtime_events_persist_to_database_when_runtime_database_url_is_set(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RUNTIME_EVENTS_PATH", raising=False)
    monkeypatch.setenv("RUNTIME_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'runtime.db'}")
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/ideas",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 12.0,
            },
        )
        assert created.status_code == 201

        events = await client.get("/api/runtime/events", params={"limit": 50})
        assert events.status_code == 200
        rows = events.json()
        assert any(row["endpoint"] == "/api/ideas" for row in rows)


@pytest.mark.asyncio
async def test_runtime_database_summary_handles_sqlite_naive_timestamps(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RUNTIME_EVENTS_PATH", raising=False)
    monkeypatch.setenv("RUNTIME_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'runtime.db'}")
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/health",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 9.5,
            },
        )
        assert created.status_code == 201

        summary = await client.get("/api/runtime/endpoints/summary", params={"seconds": 3600})
        assert summary.status_code == 200
        endpoints = summary.json().get("endpoints", [])
        assert any(row.get("endpoint") == "/api/health" for row in endpoints)


def test_verify_internal_vs_public_usage_contract_detects_missing_public_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "endpoints": [
                    {"endpoint": "/api/ideas", "event_count": 2},
                    {"endpoint": "/api/runtime/events", "event_count": 0},
                ]
            }

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def get(self, url: str, params: dict[str, Any]) -> _FakeResponse:
            assert url.endswith("/api/runtime/endpoints/summary")
            assert int(params["seconds"]) == 3600
            return _FakeResponse()

    monkeypatch.setattr(
        runtime_service,
        "summarize_by_endpoint",
        lambda seconds: [  # noqa: ARG005
            type("Row", (), {"endpoint": "/api/ideas"})(),
            type("Row", (), {"endpoint": "/api/runtime/events"})(),
        ],
    )
    monkeypatch.setattr(runtime_service.httpx, "Client", _FakeClient)

    report = runtime_service.verify_internal_vs_public_usage(
        public_api_base="https://example.test",
        runtime_window_seconds=3600,
        timeout_seconds=3.0,
    )
    assert report["pass_contract"] is False
    assert report["missing_public_records"] == ["/api/runtime/events"]


@pytest.mark.asyncio
async def test_runtime_usage_verification_endpoint_exposes_contract_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_service,
        "verify_internal_vs_public_usage",
        lambda **kwargs: {  # noqa: ARG005
            "pass_contract": True,
            "internal_endpoint_count": 2,
            "public_endpoint_count": 2,
            "missing_public_records": [],
            "runtime_window_seconds": 3600,
            "public_api_base": "https://example.test",
            "overlap_count": 2,
            "internal_only_endpoints": [],
            "public_only_endpoints": [],
            "error": "",
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/runtime/usage/verification",
            params={"public_api_base": "https://example.test", "runtime_window_seconds": 3600},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["pass_contract"] is True
        assert payload["missing_public_records"] == []
