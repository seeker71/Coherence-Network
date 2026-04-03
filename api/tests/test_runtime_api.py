from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from nacl.signing import SigningKey

from app.main import app
from app.models.runtime import IdeaRuntimeSummary, RuntimeEvent, WebViewPerformanceReport, WebViewPerformanceRow
from app.services import mvp_baseline_service, runtime_service

AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def _write_mvp_acceptance_policy(
    *,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    override: dict[str, Any],
) -> None:
    base = json.loads(json.dumps(runtime_service._DEFAULT_MVP_ACCEPTANCE_POLICY))
    payload = _deep_merge(base, override)
    path = tmp_path / "mvp_acceptance_policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_service, "_mvp_acceptance_policy_path", lambda: path)
    runtime_service.reset_mvp_acceptance_policy_cache()


@pytest.fixture(autouse=True)
def _reset_mvp_policy_cache_per_test():
    runtime_service.reset_mvp_acceptance_policy_cache()
    yield
    runtime_service.reset_mvp_acceptance_policy_cache()


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
async def test_runtime_mvp_local_baselines_endpoint_returns_runs(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    system_audit = tmp_path / "docs" / "system_audit"
    system_audit.mkdir(parents=True, exist_ok=True)
    (system_audit / "mvp_acceptance_2026-03-10_sample.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-03-10T22:15:25Z",
                "run_id": "sample",
                "branch": "codex/sample",
                "origin_main_sha": "abc123",
                "validation_scope": "local_only",
                "result": "pass",
                "checks": {"api": {"health": 200}, "web": {"root": 200}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mvp_baseline_service, "_repo_root", lambda: tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/runtime/mvp/local-baselines", params={"limit": 5})
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        assert payload["runs"][0]["run_id"] == "sample"
        assert payload["runs"][0]["result"] == "pass"


@pytest.mark.asyncio
async def test_runtime_mvp_local_baselines_endpoint_sorts_by_generated_at(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    system_audit = tmp_path / "docs" / "system_audit"
    system_audit.mkdir(parents=True, exist_ok=True)
    (system_audit / "mvp_acceptance_old.json").write_text(
        json.dumps({"generated_at_utc": "2026-03-10T10:00:00Z", "run_id": "old", "checks": {"api": {}, "web": {}}}),
        encoding="utf-8",
    )
    (system_audit / "mvp_acceptance_new.json").write_text(
        json.dumps({"generated_at_utc": "2026-03-10T12:00:00Z", "run_id": "new", "checks": {"api": {}, "web": {}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mvp_baseline_service, "_repo_root", lambda: tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/runtime/mvp/local-baselines", params={"limit": 2})
        assert response.status_code == 200
        payload = response.json()
        assert payload["runs"][0]["run_id"] == "new"
        assert payload["runs"][1]["run_id"] == "old"


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
async def test_runtime_mvp_acceptance_summary_reports_cost_rollups_and_accepted_reviews(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.1,
                "provider_base_budget_usd": 0.2,
            },
            "revenue": {"per_accepted_review_usd": 0.5},
            "reinvestment": {"ratio": 0.4},
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 140.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_pass",
                    "infrastructure_cost_usd": 0.011,
                    "external_provider_cost_usd": 0.029,
                    "total_cost_usd": 0.04,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 5.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_pass",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "4/4",
                },
            },
        )
        assert completion_event.status_code == 201

        impl_tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:codex.exec",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 80.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_impl_done",
                    "infrastructure_cost_usd": 0.008,
                    "external_provider_cost_usd": 0.0,
                    "total_cost_usd": 0.008,
                    "is_paid_provider": False,
                },
            },
        )
        assert impl_tool_event.status_code == 201

        impl_completion = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 3.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_impl_done",
                    "task_type": "impl",
                    "task_final_status": "completed",
                },
            },
        )
        assert impl_completion.status_code == 201

        summary = await client.get("/api/runtime/mvp/acceptance-summary", params={"seconds": 3600, "limit": 2000})
        assert summary.status_code == 200
        payload = summary.json()
        totals = payload["totals"]
        assert totals["tasks_seen"] == 2
        assert totals["completed_tasks"] == 2
        assert totals["review_tasks_completed"] == 1
        assert totals["accepted_reviews"] == 1
        assert totals["acceptance_rate"] == 1.0
        assert totals["infrastructure_cost_usd"] == 0.019
        assert totals["external_provider_cost_usd"] == 0.029
        assert totals["total_cost_usd"] == 0.048
        assert payload["budget"]["base_budget_usd"] == 0.3
        assert payload["revenue"]["estimated_revenue_usd"] == 0.5
        assert payload["reinvestment"]["reinvestment_pool_usd"] == 0.1808
        assert len(payload["tasks"]) == 2
        review_row = next(row for row in payload["tasks"] if row["task_id"] == "task_review_pass")
        assert review_row["task_type"] == "review"
        assert review_row["final_status"] == "completed"
        assert review_row["review_pass_fail"] == "PASS"
        assert review_row["verified_assertions"] == "4/4"
        assert review_row["review_accepted"] is True


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_contract_passes_when_budget_and_revenue_cover_cost(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.05,
                "provider_base_budget_usd": 0.05,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 1.0,
                "require_budget_coverage": True,
                "require_revenue_coverage": True,
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 100.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_pass",
                    "infrastructure_cost_usd": 0.01,
                    "external_provider_cost_usd": 0.02,
                    "total_cost_usd": 0.03,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 2.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_pass",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "3/3",
                },
            },
        )
        assert completion_event.status_code == 201

        judge = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert judge.status_code == 200
        payload = judge.json()
        assert payload["pass"] is True
        assert isinstance(payload["assertions"], list)
        assert payload["assertions"]
        ids = {str(row["id"]) for row in payload["assertions"]}
        assert "accepted_reviews_minimum" in ids
        assert "acceptance_rate_minimum" in ids
        assert "base_budget_covers_total_cost" in ids
        assert "estimated_revenue_covers_total_cost" in ids
        assert payload["contract"]["judge_id"] == "coherence_mvp_acceptance_judge_v1"
        assert payload["contract"]["external_validation_endpoint"] == "/api/runtime/mvp/acceptance-judge"
        summary = payload["summary"]
        assert summary["totals"]["accepted_reviews"] == 1
        assert summary["totals"]["total_cost_usd"] == 0.03
        assert summary["budget"]["base_budget_usd"] == 0.1
        assert summary["revenue"]["estimated_revenue_usd"] == 0.1


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_requires_public_validator_quorum(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    signing_key = SigningKey.generate()
    validator_id = "validator_public_1"
    public_key_b64 = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.05,
                "provider_base_budget_usd": 0.05,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 0.7,
                "require_budget_coverage": True,
                "require_revenue_coverage": True,
            },
            "trust": {
                "public_validator": {
                    "required": True,
                    "quorum": 1,
                    "keys": [
                        {
                            "id": validator_id,
                            "public_key_base64": public_key_b64,
                            "source": "public_validator_demo",
                        }
                    ],
                    "attestations": [],
                }
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 100.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_public",
                    "infrastructure_cost_usd": 0.01,
                    "external_provider_cost_usd": 0.02,
                    "total_cost_usd": 0.03,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 2.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_public",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "2/2",
                },
            },
        )
        assert completion_event.status_code == 201

        # Without attestation signatures, required public validator quorum must fail.
        missing_sig = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert missing_sig.status_code == 200
        missing_payload = missing_sig.json()
        assert missing_payload["pass"] is False
        assert any(item["id"] == "public_validator_quorum" and item["pass"] is False for item in missing_payload["assertions"])

        summary = await client.get("/api/runtime/mvp/acceptance-summary", params={"seconds": 3600, "limit": 2000})
        assert summary.status_code == 200
        summary_payload = summary.json()
        claim_payload = {
            "judge_id": "coherence_mvp_acceptance_judge_v1",
            "window_seconds": int(summary_payload.get("window_seconds") or 0),
            "event_limit": int(summary_payload.get("event_limit") or 0),
            "totals": {
                "accepted_reviews": int(summary_payload.get("totals", {}).get("accepted_reviews") or 0),
                "acceptance_rate": float(summary_payload.get("totals", {}).get("acceptance_rate") or 0.0),
                "total_cost_usd": float(summary_payload.get("totals", {}).get("total_cost_usd") or 0.0),
            },
            "budget": {"base_budget_usd": float(summary_payload.get("budget", {}).get("base_budget_usd") or 0.0)},
            "revenue": {"estimated_revenue_usd": float(summary_payload.get("revenue", {}).get("estimated_revenue_usd") or 0.0)},
        }
        claim_bytes = json.dumps(claim_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        sig_b64 = base64.b64encode(signing_key.sign(claim_bytes).signature).decode("ascii")
        _write_mvp_acceptance_policy(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            override={
                "budget": {
                    "hosted_base_budget_usd": 0.05,
                    "provider_base_budget_usd": 0.05,
                },
                "revenue": {"per_accepted_review_usd": 0.1},
                "acceptance": {
                    "min_accepted_reviews": 1,
                    "min_acceptance_rate": 0.7,
                    "require_budget_coverage": True,
                    "require_revenue_coverage": True,
                },
                "trust": {
                    "public_validator": {
                        "required": True,
                        "quorum": 1,
                        "keys": [
                            {
                                "id": validator_id,
                                "public_key_base64": public_key_b64,
                                "source": "public_validator_demo",
                            }
                        ],
                        "attestations": [
                            {
                                "id": validator_id,
                                "signature_base64": sig_b64,
                            }
                        ],
                    }
                },
            },
        )

        with_sig = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert with_sig.status_code == 200
        with_sig_payload = with_sig.json()
        assert with_sig_payload["pass"] is True
        assert any(item["id"] == "public_validator_quorum" and item["pass"] is True for item in with_sig_payload["assertions"])
        public_validator = with_sig_payload["contract"]["public_validator"]
        assert public_validator["required"] is True
        assert public_validator["required_quorum"] == 1
        assert public_validator["valid_signatures"] == 1
        assert public_validator["pass"] is True


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_requires_public_transparency_anchor(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.05,
                "provider_base_budget_usd": 0.05,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 0.7,
                "require_budget_coverage": True,
                "require_revenue_coverage": True,
            },
            "trust": {
                "public_validator": {"required": False},
                "public_transparency_anchor": {
                    "required": True,
                    "min_anchors": 1,
                    "trusted_domains": ["rekor.sigstore.dev"],
                    "anchors": [],
                },
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 95.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_anchor",
                    "infrastructure_cost_usd": 0.01,
                    "external_provider_cost_usd": 0.02,
                    "total_cost_usd": 0.03,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 2.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_anchor",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "2/2",
                },
            },
        )
        assert completion_event.status_code == 201

        missing_anchor = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert missing_anchor.status_code == 200
        missing_payload = missing_anchor.json()
        assert missing_payload["pass"] is False
        assert any(
            item["id"] == "public_transparency_anchor" and item["pass"] is False for item in missing_payload["assertions"]
        )
        claim_sha = str(missing_payload["contract"]["claim_sha256"])
        anchor_url = "https://rekor.sigstore.dev/api/v1/log/entries/demo"
        _write_mvp_acceptance_policy(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            override={
                "budget": {
                    "hosted_base_budget_usd": 0.05,
                    "provider_base_budget_usd": 0.05,
                },
                "revenue": {"per_accepted_review_usd": 0.1},
                "acceptance": {
                    "min_accepted_reviews": 1,
                    "min_acceptance_rate": 0.7,
                    "require_budget_coverage": True,
                    "require_revenue_coverage": True,
                },
                "trust": {
                    "public_validator": {"required": False},
                    "public_transparency_anchor": {
                        "required": True,
                        "min_anchors": 1,
                        "trusted_domains": ["rekor.sigstore.dev"],
                        "anchors": [
                            {
                                "id": "rekor_demo_entry",
                                "url": anchor_url,
                                "claim_sha256": claim_sha,
                                "source": "rekor",
                            }
                        ],
                    },
                },
            },
        )

        class _FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                _ = args, kwargs

            def __enter__(self) -> "_FakeClient":
                return self

            def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                _ = exc_type, exc, tb
                return False

            def get(self, url: str) -> _FakeResponse:
                assert url == anchor_url
                return _FakeResponse(f"entry payload contains {claim_sha}")

        monkeypatch.setattr(runtime_service.httpx, "Client", _FakeClient)
        with_anchor = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert with_anchor.status_code == 200
        with_anchor_payload = with_anchor.json()
        assert with_anchor_payload["pass"] is True
        assert any(
            item["id"] == "public_transparency_anchor" and item["pass"] is True for item in with_anchor_payload["assertions"]
        )
        anchor_report = with_anchor_payload["contract"]["public_transparency_anchor"]
        assert anchor_report["required"] is True
        assert anchor_report["valid_anchors"] == 1
        assert anchor_report["pass"] is True


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_judge_trust_adjusted_revenue_proves_uplift_and_payout_readiness(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    signing_key = SigningKey.generate()
    validator_id = "validator_revenue_trust_1"
    public_key_b64 = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")
    _write_mvp_acceptance_policy(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        override={
            "budget": {
                "hosted_base_budget_usd": 0.0,
                "provider_base_budget_usd": 0.0,
            },
            "revenue": {"per_accepted_review_usd": 0.1},
            "acceptance": {
                "min_accepted_reviews": 1,
                "min_acceptance_rate": 0.7,
                "require_budget_coverage": False,
                "require_revenue_coverage": False,
            },
            "trust": {
                "require_trust_adjusted_revenue_coverage": True,
                "require_payout_readiness": True,
                "require_trust_for_payout": True,
                "revenue_multipliers": {
                    "validator": 1.25,
                    "anchor": 1.25,
                    "cap": 2.0,
                },
                "public_validator": {
                    "required": True,
                    "quorum": 1,
                    "keys": [
                        {
                            "id": validator_id,
                            "public_key_base64": public_key_b64,
                            "source": "public_validator_demo",
                        }
                    ],
                    "attestations": [],
                },
                "public_transparency_anchor": {
                    "required": True,
                    "min_anchors": 1,
                    "trusted_domains": ["rekor.sigstore.dev"],
                    "anchors": [],
                },
            },
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tool_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 150.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "task_id": "task_review_revenue_trust",
                    "infrastructure_cost_usd": 0.04,
                    "external_provider_cost_usd": 0.08,
                    "total_cost_usd": 0.12,
                    "is_paid_provider": True,
                },
            },
        )
        assert tool_event.status_code == 201

        completion_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 3.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": "task_review_revenue_trust",
                    "task_type": "review",
                    "task_final_status": "completed",
                    "review_pass_fail": "PASS",
                    "verified_assertions": "2/2",
                },
            },
        )
        assert completion_event.status_code == 201

        without_trust = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert without_trust.status_code == 200
        without_payload = without_trust.json()
        assert without_payload["pass"] is False
        assert any(
            item["id"] == "trust_adjusted_revenue_covers_total_cost" and item["pass"] is False
            for item in without_payload["assertions"]
        )
        assert any(
            item["id"] == "payout_readiness" and item["pass"] is False
            for item in without_payload["assertions"]
        )

        claim_payload = without_payload["contract"]["claim_payload"]
        claim_bytes = json.dumps(claim_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        sig_b64 = base64.b64encode(signing_key.sign(claim_bytes).signature).decode("ascii")
        claim_sha = str(without_payload["contract"]["claim_sha256"])
        anchor_url = "https://rekor.sigstore.dev/api/v1/log/entries/revenue-proof"

        _write_mvp_acceptance_policy(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            override={
                "budget": {
                    "hosted_base_budget_usd": 0.0,
                    "provider_base_budget_usd": 0.0,
                },
                "revenue": {"per_accepted_review_usd": 0.1},
                "acceptance": {
                    "min_accepted_reviews": 1,
                    "min_acceptance_rate": 0.7,
                    "require_budget_coverage": False,
                    "require_revenue_coverage": False,
                },
                "trust": {
                    "require_trust_adjusted_revenue_coverage": True,
                    "require_payout_readiness": True,
                    "require_trust_for_payout": True,
                    "revenue_multipliers": {
                        "validator": 1.25,
                        "anchor": 1.25,
                        "cap": 2.0,
                    },
                    "public_validator": {
                        "required": True,
                        "quorum": 1,
                        "keys": [
                            {
                                "id": validator_id,
                                "public_key_base64": public_key_b64,
                                "source": "public_validator_demo",
                            }
                        ],
                        "attestations": [
                            {
                                "id": validator_id,
                                "signature_base64": sig_b64,
                            }
                        ],
                    },
                    "public_transparency_anchor": {
                        "required": True,
                        "min_anchors": 1,
                        "trusted_domains": ["rekor.sigstore.dev"],
                        "anchors": [
                            {
                                "id": "rekor_revenue_entry",
                                "url": anchor_url,
                                "claim_sha256": claim_sha,
                                "source": "rekor",
                            }
                        ],
                    },
                },
            },
        )

        class _FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                _ = args, kwargs

            def __enter__(self) -> "_FakeClient":
                return self

            def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                _ = exc_type, exc, tb
                return False

            def get(self, url: str) -> _FakeResponse:
                assert url == anchor_url
                return _FakeResponse(f"rekor entry proof {claim_sha}")

        monkeypatch.setattr(runtime_service.httpx, "Client", _FakeClient)
        with_trust = await client.get("/api/runtime/mvp/acceptance-judge", params={"seconds": 3600, "limit": 2000})
        assert with_trust.status_code == 200
        with_payload = with_trust.json()
        assert with_payload["pass"] is True
        assert any(
            item["id"] == "trust_adjusted_revenue_covers_total_cost" and item["pass"] is True
            for item in with_payload["assertions"]
        )
        assert any(
            item["id"] == "payout_readiness" and item["pass"] is True
            for item in with_payload["assertions"]
        )
        business_proof = with_payload["contract"]["business_proof"]
        revenue_proof = business_proof["revenue"]
        assert revenue_proof["estimated_revenue_usd"] == 0.1
        assert revenue_proof["trust_adjusted_revenue_usd"] == 0.15625
        assert revenue_proof["trust_revenue_uplift_usd"] == 0.05625
        assert revenue_proof["trust_adjusted_operating_surplus_usd"] == 0.03625
        assert business_proof["trust"]["public_validator_pass"] is True
        assert business_proof["trust"]["public_transparency_anchor_pass"] is True
        assert business_proof["payout_ready"] is True


@pytest.mark.asyncio
async def test_runtime_mvp_acceptance_summary_empty_window_returns_zero_totals(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = await client.get("/api/runtime/mvp/acceptance-summary", params={"seconds": 3600, "limit": 2000})
        assert summary.status_code == 200
        payload = summary.json()
        totals = payload["totals"]
        assert totals["tasks_seen"] == 0
        assert totals["completed_tasks"] == 0
        assert totals["review_tasks_completed"] == 0
        assert totals["accepted_reviews"] == 0
        assert totals["acceptance_rate"] == 0.0
        assert totals["infrastructure_cost_usd"] == 0.0
        assert totals["external_provider_cost_usd"] == 0.0
        assert totals["total_cost_usd"] == 0.0
        assert payload["budget"]["base_budget_usd"] == 0.0
        assert payload["revenue"]["estimated_revenue_usd"] == 0.0
        assert payload["reinvestment"]["reinvestment_pool_usd"] == 0.0
        assert payload["tasks"] == []


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
            json={"cycles": 1, "max_endpoints": 30, "delay_ms": 0, "timeout_seconds": 2.0},
        )
        assert run.status_code == 200
        payload = run.json()
        assert payload["result"] == "runtime_get_endpoint_exerciser_completed"
        assert payload["config"]["max_endpoints"] == 30
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
async def test_runtime_endpoint_attention_recovers_after_success_streak(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("TOOL_SUCCESS_STREAK_TARGET", "3")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        failed = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:streak-recovery-check",
                "method": "RUN",
                "status_code": 500,
                "runtime_ms": 10.0,
                "idea_id": "tool-streak-recovery-test",
            },
        )
        assert failed.status_code == 201

        for _ in range(3):
            succeeded = await client.post(
                "/api/runtime/events",
                json={
                    "source": "worker",
                    "endpoint": "tool:streak-recovery-check",
                    "method": "RUN",
                    "status_code": 200,
                    "runtime_ms": 10.0,
                    "idea_id": "tool-streak-recovery-test",
                },
            )
            assert succeeded.status_code == 201

        attention = await client.get(
            "/api/runtime/endpoints/attention",
            params={
                "seconds": 3600,
                "min_event_count": 1,
                "attention_threshold": 10.0,
                "limit": 20,
            },
        )
        assert attention.status_code == 200
        row = next(item for item in attention.json()["endpoints"] if item["endpoint"] == "/tool:streak-recovery-check")
        assert row["event_count"] == 4
        assert row["success_count"] == 3
        assert row["failure_count"] == 1
        assert row["success_rate"] == 0.75
        assert row["recent_success_streak"] == 3
        assert row["success_streak_target"] == 3
        assert row["failure_recovered"] is True
        assert row["needs_attention"] is True
        assert any(str(reason).startswith("low_success_rate:") for reason in row["reasons"])
        assert f"recovered_success_streak:{row['recent_success_streak']}/{row['success_streak_target']}" in row["reasons"]


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
        # Seed idea (DB is sole source of truth, no auto-seeding at runtime)
        await client.post("/api/ideas", json={
            "id": "portfolio-governance", "name": "Portfolio governance",
            "description": "Unified idea portfolio governance",
            "potential_value": 82.0, "estimated_cost": 10.0, "confidence": 0.75,
            "interfaces": ["machine:api"],
        }, headers=AUTH_HEADERS)

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


def test_cached_runtime_ideas_summary_payload_stale_refresh_singleflight(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry_db = tmp_path / "telemetry_cache.db"
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{telemetry_db}")
    monkeypatch.setattr(runtime_service, "_runtime_endpoint_cache_ttl_seconds", lambda cache_name, default=0.0: 0.0)

    calls = {"refresh": 0}

    def _summary(**kwargs: Any) -> list[IdeaRuntimeSummary]:
        _ = kwargs
        calls["refresh"] += 1
        time.sleep(0.2)
        idx = calls["refresh"]
        return [
            IdeaRuntimeSummary(
                idea_id=f"idea-{idx}",
                event_count=1,
                total_runtime_ms=25.0,
                average_runtime_ms=25.0,
                runtime_cost_estimate=float(idx),
                by_source={"api": 1},
            )
        ]

    monkeypatch.setattr(runtime_service, "summarize_by_idea", _summary)

    seeded = runtime_service.cached_runtime_ideas_summary_payload(
        seconds=3600,
        limit=20,
        offset=0,
        force_refresh=True,
    )
    assert seeded["ideas"][0]["idea_id"] == "idea-1"
    assert calls["refresh"] == 1

    first_stale = runtime_service.cached_runtime_ideas_summary_payload(
        seconds=3600,
        limit=20,
        offset=0,
        force_refresh=False,
    )
    second_stale = runtime_service.cached_runtime_ideas_summary_payload(
        seconds=3600,
        limit=20,
        offset=0,
        force_refresh=False,
    )
    assert first_stale["ideas"][0]["idea_id"] == "idea-1"
    assert second_stale["ideas"][0]["idea_id"] == "idea-1"

    deadline = time.time() + 2.0
    while calls["refresh"] < 2 and time.time() < deadline:
        time.sleep(0.02)

    assert calls["refresh"] == 2


def test_cached_runtime_events_stale_refresh_singleflight(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry_db = tmp_path / "telemetry_cache.db"
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{telemetry_db}")
    monkeypatch.setattr(runtime_service, "_runtime_endpoint_cache_ttl_seconds", lambda cache_name, default=0.0: 0.0)

    calls = {"refresh": 0}

    def _events(**kwargs: Any) -> list[RuntimeEvent]:
        _ = kwargs
        calls["refresh"] += 1
        time.sleep(0.2)
        idx = calls["refresh"]
        return [
            RuntimeEvent(
                id=f"rt_{idx}",
                source="api",
                endpoint="/api/ideas",
                raw_endpoint="/api/ideas",
                method="GET",
                status_code=200,
                runtime_ms=12.0,
                idea_id="portfolio-governance",
                origin_idea_id="portfolio-governance",
                metadata={},
                runtime_cost_estimate=0.001,
                recorded_at=datetime.now(timezone.utc),
            )
        ]

    monkeypatch.setattr(runtime_service, "list_events", _events)

    seeded = runtime_service.cached_runtime_events(limit=100, force_refresh=True)
    assert seeded[0].id == "rt_1"
    assert calls["refresh"] == 1

    first_stale = runtime_service.cached_runtime_events(limit=100, force_refresh=False)
    second_stale = runtime_service.cached_runtime_events(limit=100, force_refresh=False)
    assert first_stale[0].id == "rt_1"
    assert second_stale[0].id == "rt_1"

    deadline = time.time() + 2.0
    while calls["refresh"] < 2 and time.time() < deadline:
        time.sleep(0.02)

    assert calls["refresh"] == 2


def test_cached_web_view_performance_payload_stale_refresh_singleflight(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry_db = tmp_path / "telemetry_cache.db"
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", f"sqlite+pysqlite:///{telemetry_db}")
    monkeypatch.setattr(runtime_service, "_runtime_endpoint_cache_ttl_seconds", lambda cache_name, default=0.0: 0.0)

    calls = {"refresh": 0}

    def _report(**kwargs: Any) -> WebViewPerformanceReport:
        _ = kwargs
        calls["refresh"] += 1
        time.sleep(0.2)
        idx = calls["refresh"]
        return WebViewPerformanceReport(
            window_seconds=3600,
            route_prefix=None,
            total_routes=1,
            rows=[
                WebViewPerformanceRow(
                    route=f"/ideas-{idx}",
                    views=3,
                    p50_render_ms=120.0,
                    p95_render_ms=220.0,
                    average_render_ms=150.0,
                    average_api_call_count=2.0,
                    average_api_endpoint_count=2.0,
                    average_api_runtime_ms=50.0,
                    average_api_runtime_cost_estimate=0.003,
                    last_render_ms=140.0,
                    last_api_runtime_ms=52.0,
                    last_api_runtime_cost_estimate=0.0032,
                    last_view_at=datetime.now(timezone.utc),
                )
            ],
        )

    monkeypatch.setattr(runtime_service, "summarize_web_view_performance", _report)

    seeded = runtime_service.cached_web_view_performance_payload(
        seconds=3600,
        limit=20,
        force_refresh=True,
    )
    assert seeded["rows"][0]["route"] == "/ideas-1"
    assert calls["refresh"] == 1

    first_stale = runtime_service.cached_web_view_performance_payload(
        seconds=3600,
        limit=20,
        force_refresh=False,
    )
    second_stale = runtime_service.cached_web_view_performance_payload(
        seconds=3600,
        limit=20,
        force_refresh=False,
    )
    assert first_stale["rows"][0]["route"] == "/ideas-1"
    assert second_stale["rows"][0]["route"] == "/ideas-1"

    deadline = time.time() + 2.0
    while calls["refresh"] < 2 and time.time() < deadline:
        time.sleep(0.02)

    assert calls["refresh"] == 2
