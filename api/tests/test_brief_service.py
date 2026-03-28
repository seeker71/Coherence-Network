"""Tests for Ucore Daily Engagement Skill — actual brief service + router.

Spec: task_3610e59a86ceadce (Spec 171: OpenClaw Daily Engagement Skill)

Tests the real implementation in:
  api/app/routers/brief.py
  api/app/services/brief_service.py

All 15 spec acceptance criteria are covered.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.brief import router as brief_router
from app.services import brief_service


# ---------------------------------------------------------------------------
# Test app — brief router already carries prefix /api/brief
# ---------------------------------------------------------------------------

_app = FastAPI()
_app.include_router(brief_router)


@pytest.fixture(autouse=True)
def _clean_brief_state():
    brief_service.reset_state()
    yield
    brief_service.reset_state()


@pytest.fixture()
def client():
    return TestClient(_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Acceptance tests (matching spec names exactly)
# ---------------------------------------------------------------------------


def test_get_daily_brief_anonymous_returns_200(client):
    """Anonymous GET /api/brief/daily returns 200 with required fields."""
    res = client.get("/api/brief/daily")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "brief_id" in body and body["brief_id"]
    assert "generated_at" in body
    assert "sections" in body
    assert isinstance(body["sections"], dict)


def test_get_daily_brief_with_valid_contributor_returns_personalized(client):
    """Known contributor_id returns 200 with contributor_id echoed back."""
    brief_service.register_contributor("contrib_alice")
    res = client.get("/api/brief/daily", params={"contributor_id": "contrib_alice"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["contributor_id"] == "contrib_alice"
    assert "sections" in body
    assert "cta" in body


def test_get_daily_brief_with_invalid_contributor_returns_400(client):
    """Unknown contributor_id returns 400 with 'Contributor not found' message."""
    res = client.get("/api/brief/daily", params={"contributor_id": "no_such_contributor"})
    assert res.status_code == 400, res.text
    assert "no_such_contributor" in res.json()["detail"]


def test_get_daily_brief_limit_per_section_out_of_range_returns_422(client):
    """limit_per_section of 0 or 11 returns 422."""
    assert client.get("/api/brief/daily", params={"limit_per_section": 0}).status_code == 422
    assert client.get("/api/brief/daily", params={"limit_per_section": 11}).status_code == 422


def test_sections_respect_limit_per_section(client):
    """Each section contains at most limit_per_section items."""
    res = client.get("/api/brief/daily", params={"limit_per_section": 1})
    assert res.status_code == 200
    for section_name, items in res.json()["sections"].items():
        assert len(items) <= 1, f"Section {section_name!r} has {len(items)} items, limit=1"


def test_response_includes_brief_id_header(client):
    """X-Brief-ID response header matches body brief_id."""
    res = client.get("/api/brief/daily")
    assert res.status_code == 200
    body = res.json()
    header_id = res.headers.get("x-brief-id")
    assert header_id, "X-Brief-ID header missing"
    assert header_id == body["brief_id"]


def test_post_feedback_valid_returns_201(client):
    """Valid feedback POST returns 201 with full record."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    res = client.post("/api/brief/feedback", json={
        "brief_id": brief_id,
        "section": "tasks_for_providers",
        "item_id": "task_aaa",
        "action": "opened",
    })
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["brief_id"] == brief_id
    assert body["section"] == "tasks_for_providers"
    assert body["action"] == "opened"
    assert "id" in body
    assert "recorded_at" in body


def test_post_feedback_invalid_brief_id_returns_404(client):
    """Feedback for unknown brief_id returns 404."""
    res = client.post("/api/brief/feedback", json={
        "brief_id": "nonexistent-brief-xyz",
        "section": "tasks_for_providers",
        "item_id": "task_aaa",
        "action": "opened",
    })
    assert res.status_code == 404, res.text


def test_post_feedback_invalid_action_returns_422(client):
    """Feedback with invalid action returns 422."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    res = client.post("/api/brief/feedback", json={
        "brief_id": brief_id,
        "section": "tasks_for_providers",
        "item_id": "task_aaa",
        "action": "bad_action",
    })
    assert res.status_code == 422, res.text


def test_engagement_metrics_returns_zeros_when_empty(client):
    """Engagement metrics is 200 with zeros when no briefs exist."""
    res = client.get("/api/brief/engagement-metrics")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["briefs_generated"] == 0
    assert body["actions_attributable_to_brief"] == 0
    assert body["cta_conversion_rate"] == 0.0
    assert isinstance(body["section_click_rates"], dict)
    assert body["trend"] in {"improving", "stable", "degrading"}


def test_engagement_metrics_reflects_generated_briefs(client):
    """Metrics counts update after generating briefs and sending feedback."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    client.get("/api/brief/daily")  # second brief

    client.post("/api/brief/feedback", json={
        "brief_id": brief_id,
        "section": "tasks_for_providers",
        "item_id": "task_aaa",
        "action": "claimed",
    })

    body = client.get("/api/brief/engagement-metrics").json()
    assert body["briefs_generated"] == 2
    assert body["actions_attributable_to_brief"] == 1
    assert body["cta_conversion_rate"] > 0.0


def test_engagement_metrics_window_days_respected(client):
    """window_days in response matches request param; 400+ returns 422."""
    assert client.get("/api/brief/engagement-metrics", params={"window_days": 7}).json()["window_days"] == 7
    assert client.get("/api/brief/engagement-metrics", params={"window_days": 400}).status_code == 422


def test_tasks_for_providers_ordered_by_wait_time(client):
    """tasks_for_providers is ordered longest-waiting first (ascending ISO timestamps)."""
    tasks = client.get("/api/brief/daily", params={"limit_per_section": 10}).json()["sections"].get("tasks_for_providers", [])
    if len(tasks) >= 2:
        times = [t["waiting_since"] for t in tasks]
        assert times == sorted(times), f"tasks_for_providers not sorted by wait time: {times}"


def test_news_resonance_scores_in_range(client):
    """resonance_score for every news item is in [0.0, 1.0]."""
    items = client.get("/api/brief/daily").json()["sections"].get("news_resonance", [])
    for item in items:
        score = item["resonance_score"]
        assert 0.0 <= score <= 1.0, f"resonance_score {score} out of [0.0, 1.0]"


def test_coherence_scores_in_range(client):
    """coherence_score for every idea item is in [0.0, 1.0]."""
    items = client.get("/api/brief/daily").json()["sections"].get("ideas_needing_skills", [])
    for item in items:
        score = item["coherence_score"]
        assert 0.0 <= score <= 1.0, f"coherence_score {score} out of [0.0, 1.0]"


# ---------------------------------------------------------------------------
# Additional service-level coverage
# ---------------------------------------------------------------------------


def test_brief_id_is_unique_per_request(client):
    """Two brief requests produce different brief_id values."""
    id1 = client.get("/api/brief/daily").json()["brief_id"]
    id2 = client.get("/api/brief/daily").json()["brief_id"]
    assert id1 != id2


def test_feedback_all_valid_actions_accepted(client):
    """All four valid action values are accepted (201)."""
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    for action in ("claimed", "opened", "dismissed", "shared"):
        res = client.post("/api/brief/feedback", json={
            "brief_id": brief_id,
            "section": "news_resonance",
            "item_id": "news_123",
            "action": action,
        })
        assert res.status_code == 201, f"Action {action!r} rejected: {res.text}"


def test_engagement_metrics_trend_field(client):
    """trend is always one of the three allowed values."""
    trend = client.get("/api/brief/engagement-metrics").json()["trend"]
    assert trend in {"improving", "stable", "degrading"}


def test_brief_service_register_contributor():
    """register_contributor + contributor_exists work correctly."""
    brief_service.reset_state()
    assert not brief_service.contributor_exists("user_x")
    brief_service.register_contributor("user_x")
    assert brief_service.contributor_exists("user_x")


def test_brief_service_generate_raises_for_unknown_contributor():
    """generate_brief raises ValueError for unknown contributor_id."""
    brief_service.reset_state()
    with pytest.raises(ValueError, match="Contributor not found"):
        brief_service.generate_brief(contributor_id="nobody")


def test_brief_service_record_feedback_raises_for_unknown_brief():
    """record_feedback raises KeyError for unknown brief_id."""
    brief_service.reset_state()
    with pytest.raises(KeyError):
        brief_service.record_feedback(
            brief_id="no_such_brief",
            section="tasks_for_providers",
            item_id="x",
            action="opened",
        )
