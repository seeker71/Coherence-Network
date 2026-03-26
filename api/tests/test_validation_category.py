"""Validation category on ideas: API, inference, verification hooks."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.idea import Idea, IdeaStage, ManifestationStatus, ValidationCategory
from app.services.idea_validation_category import (
    infer_validation_category,
    review_prompt_addendum_for_category,
    verify_for_category,
)

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_create_read_patch_validation_category(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": "vc-net-1",
                "name": "Network check",
                "description": "Uses GET /api/health",
                "potential_value": 1.0,
                "estimated_cost": 1.0,
                "validation_category": "network_internal",
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201
        assert created.json()["validation_category"] == "network_internal"

        got = await client.get("/api/ideas/vc-net-1")
        assert got.status_code == 200
        assert got.json()["validation_category"] == "network_internal"

        patched = await client.patch(
            "/api/ideas/vc-net-1",
            json={"validation_category": "research"},
            headers=AUTH_HEADERS,
        )
        assert patched.status_code == 200
        assert patched.json()["validation_category"] == "research"

        bad = await client.patch(
            "/api/ideas/vc-net-1",
            json={"validation_category": "not_a_category"},
            headers=AUTH_HEADERS,
        )
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_infer_infrastructure_when_category_omitted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": "vc-inf-1",
                "name": "Ops",
                "description": "monitoring uptime SLA for the deployment pipeline",
                "potential_value": 2.0,
                "estimated_cost": 1.0,
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201
        assert created.json()["validation_category"] == "infrastructure"


def test_infer_validation_category_defaults() -> None:
    assert infer_validation_category([], "") == ValidationCategory.NETWORK_INTERNAL
    assert infer_validation_category(["machine:api"], "hello") == ValidationCategory.NETWORK_INTERNAL


def test_verify_for_category_structure() -> None:
    idea = Idea(
        id="x",
        name="X",
        description="See https://example.com proof",
        potential_value=1.0,
        estimated_cost=1.0,
        validation_category=ValidationCategory.EXTERNAL_PROJECT,
        interfaces=[],
    )
    out = verify_for_category(idea)
    assert out["category"] == "external_project"
    assert "passed" in out
    assert "summary" in out
    assert isinstance(out["checks"], list)


def test_review_prompt_addendum_keywords() -> None:
    net = review_prompt_addendum_for_category("network_internal")
    ext = review_prompt_addendum_for_category("external_project")
    assert "GET /api/health" in net or "/api/" in net
    assert "evidence" in ext.lower() or "screenshot" in ext.lower() or "link" in ext.lower()


def test_verify_research_with_stage() -> None:
    idea = Idea(
        id="r1",
        name="R",
        description="paper",
        potential_value=1.0,
        estimated_cost=1.0,
        stage=IdeaStage.SPECCED,
        manifestation_status=ManifestationStatus.NONE,
        validation_category=ValidationCategory.RESEARCH,
    )
    out = verify_for_category(idea)
    assert out["passed"] is True
