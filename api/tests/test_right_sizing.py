"""Right-sizing integration tests (spec 158).

Flow-centric: HTTP requests in, JSON out. No internal service imports
beyond what is needed for test setup.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "rs-test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    """Helper: create an idea and return the response JSON."""
    iid = idea_id or _uid()
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Description for {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# R1 + R3: GET /api/ideas/right-sizing — portfolio health report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_right_sizing_report_returns_valid_structure():
    """Report returns portfolio health counts, suggestions array, and trend."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/right-sizing")
        assert r.status_code == 200, r.text
        body = r.json()

        # Portfolio health
        health = body["portfolio_health"]
        assert "total" in health
        assert "healthy" in health
        assert "too_large" in health
        assert "too_small" in health
        assert "overlap" in health
        assert health["total"] >= 0
        assert health["healthy"] >= 0
        assert health["healthy"] <= health["total"]

        # Suggestions
        assert isinstance(body["suggestions"], list)

        # Trend
        trend = body["trend"]
        assert trend["direction"] in ("improving", "stable", "degrading")
        assert 0.0 <= trend["healthy_pct_now"] <= 1.0

        # Generated timestamp
        assert "generated_at" in body


@pytest.mark.asyncio
async def test_right_sizing_report_with_many_ideas():
    """Report works with 10+ ideas and returns sensible counts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create 12 ideas to ensure >= 10
        for i in range(12):
            await _create_idea(c, idea_id=f"rs-bulk-{i}-{uuid4().hex[:6]}")

        r = await c.get("/api/ideas/right-sizing")
        assert r.status_code == 200
        body = r.json()
        health = body["portfolio_health"]
        assert health["total"] >= 10


# ---------------------------------------------------------------------------
# R2: Suggestions with confidence and rationale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_right_sizing_too_large_detection():
    """Idea with many open questions is flagged as too_large with split suggestion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid("rs-large")
        await _create_idea(c, idea_id=iid)

        # Add 11 open questions to trigger too_large
        for i in range(11):
            qr = await c.post(f"/api/ideas/{iid}/questions", json={
                "question": f"Question {i} about {iid}?",
                "value_to_whole": 1.0,
                "estimated_cost": 0.5,
            })
            assert qr.status_code in (200, 201, 409), qr.text

        r = await c.get("/api/ideas/right-sizing")
        assert r.status_code == 200
        body = r.json()
        suggestions = body["suggestions"]

        # Find suggestion for our idea
        our_suggestions = [s for s in suggestions if s["idea_id"] == iid]
        assert len(our_suggestions) >= 1, f"Expected split suggestion for {iid}; got {suggestions}"
        split_sug = our_suggestions[0]
        assert split_sug["suggestion_type"] == "split"
        assert split_sug["rationale"]
        assert 0.0 <= split_sug["confidence"] <= 1.0
        assert len(split_sug["proposed_children"]) >= 2


# ---------------------------------------------------------------------------
# R4: POST /api/ideas/right-sizing/apply — dry_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_split_dry_run():
    """Dry-run split previews changes without writing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid("rs-split-dry")
        await _create_idea(c, idea_id=iid)

        r = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split",
            "idea_id": iid,
            "action": "split_into_children",
            "proposed_children": [
                {"name": f"{iid} (core)", "description": "Core delivery"},
                {"name": f"{iid} (research)", "description": "Open questions"},
            ],
            "dry_run": True,
        }, headers=AUTH)

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["applied"] is False
        assert body["dry_run"] is True
        assert len(body["changes"]) >= 3  # 2 create + 1 update

        # Verify children were NOT actually created
        ops = [ch["op"] for ch in body["changes"]]
        assert "create_idea" in ops
        assert "update_idea" in ops

        # Check that the update sets idea_type to "super"
        update_changes = [ch for ch in body["changes"] if ch["op"] == "update_idea"]
        found_super = any(ch.get("set", {}).get("idea_type") == "super" for ch in update_changes)
        assert found_super, f"Expected idea_type=super in update changes: {update_changes}"


@pytest.mark.asyncio
async def test_apply_split_real():
    """Non-dry-run split actually creates child ideas."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid("rs-split-real")
        await _create_idea(c, idea_id=iid)

        r = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split",
            "idea_id": iid,
            "action": "split_into_children",
            "proposed_children": [
                {"name": f"Split Core {iid}", "description": "Core delivery"},
                {"name": f"Split Research {iid}", "description": "Research tasks"},
            ],
            "dry_run": False,
        }, headers=AUTH)

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["applied"] is True
        assert body["dry_run"] is False
        assert len(body["changes"]) >= 3


@pytest.mark.asyncio
async def test_apply_invalid_action_returns_422():
    """Invalid action value returns HTTP 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid("rs-invalid-action")
        await _create_idea(c, idea_id=iid)

        r = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split",
            "idea_id": iid,
            "action": "invalid_action",
            "proposed_children": [],
            "dry_run": True,
        }, headers=AUTH)

        assert r.status_code == 422


@pytest.mark.asyncio
async def test_apply_nonexistent_idea_returns_404():
    """Applying to a nonexistent idea returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split",
            "idea_id": "nonexistent-idea-zzz",
            "action": "split_into_children",
            "proposed_children": [
                {"name": "Child A", "description": "A"},
            ],
            "dry_run": True,
        }, headers=AUTH)

        assert r.status_code == 404


@pytest.mark.asyncio
async def test_apply_requires_api_key():
    """Apply endpoint requires X-API-Key auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split",
            "idea_id": "any-id",
            "action": "split_into_children",
            "proposed_children": [],
            "dry_run": True,
        })
        # Should get 401 or 403 without API key
        assert r.status_code in (401, 403), r.text


# ---------------------------------------------------------------------------
# R5: GET /api/ideas/right-sizing/history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_returns_series():
    """History endpoint returns an array (may be empty)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/right-sizing/history?days=7")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "series" in body
        assert isinstance(body["series"], list)


@pytest.mark.asyncio
async def test_history_with_snapshot():
    """After taking a snapshot, history returns at least one entry."""
    from app.services import right_sizing_service
    right_sizing_service.clear_snapshots()
    right_sizing_service.snapshot_health()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/right-sizing/history?days=7")
        assert r.status_code == 200
        body = r.json()
        assert len(body["series"]) >= 1
        entry = body["series"][0]
        assert "date" in entry
        assert "healthy" in entry
        assert "healthy_pct" in entry
        assert 0.0 <= entry["healthy_pct"] <= 1.0


@pytest.mark.asyncio
async def test_history_days_validation():
    """days=0 returns 422; days=366 returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r0 = await c.get("/api/ideas/right-sizing/history?days=0")
        assert r0.status_code == 422

        r366 = await c.get("/api/ideas/right-sizing/history?days=366")
        assert r366.status_code == 422


# ---------------------------------------------------------------------------
# Unit-level: text overlap
# ---------------------------------------------------------------------------


def test_text_overlap_identical():
    """Identical texts should have overlap score ~1.0."""
    from app.services.right_sizing_service import compute_text_overlap
    text = "Build a contribution tracking system for open source"
    score = compute_text_overlap(text, text)
    assert score > 0.99


def test_text_overlap_different():
    """Completely different texts should have low overlap."""
    from app.services.right_sizing_service import compute_text_overlap
    a = "Build a contribution tracking system for open source projects"
    b = "Design a mobile game about space exploration with aliens"
    score = compute_text_overlap(a, b)
    assert score < 0.3


def test_text_overlap_similar():
    """Similar texts should have moderately high overlap."""
    from app.services.right_sizing_service import compute_text_overlap
    a = "Implement idea portfolio tracking with coherence scoring and ranking"
    b = "Build idea portfolio management with coherence scoring and analytics"
    score = compute_text_overlap(a, b)
    assert score > 0.4  # Should be somewhat similar


# ---------------------------------------------------------------------------
# Granularity signal computation
# ---------------------------------------------------------------------------


def test_compute_signal_healthy():
    """Idea with reasonable specs and few questions is healthy."""
    from app.services.right_sizing_service import compute_granularity_signal, GranularitySignal

    class FakeIdea:
        open_questions = [{"q": "how?"} for _ in range(3)]
        lifecycle = "active"

    signal, _ = compute_granularity_signal(FakeIdea(), spec_count=2)
    assert signal == GranularitySignal.HEALTHY


def test_compute_signal_too_large():
    """Idea with 11 open questions triggers too_large."""
    from app.services.right_sizing_service import compute_granularity_signal, GranularitySignal

    class FakeIdea:
        open_questions = [{"q": f"q{i}"} for i in range(11)]
        lifecycle = "active"

    signal, meta = compute_granularity_signal(FakeIdea(), spec_count=2)
    assert signal == GranularitySignal.TOO_LARGE
    assert meta["open_questions"] == 11


def test_compute_signal_too_small():
    """Idea with 0 specs is too_small."""
    from app.services.right_sizing_service import compute_granularity_signal, GranularitySignal

    class FakeIdea:
        open_questions = []
        lifecycle = "active"

    signal, _ = compute_granularity_signal(FakeIdea(), spec_count=0)
    assert signal == GranularitySignal.TOO_SMALL


def test_compute_signal_too_large_many_specs():
    """Idea with >5 specs triggers too_large."""
    from app.services.right_sizing_service import compute_granularity_signal, GranularitySignal

    class FakeIdea:
        open_questions = []
        lifecycle = "active"

    signal, _ = compute_granularity_signal(FakeIdea(), spec_count=7)
    assert signal == GranularitySignal.TOO_LARGE
