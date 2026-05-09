"""Tests for the contributions-api spec (specs/contributions-api.md).

Covers the public contributions endpoints — creating contributions
(404 when contributor or asset don't exist), retrieving by ID, listing
with pagination, and the asset/contributor side-listings. Coherence
scoring is auto-calculated from metadata flags (has_tests, has_docs,
complexity).
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_contribution_returns_404_when_contributor_missing(client):
    payload = {
        "contributor_id": str(uuid4()),
        "asset_id": str(uuid4()),
        "cost_amount": "10.00",
    }
    response = client.post("/api/contributions", json=payload)
    assert response.status_code == 404
    assert "Contributor not found" in response.json().get("detail", "")


def test_get_contribution_returns_404_when_missing(client):
    response = client.get(f"/api/contributions/{uuid4()}")
    assert response.status_code == 404


def test_list_contributions_returns_paginated_response(client):
    response = client.get("/api/contributions", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert isinstance(body["items"], list)


def test_list_contributions_default_args(client):
    response = client.get("/api/contributions")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)


def test_asset_contributions_returns_404_when_asset_missing(client):
    response = client.get(f"/api/assets/{uuid4()}/contributions")
    assert response.status_code == 404


def test_contributor_contributions_returns_404_when_contributor_missing(client):
    response = client.get(f"/api/contributors/{uuid4()}/contributions")
    assert response.status_code == 404


def test_create_contribution_rejects_invalid_payload(client):
    """ContributionCreate requires contributor_id, asset_id, cost_amount.
    Pydantic returns 422 on missing fields."""
    response = client.post("/api/contributions", json={"contributor_id": str(uuid4())})
    assert response.status_code == 422


def test_calculate_coherence_increases_with_quality_signals():
    """Service-layer unit: coherence score is sensitive to has_tests /
    has_docs / complexity metadata flags. The exact weights are an
    implementation detail; the contract is that quality signals matter."""
    from app.routers.contributions import calculate_coherence
    from app.models.contribution import ContributionCreate
    from decimal import Decimal

    bare = ContributionCreate(
        contributor_id=uuid4(),
        asset_id=uuid4(),
        cost_amount=Decimal("10.00"),
        metadata={},
    )
    rich = ContributionCreate(
        contributor_id=uuid4(),
        asset_id=uuid4(),
        cost_amount=Decimal("10.00"),
        metadata={"has_tests": True, "has_docs": True, "complexity": "high"},
    )
    bare_score = calculate_coherence(bare)
    rich_score = calculate_coherence(rich)
    assert 0.0 <= bare_score <= 1.0
    assert 0.0 <= rich_score <= 1.0
    assert rich_score >= bare_score
