from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app
from app.models.asset import Asset, AssetType
from app.models.contribution import Contribution
from app.models.contributor import Contributor, ContributorType
from app.services.contributor_hygiene import (
    is_internal_contributor_email,
    is_real_human_name,
    is_test_contributor_email,
    normalize_contributor_email,
    validate_real_human_registration,
)


def test_is_test_contributor_email_recognizes_reserved_domains() -> None:
    assert is_test_contributor_email("test@example.com") is True
    assert is_test_contributor_email("alice@example.org") is True
    assert is_test_contributor_email("dev@example.net") is True
    assert is_test_contributor_email("alice@coherence.network") is False


def test_normalize_contributor_email_collapses_plus_alias_by_default() -> None:
    assert normalize_contributor_email("Urs-Muff+abc123@coherence.network") == "urs-muff@coherence.network"
    assert normalize_contributor_email("alice@example.com") == "alice@example.com"


def test_is_internal_contributor_email_detects_system_prefixes() -> None:
    assert is_internal_contributor_email("deploy-test@coherence.network") is True
    assert is_internal_contributor_email("machine-reviewer-1@coherence.network") is True
    assert is_internal_contributor_email("system@coherence.network") is True
    assert is_internal_contributor_email("urs-muff@coherence.network") is False


def test_real_human_name_requires_first_and_last_name() -> None:
    assert is_real_human_name("Alice Smith") is True
    assert is_real_human_name("Jean-Luc Picard") is True
    assert is_real_human_name("Alice") is False
    assert is_real_human_name("Automation Bot") is False


def test_validate_real_human_registration_rejects_internal_or_test_emails() -> None:
    ok, _ = validate_real_human_registration("Alice Smith", "alice@proton.me")
    assert ok is True

    bad_internal, reason_internal = validate_real_human_registration("Alice Smith", "deploy-test@coherence.network")
    assert bad_internal is False
    assert "Internal/system" in reason_internal

    bad_test, reason_test = validate_real_human_registration("Alice Smith", "alice@example.com")
    assert bad_test is False
    assert "Test or placeholder" in reason_test


@pytest.mark.asyncio
async def test_persistent_store_rejects_test_email_contributor(tmp_path: Path) -> None:
    app.state.graph_store = InMemoryGraphStore(persist_path=str(tmp_path / "graph_store.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blocked = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Test User", "email": "test@example.com"},
        )
        assert blocked.status_code == 422

        allowed = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Real User", "email": "real@coherence.network"},
        )
        assert allowed.status_code == 201


def test_persistent_load_purges_test_contributors_and_their_contributions(tmp_path: Path) -> None:
    path = tmp_path / "graph_store.json"

    test_contributor = Contributor(
        type=ContributorType.HUMAN,
        name="Test User",
        email="test@example.com",
    )
    real_contributor = Contributor(
        type=ContributorType.HUMAN,
        name="Real User",
        email="real@coherence.network",
    )
    asset = Asset(type=AssetType.CODE, description="Repo")
    test_contribution = Contribution(
        contributor_id=test_contributor.id,
        asset_id=asset.id,
        cost_amount=Decimal("1.00"),
        coherence_score=0.5,
        metadata={},
    )
    real_contribution = Contribution(
        contributor_id=real_contributor.id,
        asset_id=asset.id,
        cost_amount=Decimal("2.00"),
        coherence_score=0.8,
        metadata={},
    )

    payload = {
        "projects": [],
        "edges": [],
        "contributors": [
            test_contributor.model_dump(mode="json"),
            real_contributor.model_dump(mode="json"),
        ],
        "assets": [asset.model_dump(mode="json")],
        "contributions": [
            test_contribution.model_dump(mode="json"),
            real_contribution.model_dump(mode="json"),
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    store = InMemoryGraphStore(persist_path=str(path))

    contributors = store.list_contributors(limit=10)
    contributions = store.list_contributions(limit=10)

    assert {c.email for c in contributors} == {"real@coherence.network"}
    assert all(c.contributor_id != test_contributor.id for c in contributions)
    assert any(c.contributor_id == real_contributor.id for c in contributions)
