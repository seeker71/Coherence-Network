"""Acceptance tests for UX Resonance Empty State (ux-resonance-empty-state).

Maps to `specs/150-homepage-readability-contrast.md` scenario 4 and homepage section 3 in
`web/app/page.tsx`: resonance API contract, empty feed fallback to top ideas, deep empty
copy, and conditional See-all links.

This file is the task-specific suite; do not modify other test modules.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_PATH = REPO_ROOT / "web" / "app" / "page.tsx"


def test_spec150_resonance_get_returns_200_json_array() -> None:
    """Scenario 4: GET /api/ideas/resonance returns 200 with a JSON array (may be empty)."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)


def test_homepage_fetch_url_uses_spec_window_and_limit() -> None:
    """Homepage requests the same query as spec 150 manual check (72h, limit 3)."""
    assert PAGE_PATH.is_file(), f"Missing {PAGE_PATH}"
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "/api/ideas/resonance?window_hours=72&limit=3" in src


def test_load_resonance_accepts_array_or_wrapped_payload() -> None:
    """Client tolerates [] or a wrapped `{ideas: ...}` payload so an empty feed does not break the page."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "Array.isArray(data) ? data : data.ideas || []" in src


def test_empty_resonance_fallback_top_three_by_free_energy() -> None:
    """When resonance is empty but ideas exist: Active ideas + top 3 by free_energy_score."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "resonanceItems.length === 0" in src
    assert "ideasData?.ideas" in src
    assert ".sort((a, b) => (b.free_energy_score ?? 0) - (a.free_energy_score ?? 0))" in src
    assert ".slice(0, 3)" in src


def test_section_headings_and_deep_empty_invite_copy() -> None:
    """Recent activity vs Active ideas; deep empty shows invite line."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "resonanceItems.length > 0 ? \"Recent activity\" : \"Active ideas\"" in src
    assert "No recent activity yet. Be the first to share an idea." in src


def test_see_all_row_only_when_resonance_or_fallback_has_items() -> None:
    """No footer link row in the deep-empty branch; resonance vs ideas href/label."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "(resonanceItems.length > 0 || topIdeas.length > 0)" in src
    assert "resonanceItems.length > 0 ? \"/resonance\" : \"/ideas\"" in src
    assert "resonanceItems.length > 0 ? \"See all activity\" : \"See all ideas\"" in src


def test_resonance_branch_limits_cards_to_three() -> None:
    """When the feed has items, only up to three cards are shown."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "resonanceItems.slice(0, 3)" in src


def test_fallback_cards_surface_status_and_value_gap() -> None:
    """Fallback cards show manifestation line and CC remaining (value gap)."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "idea.manifestation_status" in src
    assert "idea.value_gap" in src
    assert "CC remaining" in src
