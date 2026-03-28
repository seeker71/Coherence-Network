"""Tests for Ucore Daily Engagement Skill (Spec 171: OpenClaw Daily Engagement Skill).

Verifies acceptance criteria from specs/task_3610e59a86ceadce.md:
- GET /api/brief/daily
- POST /api/brief/feedback
- GET /api/brief/engagement-metrics
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import brief_service


@pytest.fixture(autouse=True)
def reset_brief_state():
    """Reset in-memory brief state before each test."""
    brief_service.reset_state()
    yield
    brief_service.reset_state()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_daily_brief(client: AsyncClient, **params) -> dict:
    r = await client.get("/api/brief/daily", params=params)
    return r


async def _post_feedback(client: AsyncClient, **body) -> dict:
    r = await client.post("/api/brief/feedback", json=body)
    return r


# ---------------------------------------------------------------------------
# GET /api/brief/daily
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_brief_anonymous_returns_200():
    """Anonymous brief (no contributor_id) returns 200 with sections and brief_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client)

    assert r.status_code == 200, r.text
    body = r.json()
    assert "brief_id" in body
    assert body["brief_id"]  # non-empty
    assert "sections" in body
    assert "generated_at" in body


@pytest.mark.asyncio
async def test_get_daily_brief_with_valid_contributor_returns_personalized():
    """Brief for a known contributor_id returns 200 and contributor_id echoed."""
    brief_service.register_contributor("contrib_test")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client, contributor_id="contrib_test")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("contributor_id") == "contrib_test"
    assert "sections" in body


@pytest.mark.asyncio
async def test_get_daily_brief_with_invalid_contributor_returns_400():
    """Unknown contributor_id returns 400 with detail message."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client, contributor_id="nonexistent")

    assert r.status_code == 400, r.text
    body = r.json()
    assert "nonexistent" in body.get("detail", "")


@pytest.mark.asyncio
async def test_get_daily_brief_limit_per_section_zero_returns_422():
    """limit_per_section=0 is out of range — must return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client, limit_per_section=0)

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_get_daily_brief_limit_per_section_eleven_returns_422():
    """limit_per_section=11 is out of range — must return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client, limit_per_section=11)

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_sections_respect_limit_per_section():
    """Each section must have at most limit_per_section items."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client, limit_per_section=1)

    assert r.status_code == 200, r.text
    body = r.json()
    for section_name, items in body.get("sections", {}).items():
        if items is not None:
            assert len(items) <= 1, (
                f"Section {section_name!r} has {len(items)} items, expected <= 1"
            )


@pytest.mark.asyncio
async def test_response_includes_brief_id_header():
    """Response must include X-Brief-ID header matching body brief_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client)

    assert r.status_code == 200, r.text
    body = r.json()
    assert "X-Brief-ID" in r.headers, "Missing X-Brief-ID response header"
    assert r.headers["X-Brief-ID"] == body["brief_id"]


@pytest.mark.asyncio
async def test_tasks_for_providers_ordered_by_wait_time():
    """tasks_for_providers section must be ordered longest-waiting first."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client, limit_per_section=10)

    assert r.status_code == 200, r.text
    tasks = r.json()["sections"].get("tasks_for_providers", [])
    if len(tasks) >= 2:
        # waiting_since should be ascending (oldest/longest-waiting first)
        waiting_times = [t["waiting_since"] for t in tasks]
        assert waiting_times == sorted(waiting_times), (
            f"tasks_for_providers not sorted by wait time: {waiting_times}"
        )


@pytest.mark.asyncio
async def test_news_resonance_scores_in_range():
    """resonance_score values in news_resonance must be in [0.0, 1.0]."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client)

    assert r.status_code == 200, r.text
    items = r.json()["sections"].get("news_resonance", [])
    for item in items:
        score = item.get("resonance_score")
        assert score is not None
        assert 0.0 <= score <= 1.0, f"resonance_score out of range: {score}"


@pytest.mark.asyncio
async def test_coherence_scores_in_range():
    """coherence_score values in ideas_needing_skills must be in [0.0, 1.0]."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client)

    assert r.status_code == 200, r.text
    items = r.json()["sections"].get("ideas_needing_skills", [])
    for item in items:
        score = item.get("coherence_score")
        assert score is not None
        assert 0.0 <= score <= 1.0, f"coherence_score out of range: {score}"


# ---------------------------------------------------------------------------
# POST /api/brief/feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_feedback_valid_returns_201():
    """POST /api/brief/feedback with valid data returns 201 with feedback record."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First generate a brief to get a valid brief_id
        brief_r = await _get_daily_brief(client)
        brief_id = brief_r.json()["brief_id"]

        # Submit feedback
        r = await _post_feedback(
            client,
            brief_id=brief_id,
            section="tasks_for_providers",
            item_id="task_aaa",
            action="opened",
        )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["brief_id"] == brief_id
    assert body["section"] == "tasks_for_providers"
    assert body["action"] == "opened"
    assert "id" in body
    assert "recorded_at" in body


@pytest.mark.asyncio
async def test_post_feedback_invalid_brief_id_returns_404():
    """POST feedback with unknown brief_id returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_feedback(
            client,
            brief_id="nonexistent-brief",
            section="tasks_for_providers",
            item_id="task_aaa",
            action="opened",
        )

    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_post_feedback_invalid_action_returns_422():
    """POST feedback with invalid action value returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        brief_r = await _get_daily_brief(client)
        brief_id = brief_r.json()["brief_id"]

        r = await _post_feedback(
            client,
            brief_id=brief_id,
            section="tasks_for_providers",
            item_id="task_aaa",
            action="invalid_action",
        )

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_feedback_invalid_section_returns_422():
    """POST feedback with invalid section name returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        brief_r = await _get_daily_brief(client)
        brief_id = brief_r.json()["brief_id"]

        r = await _post_feedback(
            client,
            brief_id=brief_id,
            section="invalid_section",
            item_id="task_aaa",
            action="opened",
        )

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_feedback_all_valid_actions_accepted():
    """All valid action values (claimed, opened, dismissed, shared) are accepted."""
    valid_actions = ["claimed", "opened", "dismissed", "shared"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for action in valid_actions:
            brief_r = await _get_daily_brief(client)
            brief_id = brief_r.json()["brief_id"]

            r = await _post_feedback(
                client,
                brief_id=brief_id,
                section="news_resonance",
                item_id="news_123",
                action=action,
            )
            assert r.status_code == 201, f"action={action!r} rejected: {r.text}"


# ---------------------------------------------------------------------------
# GET /api/brief/engagement-metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engagement_metrics_returns_zeros_when_empty():
    """engagement-metrics returns 200 with zero values when no briefs exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/brief/engagement-metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["briefs_generated"] == 0
    assert body["actions_attributable_to_brief"] == 0
    assert body["cta_conversion_rate"] == 0.0
    assert "trend" in body
    assert "section_click_rates" in body


@pytest.mark.asyncio
async def test_engagement_metrics_reflects_generated_briefs():
    """After generating briefs, engagement-metrics briefs_generated increments."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _get_daily_brief(client)
        await _get_daily_brief(client)

        r = await client.get("/api/brief/engagement-metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["briefs_generated"] >= 2


@pytest.mark.asyncio
async def test_engagement_metrics_reflects_feedback_actions():
    """actions_attributable_to_brief increments after posting feedback."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        brief_r = await _get_daily_brief(client)
        brief_id = brief_r.json()["brief_id"]

        await _post_feedback(
            client,
            brief_id=brief_id,
            section="tasks_for_providers",
            item_id="task_aaa",
            action="claimed",
        )

        r = await client.get("/api/brief/engagement-metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["actions_attributable_to_brief"] >= 1
    assert body["briefs_generated"] >= 1


@pytest.mark.asyncio
async def test_engagement_metrics_window_days_respected():
    """window_days parameter is echoed in the response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/brief/engagement-metrics", params={"window_days": 7})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 7


@pytest.mark.asyncio
async def test_engagement_metrics_window_days_max_exceeded_returns_422():
    """window_days > 365 should return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/brief/engagement-metrics", params={"window_days": 400})

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_engagement_metrics_trend_improving():
    """trend='improving' when recent 7-day feedback exceeds prior 7-day feedback."""
    from datetime import datetime, timezone, timedelta

    # Inject feedback directly to simulate historical data
    # Generate a brief to register it
    brief = brief_service.generate_brief()
    brief_id = brief["brief_id"]

    now = datetime.now(timezone.utc)

    # Simulate: 1 action in the prior 7-day window, 5 actions in the last 7 days
    prior_time = now - timedelta(days=10)
    recent_time = now - timedelta(days=2)

    with brief_service._lock:
        # Add feedback with timestamps by directly manipulating the list
        brief_service._feedback_list.append({
            "id": "fb_prior",
            "brief_id": brief_id,
            "section": "tasks_for_providers",
            "item_id": "task_aaa",
            "action": "opened",
            "recorded_at": prior_time.isoformat(),
        })
        for i in range(5):
            brief_service._feedback_list.append({
                "id": f"fb_recent_{i}",
                "brief_id": brief_id,
                "section": "tasks_for_providers",
                "item_id": f"task_{i}",
                "action": "opened",
                "recorded_at": recent_time.isoformat(),
            })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/brief/engagement-metrics", params={"window_days": 14})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trend"] == "improving", f"Expected 'improving', got {body['trend']!r}"


@pytest.mark.asyncio
async def test_engagement_metrics_cta_conversion_rate_computed():
    """cta_conversion_rate = claimed_count / briefs_generated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Generate 2 briefs
        r1 = await _get_daily_brief(client)
        r2 = await _get_daily_brief(client)
        brief_id_1 = r1.json()["brief_id"]

        # 1 claimed action out of 2 briefs → rate = 0.5
        await _post_feedback(
            client,
            brief_id=brief_id_1,
            section="tasks_for_providers",
            item_id="task_aaa",
            action="claimed",
        )

        r = await client.get("/api/brief/engagement-metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["briefs_generated"] == 2
    assert body["cta_conversion_rate"] == 0.5


@pytest.mark.asyncio
async def test_brief_id_is_stable_per_brief():
    """Each brief generation produces a unique brief_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await _get_daily_brief(client)
        r2 = await _get_daily_brief(client)

    id1 = r1.json()["brief_id"]
    id2 = r2.json()["brief_id"]
    assert id1 != id2, "Each brief should have a unique brief_id"


@pytest.mark.asyncio
async def test_generated_at_is_utc_iso8601():
    """generated_at field must be a valid UTC ISO 8601 timestamp."""
    from datetime import datetime, timezone

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _get_daily_brief(client)

    assert r.status_code == 200, r.text
    generated_at = r.json()["generated_at"]
    # Must be parseable as a datetime
    dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    assert dt.tzinfo is not None, "generated_at must be timezone-aware (UTC)"
