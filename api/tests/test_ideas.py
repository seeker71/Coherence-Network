from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_ideas_returns_ranked_scores_and_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed one idea so the list is non-empty
        created = await client.post("/api/ideas", json={
            "id": "test-ranking",
            "name": "Test Ranking",
            "description": "Verify ranking and scoring.",
            "potential_value": 50.0,
            "estimated_cost": 10.0,
            "confidence": 0.8,
        })
        assert created.status_code == 201

        resp = await client.get("/api/ideas")

    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data
    assert "summary" in data
    assert data["summary"]["total_ideas"] >= 1
    assert all("free_energy_score" in idea for idea in data["ideas"])

    scores = [idea["free_energy_score"] for idea in data["ideas"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_get_idea_by_id_and_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "get-test", "name": "Get Test", "description": "d",
            "potential_value": 10.0, "estimated_cost": 5.0,
        })
        found = await client.get("/api/ideas/get-test")
        missing = await client.get("/api/ideas/does-not-exist")

    assert found.status_code == 200
    assert found.json()["id"] == "get-test"
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_get_idea_returns_known_derived_runtime_idea(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed the idea into the test DB first (DB is the sole source of truth)
        created = await client.post("/api/ideas", json={
            "id": "coherence-network-agent-pipeline",
            "name": "Agent pipeline: visible, recoverable, and self-healing",
            "description": "The background work loop picks tasks, executes them, records results, and heals when stuck.",
            "potential_value": 88.0,
            "estimated_cost": 16.0,
            "confidence": 0.95,
            "interfaces": ["machine:api", "machine:automation", "human:operators"],
        })
        assert created.status_code == 201

        derived = await client.get("/api/ideas/coherence-network-agent-pipeline")

    assert derived.status_code == 200
    payload = derived.json()
    assert payload["id"] == "coherence-network-agent-pipeline"
    assert "agent pipeline" in payload["name"].lower()


@pytest.mark.asyncio
async def test_list_ideas_can_hide_internal_system_generated_ideas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": "internal-cleanup-seed-1234abcd",
                "name": "Internal seed",
                "description": "System-generated idea should be hidden from actionable lists.",
                "potential_value": 10.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
                "interfaces": ["machine:commit-evidence"],
                "open_questions": [],
            },
        )
        assert created.status_code == 201
        assert created.json()["open_questions"] == []

        include_all = await client.get("/api/ideas?include_internal=true")
        assert include_all.status_code == 200
        assert any(row["id"] == "internal-cleanup-seed-1234abcd" for row in include_all.json()["ideas"])

        actionable_only = await client.get("/api/ideas?include_internal=false")
        assert actionable_only.status_code == 200
        assert all(row["id"] != "internal-cleanup-seed-1234abcd" for row in actionable_only.json()["ideas"])


@pytest.mark.asyncio
async def test_list_ideas_prunes_transient_public_e2e_idea_ids_from_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.setenv("IDEA_SYNC_ENABLE_DOMAIN_DISCOVERY", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'ideas.db'}")
    monkeypatch.setattr("app.services.spec_registry_service.list_specs", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.services.runtime_service.summarize_by_idea", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.services.value_lineage_service.list_links",
        lambda *args, **kwargs: [
            SimpleNamespace(idea_id="public-e2e-deadbeef"),
            SimpleNamespace(idea_id="public-e2e-flow-gate-automation"),
            SimpleNamespace(idea_id="spec-origin-cleanup-seed-1234abcd"),
            SimpleNamespace(idea_id="endpoint-lineage-health-check-1234abcd"),
            SimpleNamespace(idea_id="discovered-non-transient"),
        ],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas?include_internal=true&limit=500")

    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["ideas"]}
    assert "public-e2e-deadbeef" not in ids
    assert "spec-origin-cleanup-seed-1234abcd" not in ids
    assert "endpoint-lineage-health-check-1234abcd" not in ids
    assert "deployment-gate-reliability" in ids
    assert "public-e2e-flow-gate-automation" in ids
    assert "portfolio-governance" in ids
    assert "oss-interface-alignment" in ids
    assert "discovered-non-transient" in ids


@pytest.mark.asyncio
async def test_create_idea_and_add_question(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    idea_id = f"new-contributor-idea-{uuid4().hex[:8]}"

    create_payload = {
        "id": idea_id,
        "name": "Contributor-originated idea",
        "description": "Created through API for attribution pipeline.",
        "potential_value": 35.0,
        "estimated_cost": 8.0,
        "confidence": 0.6,
        "interfaces": ["human:web", "machine:api"],
        "open_questions": [
            {"question": "What is the first measurable milestone?", "value_to_whole": 10.0, "estimated_cost": 2.0}
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/ideas", json=create_payload)
        assert created.status_code == 201
        assert created.json()["id"] == idea_id

        duplicate = await client.post("/api/ideas", json=create_payload)
        assert duplicate.status_code == 409

        add_question = await client.post(
            f"/api/ideas/{idea_id}/questions",
            json={
                "question": "How should this be validated publicly?",
                "value_to_whole": 12.0,
                "estimated_cost": 1.0,
            },
        )
        assert add_question.status_code == 200

        add_question_duplicate = await client.post(
            f"/api/ideas/{idea_id}/questions",
            json={
                "question": "How should this be validated publicly?",
                "value_to_whole": 12.0,
                "estimated_cost": 1.0,
            },
        )
        assert add_question_duplicate.status_code == 409


@pytest.mark.asyncio
async def test_patch_idea_updates_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "patch-test", "name": "Patch Test", "description": "d",
            "potential_value": 50.0, "estimated_cost": 10.0,
        })

        patched = await client.patch(
            "/api/ideas/patch-test",
            json={
                "actual_value": 34.5,
                "actual_cost": 8.0,
                "confidence": 0.75,
                "manifestation_status": "validated",
            },
        )

        refetched = await client.get("/api/ideas/patch-test")

    assert patched.status_code == 200
    payload = refetched.json()
    assert payload["actual_value"] == 34.5
    assert payload["actual_cost"] == 8.0
    assert payload["confidence"] == 0.75
    assert payload["manifestation_status"] == "validated"


@pytest.mark.asyncio
async def test_answer_idea_question_persists_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "answer-test", "name": "Answer Test", "description": "d",
            "potential_value": 30.0, "estimated_cost": 5.0,
            "open_questions": [
                {"question": "What route is canonical?", "value_to_whole": 10.0, "estimated_cost": 1.0}
            ],
        })

        answered = await client.post(
            "/api/ideas/answer-test/questions/answer",
            json={
                "question": "What route is canonical?",
                "answer": "Canonical route set is /api/inventory/routes/canonical",
                "measured_delta": 3.5,
            },
        )
        assert answered.status_code == 200
        refetched = await client.get("/api/ideas/answer-test")
        assert refetched.status_code == 200
        found = [
            q
            for q in refetched.json()["open_questions"]
            if q["question"] == "What route is canonical?"
        ][0]
        assert found["answer"] is not None
        assert found["measured_delta"] == 3.5


@pytest.mark.asyncio
async def test_ideas_storage_endpoint_reports_structured_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "storage-test", "name": "Storage Test", "description": "d",
            "potential_value": 10.0, "estimated_cost": 5.0,
        })
        storage = await client.get("/api/ideas/storage")
        assert storage.status_code == 200

    data = storage.json()
    assert data["backend"] == "sqlite"
    assert data["idea_count"] >= 1
    assert "bootstrap_source" in data
    assert data["database_url"].startswith("sqlite")


@pytest.mark.asyncio
async def test_db_is_sole_source_of_truth_for_ideas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DB reader returns only what's in the DB — no legacy JSON bootstrap."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    from app.services import idea_registry_service, idea_service
    from app.models.idea import Idea
    idea_service._invalidate_ideas_cache()
    idea_registry_service.save_ideas([
        Idea(
            id="db-only-idea", name="DB Only", description="Created directly in DB.",
            potential_value=20.0, estimated_cost=4.0, confidence=0.6,
            manifestation_status="none", interfaces=["machine:api"],
        )
    ], bootstrap_source="test")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ids = [row["id"] for row in listed.json()["ideas"]]
        assert "db-only-idea" in ids


@pytest.mark.asyncio
async def test_empty_db_returns_no_ideas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When DB is empty, list_ideas returns empty — no magic bootstrap."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    from app.services import idea_service
    idea_service._invalidate_ideas_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ideas = listed.json()["ideas"]
        # Empty DB = no seeded defaults at runtime
        assert isinstance(ideas, list)


@pytest.mark.asyncio
async def test_create_idea_persists_to_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ideas created via API persist in the DB and survive cache invalidation."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/ideas", json={
            "id": "test-persist",
            "name": "Test Persistence",
            "description": "Verify idea survives cache clear.",
            "potential_value": 30.0,
            "estimated_cost": 5.0,
            "confidence": 0.7,
        })
        assert created.status_code == 201

        from app.services import idea_service
        idea_service._invalidate_ideas_cache()

        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ids = [row["id"] for row in listed.json()["ideas"]]
        assert "test-persist" in ids


@pytest.mark.asyncio
async def test_ideas_cards_endpoint_returns_paginated_card_feed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/ideas", json={
            "id": "cards-test", "name": "Cards Test", "description": "d",
            "potential_value": 40.0, "estimated_cost": 8.0,
        })
        response = await client.get(
            "/api/ideas/cards",
            params={"limit": 10, "state": "all", "sort": "attention_desc"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("items"), list)
    assert payload["pagination"]["limit"] == 10
    assert payload["summary"]["total"] >= len(payload["items"])
    assert isinstance(payload.get("change_token"), str) and payload["change_token"]
    assert len(payload["items"]) >= 1
    first = payload["items"][0]
    assert "idea_id" in first
    assert "state" in first
    assert "state_icon" in first
    assert "attention_level" in first
    assert isinstance(first.get("links"), dict)


@pytest.mark.asyncio
async def test_ideas_cards_changes_endpoint_detects_no_change_for_same_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("COMMIT_EVIDENCE_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'commit_evidence.db'}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cards = await client.get("/api/ideas/cards", params={"limit": 5})
        assert cards.status_code == 200
        token = cards.json().get("change_token")
        assert isinstance(token, str) and token

        unchanged = await client.get("/api/ideas/cards/changes", params={"since_token": token})
        assert unchanged.status_code == 200
        unchanged_payload = unchanged.json()
        assert unchanged_payload["changed"] is False
        assert unchanged_payload["token"] == token

        initial = await client.get("/api/ideas/cards/changes")
        assert initial.status_code == 200
        assert initial.json()["changed"] is True


@pytest.mark.asyncio
async def test_ideas_cards_defaults_include_internal_and_allow_actionable_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("COMMIT_EVIDENCE_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'commit_evidence.db'}")

    internal_id = "internal-cards-hidden-example"
    external_id = "cards-visible-example"
    base_payload = {
        "name": "Cards Example",
        "description": "Cards endpoint visibility test.",
        "potential_value": 14.0,
        "estimated_cost": 2.0,
        "confidence": 0.6,
        "interfaces": ["machine:api"],
        "open_questions": [],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_internal = await client.post(
            "/api/ideas",
            json={
                "id": internal_id,
                **base_payload,
                "interfaces": ["machine:commit-evidence"],
            },
        )
        assert create_internal.status_code == 201
        create_external = await client.post("/api/ideas", json={"id": external_id, **base_payload})
        assert create_external.status_code == 201

        defaults = await client.get("/api/ideas/cards", params={"limit": 200})
        assert defaults.status_code == 200
        default_ids = {row["idea_id"] for row in defaults.json().get("items", [])}
        assert internal_id in default_ids
        assert external_id in default_ids

        actionable_only = await client.get(
            "/api/ideas/cards",
            params={"limit": 200, "only_actionable": "true", "include_internal_ideas": "false"},
        )
        assert actionable_only.status_code == 200
        actionable_ids = {row["idea_id"] for row in actionable_only.json().get("items", [])}
        assert external_id in actionable_ids
        assert internal_id not in actionable_ids
