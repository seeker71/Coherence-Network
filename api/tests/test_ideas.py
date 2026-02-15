from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import idea_service


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
                "answered_by": "human:tester",
                "evidence_refs": ["specs/050-canonical-route-registry-and-runtime-mapping.md"],
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
        assert found["answered_by"] == "human:tester"
        assert "specs/050-canonical-route-registry-and-runtime-mapping.md" in (found.get("evidence_refs") or [])


@pytest.mark.asyncio
async def test_living_codex_csharp_top_roi_ideas_are_seeded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    expected_ids = {
        "living-codex-csharp-profile-edit-completion",
        "living-codex-csharp-concept-creation-ui",
        "living-codex-csharp-contribution-dashboard-ui",
        "living-codex-csharp-enhanced-news-ui",
        "living-codex-csharp-graph-visualization-ui",
        "living-codex-csharp-people-discovery-ui",
        "living-codex-csharp-portal-management-ui",
        "living-codex-csharp-ucore-ontology-browser-ui",
        "living-codex-csharp-realtime-ui-completion",
        "living-codex-csharp-temporal-ui",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")

    assert listed.status_code == 200
    ids = {idea["id"] for idea in listed.json()["ideas"]}
    assert expected_ids.issubset(ids)


@pytest.mark.asyncio
async def test_ideas_can_load_defaults_from_typed_seed_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    seed_path = tmp_path / "idea_defaults.json"
    seed_path.write_text(
        json.dumps(
            {
                "ideas": [
                    {
                        "id": "seed-test-idea",
                        "name": "Seed test idea",
                        "description": "Loaded from typed JSON seed.",
                        "potential_value": 55.0,
                        "actual_value": 0.0,
                        "estimated_cost": 6.0,
                        "actual_cost": 0.0,
                        "resistance_risk": 2.0,
                        "confidence": 0.8,
                        "manifestation_status": "none",
                        "interfaces": ["machine:api"],
                        "open_questions": [
                            {
                                "question": "Is typed seed loading active?",
                                "value_to_whole": 9.0,
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
    monkeypatch.setenv("IDEA_DEFAULTS_PATH", str(seed_path))
    monkeypatch.setattr(idea_service, "_DEFAULT_IDEAS_CACHE", None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")

    assert listed.status_code == 200
    ids = {idea["id"] for idea in listed.json()["ideas"]}
    assert "seed-test-idea" in ids
