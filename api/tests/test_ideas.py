from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_ideas_returns_ranked_scores_and_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas")

    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data
    assert "summary" in data
    assert data["summary"]["total_ideas"] >= 1
    assert all("free_energy_score" in idea for idea in data["ideas"])

    scores = [idea["free_energy_score"] for idea in data["ideas"]]
    assert scores == sorted(scores, reverse=True)
    assert portfolio_path.exists()


@pytest.mark.asyncio
async def test_get_idea_by_id_and_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        idea_id = listed.json()["ideas"][0]["id"]

        found = await client.get(f"/api/ideas/{idea_id}")
        missing = await client.get("/api/ideas/does-not-exist")

    assert found.status_code == 200
    assert found.json()["id"] == idea_id
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_get_idea_returns_known_derived_runtime_idea(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        derived = await client.get("/api/ideas/coherence-network-agent-pipeline")

    assert derived.status_code == 200
    payload = derived.json()
    assert payload["id"] == "coherence-network-agent-pipeline"
    assert payload["name"] == "Coherence network agent pipeline"


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
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        idea_id = listed.json()["ideas"][0]["id"]

        patched = await client.patch(
            f"/api/ideas/{idea_id}",
            json={
                "actual_value": 34.5,
                "actual_cost": 8.0,
                "confidence": 0.75,
                "manifestation_status": "validated",
            },
        )

        refetched = await client.get(f"/api/ideas/{idea_id}")

    assert patched.status_code == 200
    payload = refetched.json()
    assert payload["actual_value"] == 34.5
    assert payload["actual_cost"] == 8.0
    assert payload["confidence"] == 0.75
    assert payload["manifestation_status"] == "validated"

    raw = json.loads(portfolio_path.read_text(encoding="utf-8"))
    assert any(item["id"] == idea_id and item["manifestation_status"] == "validated" for item in raw["ideas"])


@pytest.mark.asyncio
async def test_answer_idea_question_persists_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        idea = listed.json()["ideas"][0]
        idea_id = idea["id"]
        question = idea["open_questions"][0]["question"]

        answered = await client.post(
            f"/api/ideas/{idea_id}/questions/answer",
            json={
                "question": question,
                "answer": "Canonical route set is /api/inventory/routes/canonical",
                "measured_delta": 3.5,
            },
        )
        assert answered.status_code == 200
        refetched = await client.get(f"/api/ideas/{idea_id}")
        assert refetched.status_code == 200
        found = [
            q
            for q in refetched.json()["open_questions"]
            if q["question"] == question
        ][0]
        assert found["answer"] is not None
        assert found["measured_delta"] == 3.5


@pytest.mark.asyncio
async def test_ideas_storage_endpoint_reports_structured_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("IDEA_REGISTRY_DATABASE_URL", raising=False)
    monkeypatch.delenv("IDEA_REGISTRY_DB_URL", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_load = await client.get("/api/ideas")
        assert first_load.status_code == 200
        storage = await client.get("/api/ideas/storage")
        assert storage.status_code == 200

    data = storage.json()
    assert data["backend"] == "sqlite"
    assert data["idea_count"] >= 1
    assert data["question_count"] >= 1
    assert "bootstrap_source" in data
    assert data["database_url"].startswith("sqlite")

    db_path = portfolio_path.with_suffix(".db")
    assert db_path.exists()


@pytest.mark.asyncio
async def test_legacy_json_bootstraps_into_structured_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "custom-db-bootstrap",
                        "name": "Custom bootstrap idea",
                        "description": "Legacy file import should seed DB registry.",
                        "potential_value": 20.0,
                        "actual_value": 0.0,
                        "estimated_cost": 4.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.6,
                        "manifestation_status": "none",
                        "interfaces": ["machine:api"],
                        "open_questions": [
                            {
                                "question": "Can legacy JSON seed DB?",
                                "value_to_whole": 10.0,
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
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("IDEA_REGISTRY_DATABASE_URL", raising=False)
    monkeypatch.delenv("IDEA_REGISTRY_DB_URL", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        assert listed.status_code == 200
        ids = [row["id"] for row in listed.json()["ideas"]]
        assert "custom-db-bootstrap" in ids
        storage = await client.get("/api/ideas/storage")
        assert storage.status_code == 200
        assert str(storage.json()["bootstrap_source"]).startswith("legacy_json")


@pytest.mark.asyncio
async def test_required_federation_idea_is_backfilled_for_existing_portfolio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    portfolio_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "custom-local-only",
                        "name": "Custom local idea",
                        "description": "Existing portfolio should retain custom ideas while system ideas are backfilled.",
                        "potential_value": 18.0,
                        "actual_value": 0.0,
                        "estimated_cost": 5.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 1.0,
                        "confidence": 0.55,
                        "manifestation_status": "none",
                        "interfaces": ["machine:api"],
                        "open_questions": [],
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
        by_id = {row["id"]: row for row in ideas}
        assert "custom-local-only" in by_id
        assert "federated-instance-aggregation" in by_id
        federation = by_id["federated-instance-aggregation"]
        assert federation["manifestation_status"] == "none"
        assert federation["potential_value"] >= 100.0
        assert any("federation contract" in q["question"].lower() for q in federation["open_questions"])
