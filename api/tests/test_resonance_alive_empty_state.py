"""Acceptance tests for Resonance alive empty-state heartbeat experience.

This suite verifies:
- API pulse contract (`GET /api/ideas/resonance`) remains safe in empty state.
- Full create-read-update flow produces `last_activity_at` evidence over time.
- Resonance web page source includes ambient breathing empty-state affordances.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]
RESONANCE_PAGE_PATH = REPO_ROOT / "web" / "app" / "resonance" / "page.tsx"


@pytest.mark.asyncio
async def test_resonance_endpoint_empty_state_returns_200_array(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Empty state for resonance is valid and returns 200 with an array payload."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/ideas/resonance", params={"window_hours": 72, "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload == []


@pytest.mark.asyncio
async def test_resonance_create_read_update_flow_surfaces_last_known_pulse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Create+read+update flow yields resonance activity with `last_activity_at`."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    idea_id = "alive-empty-proof"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "Alive Empty Proof",
                "description": "Heartbeat proof for resonance page empty state.",
                "potential_value": 55.0,
                "estimated_cost": 8.0,
                "confidence": 0.78,
            },
        )
        assert created.status_code == 201

        read_back = await client.get(f"/api/ideas/{idea_id}")
        assert read_back.status_code == 200
        assert read_back.json()["id"] == idea_id

        question_added = await client.post(
            f"/api/ideas/{idea_id}/questions",
            json={
                "question": "How do we prove this is alive over time?",
                "value_to_whole": 15.0,
                "estimated_cost": 2.0,
            },
        )
        assert question_added.status_code == 200

        question_answered = await client.post(
            f"/api/ideas/{idea_id}/questions/answer",
            json={
                "question": "How do we prove this is alive over time?",
                "answer": "Track pulse timestamps and surface them in resonance empty state.",
            },
        )
        assert question_answered.status_code == 200

        resonance = await client.get("/api/ideas/resonance", params={"window_hours": 72, "limit": 10})

    assert resonance.status_code == 200
    items = resonance.json()
    assert isinstance(items, list)
    matched = [item for item in items if item.get("idea_id") == idea_id]
    assert matched, "Expected created+updated idea to appear in resonance feed."
    assert isinstance(matched[0].get("last_activity_at"), str)
    assert matched[0]["last_activity_at"], "last_activity_at should not be empty."


@pytest.mark.asyncio
async def test_resonance_endpoint_validation_errors_for_bad_query_bounds() -> None:
    """Bad query bounds return 422; valid boundaries remain accepted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        too_small_window = await client.get("/api/ideas/resonance", params={"window_hours": 0, "limit": 5})
        too_large_window = await client.get("/api/ideas/resonance", params={"window_hours": 721, "limit": 5})
        too_large_limit = await client.get("/api/ideas/resonance", params={"window_hours": 72, "limit": 101})
        boundary_ok = await client.get("/api/ideas/resonance", params={"window_hours": 720, "limit": 100})

    assert too_small_window.status_code == 422
    assert too_large_window.status_code == 422
    assert too_large_limit.status_code == 422
    assert boundary_ok.status_code == 200
    assert isinstance(boundary_ok.json(), list)


def test_resonance_page_contains_ambient_breathing_empty_state_contract() -> None:
    """Source-level contract: heartbeat empty state is organic and timestamp-aware."""
    src = RESONANCE_PAGE_PATH.read_text(encoding="utf-8")

    assert "Last known pulse" in src
    assert "formatPulseTimestamp" in src
    assert "No pulse recorded yet" in src

    assert "ambient-ring ambient-ring-1" in src
    assert "ambient-particle ambient-particle-a" in src
    assert "ambient-wave" in src

    assert "The network is breathing quietly." in src
    assert "Spark the next pulse" in src
