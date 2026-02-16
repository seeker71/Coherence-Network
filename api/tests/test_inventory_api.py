from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service
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
            isinstance(item.get("path"), str) and item["path"].startswith("specs/")
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
                        "https://coherence-network.vercel.app/flow",
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
        assert "088" in row["spec"]["spec_ids"]
        assert row["implementation"]["lineage_link_count"] >= 1
        assert row["contributions"]["usage_events_count"] >= 1
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
