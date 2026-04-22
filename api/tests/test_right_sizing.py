"""Right-sizing integration tests (spec 158).

Three flows cover the surface:

  · Portfolio health report + suggestions + apply (dry-run + real)
    + error paths (422 invalid action, 404 missing idea, 401/403
    missing API key)
  · History endpoint + days validation
  · Service-layer helpers: text overlap (identical/different/similar)
    + granularity signal (healthy, too_large by questions, too_large
    by specs, too_small)
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
    iid = idea_id or _uid()
    payload = {
        "id": iid, "name": f"Idea {iid}", "description": f"Description for {iid}",
        "potential_value": 100.0, "estimated_cost": 10.0, "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_right_sizing_report_suggestions_and_apply_flow():
    """Report returns portfolio health + suggestions + trend; a
    too_large idea surfaces as a split suggestion; apply split
    (dry-run preview → real create) + error paths (422/404/401)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Seed enough ideas so report has meaningful counts.
        for i in range(12):
            await _create_idea(c, idea_id=f"rs-bulk-{i}-{uuid4().hex[:6]}")

        # Trigger too_large: one idea with 11 open questions.
        large_id = _uid("rs-large")
        await _create_idea(c, idea_id=large_id)
        for i in range(11):
            await c.post(f"/api/ideas/{large_id}/questions", json={
                "question": f"Question {i} about {large_id}?",
                "value_to_whole": 1.0, "estimated_cost": 0.5,
            })

        # Report shape + content.
        report = (await c.get("/api/ideas/right-sizing")).json()
        health = report["portfolio_health"]
        for field in ("total", "healthy", "too_large", "too_small", "overlap"):
            assert field in health
        assert health["total"] >= 10 and health["healthy"] <= health["total"]
        assert isinstance(report["suggestions"], list)
        trend = report["trend"]
        assert trend["direction"] in ("improving", "stable", "degrading")
        assert 0.0 <= trend["healthy_pct_now"] <= 1.0
        assert "generated_at" in report

        # The too-large idea surfaces as a split suggestion with
        # confidence + proposed children.
        our_suggestion = next(s for s in report["suggestions"] if s["idea_id"] == large_id)
        assert our_suggestion["suggestion_type"] == "split"
        assert our_suggestion["rationale"]
        assert 0.0 <= our_suggestion["confidence"] <= 1.0
        assert len(our_suggestion["proposed_children"]) >= 2

        # Apply split dry-run — preview changes, no writes.
        dry_id = _uid("rs-dry")
        await _create_idea(c, idea_id=dry_id)
        dry = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split", "idea_id": dry_id,
            "action": "split_into_children",
            "proposed_children": [
                {"name": f"{dry_id} (core)", "description": "Core delivery"},
                {"name": f"{dry_id} (research)", "description": "Open questions"},
            ],
            "dry_run": True,
        }, headers=AUTH)
        assert dry.status_code == 200
        dry_body = dry.json()
        assert dry_body["applied"] is False and dry_body["dry_run"] is True
        assert len(dry_body["changes"]) >= 3
        ops = {ch["op"] for ch in dry_body["changes"]}
        assert {"create_idea", "update_idea"} <= ops
        # Super-idea retype is in the update.
        update_changes = [ch for ch in dry_body["changes"] if ch["op"] == "update_idea"]
        assert any(ch.get("set", {}).get("idea_type") == "super" for ch in update_changes)

        # Real apply — split actually creates children.
        real_id = _uid("rs-real")
        await _create_idea(c, idea_id=real_id)
        real = (await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split", "idea_id": real_id,
            "action": "split_into_children",
            "proposed_children": [
                {"name": f"Split Core {real_id}", "description": "Core delivery"},
                {"name": f"Split Research {real_id}", "description": "Research tasks"},
            ],
            "dry_run": False,
        }, headers=AUTH)).json()
        assert real["applied"] is True and real["dry_run"] is False
        assert len(real["changes"]) >= 3

        # Error paths.
        bad_action = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split", "idea_id": real_id,
            "action": "invalid_action", "proposed_children": [], "dry_run": True,
        }, headers=AUTH)
        assert bad_action.status_code == 422

        bad_idea = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split", "idea_id": "nonexistent-idea-zzz",
            "action": "split_into_children",
            "proposed_children": [{"name": "A", "description": "A"}],
            "dry_run": True,
        }, headers=AUTH)
        assert bad_idea.status_code == 404

        no_auth = await c.post("/api/ideas/right-sizing/apply", json={
            "suggestion_type": "split", "idea_id": "any-id",
            "action": "split_into_children",
            "proposed_children": [], "dry_run": True,
        })
        assert no_auth.status_code in (401, 403)


@pytest.mark.asyncio
async def test_right_sizing_history_flow():
    """History returns a series (possibly empty); after a snapshot
    it contains at least one well-shaped entry; days out of range
    returns 422."""
    from app.services import right_sizing_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Empty is fine.
        empty = (await c.get("/api/ideas/right-sizing/history?days=7")).json()
        assert "series" in empty and isinstance(empty["series"], list)

        # With a snapshot, at least one entry appears with the expected shape.
        right_sizing_service.clear_snapshots()
        right_sizing_service.snapshot_health()
        filled = (await c.get("/api/ideas/right-sizing/history?days=7")).json()
        assert len(filled["series"]) >= 1
        entry = filled["series"][0]
        assert "date" in entry and "healthy" in entry and "healthy_pct" in entry
        assert 0.0 <= entry["healthy_pct"] <= 1.0

        # Validation — days=0 and days=366 both 422.
        assert (await c.get("/api/ideas/right-sizing/history?days=0")).status_code == 422
        assert (await c.get("/api/ideas/right-sizing/history?days=366")).status_code == 422


def test_right_sizing_service_helpers():
    """Text overlap scores identical ~1.0, different < 0.3, similar
    > 0.4. Granularity signal: healthy (few questions + modest
    specs), too_large (11 questions OR 7 specs), too_small (0 specs)."""
    from app.services.right_sizing_service import (
        compute_text_overlap,
        compute_granularity_signal,
        GranularitySignal,
    )

    # Text overlap across three regimes.
    text = "Build a contribution tracking system for open source"
    assert compute_text_overlap(text, text) > 0.99
    assert compute_text_overlap(
        "Build a contribution tracking system for open source projects",
        "Design a mobile game about space exploration with aliens",
    ) < 0.3
    assert compute_text_overlap(
        "Implement idea portfolio tracking with coherence scoring and ranking",
        "Build idea portfolio management with coherence scoring and analytics",
    ) > 0.4

    # Granularity signal across the four states.
    class Healthy:
        open_questions = [{"q": "how?"} for _ in range(3)]
        lifecycle = "active"
    assert compute_granularity_signal(Healthy(), spec_count=2)[0] == GranularitySignal.HEALTHY

    class LargeQuestions:
        open_questions = [{"q": f"q{i}"} for i in range(11)]
        lifecycle = "active"
    signal, meta = compute_granularity_signal(LargeQuestions(), spec_count=2)
    assert signal == GranularitySignal.TOO_LARGE and meta["open_questions"] == 11

    class LargeSpecs:
        open_questions = []
        lifecycle = "active"
    assert compute_granularity_signal(LargeSpecs(), spec_count=7)[0] == GranularitySignal.TOO_LARGE

    class Small:
        open_questions = []
        lifecycle = "active"
    assert compute_granularity_signal(Small(), spec_count=0)[0] == GranularitySignal.TOO_SMALL
