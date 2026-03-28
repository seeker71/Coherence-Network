"""Acceptance tests for spec 138: idea lifecycle stages."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.idea import IdeaStage
from app.services import idea_service

AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _new_id(prefix: str = "lifecycle") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


@pytest.mark.asyncio
async def test_advance_none_to_specced() -> None:
    idea_id = _new_id("adv-none")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Advance test",
                "description": "Lifecycle advance from none.",
                "potential_value": 10.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201
        assert created.json()["stage"] == "none"

        adv = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert adv.status_code == 200
        assert adv.json()["stage"] == "specced"


@pytest.mark.asyncio
async def test_advance_through_all_stages() -> None:
    idea_id = _new_id("adv-all")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post(
                "/api/ideas",
                json={
                    "id": idea_id,
                    "name": "Full pipeline",
                    "description": "Walk all stages.",
                    "potential_value": 12.0,
                    "estimated_cost": 3.0,
                    "confidence": 0.5,
                },
                headers=AUTH_HEADERS,
            )
        ).status_code == 201

        order = ["specced", "implementing", "testing", "reviewing", "complete"]
        for expected in order:
            r = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
            assert r.status_code == 200, r.text
            assert r.json()["stage"] == expected


@pytest.mark.asyncio
async def test_advance_complete_returns_409() -> None:
    idea_id = _new_id("adv-409")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Done",
                "description": "Already complete.",
                "potential_value": 8.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        for _ in range(5):
            await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)

        r = await client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert r.status_code == 409
        assert "complete" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_skip_stage_returns_422() -> None:
    idea_id = _new_id("skip")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Skip test",
                "description": "PATCH cannot skip stages.",
                "potential_value": 9.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        r = await client.patch(
            f"/api/ideas/{idea_id}",
            json={"stage": "testing"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert isinstance(detail, str)
        assert "skip" in detail.lower() or "next allowed" in detail.lower()


@pytest.mark.asyncio
async def test_set_stage_explicit() -> None:
    idea_id = _new_id("set")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Explicit stage",
                "description": "Admin override.",
                "potential_value": 11.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        r = await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": "implementing"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["stage"] == "implementing"


@pytest.mark.asyncio
async def test_set_invalid_stage_returns_422() -> None:
    idea_id = _new_id("bad-stage")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Bad stage",
                "description": "Invalid enum.",
                "potential_value": 5.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        r = await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": "not_a_valid_stage"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_auto_advance_on_spec_task() -> None:
    idea_id = _new_id("auto-spec")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Auto spec",
                "description": "Spec task completion.",
                "potential_value": 7.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
    idea_service.auto_advance_for_task(idea_id, "spec")
    got = idea_service.get_idea(idea_id)
    assert got is not None
    assert got.stage == IdeaStage.SPECCED


@pytest.mark.asyncio
async def test_auto_advance_noop_if_already_past() -> None:
    idea_id = _new_id("auto-noop")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Noop",
                "description": "Already past target.",
                "potential_value": 6.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        await client.post(
            f"/api/ideas/{idea_id}/stage",
            json={"stage": "complete"},
            headers=AUTH_HEADERS,
        )
    idea_service.auto_advance_for_task(idea_id, "spec")
    got = idea_service.get_idea(idea_id)
    assert got is not None
    assert got.stage == IdeaStage.COMPLETE


@pytest.mark.asyncio
async def test_progress_dashboard_counts() -> None:
    ids = [_new_id("prog-a"), _new_id("prog-b"), _new_id("prog-c")]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i, idea_id in enumerate(ids):
            await client.post(
                "/api/ideas",
                json={
                    "id": idea_id,
                    "name": f"P{i}",
                    "description": "Progress bucket.",
                    "potential_value": 5.0,
                    "estimated_cost": 1.0,
                    "confidence": 0.5,
                },
                headers=AUTH_HEADERS,
            )
        await client.post(f"/api/ideas/{ids[1]}/stage", json={"stage": "specced"}, headers=AUTH_HEADERS)
        await client.post(f"/api/ideas/{ids[2]}/stage", json={"stage": "complete"}, headers=AUTH_HEADERS)

        r = await client.get("/api/ideas/progress")
        assert r.status_code == 200
        data = r.json()
        assert data["total_ideas"] >= 3
        assert "by_stage" in data
        assert data["by_stage"]["none"]["count"] >= 1
        assert ids[0] in data["by_stage"]["none"]["idea_ids"]
        assert ids[1] in data["by_stage"]["specced"]["idea_ids"]
        assert ids[2] in data["by_stage"]["complete"]["idea_ids"]


@pytest.mark.asyncio
async def test_progress_completion_pct() -> None:
    idea_id = _new_id("pct")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Pct",
                "description": "Completion fraction.",
                "potential_value": 4.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        before = await client.get("/api/ideas/progress")
        total_before = before.json()["total_ideas"]
        complete_before = before.json()["by_stage"]["complete"]["count"]

        await client.post(f"/api/ideas/{idea_id}/stage", json={"stage": "complete"}, headers=AUTH_HEADERS)
        after = await client.get("/api/ideas/progress")
        body = after.json()
        assert body["total_ideas"] == total_before
        assert body["by_stage"]["complete"]["count"] == complete_before + 1
        expected_pct = round((complete_before + 1) / total_before, 4) if total_before else 0.0
        assert body["completion_pct"] == pytest.approx(expected_pct, abs=1e-4)


@pytest.mark.asyncio
async def test_stage_syncs_manifestation_status() -> None:
    idea_id = _new_id("sync")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Sync",
                "description": "Manifestation sync.",
                "potential_value": 8.0,
                "estimated_cost": 2.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        r1 = await client.post(f"/api/ideas/{idea_id}/stage", json={"stage": "specced"}, headers=AUTH_HEADERS)
        assert r1.json()["manifestation_status"] == "partial"

        r2 = await client.post(f"/api/ideas/{idea_id}/stage", json={"stage": "complete"}, headers=AUTH_HEADERS)
        assert r2.json()["manifestation_status"] == "validated"


@pytest.mark.asyncio
async def test_new_idea_defaults_to_none_stage() -> None:
    idea_id = _new_id("default-stage")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Default",
                "description": "Default stage none.",
                "potential_value": 3.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 201
        assert r.json()["stage"] == "none"
