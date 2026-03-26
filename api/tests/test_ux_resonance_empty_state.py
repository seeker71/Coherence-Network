"""UX: homepage resonance empty-state and fallback (ux-resonance-empty-state).

Acceptance criteria (aligned with `web/app/page.tsx` and spec 150 scenario 4):

- GET /api/ideas/resonance returns HTTP 200 with a JSON array (may be empty); homepage
  must not break when empty.
- When the resonance feed is empty but ideas exist, the homepage shows the "Active ideas"
  heading and falls back to the top ideas by free_energy_score (up to 3).
- When resonance is empty and there are no ideas to show, the homepage shows a friendly
  empty-state line and does not show the "See all …" footer link in that branch.
- When resonance has items, the section uses "Recent activity" and links to /resonance.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE_PATH = REPO_ROOT / "web" / "app" / "page.tsx"


def test_resonance_feed_returns_200_json_array_empty_ok() -> None:
    """Spec 150 scenario 4: resonance endpoint is 200 with array (possibly empty)."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_homepage_resonance_section_documents_fallback_sort() -> None:
    """Empty resonance uses ideas sorted by free_energy_score descending, slice 0..3."""
    assert PAGE_PATH.is_file(), f"Missing {PAGE_PATH}"
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "resonanceItems.length === 0" in src
    assert "free_energy_score" in src
    assert ".sort((a, b) => (b.free_energy_score ?? 0) - (a.free_energy_score ?? 0))" in src
    assert ".slice(0, 3)" in src


def test_homepage_resonance_section_headings_and_empty_copy() -> None:
    """Headings switch; deep empty state shows invite copy."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert '"Recent activity"' in src
    assert '"Active ideas"' in src
    assert "No recent activity yet. Be the first to share an idea." in src


def test_homepage_resonance_section_conditional_see_all_links() -> None:
    """Resonance vs fallback: correct label and href; link row only when there is content."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert 'href="/resonance"' in src
    assert 'href="/ideas"' in src
    assert "See all activity" in src
    assert "See all ideas" in src
    assert "(resonanceItems.length > 0 || topIdeas.length > 0)" in src


def test_homepage_fallback_cards_show_status_and_cc_remaining() -> None:
    """Idea fallback cards surface manifestation_status and value gap (CC remaining)."""
    src = PAGE_PATH.read_text(encoding="utf-8")
    assert "idea.manifestation_status" in src
    assert "CC remaining" in src
