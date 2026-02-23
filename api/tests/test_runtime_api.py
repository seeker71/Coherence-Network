from __future__ import annotations

import json
from datetime import datetime, timezone
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
async def test_runtime_change_token_only_advances_when_data_changes(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("AGENT_TASKS_PATH", str(tmp_path / "agent_tasks.json"))
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'telemetry.db'}")
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/api/runtime/change-token")
        assert first.status_code == 200
        first_token = first.json()["token"]

        second = await client.get("/api/runtime/change-token")
        assert second.status_code == 200
        assert second.json()["token"] == first_token
        assert runtime_service.list_events(limit=20) == []

        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/ideas",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 15.0,
            },
        )
        assert created.status_code == 201

        third = await client.get("/api/runtime/change-token", params={"force_refresh": True})
        assert third.status_code == 200
        assert third.json()["token"] != first_token


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
async def test_runtime_middleware_exposes_runtime_headers_and_page_view_metadata(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/ideas",
            headers={
                "x-page-view-id": "view_abc",
                "x-page-route": "/ideas",
            },
        )
        assert response.status_code == 200
        assert float(response.headers["x-coherence-runtime-ms"]) > 0.0
        assert float(response.headers["x-coherence-runtime-cost-estimate"]) > 0.0
        exposed = response.headers.get("access-control-expose-headers", "")
        assert "x-coherence-runtime-ms" in exposed.lower()
        assert "x-coherence-runtime-cost-estimate" in exposed.lower()

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        ideas_event = next(row for row in rows if row["source"] == "api" and row["endpoint"] == "/api/ideas")
        assert ideas_event["metadata"]["page_view_id"] == "view_abc"
        assert ideas_event["metadata"]["page_route"] == "/ideas"


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
async def test_runtime_endpoint_summary_includes_paid_usage_fields(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        paid = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 150.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {"tracking_kind": "agent_tool_call", "is_paid_provider": True, "runtime_cost_usd": 0.0123},
            },
        )
        assert paid.status_code == 201

        free = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 500,
                "runtime_ms": 90.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {"tracking_kind": "agent_tool_call", "is_paid_provider": False, "runtime_cost_usd": 0.0031},
            },
        )
        assert free.status_code == 201

        summary = await client.get("/api/runtime/endpoints/summary", params={"seconds": 3600})
        assert summary.status_code == 200
        rows = summary.json()["endpoints"]
        row = next(entry for entry in rows if entry["endpoint"] == "/tool:openrouter.chat_completion")
        assert row["paid_tool_event_count"] == 1
        assert row["paid_tool_failure_count"] == 0
        assert row["paid_tool_ratio"] == 0.5
        assert row["paid_tool_runtime_cost"] == 0.0123
        assert row["paid_tool_average_runtime_ms"] == 150.0
        assert "paid_tool_average_runtime_ms" in row


@pytest.mark.asyncio
async def test_runtime_web_view_summary_reports_render_and_api_cost(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/ideas",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 40.0,
                "metadata": {"page_view_id": "view_1"},
            },
        )
        assert created.status_code == 201

        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "web",
                "endpoint": "/ideas",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 320.0,
                "metadata": {
                    "tracking_kind": "web_view_complete",
                    "page_view_id": "view_1",
                    "api_call_count": 1,
                    "api_endpoint_count": 1,
                },
            },
        )
        assert created.status_code == 201

        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "web",
                "endpoint": "/ideas",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 180.0,
                "metadata": {
                    "tracking_kind": "web_view_complete",
                    "page_view_id": "view_2",
                    "api_call_count": 0,
                    "api_endpoint_count": 0,
                },
            },
        )
        assert created.status_code == 201

        summary = await client.get("/api/runtime/web/views/summary", params={"seconds": 3600, "limit": 20})
        assert summary.status_code == 200
        payload = summary.json()
        row = next(item for item in payload["rows"] if item["route"] == "/ideas")
        assert row["views"] == 2
        assert row["p50_render_ms"] > 0.0
        assert row["average_api_runtime_ms"] >= 20.0
        assert row["average_api_runtime_cost_estimate"] > 0.0


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


@pytest.mark.asyncio
async def test_runtime_endpoint_attention_reports_paid_ratio_and_friction(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
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
                "metadata": {"is_paid_provider": False},
                "idea_id": "oss-interface-alignment",
            },
        )
        assert created.status_code == 201

        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/ideas",
                "method": "GET",
                "status_code": 500,
                "runtime_ms": 45.0,
                "metadata": {"is_paid_provider": True},
                "idea_id": "oss-interface-alignment",
            },
        )
        assert created.status_code == 201

        friction_event = await client.post(
            "/api/friction/events",
            json={
                "id": "friction-test-1",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "stage": "runtime",
                "block_type": "runtime_failure",
                "severity": "high",
                "owner": "test",
                "unblock_condition": "reduce failure rate",
                "energy_loss_estimate": 2.25,
                "cost_of_delay": 0.0,
                "status": "open",
                "endpoint": "/api/ideas",
                "notes": "endpoint-specific friction test",
            },
        )
        assert friction_event.status_code == 201

        attention = await client.get(
            "/api/runtime/endpoints/attention",
            params={
                "seconds": 3600,
                "min_event_count": 1,
                "attention_threshold": 0.0,
                "limit": 20,
            },
        )
        assert attention.status_code == 200
        row = next(item for item in attention.json()["endpoints"] if item["endpoint"] == "/api/ideas")
        assert row["event_count"] == 2
        assert row["success_count"] == 1
        assert row["failure_count"] == 1
        assert row["success_rate"] == 0.5
        assert row["paid_tool_event_count"] == 1
        assert row["paid_tool_ratio"] == 0.5
        assert row["friction_event_count"] == 1
        assert row["friction_event_density"] == 0.5
        assert row["needs_attention"] is True


@pytest.mark.asyncio
async def test_runtime_endpoint_attention_clamps_friction_density_to_one(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/specs",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 20.0,
                "metadata": {"is_paid_provider": False},
                "idea_id": "portfolio-governance",
            },
        )
        assert created.status_code == 201

        for idx in range(3):
            friction_event = await client.post(
                "/api/friction/events",
                json={
                    "id": f"friction-density-{idx}",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "stage": "runtime",
                    "block_type": "runtime_failure",
                    "severity": "high",
                    "owner": "test",
                    "unblock_condition": "reduce failure rate",
                    "energy_loss_estimate": 1.0,
                    "cost_of_delay": 0.0,
                    "status": "open",
                    "endpoint": "/api/specs",
                },
            )
            assert friction_event.status_code == 201

        attention = await client.get(
            "/api/runtime/endpoints/attention",
            params={"seconds": 3600, "min_event_count": 1, "attention_threshold": 0.0, "limit": 20},
        )
        assert attention.status_code == 200
        row = next(item for item in attention.json()["endpoints"] if item["endpoint"] == "/api/specs")
        assert row["friction_event_count"] == 3
        assert row["friction_event_density"] == 1.0


@pytest.mark.asyncio
async def test_runtime_endpoint_attention_includes_idea_value_gap(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/spec-registry/abc",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 8.0,
                "metadata": {"is_paid_provider": False},
                "idea_id": "portfolio-governance",
            },
        )
        assert created.status_code == 201

        created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/spec-registry/abc",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 9.0,
                "metadata": {"is_paid_provider": False},
                "idea_id": "portfolio-governance",
            },
        )
        assert created.status_code == 201

        payload = await client.get(
            "/api/runtime/endpoints/attention",
            params={"seconds": 3600, "min_event_count": 1, "attention_threshold": 0.0},
        )
        assert payload.status_code == 200
        row = next(item for item in payload.json()["endpoints"] if item["endpoint"] == "/api/spec-registry/{spec_id}")
        assert row["idea_id"] == "portfolio-governance"
        assert row["value_gap"] >= 0.0
        assert row["potential_value"] == 82.0
