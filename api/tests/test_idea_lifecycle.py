"""Acceptance tests for idea lifecycle management (spec 138)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.idea import IDEA_STAGE_ORDER, IdeaStage, ManifestationStatus
from app.services import idea_service


client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _new_idea_id() -> str:
    return f"idea-lifecycle-{uuid.uuid4().hex[:12]}"


def _create_idea_via_api() -> str:
    idea_id = _new_idea_id()
    response = client.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": "Idea lifecycle coverage",
            "description": "Seeded for lifecycle acceptance tests.",
            "potential_value": 10.0,
            "estimated_cost": 2.0,
            "confidence": 0.5,
        },
    )
    assert response.status_code == 201, response.text
    return idea_id


def _create_idea_via_service() -> str:
    idea_id = _new_idea_id()
    created = idea_service.create_idea(
        idea_id=idea_id,
        name="Idea lifecycle coverage",
        description="Seeded for lifecycle acceptance tests.",
        potential_value=10.0,
        estimated_cost=2.0,
        confidence=0.5,
    )
    assert created is not None
    return idea_id


def test_advance_none_to_specced() -> None:
    idea_id = _create_idea_via_api()

    response = client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == idea_id
    assert payload["stage"] == IdeaStage.SPECCED.value
    assert payload["manifestation_status"] == ManifestationStatus.PARTIAL.value


def test_advance_through_all_stages() -> None:
    idea_id = _create_idea_via_api()
    observed_stages: list[str] = []

    for expected_stage in IDEA_STAGE_ORDER[1:]:
        response = client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert response.status_code == 200, response.text
        observed_stages.append(response.json()["stage"])

    assert observed_stages == [stage.value for stage in IDEA_STAGE_ORDER[1:]]


def test_advance_complete_returns_409() -> None:
    idea_id = _create_idea_via_api()

    for _ in IDEA_STAGE_ORDER[1:]:
        response = client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)
        assert response.status_code == 200, response.text

    complete_response = client.post(f"/api/ideas/{idea_id}/advance", headers=AUTH_HEADERS)

    assert complete_response.status_code == 409
    assert complete_response.json() == {"detail": "Idea is already complete"}


def test_skip_stage_returns_422() -> None:
    idea_id = _create_idea_via_api()

    response = client.post(
        f"/api/ideas/{idea_id}/stage",
        json={"stage": "skip-to-complete"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"] == ["body", "stage"]
    assert detail["type"] == "enum"


def test_set_stage_explicit() -> None:
    idea_id = _create_idea_via_api()

    response = client.post(
        f"/api/ideas/{idea_id}/stage",
        json={"stage": IdeaStage.IMPLEMENTING.value},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["stage"] == IdeaStage.IMPLEMENTING.value
    assert payload["manifestation_status"] == ManifestationStatus.PARTIAL.value


def test_set_invalid_stage_returns_422() -> None:
    idea_id = _create_idea_via_api()

    response = client.post(
        f"/api/ideas/{idea_id}/stage",
        json={"stage": "bogus"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"] == ["body", "stage"]
    assert detail["type"] == "enum"


def test_auto_advance_on_spec_task() -> None:
    idea_id = _create_idea_via_service()

    idea_service.auto_advance_for_task(idea_id, "spec")

    updated = idea_service.get_idea(idea_id)
    assert updated is not None
    assert updated.stage == IdeaStage.SPECCED
    assert updated.manifestation_status == ManifestationStatus.PARTIAL


def test_auto_advance_noop_if_already_past() -> None:
    idea_id = _create_idea_via_service()
    updated, error = idea_service.set_idea_stage(idea_id, IdeaStage.TESTING)
    assert error is None
    assert updated is not None

    idea_service.auto_advance_for_task(idea_id, "spec")

    unchanged = idea_service.get_idea(idea_id)
    assert unchanged is not None
    assert unchanged.stage == IdeaStage.TESTING


def test_progress_dashboard_counts() -> None:
    ids = [(_create_idea_via_service(), stage) for stage in IDEA_STAGE_ORDER[:4]]

    for idea_id, stage in ids[1:]:
        updated, error = idea_service.set_idea_stage(idea_id, stage)
        assert error is None
        assert updated is not None

    response = client.get("/api/ideas/progress")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_ideas"] == 4
    assert payload["by_stage"]["none"]["count"] == 1
    assert payload["by_stage"]["specced"]["count"] == 1
    assert payload["by_stage"]["implementing"]["count"] == 1
    assert payload["by_stage"]["testing"]["count"] == 1
    assert payload["by_stage"]["reviewing"]["count"] == 0
    assert payload["by_stage"]["complete"]["count"] == 0
    assert set(payload["by_stage"]["none"]["idea_ids"]) == {ids[0][0]}


def test_progress_completion_pct() -> None:
    idea_a = _create_idea_via_service()
    idea_b = _create_idea_via_service()
    idea_c = _create_idea_via_service()
    idea_d = _create_idea_via_service()

    for idea_id in (idea_a, idea_b):
        updated, error = idea_service.set_idea_stage(idea_id, IdeaStage.COMPLETE)
        assert error is None
        assert updated is not None

    response = client.get("/api/ideas/progress")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_ideas"] == 4
    assert payload["by_stage"]["complete"]["count"] == 2
    assert payload["completion_pct"] == 0.5


def test_stage_syncs_manifestation_status() -> None:
    idea_id = _create_idea_via_service()

    specced, error = idea_service.set_idea_stage(idea_id, IdeaStage.SPECCED)
    assert error is None
    assert specced is not None
    assert specced.manifestation_status == ManifestationStatus.PARTIAL

    testing, error = idea_service.set_idea_stage(idea_id, IdeaStage.TESTING)
    assert error is None
    assert testing is not None
    assert testing.manifestation_status == ManifestationStatus.PARTIAL

    complete, error = idea_service.set_idea_stage(idea_id, IdeaStage.COMPLETE)
    assert error is None
    assert complete is not None
    assert complete.manifestation_status == ManifestationStatus.VALIDATED


def test_new_idea_defaults_to_none_stage() -> None:
    idea_id = _create_idea_via_api()

    response = client.get(f"/api/ideas/{idea_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["stage"] == IdeaStage.NONE.value
    assert payload["manifestation_status"] == ManifestationStatus.NONE.value
