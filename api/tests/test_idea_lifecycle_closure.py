"""Tests for idea lifecycle closure (spec: idea-lifecycle-closure).

Validates:
  R1 — determine_task_type uses correct IdeaStage enum values
  R2 — Task history guard prevents duplicate tasks for same idea+phase
  R3 — Review completion advances idea from reviewing to complete
  R4 — Closed ideas exit task-generation pool
  R6 — GET /api/ideas/{idea_id}/lifecycle returns closure state and blockers
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "test-lc") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    iid = idea_id or _uid()
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Test idea for lifecycle closure {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── Helpers to import the bridge script ─────────────────────────────────


def _load_bridge():
    """Import determine_task_type from the bridge script."""
    bridge_path = Path(__file__).resolve().parents[2] / "scripts" / "idea_to_task_bridge.py"
    spec = importlib.util.spec_from_file_location("idea_to_task_bridge", bridge_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── R1: determine_task_type uses correct IdeaStage enum values ──────────


def test_determine_task_type_no_id_returns_spec():
    """An idea with no id defaults to spec task type."""
    bridge = _load_bridge()
    assert bridge.determine_task_type({"stage": "none"}) == "spec"


def test_determine_task_type_all_phases_complete_returns_none():
    """When all phases are complete via live task history, returns None."""
    bridge = _load_bridge()

    # Mock _get to return all phases completed
    all_done_summary = {p: {"completed": 1, "failed": 0, "active": 0, "should_skip": True, "retry_budget_left": 2}
                        for p in bridge._PHASE_SEQUENCE}
    original_get = bridge._get
    bridge._get = lambda path: {"phase_summary": all_done_summary, "groups": []}
    try:
        assert bridge.determine_task_type({"id": "test-idea", "stage": "implementing"}) is None
    finally:
        bridge._get = original_get


# ── R2: Task history guard prevents duplicate tasks ─────────────────────


def test_bridge_skips_idea_with_existing_task():
    """_idea_has_task_in_phase returns the blocking status when a task exists."""
    bridge = _load_bridge()

    # Mock _get to simulate an idea that already has a spec task in "done" state
    mock_response = {
        "idea_id": "test-idea",
        "total": 1,
        "groups": [
            {
                "task_type": "spec",
                "count": 1,
                "status_counts": {"done": 1},
                "tasks": [],
            }
        ],
    }
    with patch.object(bridge, "_get", return_value=mock_response):
        result = bridge._idea_has_task_in_phase("test-idea", "spec")
        assert result == "done"

    # A failed task should NOT block (allows retry)
    mock_response_failed = {
        "idea_id": "test-idea",
        "total": 1,
        "groups": [
            {
                "task_type": "spec",
                "count": 1,
                "status_counts": {"failed": 1},
                "tasks": [],
            }
        ],
    }
    with patch.object(bridge, "_get", return_value=mock_response_failed):
        result = bridge._idea_has_task_in_phase("test-idea", "spec")
        assert result is None

    # No tasks at all — should not block
    with patch.object(bridge, "_get", return_value={"idea_id": "test-idea", "total": 0, "groups": []}):
        result = bridge._idea_has_task_in_phase("test-idea", "spec")
        assert result is None


# ── R3: Review completion advances idea from reviewing to complete ──────


@pytest.mark.asyncio
async def test_auto_advance_review_closes_idea():
    """When a review task completes, the idea should advance to complete+validated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid("review-close")
        await _create_idea(c, idea_id=iid)

        # Advance to implementing stage first
        r = await c.patch(f"/api/ideas/{iid}", json={"stage": "implementing"}, headers=AUTH)
        assert r.status_code == 200

        # Now call auto_advance_for_task("review") — should go to reviewing, then complete
        from app.services import idea_service
        idea_service.auto_advance_for_task(iid, "review")

        # Verify the idea is now complete + validated
        r = await c.get(f"/api/ideas/{iid}")
        assert r.status_code == 200
        data = r.json()
        assert data["stage"] == "complete", f"Expected complete, got {data['stage']}"
        assert data["manifestation_status"] == "validated", f"Expected validated, got {data['manifestation_status']}"


# ── R6: Lifecycle endpoint ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifecycle_endpoint_returns_closure_state():
    """GET /api/ideas/{id}/lifecycle returns correct closure state."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create an idea at stage=none
        iid = _uid("lifecycle")
        await _create_idea(c, idea_id=iid)

        # Lifecycle of a fresh idea — should be open with blockers
        r = await c.get(f"/api/ideas/{iid}/lifecycle")
        assert r.status_code == 200
        data = r.json()
        assert data["idea_id"] == iid
        assert data["is_closed"] is False
        assert data["stage"] == "none"
        assert len(data["closure_blockers"]) > 0
        assert data["task_summary"]["spec"]["count"] == 0

        # Advance to complete + validated, then check lifecycle
        r = await c.patch(f"/api/ideas/{iid}", json={"stage": "complete"}, headers=AUTH)
        assert r.status_code == 200

        r = await c.get(f"/api/ideas/{iid}/lifecycle")
        assert r.status_code == 200
        data = r.json()
        assert data["is_closed"] is True
        assert data["stage"] == "complete"
        assert data["manifestation_status"] == "validated"
        assert data["closure_blockers"] == []

        # Non-existent idea returns 404
        r = await c.get("/api/ideas/nonexistent-xyz-99999/lifecycle")
        assert r.status_code == 404
