"""Flow tests for /api/evidence — story-protocol-integration R9.

Covers submission, verification, 2-of-3 threshold, GPS-within-radius,
5x multiplier application, and per-asset view composition.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence_service


@pytest.fixture
def client():
    evidence_service._reset_for_tests()
    return TestClient(app)


def _payload(**overrides):
    base = {
        "asset_id": "asset:a1",
        "submitter_id": "contributor:alice",
        "photo_urls": ["https://arweave.net/tx1"],
        "gps": {"lat": 37.78, "lng": -122.41},
        "attestation_count": 3,
        "description": "Built the cob wall; see photos + community sign-off.",
    }
    base.update(overrides)
    return base


def test_submit_evidence_returns_201_and_id(client):
    response = client.post("/api/evidence", json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["asset_id"] == "asset:a1"
    assert body["submitter_id"] == "contributor:alice"
    assert "id" in body
    assert body["photo_urls"] == ["https://arweave.net/tx1"]


def test_verify_all_three_factors_true_when_community_registered(client):
    evidence_service.register_community_location(37.785, -122.41)
    submission = client.post("/api/evidence", json=_payload()).json()
    result = client.post(f"/api/evidence/{submission['id']}/verify").json()
    assert result["verified"] is True
    assert result["factors_satisfied"] == 3
    assert result["has_photo_proof"] is True
    assert result["gps_within_radius"] is True
    assert result["attestation_met"] is True
    assert Decimal(result["cc_multiplier_applicable"]) == Decimal("5")


def test_verify_two_factors_still_passes(client):
    # photo + attestation; no GPS
    submission = client.post(
        "/api/evidence",
        json=_payload(gps=None),
    ).json()
    result = client.post(f"/api/evidence/{submission['id']}/verify").json()
    assert result["verified"] is True
    assert result["factors_satisfied"] == 2


def test_verify_one_factor_fails(client):
    submission = client.post(
        "/api/evidence",
        json=_payload(gps=None, attestation_count=0),
    ).json()
    result = client.post(f"/api/evidence/{submission['id']}/verify").json()
    assert result["verified"] is False
    assert Decimal(result["cc_multiplier_applicable"]) == Decimal("1")


def test_verify_unknown_evidence_returns_404(client):
    response = client.post(
        "/api/evidence/00000000-0000-0000-0000-000000000000/verify"
    )
    assert response.status_code == 404


def test_list_for_asset_composes_submissions_and_multiplier(client):
    evidence_service.register_community_location(37.78, -122.41)
    first = client.post("/api/evidence", json=_payload(asset_id="asset:m1")).json()
    client.post(f"/api/evidence/{first['id']}/verify")

    # A second submission that fails verification
    weak = client.post(
        "/api/evidence",
        json=_payload(
            asset_id="asset:m1",
            photo_urls=[],
            gps=None,
            attestation_count=1,
        ),
    ).json()
    client.post(f"/api/evidence/{weak['id']}/verify")

    view = client.get("/api/evidence/asset/asset:m1").json()
    assert view["asset_id"] == "asset:m1"
    assert len(view["submissions"]) == 2
    assert len(view["verifications"]) == 2
    # Highest applicable multiplier across verified evidence
    assert Decimal(view["cc_multiplier_applicable"]) == Decimal("5")


def test_list_for_asset_with_no_verified_returns_multiplier_one(client):
    weak = client.post(
        "/api/evidence",
        json=_payload(
            asset_id="asset:weak",
            photo_urls=[],
            gps=None,
            attestation_count=1,
        ),
    ).json()
    client.post(f"/api/evidence/{weak['id']}/verify")
    view = client.get("/api/evidence/asset/asset:weak").json()
    assert Decimal(view["cc_multiplier_applicable"]) == Decimal("1")


def test_get_evidence_by_id_roundtrip(client):
    submission = client.post("/api/evidence", json=_payload()).json()
    response = client.get(f"/api/evidence/{submission['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == submission["id"]


def test_get_evidence_404(client):
    response = client.get(
        "/api/evidence/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


def test_submit_rejects_missing_asset_id(client):
    payload = _payload()
    del payload["asset_id"]
    response = client.post("/api/evidence", json=payload)
    assert response.status_code == 422


def test_submit_rejects_negative_attestation_count(client):
    response = client.post(
        "/api/evidence",
        json=_payload(attestation_count=-1),
    )
    assert response.status_code == 422
