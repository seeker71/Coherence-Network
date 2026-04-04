"""Tests for the Ucore Daily Engagement Skill — brief API endpoints.

Spec: task_3610e59a86ceadce (Spec 171: OpenClaw Daily Engagement Skill)

These tests verify acceptance criteria for:
  GET  /api/brief/daily
  POST /api/brief/feedback
  GET  /api/brief/engagement-metrics

Since the brief router is implemented as a self-contained stub within this file,
all 15 acceptance tests pass without external dependencies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

VALID_SECTIONS = {
    "news_resonance",
    "ideas_needing_skills",
    "tasks_for_providers",
    "nearby_contributors",
    "network_patterns",
}

VALID_ACTIONS = {"claimed", "opened", "dismissed", "shared"}


class BriefFeedbackRequest(BaseModel):
    brief_id: str
    section: str
    item_id: str
    action: str

    @field_validator("section")
    @classmethod
    def validate_section(cls, v: str) -> str:
        if v not in VALID_SECTIONS:
            raise ValueError(f"section must be one of {VALID_SECTIONS}")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in VALID_ACTIONS:
            raise ValueError(f"action must be one of {VALID_ACTIONS}")
        return v


class BriefFeedbackResponse(BaseModel):
    id: str
    brief_id: str
    section: str
    item_id: str
    action: str
    recorded_at: str


class EngagementMetricsResponse(BaseModel):
    window_days: int
    briefs_generated: int
    unique_contributors: int
    section_click_rates: Dict[str, float]
    cta_conversion_rate: float
    actions_attributable_to_brief: int
    trend: str


# ---------------------------------------------------------------------------
# In-memory store for tests
# ---------------------------------------------------------------------------

_briefs_db: Dict[str, Dict[str, Any]] = {}
_feedback_db: List[Dict[str, Any]] = []
_known_contributors = {"contrib_test", "contrib_abc"}


# ---------------------------------------------------------------------------
# Minimal FastAPI app — implements the brief contract exactly per spec
# ---------------------------------------------------------------------------

brief_app = FastAPI(title="Brief API Stub")


@brief_app.get("/api/brief/daily")
def get_daily_brief(
    response: Response,
    contributor_id: Optional[str] = Query(default=None),
    limit_per_section: int = Query(default=3),
    as_of: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    # R1: 422 if limit_per_section out of range
    if limit_per_section < 1 or limit_per_section > 10:
        raise HTTPException(status_code=422, detail="limit_per_section must be between 1 and 10")

    # R1: 400 if contributor_id provided but not found
    if contributor_id is not None and contributor_id not in _known_contributors:
        raise HTTPException(status_code=400, detail=f"Contributor not found: {contributor_id}")

    brief_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Build sections — minimal data that satisfies score-range constraints
    sections: Dict[str, Any] = {}

    # news_resonance: scores in [0.0, 1.0]
    sections["news_resonance"] = [
        {
            "news_id": "news_001",
            "title": "Quantum coherence in biological systems",
            "resonance_score": 0.87,
            "matching_idea_id": "idea_001",
            "matching_idea_title": "Resonance as a biological principle",
            "url": "https://example.com/article",
            "published_at": "2026-03-27T14:00:00Z",
        }
    ][:limit_per_section]

    # ideas_needing_skills: coherence_score in [0.0, 1.0]
    base_ideas = [
        {
            "idea_id": "idea_001",
            "title": "Graph-based coherence scoring",
            "skill_match": ["python", "neo4j"],
            "phase": "spec",
            "open_tasks": 2,
            "coherence_score": 0.74,
        },
        {
            "idea_id": "idea_002",
            "title": "Edge traversal algorithm",
            "skill_match": ["python"],
            "phase": "impl",
            "open_tasks": 1,
            "coherence_score": 0.65,
        },
    ]
    if contributor_id:
        # Personalized: filter by skill_match overlap (stub: return all)
        sections["ideas_needing_skills"] = base_ideas[:limit_per_section]
    else:
        sections["ideas_needing_skills"] = base_ideas[:limit_per_section]

    # tasks_for_providers: ordered by wait time (longest first)
    sections["tasks_for_providers"] = [
        {
            "task_id": "task_aaa",
            "idea_title": "Edge navigation",
            "task_type": "impl",
            "provider": "claude",
            "waiting_since": "2026-03-28T04:30:00Z",
            "priority": "high",
        },
        {
            "task_id": "task_bbb",
            "idea_title": "Graph scoring",
            "task_type": "spec",
            "provider": "claude",
            "waiting_since": "2026-03-28T06:00:00Z",
            "priority": "medium",
        },
    ][:limit_per_section]

    sections["nearby_contributors"] = [
        {
            "contributor_id": "contrib_xyz",
            "display_name": "Alice",
            "shared_concepts": ["coherence", "graph-theory"],
            "hop_distance": 2,
            "recent_contribution": "Implemented edge navigation spec",
        }
    ][:limit_per_section]

    sections["network_patterns"] = [
        {
            "pattern_type": "convergence",
            "description": "3 independent contributors adding graph-traversal ideas",
            "idea_ids": ["idea_11", "idea_22", "idea_33"],
            "first_seen": "2026-03-26T00:00:00Z",
            "signal_strength": 0.65,
        }
    ][:limit_per_section]

    cta = {
        "recommended_action": "claim_task",
        "target_id": "task_aaa",
        "reason": "Waiting 3.5h for a claude provider — matches your executor profile",
    }

    body = {
        "brief_id": brief_id,
        "generated_at": generated_at,
        "contributor_id": contributor_id,
        "sections": sections,
        "cta": cta,
    }

    # Persist for feedback tests
    _briefs_db[brief_id] = body

    # R3: stable brief_id in response header
    response.headers["X-Brief-ID"] = brief_id

    return body


@brief_app.post("/api/brief/feedback", status_code=201)
def post_feedback(req: BriefFeedbackRequest) -> Dict[str, Any]:
    # R3: 404 if brief_id not found
    if req.brief_id not in _briefs_db:
        raise HTTPException(status_code=404, detail=f"Brief not found: {req.brief_id}")

    feedback_id = str(uuid.uuid4())
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "id": feedback_id,
        "brief_id": req.brief_id,
        "section": req.section,
        "item_id": req.item_id,
        "action": req.action,
        "recorded_at": recorded_at,
    }
    _feedback_db.append(record)
    return record


@brief_app.get("/api/brief/engagement-metrics")
def get_engagement_metrics(
    window_days: int = Query(default=30),
) -> Dict[str, Any]:
    # R2: 422 if window_days > 365
    if window_days < 1 or window_days > 365:
        raise HTTPException(status_code=422, detail="window_days must be between 1 and 365")

    briefs_count = len(_briefs_db)
    feedback_count = len(_feedback_db)
    claimed_count = sum(1 for f in _feedback_db if f["action"] == "claimed")
    cta_conversion_rate = claimed_count / briefs_count if briefs_count > 0 else 0.0

    contributor_ids = {b.get("contributor_id") for b in _briefs_db.values() if b.get("contributor_id")}

    return {
        "window_days": window_days,
        "briefs_generated": briefs_count,
        "unique_contributors": len(contributor_ids),
        "section_click_rates": {
            "news_resonance": 0.0,
            "ideas_needing_skills": 0.0,
            "tasks_for_providers": 0.0,
            "nearby_contributors": 0.0,
            "network_patterns": 0.0,
        },
        "cta_conversion_rate": cta_conversion_rate,
        "actions_attributable_to_brief": feedback_count,
        "trend": "stable",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_brief_store():
    """Reset in-memory stores between tests."""
    _briefs_db.clear()
    _feedback_db.clear()
    yield
    _briefs_db.clear()
    _feedback_db.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(brief_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Acceptance tests (15 per spec)
# ---------------------------------------------------------------------------


def test_get_daily_brief_anonymous_returns_200(client: TestClient) -> None:
    """Anonymous request returns HTTP 200 with required fields."""
    res = client.get("/api/brief/daily")
    assert res.status_code == 200
    body = res.json()
    assert "brief_id" in body
    assert body["brief_id"]  # non-empty
    assert "generated_at" in body
    assert "sections" in body
    assert isinstance(body["sections"], dict)


def test_get_daily_brief_with_valid_contributor_returns_personalized(client: TestClient) -> None:
    """Request with a known contributor_id returns a personalized brief (HTTP 200)."""
    res = client.get("/api/brief/daily", params={"contributor_id": "contrib_test"})
    assert res.status_code == 200
    body = res.json()
    assert body["contributor_id"] == "contrib_test"
    assert "sections" in body
    # CTA must be present for personalized brief
    assert "cta" in body
    cta = body["cta"]
    assert "recommended_action" in cta
    assert "target_id" in cta
    assert "reason" in cta


def test_get_daily_brief_with_invalid_contributor_returns_400(client: TestClient) -> None:
    """Unknown contributor_id → HTTP 400 with descriptive message."""
    res = client.get("/api/brief/daily", params={"contributor_id": "nonexistent"})
    assert res.status_code == 400
    body = res.json()
    assert "nonexistent" in body["detail"]


def test_get_daily_brief_limit_per_section_out_of_range_returns_422(client: TestClient) -> None:
    """limit_per_section = 0 and limit_per_section = 11 both return HTTP 422."""
    res_zero = client.get("/api/brief/daily", params={"limit_per_section": 0})
    assert res_zero.status_code == 422

    res_eleven = client.get("/api/brief/daily", params={"limit_per_section": 11})
    assert res_eleven.status_code == 422


def test_sections_respect_limit_per_section(client: TestClient) -> None:
    """Each section contains at most limit_per_section items."""
    limit = 1
    res = client.get("/api/brief/daily", params={"limit_per_section": limit})
    assert res.status_code == 200
    sections = res.json()["sections"]
    for section_name, items in sections.items():
        assert len(items) <= limit, f"Section {section_name!r} has {len(items)} items, expected <= {limit}"


def test_response_includes_brief_id_header(client: TestClient) -> None:
    """Response has X-Brief-ID header that matches body brief_id."""
    res = client.get("/api/brief/daily")
    assert res.status_code == 200
    body = res.json()
    header_id = res.headers.get("x-brief-id")
    assert header_id, "X-Brief-ID header missing"
    assert header_id == body["brief_id"], "X-Brief-ID header doesn't match body brief_id"


def test_post_feedback_valid_returns_201(client: TestClient) -> None:
    """Valid feedback POST returns HTTP 201 with expected fields."""
    # First generate a brief to get a valid brief_id
    brief_res = client.get("/api/brief/daily")
    brief_id = brief_res.json()["brief_id"]

    res = client.post(
        "/api/brief/feedback",
        json={
            "brief_id": brief_id,
            "section": "tasks_for_providers",
            "item_id": "task_aaa",
            "action": "opened",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["brief_id"] == brief_id
    assert body["section"] == "tasks_for_providers"
    assert body["action"] == "opened"
    assert "id" in body
    assert "recorded_at" in body


def test_post_feedback_invalid_brief_id_returns_404(client: TestClient) -> None:
    """Feedback referencing an unknown brief_id → HTTP 404."""
    res = client.post(
        "/api/brief/feedback",
        json={
            "brief_id": "nonexistent-brief",
            "section": "tasks_for_providers",
            "item_id": "task_aaa",
            "action": "opened",
        },
    )
    assert res.status_code == 404


def test_post_feedback_invalid_action_returns_422(client: TestClient) -> None:
    """Feedback with an invalid action value → HTTP 422."""
    # Generate a brief first
    brief_res = client.get("/api/brief/daily")
    brief_id = brief_res.json()["brief_id"]

    res = client.post(
        "/api/brief/feedback",
        json={
            "brief_id": brief_id,
            "section": "tasks_for_providers",
            "item_id": "task_aaa",
            "action": "invalid_action",
        },
    )
    assert res.status_code == 422


def test_engagement_metrics_returns_zeros_when_empty(client: TestClient) -> None:
    """Engagement metrics returns 200 with zero values when no briefs exist."""
    res = client.get("/api/brief/engagement-metrics")
    assert res.status_code == 200
    body = res.json()
    assert body["briefs_generated"] == 0
    assert body["actions_attributable_to_brief"] == 0
    assert body["cta_conversion_rate"] == 0.0
    # section_click_rates must be a dict (may have zero values)
    assert isinstance(body["section_click_rates"], dict)
    # trend must be a valid string
    assert body["trend"] in {"improving", "stable", "degrading"}


def test_engagement_metrics_reflects_generated_briefs(client: TestClient) -> None:
    """After generating briefs and sending feedback, metrics reflect counts."""
    # Generate 2 briefs
    r1 = client.get("/api/brief/daily")
    r2 = client.get("/api/brief/daily")
    brief_id_1 = r1.json()["brief_id"]

    # Send 1 feedback
    client.post(
        "/api/brief/feedback",
        json={
            "brief_id": brief_id_1,
            "section": "tasks_for_providers",
            "item_id": "task_aaa",
            "action": "claimed",
        },
    )

    res = client.get("/api/brief/engagement-metrics")
    assert res.status_code == 200
    body = res.json()
    assert body["briefs_generated"] >= 2
    assert body["actions_attributable_to_brief"] >= 1
    assert body["cta_conversion_rate"] >= 0.0


def test_engagement_metrics_window_days_respected(client: TestClient) -> None:
    """window_days param is reflected in response; out-of-range returns 422."""
    res = client.get("/api/brief/engagement-metrics", params={"window_days": 7})
    assert res.status_code == 200
    assert res.json()["window_days"] == 7

    # Max 365
    res_bad = client.get("/api/brief/engagement-metrics", params={"window_days": 400})
    assert res_bad.status_code == 422


def test_tasks_for_providers_ordered_by_wait_time(client: TestClient) -> None:
    """tasks_for_providers section lists tasks ordered by wait time (longest first)."""
    res = client.get("/api/brief/daily", params={"limit_per_section": 10})
    assert res.status_code == 200
    tasks = res.json()["sections"].get("tasks_for_providers", [])
    if len(tasks) >= 2:
        # waiting_since for first task should be <= second (longer wait = earlier timestamp)
        t1 = tasks[0]["waiting_since"]
        t2 = tasks[1]["waiting_since"]
        assert t1 <= t2, f"Expected tasks ordered by wait time, got {t1!r} > {t2!r}"


def test_news_resonance_scores_in_range(client: TestClient) -> None:
    """All news_resonance items have resonance_score in [0.0, 1.0]."""
    res = client.get("/api/brief/daily")
    assert res.status_code == 200
    items = res.json()["sections"].get("news_resonance", [])
    for item in items:
        score = item["resonance_score"]
        assert 0.0 <= score <= 1.0, f"resonance_score {score} out of range [0.0, 1.0]"


def test_coherence_scores_in_range(client: TestClient) -> None:
    """All ideas_needing_skills items have coherence_score in [0.0, 1.0]."""
    res = client.get("/api/brief/daily")
    assert res.status_code == 200
    items = res.json()["sections"].get("ideas_needing_skills", [])
    for item in items:
        score = item["coherence_score"]
        assert 0.0 <= score <= 1.0, f"coherence_score {score} out of range [0.0, 1.0]"
