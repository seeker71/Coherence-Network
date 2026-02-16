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
            "/usage",
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
