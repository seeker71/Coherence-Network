"""Extended tests for Ucore Daily Engagement Skill (Spec 171).

Spec: task_3610e59a86ceadce - OpenClaw Daily Engagement Skill
"""
from __future__ import annotations
import uuid
from datetime import datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.brief import router as brief_router
from app.services import brief_service

_app = FastAPI()
_app.include_router(brief_router)

VALID_SECTION_KEYS = {
    "news_resonance", "ideas_needing_skills", "tasks_for_providers",
    "nearby_contributors", "network_patterns",
}

@pytest.fixture(autouse=True)
def _clean_state():
    brief_service.reset_state()
    yield
    brief_service.reset_state()

@pytest.fixture()
def client() -> TestClient:
    return TestClient(_app, raise_server_exceptions=True)

def test_generated_at_is_utc_iso8601(client):
    body = client.get("/api/brief/daily").json()
    ts = body["generated_at"]
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        pytest.fail(f"generated_at not valid ISO 8601: {ts!r}")
    assert dt.tzinfo is not None

def test_recorded_at_is_iso8601_in_feedback(client):
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    res = client.post("/api/brief/feedback", json={
        "brief_id": brief_id, "section": "news_resonance",
        "item_id": "n1", "action": "opened",
    })
    assert res.status_code == 201
    dt = datetime.fromisoformat(res.json()["recorded_at"].replace("Z", "+00:00"))
    assert dt.tzinfo is not None

def test_brief_id_is_uuid_format(client):
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    assert str(uuid.UUID(brief_id)) == brief_id

def test_sections_contain_only_valid_keys(client):
    body = client.get("/api/brief/daily").json()
    for key in body["sections"]:
        assert key in VALID_SECTION_KEYS, f"Unexpected section key: {key!r}"

def test_cta_present_in_anonymous_brief(client):
    body = client.get("/api/brief/daily").json()
    assert "cta" in body
    for field in ("recommended_action", "target_id", "reason"):
        assert field in body["cta"]

def test_network_patterns_signal_strength_in_range(client):
    items = client.get("/api/brief/daily").json()["sections"].get("network_patterns", [])
    for item in items:
        s = item["signal_strength"]
        assert 0.0 <= s <= 1.0, f"signal_strength {s} out of [0.0, 1.0]"

def test_tasks_for_providers_required_fields(client):
    tasks = client.get("/api/brief/daily").json()["sections"].get("tasks_for_providers", [])
    for task in tasks:
        for field in ("task_id", "provider", "waiting_since", "priority"):
            assert field in task

def test_nearby_contributors_hop_distance_positive(client):
    items = client.get("/api/brief/daily").json()["sections"].get("nearby_contributors", [])
    for item in items:
        assert item["hop_distance"] >= 1

def test_post_feedback_invalid_section_returns_422(client):
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    res = client.post("/api/brief/feedback", json={
        "brief_id": brief_id, "section": "bad_section",
        "item_id": "x", "action": "opened",
    })
    assert res.status_code == 422

def test_post_feedback_all_valid_sections_accepted(client):
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    for section in VALID_SECTION_KEYS:
        res = client.post("/api/brief/feedback", json={
            "brief_id": brief_id, "section": section,
            "item_id": "item", "action": "opened",
        })
        assert res.status_code == 201, f"{section!r} rejected: {res.text}"

def test_engagement_metrics_section_click_rates_all_five(client):
    body = client.get("/api/brief/engagement-metrics").json()
    assert set(body["section_click_rates"].keys()) == VALID_SECTION_KEYS

def test_engagement_metrics_unique_contributors(client):
    brief_service.register_contributor("c_a")
    brief_service.register_contributor("c_b")
    client.get("/api/brief/daily", params={"contributor_id": "c_a"})
    client.get("/api/brief/daily", params={"contributor_id": "c_b"})
    assert client.get("/api/brief/engagement-metrics").json()["unique_contributors"] == 2

def test_engagement_metrics_multiple_feedbacks_counted(client):
    brief_id = client.get("/api/brief/daily").json()["brief_id"]
    for action in ("opened", "dismissed", "shared"):
        client.post("/api/brief/feedback", json={
            "brief_id": brief_id, "section": "news_resonance",
            "item_id": "x", "action": action,
        })
    assert client.get("/api/brief/engagement-metrics").json()["actions_attributable_to_brief"] == 3

def test_engagement_metrics_cta_conversion_rate_formula(client):
    b1 = client.get("/api/brief/daily").json()["brief_id"]
    client.get("/api/brief/daily")
    client.post("/api/brief/feedback", json={
        "brief_id": b1, "section": "tasks_for_providers",
        "item_id": "t1", "action": "claimed",
    })
    assert client.get("/api/brief/engagement-metrics").json()["cta_conversion_rate"] == 0.5

def test_engagement_metrics_window_days_minimum(client):
    res = client.get("/api/brief/engagement-metrics", params={"window_days": 1})
    assert res.status_code == 200
    assert res.json()["window_days"] == 1

def test_engagement_metrics_window_days_maximum_365(client):
    res = client.get("/api/brief/engagement-metrics", params={"window_days": 365})
    assert res.status_code == 200
    assert res.json()["window_days"] == 365

def test_personalized_brief_contributor_id_echoed(client):
    brief_service.register_contributor("contrib_z")
    body = client.get("/api/brief/daily", params={"contributor_id": "contrib_z"}).json()
    assert body["contributor_id"] == "contrib_z"
    assert isinstance(body["sections"], dict)

def test_anonymous_brief_contributor_id_is_null(client):
    assert client.get("/api/brief/daily").json()["contributor_id"] is None
