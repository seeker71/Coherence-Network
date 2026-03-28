"""Acceptance tests for spec 138: Idea Lifecycle Management (idea-e92e6d043871)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.idea import IdeaStage, ManifestationStatus
from app.services import idea_service

AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _base_idea_payload(idea_id: str) -> dict:
    return {
        "id": idea_id,
        "name": "Lifecycle test",
        "description": "Spec 138 acceptance coverage.",
        "potential_value": 10.0,
        "estimated_cost": 2.0,
        "confidence": 0.7,
    }


@pytest.mark.asyncio
async def test_advance_none_to_specced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-advance-one"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)
        assert create.status_code == 201
        assert create.json()["stage"] == "none"

        adv = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert adv.status_code == 200
        body = adv.json()
        assert body["stage"] == "specced"
        assert body["manifestation_status"] == "partial"


@pytest.mark.asyncio
async def test_advance_through_all_stages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-advance-all"
    expected = ["specced", "implementing", "testing", "reviewing", "complete"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)
        assert create.status_code == 201

        for want in expected:
            resp = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
            assert resp.status_code == 200
            assert resp.json()["stage"] == want


@pytest.mark.asyncio
async def test_advance_complete_returns_409(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-complete-409"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)).status_code == 201
        for _ in range(5):
            r = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
            assert r.status_code == 200

        final = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert final.status_code == 409
        assert "complete" in final.json()["detail"].lower()


@pytest.mark.asyncio
async def test_skip_stage_returns_422(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Reject requests that cannot be coerced to a valid stage (missing required field)."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-skip-422"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)).status_code == 201
        bad = await client.post(f"/api/ideas/{idea_id}/stage", json={}, headers=AUTH_HEADERS)
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_set_stage_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-set-stage"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)).status_code == 201
        resp = await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": "implementing"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["stage"] == "implementing"
        assert resp.json()["manifestation_status"] == "partial"


@pytest.mark.asyncio
async def test_set_invalid_stage_returns_422(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-invalid-stage"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)).status_code == 201
        bad = await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": "not_a_valid_lifecycle_stage"},
            headers=AUTH_HEADERS,
        )
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_auto_advance_on_spec_task(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-auto-spec"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)).status_code == 201

    idea_service.auto_advance_for_task(idea_id, "spec")
    refreshed = idea_service.get_idea(idea_id)
    assert refreshed is not None
    assert refreshed.stage == IdeaStage.SPECCED


@pytest.mark.asyncio
async def test_auto_advance_noop_if_already_past(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-auto-noop"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)).status_code == 201
        r = await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": "testing"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200

    idea_service.auto_advance_for_task(idea_id, "spec")
    refreshed = idea_service.get_idea(idea_id)
    assert refreshed is not None
    assert refreshed.stage == IdeaStage.TESTING


@pytest.mark.asyncio
async def test_progress_dashboard_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i, st in enumerate(["none", "specced", "complete"]):
            rid = f"lc-dash-{i}"
            assert (
                await client.post("/api/ideas", json=_base_idea_payload(rid), headers=AUTH_HEADERS)
            ).status_code == 201
            if st != "none":
                await client.post(
                    f"/api/ideas/{rid}/stage",
                    json={"stage": st},
                    headers=AUTH_HEADERS,
                )

        resp = await client.get("/api/ideas/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ideas"] == 3
        by_stage = data["by_stage"]
        assert by_stage["none"]["count"] == 1
        assert "lc-dash-0" in by_stage["none"]["idea_ids"]
        assert by_stage["specced"]["count"] == 1
        assert "lc-dash-1" in by_stage["specced"]["idea_ids"]
        assert by_stage["complete"]["count"] == 1
        assert "lc-dash-2" in by_stage["complete"]["idea_ids"]


@pytest.mark.asyncio
async def test_progress_completion_pct(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(2):
            rid = f"lc-pct-{i}"
            assert (
                await client.post("/api/ideas", json=_base_idea_payload(rid), headers=AUTH_HEADERS)
            ).status_code == 201
        await client.post(
            "/api/ideas/lc-pct-0/stage",
            json={"stage": "complete"},
            headers=AUTH_HEADERS,
        )

        resp = await client.get("/api/ideas/progress")
        assert resp.status_code == 200
        assert resp.json()["completion_pct"] == 0.5


@pytest.mark.asyncio
async def test_stage_syncs_manifestation_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-manifest"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)
        assert c.json()["manifestation_status"] == "none"

        a1 = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert a1.json()["stage"] == "specced"
        assert a1.json()["manifestation_status"] == "partial"

        for _ in range(4):
            await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        done = await client.get(f"/api/ideas/{idea_id}")
        assert done.json()["stage"] == "complete"
        assert done.json()["manifestation_status"] == "validated"


@pytest.mark.asyncio
async def test_new_idea_defaults_to_none_stage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "lc-default-stage"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/ideas", json=_base_idea_payload(idea_id), headers=AUTH_HEADERS)
        assert c.status_code == 201
        assert c.json()["stage"] == "none"

    raw = idea_service.get_idea(idea_id)
    assert raw is not None
    assert raw.stage == IdeaStage.NONE
    assert raw.manifestation_status == ManifestationStatus.NONE
