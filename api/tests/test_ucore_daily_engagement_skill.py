"""Extended tests for Ucore Daily Engagement Skill (Spec 171).

Spec: task_3610e59a86ceadce — OpenClaw Daily Engagement Skill

Additional coverage beyond test_brief.py and test_brief_service.py:
- ISO 8601 timestamp format validation
- UUID format for brief_id
- Section key whitelist enforcement
- CTA presence in anonymous brief
- Score range checks (network_patterns signal_strength)
- Field completeness checks (tasks, nearby_contributors)
- Feedback section validation (invalid section → 422)
- All valid sections accepted in feedback
- Engagement metrics: unique_contributors, multiple feedbacks,
  cta_conversion_rate formula, window_days boundary values
- Personalized brief with registered contributor
- Anonymous brief has contributor_id = null
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.brief import router as brief_router
from app.services import brief_service

# ---------------------------------------------------------------------------
# Test app — real router + service
# ---------------------------------------------------------------------------

_app = FastAPI()
_app.include_router(brief_router)


@pytest.fixture(autouse=True)
def _clean_state():
    brief_service.reset_state()
    yield
    brief_service.reset_state()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Timestamp format tests
# ---------------------------------------------------------------------------


def test_generated_at_is_utc_iso8601(client: TestClient) -> None:
    """generated_at must be a valid, timezone-aware ISO 8601 timestamp."""
    body = client.get("/api/brief/daily").json()
    ts = body["generated_at"]
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        pytest.fail(f"generated_at is not valid ISO 8601: {ts!r}")
    assert dt.tzinfo is not None, "generated_at must be timezone-aware"


def test_recorded_at_is_iso8601_in_feedback_response(client: TestClient) -> None:
    """recorded_at in feedback response must be timezone-aware ISO 8601."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    res = client.post(
        "/api/brief/feedback",
        json={
            "brief_id": brief_id,
            "section": "news_resonance",
            "item_id": "news_001",
            "action": "opened",
        },
    )
    assert res.status_code == 201
    recorded_at = res.json()["recorded_at"]
    dt = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# UUID format test
# ---------------------------------------------------------------------------


def test_brief_id_is_uuid_format(client: TestClient) -> None:
    """brief_id must be a well-formed UUID string."""
    body = client.get("/api/brief/daily").json()
    brief_id = body["brief_id"]
    parsed = uuid.UUID(brief_id)  # raises ValueError if not valid UUID
    assert str(parsed) == brief_id


# ---------------------------------------------------------------------------
# Section key whitelist
# ---------------------------------------------------------------------------

VALID_SECTION_KEYS = {
    "news_resonance",
    "ideas_needing_skills",
    "tasks_for_providers",
    "nearby_contributors",
    "network_patterns",
}


def test_sections_contain_only_valid_keys(client: TestClient) -> None:
    """All section keys in the brief response are from the allowed set."""
    body = client.get("/api/brief/daily").json()
    for key in body["sections"]:
        assert key in VALID_SECTION_KEYS, f"Unexpected section key: {key!r}"


# ---------------------------------------------------------------------------
# CTA presence
# ---------------------------------------------------------------------------


def test_cta_present_in_anonymous_brief(client: TestClient) -> None:
    """Anonymous brief response includes a CTA with required fields."""
    body = client.get("/api/brief/daily").json()
    assert "cta" in body
    cta = body["cta"]
    assert "recommended_action" in cta
    assert "target_id" in cta
    assert "reason" in cta


# ---------------------------------------------------------------------------
# Score range tests
# ---------------------------------------------------------------------------


def test_network_patterns_signal_strength_in_range(client: TestClient) -> None:
    """signal_strength for all network_patterns items is in [0.0, 1.0]."""
    items = client.get("/api/brief/daily").json()["sections"].get("network_patterns", [])
    for item in items:
        s = item["signal_strength"]
        assert 0.0 <= s <= 1.0, f"signal_strength {s} out of [0.0, 1.0]"


# ---------------------------------------------------------------------------
# Field completeness
# ---------------------------------------------------------------------------


def test_tasks_for_providers_required_fields(client: TestClient) -> None:
    """Each task in tasks_for_providers has required fields."""
    tasks = client.get("/api/brief/daily").json()["sections"].get("tasks_for_providers", [])
    for task in tasks:
        assert "task_id" in task
        assert "provider" in task
        assert "waiting_since" in task
        assert "priority" in task


def test_nearby_contributors_hop_distance_is_positive(client: TestClient) -> None:
    """hop_distance for each nearby_contributor must be >= 1."""
    items = client.get("/api/brief/daily").json()["sections"].get("nearby_contributors", [])
    for item in items:
        assert item["hop_distance"] >= 1, f"hop_distance must be >= 1, got {item['hop_distance']}"


# ---------------------------------------------------------------------------
# Feedback validation
# ---------------------------------------------------------------------------


def test_post_feedback_invalid_section_returns_422(client: TestClient) -> None:
    """Feedback with an invalid section value returns HTTP 422."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    res = client.post(
        "/api/brief/feedback",
        json={
            "brief_id": brief_id,
            "section": "not_a_real_section",
            "item_id": "x",
            "action": "opened",
        },
    )
    assert res.status_code == 422


def test_post_feedback_all_valid_sections_accepted(client: TestClient) -> None:
    """All five valid section values are accepted in feedback (HTTP 201)."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    for section in VALID_SECTION_KEYS:
        res = client.post(
            "/api/brief/feedback",
            json={
                "brief_id": brief_id,
                "section": section,
                "item_id": "test_item",
                "action": "opened",
            },
        )
        assert res.status_code == 201, f"Section {section!r} rejected: {res.text}"


# ---------------------------------------------------------------------------
# Engagement metrics
# ---------------------------------------------------------------------------


def test_engagement_metrics_section_click_rates_has_all_five_sections(client: TestClient) -> None:
    """section_click_rates contains all five section keys."""
    body = client.get("/api/brief/engagement-metrics").json()
    assert set(body["section_click_rates"].keys()) == VALID_SECTION_KEYS


def test_engagement_metrics_unique_contributors(client: TestClient) -> None:
    """unique_contributors reflects the number of distinct contributors with briefs."""
    brief_service.register_contributor("contrib_a")
    brief_service.register_contributor("contrib_b")
    client.get("/api/brief/daily", params={"contributor_id": "contrib_a"})
    client.get("/api/brief/daily", params={"contributor_id": "contrib_b"})
    body = client.get("/api/brief/engagement-metrics").json()
    assert body["unique_contributors"] == 2


def test_engagement_metrics_multiple_feedbacks_counted(client: TestClient) -> None:
    """actions_attributable_to_brief counts all feedback records."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    for action in ("opened", "dismissed", "shared"):
        client.post(
            "/api/brief/feedback",
            json={
                "brief_id": brief_id,
                "section": "news_resonance",
                "item_id": "item_x",
                "action": action,
            },
        )
    body = client.get("/api/brief/engagement-metrics").json()
    assert body["actions_attributable_to_brief"] == 3


def test_engagement_metrics_cta_conversion_rate_formula(client: TestClient) -> None:
    """cta_conversion_rate = claimed_count / briefs_generated (2 briefs, 1 claimed → 0.5)."""
    b1 = client.get("/api/brief/daily").json()["brief_id"]
    client.get("/api/brief/daily")  # second brief, no feedback

    client.post(
        "/api/brief/feedback",
        json={
            "brief_id": b1,
            "section": "tasks_for_providers",
            "item_id": "task_aaa",
            "action": "claimed",
        },
    )

    body = client.get("/api/brief/engagement-metrics").json()
    assert body["cta_conversion_rate"] == 0.5


def test_engagement_metrics_window_days_minimum_one(client: TestClient) -> None:
    """window_days=1 is valid and reflected in response."""
    res = client.get("/api/brief/engagement-metrics", params={"window_days": 1})
    assert res.status_code == 200
    assert res.json()["window_days"] == 1


def test_engagement_metrics_window_days_maximum_365(client: TestClient) -> None:
    """window_days=365 is valid and reflected in response."""
    res = client.get("/api/brief/engagement-metrics", params={"window_days": 365})
    assert res.status_code == 200
    assert res.json()["window_days"] == 365


# ---------------------------------------------------------------------------
# Personalization + anonymous contributor_id
# ---------------------------------------------------------------------------


def test_personalized_brief_returns_correct_contributor_id(client: TestClient) -> None:
    """Personalized brief echoes contributor_id and includes sections dict."""
    brief_service.register_contributor("contrib_skilled")
    body = client.get("/api/brief/daily", params={"contributor_id": "contrib_skilled"}).json()
    assert body["contributor_id"] == "contrib_skilled"
    assert isinstance(body["sections"], dict)


def test_anonymous_brief_contributor_id_is_null(client: TestClient) -> None:
    """Anonymous brief has contributor_id = null (None)."""
    body = client.get("/api/brief/daily").json()
    assert body["contributor_id"] is None
