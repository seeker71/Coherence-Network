from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service
from app.services import inventory_service
from app.services import route_registry_service


@pytest.mark.asyncio
async def test_system_lineage_inventory_includes_core_sections(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    link_payload = {
        "idea_id": "portfolio-governance",
        "spec_id": "049-system-lineage-inventory-and-runtime-telemetry",
        "implementation_refs": ["PR#inventory"],
        "contributors": {
            "idea": "alice",
            "spec": "bob",
            "implementation": "carol",
            "review": "dave",
        },
        "estimated_cost": 10.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unique_email = f"urs-muff+{uuid4().hex[:8]}@coherence.network"
        contributor = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "urs-muff", "email": unique_email},
        )
        assert contributor.status_code == 201
        contributor_id = contributor.json()["id"]

        asset = await client.post(
            "/api/assets",
            json={"type": "CODE", "description": "seeker71/Coherence-Network"},
        )
        assert asset.status_code == 201
        asset_id = asset.json()["id"]

        contribution = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "1.75",
                "metadata": {"idea_ids": ["portfolio-governance"]},
            },
        )
        assert contribution.status_code == 201

        created = await client.post("/api/value-lineage/links", json=link_payload)
        assert created.status_code == 201
        lineage_id = created.json()["id"]

        usage = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "api", "metric": "validated_flow", "value": 3.0},
        )
        assert usage.status_code == 201

        inventory = await client.get("/api/inventory/system-lineage", params={"runtime_window_seconds": 3600})
        assert inventory.status_code == 200
        data = inventory.json()

        assert "ideas" in data
        assert "questions" in data
        assert "specs" in data
        assert "implementation_usage" in data
        assert "runtime" in data

        assert data["ideas"]["summary"]["total_ideas"] >= 1
        assert data["questions"]["total"] >= 1
        assert data["specs"]["count"] >= 1
        assert data["implementation_usage"]["lineage_links_count"] >= 1
        assert data["implementation_usage"]["usage_events_count"] >= 1
        assert isinstance(data["runtime"]["ideas"], list)
        assert all("question_roi" in row for row in data["questions"]["unanswered"])
        assert all(
            isinstance(item.get("path"), str) and item["path"].startswith("/api/spec-registry/")
            for item in data["specs"]["items"]
        )


@pytest.mark.asyncio
async def test_canonical_routes_inventory_endpoint_returns_registry() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/routes/canonical")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_routes" in data
        assert "web_routes" in data
        assert any(route["path"] == "/api/inventory/system-lineage" for route in data["api_routes"])
        assert any(route["path"] == "/api/inventory/route-evidence" for route in data["api_routes"])


@pytest.mark.asyncio
async def test_canonical_routes_fallback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        route_registry_service,
        "_registry_path",
        lambda: Path("/definitely-missing/canonical_routes.json"),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/routes/canonical")
        assert resp.status_code == 200
        data = resp.json()
        assert any(route["path"] == "/api/runtime/events" for route in data["api_routes"])


@pytest.mark.asyncio
async def test_canonical_routes_uses_env_override_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "canonical_routes_override.json"
    override.write_text(
        json.dumps(
            {
                "version": "override-test",
                "milestone": "override",
                "api_routes": [
                    {
                        "path": "/api/override-check",
                        "methods": ["GET"],
                        "purpose": "test",
                        "idea_id": "portfolio-governance",
                    }
                ],
                "web_routes": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CANONICAL_ROUTES_PATH", str(override))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/routes/canonical")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "override-test"
        assert any(route["path"] == "/api/override-check" for route in data["api_routes"])


@pytest.mark.asyncio
async def test_route_evidence_inventory_reports_api_and_web_coverage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe_payload = {
        "generated_at": "2026-02-16T00:00:00+00:00",
        "api": [
            {
                "path_template": "/api/inventory/system-lineage",
                "path": "/api/inventory/system-lineage",
                "method": "GET",
                "status_code": 200,
            }
        ],
        "web": [
            {
                "path_template": "/flow",
                "path": "/flow",
                "status_code": 200,
            }
        ],
    }
    (tmp_path / "route_evidence_probe_2026-02-16.json").write_text(
        json.dumps(probe_payload),
        encoding="utf-8",
    )
    monkeypatch.setenv("ROUTE_EVIDENCE_PROBE_DIR", str(tmp_path))
    monkeypatch.setattr(
        inventory_service.runtime_service,
        "summarize_by_endpoint",
        lambda seconds=86400: [SimpleNamespace(endpoint="/api/inventory/system-lineage", event_count=2)],
    )
    monkeypatch.setattr(
        inventory_service,
        "_read_commit_evidence_records",
        lambda limit=1200: [
            {
                "e2e_validation": {
                    "public_endpoints": [
                        "https://coherence-network-production.up.railway.app/api/inventory/system-lineage",
                        "https://coherence-web-production.up.railway.app/flow",
                    ]
                }
            }
        ],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/route-evidence")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary"]["api_total"] >= 1
        assert payload["summary"]["web_total"] >= 1
        assert payload["summary"]["api_with_actual_evidence"] >= 1
        assert payload["summary"]["web_with_actual_evidence"] >= 1


@pytest.mark.asyncio
async def test_route_evidence_inventory_does_not_pass_empty_real_data_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        inventory_service.route_registry_service,
        "get_canonical_routes",
        lambda: {
            "api_routes": [
                {
                    "path": "/api/inventory/system-lineage",
                    "methods": ["GET"],
                    "purpose": "lineage",
                    "idea_id": "portfolio-governance",
                }
            ],
            "web_routes": [],
        },
    )
    monkeypatch.setattr(inventory_service.runtime_service, "summarize_by_endpoint", lambda seconds=86400: [])
    monkeypatch.setattr(inventory_service, "_read_commit_evidence_records", lambda limit=1200: [])
    monkeypatch.setattr(
        inventory_service,
        "_read_latest_route_evidence_probe",
        lambda: {
            "api": [
                {
                    "path_template": "/api/inventory/system-lineage",
                    "method": "GET",
                    "probe_method": "GET",
                    "status_code": 200,
                    "probe_ok": True,
                    "data_present": False,
                }
            ],
            "web": [],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/route-evidence")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["summary"]["api_total"] == 1
        assert payload["summary"]["api_with_actual_evidence"] == 0
        assert payload["summary"]["api_missing_actual_evidence"] == 1
        assert payload["summary"]["api_missing_real_data"] == 1


@pytest.mark.asyncio
async def test_standing_question_exists_for_every_idea(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ideas = listed.json()["ideas"]
        for idea in ideas:
            assert any(
                "How can we improve this idea" in q["question"] for q in idea["open_questions"]
            )


@pytest.mark.asyncio
async def test_next_highest_roi_task_generation_from_answered_questions(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ideas = await client.get("/api/ideas")
        first = ideas.json()["ideas"][0]
        question = first["open_questions"][0]["question"]
        answered = await client.post(
            f"/api/ideas/{first['id']}/questions/answer",
            json={
                "question": question,
                "answer": "Apply this answer to generate next measurable task.",
                "measured_delta": 4.0,
            },
        )
        assert answered.status_code == 200

        suggest = await client.post("/api/inventory/questions/next-highest-roi-task")
        assert suggest.status_code == 200
        payload = suggest.json()
        assert payload["result"] == "task_suggested"
        assert payload["answer_roi"] >= 0

        created = await client.post(
            "/api/inventory/questions/next-highest-roi-task",
            params={"create_task": True},
        )
        assert created.status_code == 200
        created_payload = created.json()
        assert created_payload["result"] == "task_suggested"
        assert "created_task" in created_payload


@pytest.mark.asyncio
async def test_page_lineage_inventory_endpoint_returns_page_to_idea_mapping() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/page-lineage")
        assert resp.status_code == 200
        data = resp.json()
        assert "pages" in data
        assert isinstance(data["pages"], list)
        assert any(row.get("path") == "/portfolio" for row in data["pages"])

        paths = {row["path"] for row in data["pages"] if isinstance(row.get("path"), str)}
        expected_paths = {
            "/",
            "/portfolio",
            "/flow",
            "/ideas",
            "/ideas/[idea_id]",
            "/specs",
            "/specs/[spec_id]",
            "/usage",
            "/automation",
            "/contribute",
            "/friction",
            "/gates",
            "/import",
            "/project/[ecosystem]/[name]",
            "/search",
            "/api-health",
            "/contributors",
            "/contributions",
            "/assets",
            "/tasks",
            "/agent",
        }
        assert expected_paths.issubset(paths)
        assert len(paths) == len(data["pages"])


@pytest.mark.asyncio
async def test_flow_inventory_endpoint_tracks_spec_process_implementation_validation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))

    (evidence_dir / "commit_evidence_flow_test.json").write_text(
        json.dumps(
            {
                "date": "2026-02-16",
                "thread_branch": "codex/flow-test",
                "commit_scope": "Flow visibility test",
                "files_owned": ["api/app/routers/inventory.py"],
                "idea_ids": ["portfolio-governance"],
                "spec_ids": ["088"],
                "task_ids": ["flow-visibility-task"],
                "contributors": [
                    {
                        "contributor_id": "openai-codex",
                        "contributor_type": "machine",
                        "roles": ["implementation", "validation"],
                    },
                    {
                        "contributor_id": "urs-muff",
                        "contributor_type": "human",
                        "roles": ["review"],
                    },
                ],
                "agent": {"name": "OpenAI Codex", "version": "gpt-5"},
                "evidence_refs": ["pytest -q tests/test_inventory_api.py"],
                "change_files": ["api/app/routers/inventory.py", "web/app/flow/page.tsx"],
                "change_intent": "runtime_feature",
                "e2e_validation": {
                    "status": "pass",
                    "expected_behavior_delta": "Flow page and endpoint reflect end-to-end tracking.",
                    "public_endpoints": [
                        "https://coherence-web-production.up.railway.app/flow",
                        "https://coherence-network-production.up.railway.app/api/inventory/flow",
                    ],
                    "test_flows": ["idea->spec->process->implementation->validation visible in UI and API"],
                },
                "local_validation": {"status": "pass"},
                "ci_validation": {"status": "pass"},
                "deploy_validation": {"status": "pass"},
                "phase_gate": {"can_move_next_phase": True},
            }
        ),
        encoding="utf-8",
    )

    link_payload = {
        "idea_id": "portfolio-governance",
        "spec_id": "088",
        "implementation_refs": ["web/app/flow/page.tsx"],
        "contributors": {
            "idea": "urs-muff",
            "spec": "openai-codex",
            "implementation": "openai-codex",
            "review": "urs-muff",
        },
        "estimated_cost": 8.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/value-lineage/links", json=link_payload)
        assert created.status_code == 201
        lineage_id = created.json()["id"]

        usage = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "api", "metric": "flow_visible", "value": 5.0},
        )
        assert usage.status_code == 201

        runtime = await client.post(
            "/api/runtime/events",
            json={
                "source": "web",
                "endpoint": "/flow",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 90.0,
                "idea_id": "portfolio-governance",
                "metadata": {"surface": "web-ui"},
            },
        )
        assert runtime.status_code == 201

        flow = await client.get("/api/inventory/flow", params={"idea_id": "portfolio-governance"})
        assert flow.status_code == 200
        payload = flow.json()
        assert payload["summary"]["ideas"] == 1
        assert len(payload["items"]) == 1
        row = payload["items"][0]
        assert row["idea_id"] == "portfolio-governance"
        assert row["spec"]["tracked"] is True
        assert row["process"]["tracked"] is True
        assert row["implementation"]["tracked"] is True
        assert row["validation"]["tracked"] is True
        assert row["contributors"]["tracked"] is True
        assert row["contributions"]["tracked"] is True
        assert row["assets"]["tracked"] is True
        assert "088" in row["spec"]["spec_ids"]
        assert row["implementation"]["lineage_link_count"] >= 1
        assert row["contributions"]["usage_events_count"] >= 1
        assert row["contributions"]["registry_contribution_count"] >= 1
        assert row["contributions"]["registry_total_cost"] >= 1.75
        assert row["assets"]["count"] >= 1
        assert row["validation"]["local"]["pass"] >= 1
        assert row["validation"]["ci"]["pass"] >= 1
        assert row["validation"]["deploy"]["pass"] >= 1
        assert row["validation"]["e2e"]["pass"] >= 1
        assert row["contributors"]["total_unique"] >= 2
        assert "interdependencies" in row
        assert row["interdependencies"]["blocked"] is False
        assert isinstance(payload["unblock_queue"], list)


@pytest.mark.asyncio
async def test_endpoint_traceability_inventory_reports_coverage_and_gaps(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    (tmp_path / "idea_lineage.json").write_text(
        json.dumps({"origin_map": {"portfolio-governance": "system-root"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_LINEAGE_MAP_PATH", str(tmp_path / "idea_lineage.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))

    (evidence_dir / "commit_evidence_traceability_test.json").write_text(
        json.dumps(
            {
                "date": "2026-02-16",
                "thread_branch": "codex/endpoint-traceability-test",
                "commit_scope": "Endpoint traceability inventory coverage test",
                "files_owned": ["api/app/routers/ideas.py"],
                "idea_ids": ["portfolio-governance"],
                "spec_ids": ["053"],
                "task_ids": ["endpoint-traceability-audit"],
                "contributors": [
                    {
                        "contributor_id": "openai-codex",
                        "contributor_type": "machine",
                        "roles": ["implementation", "validation"],
                    }
                ],
                "agent": {"name": "OpenAI Codex", "version": "gpt-5"},
                "evidence_refs": ["pytest -q tests/test_inventory_api.py"],
                "change_files": ["api/app/routers/ideas.py"],
                "change_intent": "runtime_feature",
                "e2e_validation": {
                    "status": "pass",
                    "expected_behavior_delta": "Endpoint coverage has explicit idea/spec/process traceability.",
                    "public_endpoints": [
                        "https://coherence-network-production.up.railway.app/api/inventory/endpoint-traceability"
                    ],
                    "test_flows": ["api:/api/inventory/endpoint-traceability -> inspect summary and gaps"],
                },
                "local_validation": {"status": "pass"},
                "ci_validation": {"status": "pass"},
                "deploy_validation": {"status": "pass"},
                "phase_gate": {"can_move_next_phase": True},
            }
        ),
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        runtime_created = await client.post(
            "/api/runtime/events",
            json={
                "source": "api",
                "endpoint": "/api/ideas",
                "method": "GET",
                "status_code": 200,
                "runtime_ms": 22.0,
            },
        )
        assert runtime_created.status_code == 201

        resp = await client.get("/api/inventory/endpoint-traceability")
        assert resp.status_code == 200
        payload = resp.json()

    assert payload["summary"]["total_endpoints"] >= 40
    assert payload["summary"]["missing_idea"] == 0
    assert payload["summary"]["with_origin_idea"] == payload["summary"]["total_endpoints"]
    assert payload["summary"]["with_usage_events"] >= 1
    assert payload["summary"]["missing_spec"] >= 1
    assert payload["context"]["spec_count"] >= payload["context"]["idea_count"]
    assert any(row["path"] == "/api/inventory/endpoint-traceability" for row in payload["items"])

    ideas_row = next(row for row in payload["items"] if row["path"] == "/api/ideas")
    assert ideas_row["idea"]["tracked"] is True
    assert ideas_row["idea"]["origin_idea_id"] == "system-root"
    assert ideas_row["usage"]["tracked"] is True
    assert ideas_row["usage"]["event_count"] >= 1
    assert ideas_row["spec"]["tracked"] is True
    assert ideas_row["process"]["tracked"] is True


@pytest.mark.asyncio
async def test_sync_implementation_request_questions_creates_tasks_without_duplicates(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    portfolio = {
        "ideas": [
            {
                "id": "automation-idea",
                "name": "Automation idea",
                "description": "Track and automate implementation requests.",
                "potential_value": 90.0,
                "actual_value": 0.0,
                "estimated_cost": 10.0,
                "actual_cost": 0.0,
                "resistance_risk": 1.0,
                "confidence": 0.8,
                "manifestation_status": "partial",
                "interfaces": ["machine:api"],
                "open_questions": [
                    {
                        "question": "Can we implement public contributor registration flow?",
                        "value_to_whole": 22.0,
                        "estimated_cost": 2.0,
                    },
                    {
                        "question": "Which indicator should we monitor next?",
                        "value_to_whole": 10.0,
                        "estimated_cost": 2.0,
                    },
                ],
            }
        ]
    }
    (tmp_path / "ideas.json").write_text(json.dumps(portfolio), encoding="utf-8")

    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/inventory/questions/sync-implementation-tasks")
        assert created.status_code == 200
        first = created.json()
        assert first["result"] == "implementation_tasks_synced"
        assert first["created_count"] == 1
        assert first["skipped_existing_count"] == 0
        assert first["skipped_non_impl_count"] >= 1
        assert len(first["created_tasks"]) == 1

        rerun = await client.post("/api/inventory/questions/sync-implementation-tasks")
        assert rerun.status_code == 200
        second = rerun.json()
        assert second["created_count"] == 0
        assert second["skipped_existing_count"] == 1


@pytest.mark.asyncio
async def test_next_highest_roi_task_skips_duplicate_when_active_task_exists(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ideas = await client.get("/api/ideas")
        first = ideas.json()["ideas"][0]
        question = first["open_questions"][0]["question"]
        answered = await client.post(
            f"/api/ideas/{first['id']}/questions/answer",
            json={
                "question": question,
                "answer": "Implement this through a new tracked endpoint and rollout task.",
                "measured_delta": 2.0,
            },
        )
        assert answered.status_code == 200

        created = await client.post(
            "/api/inventory/questions/next-highest-roi-task",
            params={"create_task": True},
        )
        assert created.status_code == 200
        payload = created.json()
        assert payload["result"] == "task_already_active"
        assert payload["active_task"]["id"]
        assert payload["active_task"]["status"] in {"pending", "running", "needs_decision"}

        listed = await client.get("/api/agent/tasks")
        assert listed.status_code == 200
        data = listed.json()
        assert data["total"] == 1


@pytest.mark.asyncio
async def test_flow_inventory_exposes_interdependencies_and_prioritizes_unblock_queue(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    portfolio = {
        "ideas": [
            {
                "id": "idea-high-unblock",
                "name": "High unblock value",
                "description": "Missing spec should block the rest.",
                "potential_value": 120.0,
                "actual_value": 20.0,
                "estimated_cost": 12.0,
                "actual_cost": 0.0,
                "resistance_risk": 2.0,
                "confidence": 0.9,
                "manifestation_status": "none",
                "interfaces": ["machine:api"],
                "open_questions": [
                    {
                        "question": "How do we unblock the chain first?",
                        "value_to_whole": 20.0,
                        "estimated_cost": 2.0,
                    }
                ],
            },
            {
                "id": "idea-lower-unblock",
                "name": "Lower unblock value",
                "description": "Also missing spec but lower weighted upside.",
                "potential_value": 60.0,
                "actual_value": 30.0,
                "estimated_cost": 10.0,
                "actual_cost": 0.0,
                "resistance_risk": 2.0,
                "confidence": 0.6,
                "manifestation_status": "none",
                "interfaces": ["machine:api"],
                "open_questions": [],
            },
        ]
    }
    (tmp_path / "ideas.json").write_text(json.dumps(portfolio), encoding="utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/flow")
        assert resp.status_code == 200
        payload = resp.json()

        assert payload["summary"]["blocked_ideas"] >= 2
        assert payload["summary"]["queue_items"] >= 2
        queue = payload["unblock_queue"]
        assert len(queue) >= 2
        assert queue[0]["unblock_priority_score"] >= queue[1]["unblock_priority_score"]
        queue_by_id = {row["idea_id"]: row for row in queue}
        assert "idea-high-unblock" in queue_by_id
        assert "idea-lower-unblock" in queue_by_id
        assert queue_by_id["idea-high-unblock"]["unblock_priority_score"] > queue_by_id["idea-lower-unblock"]["unblock_priority_score"]
        assert queue_by_id["idea-high-unblock"]["blocking_stage"] == "spec"
        assert queue_by_id["idea-high-unblock"]["task_type"] == "spec"
        assert "process" in queue_by_id["idea-high-unblock"]["downstream_blocked"]
        assert "implementation" in queue_by_id["idea-high-unblock"]["downstream_blocked"]
        assert "validation" in queue_by_id["idea-high-unblock"]["downstream_blocked"]

        row = next(item for item in payload["items"] if item["idea_id"] == "idea-high-unblock")
        assert row["interdependencies"]["blocked"] is True
        assert row["interdependencies"]["blocking_stage"] == "spec"
        assert row["interdependencies"]["upstream_required"] == []
        assert set(row["interdependencies"]["downstream_blocked"]) >= {"process", "implementation", "validation"}
        assert row["interdependencies"]["unblock_priority_score"] > 0


@pytest.mark.asyncio
async def test_next_unblock_task_endpoint_creates_task_and_avoids_active_duplicate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    (tmp_path / "ideas.json").write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "unblock-task-idea",
                        "name": "Unblock task idea",
                        "description": "Flow should propose a spec-first unblock task.",
                        "potential_value": 90.0,
                        "actual_value": 10.0,
                        "estimated_cost": 10.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.8,
                        "manifestation_status": "none",
                        "interfaces": ["machine:api"],
                        "open_questions": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suggest = await client.post("/api/inventory/flow/next-unblock-task")
        assert suggest.status_code == 200
        suggested = suggest.json()
        assert suggested["result"] == "task_suggested"
        assert suggested["blocking_stage"] == "spec"
        assert suggested["task_type"] == "spec"
        assert suggested["unblock_priority_score"] > 0

        created = await client.post("/api/inventory/flow/next-unblock-task", params={"create_task": True})
        assert created.status_code == 200
        created_payload = created.json()
        assert created_payload["result"] == "task_suggested"
        assert created_payload["created_task"]["id"]
        assert created_payload["created_task"]["task_type"] == "spec"

        duplicate = await client.post("/api/inventory/flow/next-unblock-task", params={"create_task": True})
        assert duplicate.status_code == 200
        duplicate_payload = duplicate.json()
        assert duplicate_payload["result"] == "task_already_active"
        assert duplicate_payload["active_task"]["id"] == created_payload["created_task"]["id"]


@pytest.mark.asyncio
async def test_flow_inventory_counts_spec_registry_specs_for_idea(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    idea_id = "public-e2e-flow-gate-automation"
    spec_id = "095-public-e2e-flow-gate-automation-test"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_spec = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": spec_id,
                "title": "Public E2E Flow Gate Automation",
                "summary": "Spec registry spec should count for flow spec coverage.",
                "idea_id": idea_id,
                "process_summary": "Run profile-specific journeys and record evidence.",
                "pseudocode_summary": "profile -> journeys -> execute -> persist -> gate",
                "implementation_summary": "Extend gate service and API responses.",
            },
        )
        assert create_spec.status_code == 201

        flow = await client.get("/api/inventory/flow", params={"idea_id": idea_id})
        assert flow.status_code == 200
        payload = flow.json()
        assert payload["summary"]["ideas"] == 1
        assert payload["summary"]["with_spec"] == 1
        row = payload["items"][0]
        assert row["spec"]["tracked"] is True
        assert spec_id in row["spec"]["spec_ids"]
        assert row["process"]["tracked"] is True
        assert row["implementation"]["tracked"] is True

@pytest.mark.asyncio
async def test_asset_modularity_endpoint_returns_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        inventory_service,
        "evaluate_asset_modularity",
        lambda runtime_window_seconds=86400, max_implementation_files=5000: {
            "generated_at": "2026-02-16T00:00:00+00:00",
            "status": "fail",
            "result": "asset_modularity_drift_detected",
            "runtime_window_seconds": runtime_window_seconds,
            "thresholds": {"implementation_file_lines": 450},
            "summary": {"blocking_assets": 1, "ideas_scanned": 1, "specs_scanned": 1, "implementation_files_scanned": 1},
            "blockers": [
                {
                    "asset_category": "implementation",
                    "asset_id": "api/app/big_module.py",
                    "metric": "line_count",
                    "current_value": 700,
                    "threshold": 450,
                    "estimated_roi": 4.2,
                }
            ],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/asset-modularity")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "fail"
        assert payload["summary"]["blocking_assets"] == 1
        assert payload["blockers"][0]["asset_id"] == "api/app/big_module.py"


@pytest.mark.asyncio
async def test_sync_asset_modularity_tasks_endpoint_creates_deduped_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        inventory_service,
        "evaluate_asset_modularity",
        lambda runtime_window_seconds=86400, max_implementation_files=5000: {
            "generated_at": "2026-02-16T00:00:00+00:00",
            "status": "fail",
            "result": "asset_modularity_drift_detected",
            "summary": {"blocking_assets": 1},
            "thresholds": {"implementation_file_lines": 450},
            "blockers": [
                {
                    "asset_category": "implementation",
                    "asset_kind": "source_file",
                    "asset_id": "api/app/big_module.py",
                    "idea_id": "portfolio-governance",
                    "spec_id": "089-endpoint-traceability-coverage",
                    "metric": "line_count",
                    "current_value": 700,
                    "threshold": 450,
                    "estimated_split_cost_hours": 4.0,
                    "estimated_value_to_whole": 18.0,
                    "estimated_roi": 4.5,
                    "recommended_task_type": "impl",
                    "task_fingerprint": "asset-modularity::big-module-line-count",
                    "direction": "Split api/app/big_module.py into modular files <= 450 lines.",
                }
            ],
        },
    )

    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/inventory/gaps/sync-asset-modularity-tasks", params={"max_tasks": 10})
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["result"] == "asset_modularity_tasks_synced"
        assert first_payload["created_count"] == 1
        assert first_payload["created_tasks"][0]["task_type"] == "impl"

        second = await client.post("/api/inventory/gaps/sync-asset-modularity-tasks", params={"max_tasks": 10})
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["created_count"] == 0
        assert second_payload["skipped_existing_count"] >= 1

@pytest.mark.asyncio
async def test_proactive_questions_endpoint_derives_questions_from_recent_evidence(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))

    (evidence_dir / "commit_evidence_2026-02-16_runtime-fix-a.json").write_text(
        json.dumps(
            {
                "date": "2026-02-16",
                "commit_scope": "fix missing idea/spec links in flow page",
                "idea_ids": ["portfolio-governance"],
                "change_intent": "runtime_fix",
            }
        ),
        encoding="utf-8",
    )
    (evidence_dir / "commit_evidence_2026-02-16_runtime-feature-b.json").write_text(
        json.dumps(
            {
                "date": "2026-02-16",
                "commit_scope": "add public validation and e2e checks for deployment",
                "idea_ids": ["oss-interface-alignment"],
                "change_intent": "runtime_feature",
            }
        ),
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/questions/proactive", params={"limit": 20, "top": 20})
        assert resp.status_code == 200
        payload = resp.json()

        assert payload["summary"]["recent_records"] >= 2
        assert payload["summary"]["candidate_questions"] >= 2
        assert len(payload["questions"]) >= 2
        assert any(row["idea_id"] == "portfolio-governance" for row in payload["questions"])
        assert any("prevented" in row["question"].lower() for row in payload["questions"])
        assert all(float(row["question_roi"]) > 0 for row in payload["questions"])


@pytest.mark.asyncio
async def test_sync_proactive_questions_adds_missing_questions_without_duplicates(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))

    (evidence_dir / "commit_evidence_2026-02-16_process-gap.json").write_text(
        json.dumps(
            {
                "date": "2026-02-16",
                "commit_scope": "manual follow-up to close missing process and implementation links",
                "idea_ids": ["portfolio-governance"],
                "change_intent": "runtime_fix",
            }
        ),
        encoding="utf-8",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/inventory/questions/sync-proactive", params={"limit": 20, "max_add": 10})
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["result"] == "proactive_questions_synced"
        assert first_payload["created_count"] >= 1
        assert first_payload["candidate_count"] >= first_payload["created_count"]

        second = await client.post("/api/inventory/questions/sync-proactive", params={"limit": 20, "max_add": 10})
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["created_count"] == 0
        assert second_payload["skipped_existing_count"] >= 1

        idea = await client.get("/api/ideas/portfolio-governance")
        assert idea.status_code == 200
        questions = idea.json()["open_questions"]
        assert any("manual follow-up" in q["question"].lower() for q in questions)


@pytest.mark.asyncio
async def test_sync_traceability_gaps_links_spec_to_idea_creates_missing_specs_and_usage_tasks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))

    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seeded = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": "spec-without-idea-link",
                "title": "Spec without idea",
                "summary": "This spec intentionally has no idea_id to verify automatic linking.",
                "created_by_contributor_id": "user-1",
            },
        )
        assert seeded.status_code == 201
        assert seeded.json()["idea_id"] is None

        synced = await client.post(
            "/api/inventory/gaps/sync-traceability",
            params={
                "runtime_window_seconds": 86400,
                "max_spec_idea_links": 20,
                "max_missing_endpoint_specs": 20,
                "max_usage_gap_tasks": 2000,
            },
        )
        assert synced.status_code == 200
        payload = synced.json()
        assert payload["result"] == "traceability_gap_artifacts_synced"
        assert payload["traceability_summary"]["total_endpoints"] >= 1
        assert payload["linked_specs_to_ideas_count"] >= 1
        assert payload["created_missing_endpoint_specs_count"] >= 0
        assert payload["created_usage_gap_tasks_count"] >= 0

        linked_spec = await client.get("/api/spec-registry/spec-without-idea-link")
        assert linked_spec.status_code == 200
        linked_spec_payload = linked_spec.json()
        assert isinstance(linked_spec_payload["idea_id"], str)
        assert linked_spec_payload["idea_id"].strip() != ""
        assert isinstance(linked_spec_payload["process_summary"], str)
        assert linked_spec_payload["process_summary"].strip() != ""
        assert isinstance(linked_spec_payload["pseudocode_summary"], str)
        assert linked_spec_payload["pseudocode_summary"].strip() != ""
        assert payload["updated_spec_process_pseudocode_count"] >= 1

        if payload["created_missing_endpoint_specs_count"] > 0:
            created = payload["created_missing_endpoint_specs"][0]
            traceability = await client.get(
                "/api/inventory/endpoint-traceability",
                params={"runtime_window_seconds": 86400},
            )
            assert traceability.status_code == 200
            trace_items = traceability.json()["items"]
            row = next(
                item
                for item in trace_items
                if item["path"] == created["path"]
            )
            assert row["spec"]["tracked"] is True
            assert created["spec_id"] in row["spec"]["spec_ids"]

        idea = await client.get(f"/api/ideas/{linked_spec_payload['idea_id']}")
        assert idea.status_code == 200

        listed_tasks = await client.get("/api/agent/tasks")
        assert listed_tasks.status_code == 200
        assert listed_tasks.json()["total"] >= 1

        rerun = await client.post(
            "/api/inventory/gaps/sync-traceability",
            params={
                "runtime_window_seconds": 86400,
                "max_spec_idea_links": 20,
                "max_missing_endpoint_specs": 20,
                "max_usage_gap_tasks": 2000,
            },
        )
        assert rerun.status_code == 200
        rerun_payload = rerun.json()
        assert rerun_payload["created_usage_gap_tasks_count"] == 0
        if payload["created_usage_gap_tasks_count"] > 0:
            assert rerun_payload["skipped_existing_usage_gap_tasks_count"] >= 1


@pytest.mark.asyncio
async def test_process_completeness_report_has_checks_and_blockers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get("/api/inventory/process-completeness", params={"runtime_window_seconds": 86400})
        assert report.status_code == 200
        payload = report.json()

        assert payload["result"] in {"process_complete", "process_gaps_detected"}
        assert payload["status"] in {"pass", "fail"}
        assert isinstance(payload["checks"], list)
        assert len(payload["checks"]) >= 8
        check_ids = {row["id"] for row in payload["checks"]}
        assert "specs_linked_to_ideas" in check_ids
        assert "specs_have_process_and_pseudocode" in check_ids
        assert "all_endpoints_have_usage_events" in check_ids
        assert isinstance(payload["blockers"], list)
        assert payload["summary"]["checks_total"] == len(payload["checks"])


@pytest.mark.asyncio
async def test_process_completeness_auto_sync_runs_traceability_sync(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))
    agent_service._store.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seeded = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": "auto-sync-process-completeness-spec",
                "title": "Auto sync process completeness seed",
                "summary": "Seed spec for process completeness auto-sync.",
                "created_by_contributor_id": "user-2",
            },
        )
        assert seeded.status_code == 201
        assert seeded.json()["idea_id"] is None

        report = await client.get(
            "/api/inventory/process-completeness",
            params={
                "runtime_window_seconds": 86400,
                "auto_sync": True,
                "max_spec_idea_links": 10,
                "max_missing_endpoint_specs": 10,
                "max_spec_process_backfills": 20,
                "max_usage_gap_tasks": 5,
            },
        )
        assert report.status_code == 200
        payload = report.json()
        assert payload["auto_sync_applied"] is True
        assert isinstance(payload["auto_sync_report"], dict)
        assert payload["auto_sync_report"]["result"] == "traceability_gap_artifacts_synced"
        assert payload["auto_sync_report"]["linked_specs_to_ideas_count"] >= 1


@pytest.mark.asyncio
async def test_sync_process_gap_tasks_creates_and_dedupes_blocker_tasks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    evidence_dir = tmp_path / "system_audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IDEA_COMMIT_EVIDENCE_DIR", str(evidence_dir))
    agent_service._store.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/inventory/gaps/sync-process-tasks",
            params={
                "runtime_window_seconds": 86400,
                "auto_sync": True,
                "max_tasks": 20,
                "max_spec_idea_links": 50,
                "max_missing_endpoint_specs": 50,
                "max_spec_process_backfills": 100,
                "max_usage_gap_tasks": 100,
            },
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["result"] == "process_gap_tasks_synced"
        assert first_payload["blockers_count"] >= first_payload["created_count"]
        assert first_payload["created_count"] >= 1
        assert first_payload["process_auto_sync_applied"] is True

        second = await client.post(
            "/api/inventory/gaps/sync-process-tasks",
            params={
                "runtime_window_seconds": 86400,
                "auto_sync": False,
                "max_tasks": 20,
            },
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["created_count"] == 0
        assert second_payload["skipped_existing_count"] >= 1
