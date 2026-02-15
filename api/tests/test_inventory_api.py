from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import idea_service, route_registry_service


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
        assert "manifestations" in data
        assert "questions" in data
        assert "question_ontology" in data
        assert "specs" in data
        assert "implementation_usage" in data
        assert "assets" in data
        assert "contributors" in data
        assert "roi_insights" in data
        assert "roi_estimator" in data
        assert "next_roi_work" in data
        assert "operating_console" in data
        assert "evidence_contract" in data
        assert "tracking_mechanism" in data
        assert "availability_gaps" in data
        assert "runtime" in data

        assert data["ideas"]["summary"]["total_ideas"] >= 1
        assert data["manifestations"]["total"] >= 1
        assert data["questions"]["total"] >= 1
        assert data["question_ontology"]["total_questions"] >= 1
        assert data["question_ontology"]["unlinked_count"] == 0
        assert data["specs"]["count"] >= 1
        assert data["implementation_usage"]["lineage_links_count"] >= 1
        assert data["implementation_usage"]["usage_events_count"] >= 1
        assert data["assets"]["total"] >= 1
        assert "by_type" in data["assets"]
        assert "coverage" in data["assets"]
        assert "by_perspective" in data["contributors"]
        assert "most_estimated_roi" in data["roi_insights"]
        assert "weights" in data["roi_estimator"]
        assert data["next_roi_work"]["selection_basis"] == "highest_idea_estimated_roi_then_question_roi"
        assert "estimated_roi_rank" in data["operating_console"]
        assert "checks" in data["evidence_contract"]
        assert "improvements_ranked" in data["tracking_mechanism"]
        ranked = data["tracking_mechanism"]["improvements_ranked"]
        assert isinstance(ranked, list)
        assert len(ranked) >= 1
        rois = [float(row.get("estimated_roi") or 0.0) for row in ranked]
        assert rois == sorted(rois, reverse=True)
        assert data["tracking_mechanism"]["best_next_improvement"] == ranked[0]
        assert data["availability_gaps"]["api_routes_total"] >= 1
        assert data["availability_gaps"]["web_api_usage_paths_total"] >= 1
        assert "why_previously_missed" in data["availability_gaps"]
        assert isinstance(data["runtime"]["ideas"], list)
        assert all("question_roi" in row for row in data["questions"]["unanswered"])


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
async def test_page_lineage_endpoint_covers_web_pages_and_returns_entry() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        all_rows = await client.get("/api/inventory/page-lineage")
        assert all_rows.status_code == 200
        payload = all_rows.json()
        assert payload["web_pages_total"] >= 1
        assert payload["mapped_pages_total"] >= 1
        assert isinstance(payload["entries"], list)
        assert len(payload["missing_pages"]) == 0

        by_path = await client.get("/api/inventory/page-lineage", params={"page_path": "/portfolio"})
        assert by_path.status_code == 200
        entry = by_path.json().get("entry")
        assert entry is not None
        assert entry["idea_id"] == "portfolio-governance"
        assert entry["root_idea_id"] == "coherence-network-overall"


@pytest.mark.asyncio
async def test_assets_inventory_endpoint_lists_registered_assets() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/inventory/assets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert isinstance(data["items"], list)
        assert "coverage" in data

        ideas_only = await client.get("/api/inventory/assets", params={"asset_type": "idea", "limit": 20})
        assert ideas_only.status_code == 200
        rows = ideas_only.json()["items"]
        assert all(row["asset_type"] == "idea" for row in rows)


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
        web_ui = next((idea for idea in ideas if idea["id"] == "web-ui-governance"), None)
        assert web_ui is not None
        web_ui_questions = {q["question"] for q in web_ui["open_questions"]}
        assert "How can we improve the UI?" in web_ui_questions
        assert "What is missing from the UI for machine and human contributors?" in web_ui_questions
        assert "Which UI element has the highest actual value and least cost?" in web_ui_questions
        assert "Which UI element has the highest cost and least value?" in web_ui_questions
        required_core = set(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ()))
        listed_ids = {idea["id"] for idea in ideas}
        assert required_core.issubset(listed_ids)


@pytest.mark.asyncio
async def test_missing_default_idea_is_added_for_existing_portfolio_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio_path = tmp_path / "ideas.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "legacy-only",
                        "name": "Legacy idea",
                        "description": "pre-existing file without newer defaults",
                        "potential_value": 10.0,
                        "actual_value": 0.0,
                        "estimated_cost": 5.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.5,
                        "manifestation_status": "none",
                        "interfaces": ["human:web"],
                        "open_questions": [
                            {
                                "question": "Legacy open question?",
                                "value_to_whole": 1.0,
                                "estimated_cost": 1.0,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ideas = listed.json()["ideas"]
        assert any(idea["id"] == "web-ui-governance" for idea in ideas)
        listed_ids = {idea["id"] for idea in ideas}
        required_core = set(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ()))
        assert required_core.issubset(listed_ids)


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
                "answer": "Apply this answer to generate next implementation task.",
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
async def test_inventory_contributor_perspective_and_roi_rankings(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    link_payload = {
        "idea_id": "portfolio-governance",
        "spec_id": "054-web-ui-standing-questions-and-cost-value-signals",
        "implementation_refs": ["PR#ui-roi"],
        "contributors": {
            "idea": "human-alice",
            "spec": "codex-spec",
            "implementation": "human-bob",
            "review": "ci-review-bot",
        },
        "estimated_cost": 8.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/value-lineage/links", json=link_payload)
        assert created.status_code == 201
        lineage_id = created.json()["id"]
        usage = await client.post(
            f"/api/value-lineage/links/{lineage_id}/usage-events",
            json={"source": "api", "metric": "validated_flow", "value": 4.0},
        )
        assert usage.status_code == 201

        inventory = await client.get("/api/inventory/system-lineage", params={"runtime_window_seconds": 3600})
        assert inventory.status_code == 200
        data = inventory.json()

        by_perspective = data["contributors"]["by_perspective"]
        assert by_perspective["human"] >= 1
        assert by_perspective["machine"] >= 1

        roi = data["roi_insights"]
        assert isinstance(roi["most_estimated_roi"], list)
        assert isinstance(roi["least_estimated_roi"], list)
        assert isinstance(roi["missing_actual_roi_high_potential"], list)


@pytest.mark.asyncio
async def test_next_highest_estimated_roi_task_endpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suggest = await client.post("/api/inventory/roi/next-task")
        assert suggest.status_code == 200
        payload = suggest.json()
        assert payload["result"] == "task_suggested"
        assert payload["selection_basis"] == "estimated_roi_queue"
        assert payload["idea_estimated_roi"] >= 0

        created = await client.post("/api/inventory/roi/next-task", params={"create_task": True})
        assert created.status_code == 200
        created_payload = created.json()
        assert created_payload["result"] == "task_suggested"
        assert "created_task" in created_payload


@pytest.mark.asyncio
async def test_inventory_detects_duplicate_questions_and_exposes_quality_issue(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio_path = tmp_path / "ideas.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "dup-idea",
                        "name": "Duplicate question idea",
                        "description": "Has duplicate questions for issue detection",
                        "potential_value": 20.0,
                        "actual_value": 0.0,
                        "estimated_cost": 5.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.6,
                        "manifestation_status": "none",
                        "interfaces": ["human:web"],
                        "open_questions": [
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 5.0,
                                "estimated_cost": 1.0,
                            },
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 6.0,
                                "estimated_cost": 1.0,
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ideas = await client.get("/api/ideas")
        assert ideas.status_code == 200
        dup_idea = next((x for x in ideas.json()["ideas"] if x["id"] == "dup-idea"), None)
        assert dup_idea is not None
        questions = [q["question"] for q in dup_idea["open_questions"]]
        normalized = {" ".join(q.lower().split()) for q in questions}
        assert len(questions) == len(normalized)

        inventory = await client.get("/api/inventory/system-lineage")
        assert inventory.status_code == 200
        payload = inventory.json()
        dup = payload["quality_issues"]["duplicate_idea_questions"]
        assert dup["count"] == 0


@pytest.mark.asyncio
async def test_inventory_issue_scan_can_create_deduped_task(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio_path = tmp_path / "ideas.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "dup-idea",
                        "name": "Duplicate question idea",
                        "description": "Has duplicate questions for issue detection",
                        "potential_value": 20.0,
                        "actual_value": 0.0,
                        "estimated_cost": 5.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.6,
                        "manifestation_status": "none",
                        "interfaces": ["human:web"],
                        "open_questions": [
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 5.0,
                                "estimated_cost": 1.0,
                            },
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 6.0,
                                "estimated_cost": 1.0,
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setattr(
        idea_service,
        "REQUIRED_CORE_IDEA_IDS",
        tuple(list(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ())) + ["missing-core-for-scan-test"]),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/inventory/issues/scan", params={"create_tasks": True})
        assert first.status_code == 200
        p1 = first.json()
        assert p1["issues_count"] >= 1
        assert len(p1["created_tasks"]) == 1
        assert p1["created_tasks"][0]["deduped"] is False

        second = await client.post("/api/inventory/issues/scan", params={"create_tasks": True})
        assert second.status_code == 200
        p2 = second.json()
        assert p2["issues_count"] >= 1
        assert len(p2["created_tasks"]) == 1
        assert p2["created_tasks"][0]["deduped"] is True


@pytest.mark.asyncio
async def test_api_web_availability_scan_reports_gaps_and_can_create_tasks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.post("/api/inventory/availability/scan")
        assert report.status_code == 200
        payload = report.json()
        assert payload["api_routes_total"] >= 1
        assert payload["web_api_usage_paths_total"] >= 1
        assert isinstance(payload["gaps"], list)
        assert "why_previously_missed" in payload

        created = await client.post("/api/inventory/availability/scan", params={"create_tasks": True})
        assert created.status_code == 200
        created_payload = created.json()
        assert created_payload["create_tasks"] is True
        assert len(created_payload["generated_tasks"]) == created_payload["gaps_count"]


@pytest.mark.asyncio
async def test_evidence_contract_reports_violation_for_missing_core_idea(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio_path = tmp_path / "ideas.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "dup-idea",
                        "name": "Duplicate question idea",
                        "description": "Has duplicate questions for evidence violation",
                        "potential_value": 20.0,
                        "actual_value": 0.0,
                        "estimated_cost": 5.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.6,
                        "manifestation_status": "none",
                        "interfaces": ["human:web"],
                        "open_questions": [
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 5.0,
                                "estimated_cost": 1.0,
                            },
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 6.0,
                                "estimated_cost": 1.0,
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setattr(
        idea_service,
        "REQUIRED_CORE_IDEA_IDS",
        tuple(list(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ())) + ["missing-core-for-evidence-test"]),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        inventory = await client.get("/api/inventory/system-lineage")
        assert inventory.status_code == 200
        payload = inventory.json()
        violations = payload["evidence_contract"]["violations"]
        assert any(v["subsystem_id"] == "portfolio_completeness" for v in violations)


@pytest.mark.asyncio
async def test_evidence_scan_can_create_deduped_task(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio_path = tmp_path / "ideas.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "dup-idea",
                        "name": "Duplicate question idea",
                        "description": "Has duplicate questions for evidence violation",
                        "potential_value": 20.0,
                        "actual_value": 0.0,
                        "estimated_cost": 5.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.6,
                        "manifestation_status": "none",
                        "interfaces": ["human:web"],
                        "open_questions": [
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 5.0,
                                "estimated_cost": 1.0,
                            },
                            {
                                "question": "What is missing from the UI?",
                                "value_to_whole": 6.0,
                                "estimated_cost": 1.0,
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    monkeypatch.setattr(
        idea_service,
        "REQUIRED_CORE_IDEA_IDS",
        tuple(list(getattr(idea_service, "REQUIRED_CORE_IDEA_IDS", ())) + ["missing-core-for-test"]),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/inventory/evidence/scan", params={"create_tasks": True})
        assert first.status_code == 200
        p1 = first.json()
        assert p1["issues_count"] >= 1
        assert len(p1["created_tasks"]) >= 1
        assert p1["created_tasks"][0]["deduped"] is False

        second = await client.post("/api/inventory/evidence/scan", params={"create_tasks": True})
        assert second.status_code == 200
        p2 = second.json()
        assert p2["issues_count"] >= 1
        assert len(p2["created_tasks"]) >= 1
        assert p2["created_tasks"][0]["deduped"] is True


@pytest.mark.asyncio
async def test_auto_answer_high_roi_questions_updates_answers_and_creates_derived_ideas(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run = await client.post(
            "/api/inventory/questions/auto-answer",
            params={"limit": 20, "create_derived_ideas": True},
        )
        assert run.status_code == 200
        payload = run.json()
        assert payload["result"] == "completed"
        assert payload["answered_count"] >= 1

        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ideas = listed.json()["ideas"]
        assert any(
            any((q.get("answer") or "").strip() for q in idea["open_questions"])
            for idea in ideas
        )
        assert any(
            idea["id"] in {"tracking-maturity-scorecard", "tracking-audit-anomaly-detection"}
            for idea in ideas
        )


@pytest.mark.asyncio
async def test_roi_estimator_endpoint_exposes_weights_and_observations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("ROI_ESTIMATOR_PATH", str(tmp_path / "roi_estimator.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        estimator = await client.get("/api/inventory/roi/estimator")
        assert estimator.status_code == 200
        payload = estimator.json()
        assert "weights" in payload
        assert "suggested_weights" in payload
        assert "observations" in payload
        assert "formula" in payload

        patched = await client.patch(
            "/api/inventory/roi/estimator/weights",
            json={"question_multiplier": 1.2, "updated_by": "human:tester"},
        )
        assert patched.status_code == 200
        patched_payload = patched.json()
        assert patched_payload["weights"]["question_multiplier"] == 1.2


@pytest.mark.asyncio
async def test_roi_measurement_and_calibration_updates_estimator(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("ROI_ESTIMATOR_PATH", str(tmp_path / "roi_estimator.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        first = listed.json()["ideas"][0]
        question = first["open_questions"][0]["question"]
        answered = await client.post(
            f"/api/ideas/{first['id']}/questions/answer",
            json={
                "question": question,
                "answer": "Measure realized delta for calibration.",
                "measured_delta": 6.0,
            },
        )
        assert answered.status_code == 200

        measurement = await client.post(
            "/api/inventory/roi/estimator/measurements",
            json={
                "subject_type": "question",
                "subject_id": question,
                "idea_id": first["id"],
                "estimated_roi": 2.0,
                "actual_roi": 3.0,
                "measured_by": "codex:test",
                "source": "test",
            },
        )
        assert measurement.status_code == 200
        m_payload = measurement.json()
        assert m_payload["result"] == "measurement_recorded"

        calibration = await client.post(
            "/api/inventory/roi/estimator/calibrate",
            params={"apply": True, "min_samples": 1, "calibrated_by": "codex:test"},
        )
        assert calibration.status_code == 200
        c_payload = calibration.json()
        assert c_payload["result"] in {"calibrated", "calibration_suggested_only"}
        assert "run" in c_payload
        assert "estimator" in c_payload
