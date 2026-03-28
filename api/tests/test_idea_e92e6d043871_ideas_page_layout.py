"""Tests for idea-e92e6d043871: Ideas page — lead with ideas, push dashboard below.

Acceptance criteria:
- The Ideas page shows idea cards BEFORE the lifecycle dashboard section.
- The lifecycle dashboard (stage transitions, progress bars, backlog counts) lives
  below the fold — hidden by default in a collapsible <details> element.
- API endpoints used by the page (/api/ideas, /api/ideas/progress) return valid data.
- The progress dashboard endpoint returns stage bucket data (by_stage).
- Summary stats (total ideas, value created, remaining opportunity) are shown
  as simple headline numbers — NOT as progress bars or stage counts at the top.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_IDEAS_PAGE = _REPO_ROOT / "web" / "app" / "ideas" / "page.tsx"

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------


def test_ideas_list_returns_200_with_ideas_and_summary() -> None:
    """GET /api/ideas returns HTTP 200 with 'ideas' list and 'summary' dict."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data, "Response must include 'ideas' key"
    assert "summary" in data, "Response must include 'summary' key"
    summary = data["summary"]
    for key in ("total_ideas", "total_potential_value", "total_actual_value", "total_value_gap"):
        assert key in summary, f"summary must include '{key}'"


def test_ideas_list_ideas_sorted_by_free_energy_score_descending() -> None:
    """GET /api/ideas returns ideas sorted by free_energy_score descending."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200
    ideas = resp.json()["ideas"]
    if len(ideas) < 2:
        pytest.skip("need at least 2 ideas to verify sort order")
    scores = [i.get("free_energy_score", 0.0) for i in ideas]
    assert scores == sorted(scores, reverse=True), (
        "ideas must be sorted by free_energy_score descending"
    )


def test_ideas_list_each_idea_has_required_fields() -> None:
    """Each idea in GET /api/ideas has the fields the Ideas page renders."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200
    ideas = resp.json()["ideas"]
    if not ideas:
        pytest.skip("no ideas to verify")
    required = {
        "id", "name", "description",
        "potential_value", "actual_value",
        "confidence", "manifestation_status",
        "free_energy_score",
    }
    for idea in ideas[:5]:  # spot-check first 5
        missing = required - idea.keys()
        assert not missing, f"idea {idea.get('id')} missing fields: {missing}"


def test_progress_dashboard_returns_200_with_by_stage() -> None:
    """GET /api/ideas/progress returns HTTP 200 with by_stage and total_ideas."""
    resp = client.get("/api/ideas/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert "by_stage" in data, "progress dashboard must include 'by_stage'"
    assert "total_ideas" in data, "progress dashboard must include 'total_ideas'"
    assert "completion_pct" in data, "progress dashboard must include 'completion_pct'"


def test_progress_dashboard_by_stage_has_known_stages() -> None:
    """Progress dashboard by_stage includes all lifecycle stages."""
    resp = client.get("/api/ideas/progress")
    assert resp.status_code == 200
    by_stage = resp.json().get("by_stage", {})
    expected_stages = {"none", "specced", "implementing", "testing", "reviewing", "complete"}
    for stage in expected_stages:
        assert stage in by_stage, f"by_stage must include stage '{stage}'"


def test_progress_dashboard_completion_pct_in_range() -> None:
    """Progress dashboard completion_pct is between 0.0 and 1.0."""
    resp = client.get("/api/ideas/progress")
    assert resp.status_code == 200
    pct = resp.json()["completion_pct"]
    assert 0.0 <= pct <= 1.0, f"completion_pct must be 0.0–1.0, got {pct}"


def test_progress_dashboard_by_stage_buckets_have_count_and_ids() -> None:
    """Each stage bucket in by_stage includes 'count' and 'idea_ids'."""
    resp = client.get("/api/ideas/progress")
    assert resp.status_code == 200
    by_stage = resp.json().get("by_stage", {})
    for stage, bucket in by_stage.items():
        assert "count" in bucket, f"stage '{stage}' bucket missing 'count'"
        assert "idea_ids" in bucket, f"stage '{stage}' bucket missing 'idea_ids'"
        assert isinstance(bucket["count"], int), f"stage '{stage}' count must be int"
        assert isinstance(bucket["idea_ids"], list), f"stage '{stage}' idea_ids must be list"


# ---------------------------------------------------------------------------
# Page structure tests (static analysis of web/app/ideas/page.tsx)
# ---------------------------------------------------------------------------


def _page_src() -> str:
    assert _IDEAS_PAGE.is_file(), f"Ideas page not found: {_IDEAS_PAGE}"
    return _IDEAS_PAGE.read_text(encoding="utf-8")


def test_ideas_page_file_exists() -> None:
    """web/app/ideas/page.tsx must exist."""
    assert _IDEAS_PAGE.is_file(), f"Missing {_IDEAS_PAGE}"


def test_ideas_page_idea_cards_before_lifecycle_dashboard() -> None:
    """Idea cards section must appear before the lifecycle dashboard in the page source.

    The page must lead with living idea content before any stage/lifecycle
    operational views, so that newcomers see ideas first.
    """
    src = _page_src()

    # Find position of the ideas/hierarchy section heading
    hierarchy_match = re.search(
        r'(ideas-hierarchy-heading|Portfolio hierarchy|IdeaHierarchySubtree)',
        src,
    )
    assert hierarchy_match is not None, (
        "Ideas page must include an ideas hierarchy/cards section"
    )

    # Find position of the lifecycle dashboard section
    dashboard_match = re.search(
        r'(<details|lifecycle.*dashboard|Show lifecycle|stage transitions)',
        src,
        re.IGNORECASE,
    )
    assert dashboard_match is not None, (
        "Ideas page must include a lifecycle dashboard section"
    )

    assert hierarchy_match.start() < dashboard_match.start(), (
        "Idea cards/hierarchy section must appear BEFORE the lifecycle dashboard "
        "in page.tsx. Lead with living ideas, push dashboard below."
    )


def test_ideas_page_lifecycle_dashboard_is_collapsible_details_element() -> None:
    """The lifecycle dashboard must be wrapped in a <details> element (collapsed by default).

    This ensures the operational view is below the fold for newcomers and only
    expanded on demand by returning users.
    """
    src = _page_src()
    assert "<details" in src, (
        "Lifecycle dashboard must be in a <details> element so it is collapsed by default"
    )


def test_ideas_page_lifecycle_dashboard_has_summary_toggle() -> None:
    """The <details> element must have a <summary> toggle label."""
    src = _page_src()
    assert "<summary" in src, (
        "Lifecycle <details> must include a <summary> element for the toggle label"
    )


def test_ideas_page_stage_progress_bars_inside_details() -> None:
    """Progress bars for stage distribution must be inside the <details> element.

    Stage progress bars are operational/secondary content. They must NOT appear
    above the idea cards.
    """
    src = _page_src()
    details_match = re.search(r'<details', src)
    assert details_match is not None, "page must have <details> element"

    # Look for JSX rendering of per-stage progress bars (not constant declarations)
    # These patterns match actual JSX usage, not TypeScript definitions at the top
    progress_phase_match = re.search(
        r'Progress by phase|bucket\.count / progress\.total_ideas|pct, 2\)\}%',
        src,
    )
    if progress_phase_match is None:
        pytest.skip("no explicit phase progress bar rendering found")

    assert progress_phase_match.start() > details_match.start(), (
        "Stage progress bar content must appear inside (after) the <details> element, "
        "not above the idea cards."
    )


def test_ideas_page_stage_transitions_inside_details() -> None:
    """Stage transitions listing must be inside the <details> element.

    Stage transitions are lifecycle-operational. They must appear below the fold.
    """
    src = _page_src()
    details_match = re.search(r'<details', src)
    assert details_match is not None, "page must have <details> element"

    # Look for JSX rendering of AUTO_ADVANCE_TRIGGERS (not its constant declaration)
    # The JSX map call renders stage transition items
    transitions_match = re.search(
        r'Stage transitions|{AUTO_ADVANCE_TRIGGERS\.map|trigger\.taskType|trigger\.detail',
        src,
    )
    if transitions_match is None:
        pytest.skip("no stage transitions markup found")

    assert transitions_match.start() > details_match.start(), (
        "Stage transitions must appear inside (after) the <details> element, "
        "not before the idea cards."
    )


def test_ideas_page_summary_stats_are_simple_numbers_not_bars() -> None:
    """Top-level summary stats show simple numbers, not stage-level progress bars.

    The summary grid (Total ideas, Value created, Remaining opportunity) provides
    one-glance orientation for newcomers without exposing pipeline detail.
    """
    src = _page_src()
    # Verify simple summary stat labels are present
    assert "Total ideas" in src or "total_ideas" in src, (
        "page must show 'Total ideas' stat"
    )
    # The stats section must NOT show stage-level breakdown at the top
    # (before the ideas section). We verify by checking STAGE_ORDER usage is
    # after the portfolio hierarchy section.
    hierarchy_match = re.search(r'ideas-hierarchy-heading|Portfolio hierarchy', src)
    # Use JSX render pattern (curly-brace map call) not the constant definition
    stage_order_match = re.search(r'\{STAGE_ORDER\.map|Progress by phase', src)
    if hierarchy_match and stage_order_match:
        assert stage_order_match.start() > hierarchy_match.start(), (
            "Stage iteration ({STAGE_ORDER.map}) JSX rendering must appear after the ideas "
            "section, not before. Do not show stage breakdown above idea cards."
        )


def test_ideas_page_page_heading_is_ideas() -> None:
    """The page h1 heading must be 'Ideas'."""
    src = _page_src()
    assert re.search(r'<h1[^>]*>\s*(Ideas|{[^}]+})\s*</h1>', src, re.IGNORECASE), (
        "Ideas page must have an h1 heading"
    )


def test_ideas_page_has_link_to_share_idea() -> None:
    """The page must include a link to share/submit a new idea."""
    src = _page_src()
    assert 'href="/"' in src or "share" in src.lower(), (
        "Ideas page must include a path for newcomers to share a new idea"
    )


def test_ideas_page_idea_card_links_to_detail_page() -> None:
    """Idea cards must link to individual idea detail pages (/ideas/{id})."""
    src = _page_src()
    assert '/ideas/${' in src or 'href={`/ideas/' in src or "encodeURIComponent(idea.id)" in src, (
        "Idea cards must link to /ideas/{id} detail pages"
    )


def test_ideas_page_no_stage_counts_in_top_stats_grid() -> None:
    """The top stats grid must NOT display stage bucket counts.

    Stage counts belong inside the lifecycle <details> section, not in the
    headline metrics visible before the idea cards.
    """
    src = _page_src()
    # Locate the top stats section — it contains 'Total ideas', 'Value created', etc.
    # There should not be stage labels (Backlog, Specced, etc.) in the top stats grid.
    top_stats_end = src.find("ideas-hierarchy-heading")
    if top_stats_end == -1:
        top_stats_end = src.find("Portfolio hierarchy")
    if top_stats_end == -1:
        pytest.skip("could not identify top stats section boundary")

    top_section = src[:top_stats_end]
    # Stage-specific labels that belong in the lifecycle dashboard
    for stage_label in ("Backlog", "Specced", "Implementing", "Reviewing", "Complete"):
        # Allow partial matches only if they're inside the details section
        # In the top section they shouldn't appear as bucket labels
        if f'">{stage_label}<' in top_section or f">{stage_label}</span>" in top_section:
            # Check it's not just part of a description or meta text
            context = top_section[max(0, top_section.find(stage_label)-50):top_section.find(stage_label)+50]
            assert "STAGE_LABEL" in context or "stage" not in context.lower(), (
                f"Stage label '{stage_label}' with count should not appear before idea cards. "
                "Push stage breakdown into the lifecycle <details> section."
            )
