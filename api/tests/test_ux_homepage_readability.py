"""UX Homepage Readability tests (ux-homepage-readability).

Verifies acceptance criteria from specs/ux-homepage-readability.md:
- R1: CSS token values in globals.css (--foreground, --muted-foreground, hero-headline, bloom)
- R2: Hero headline class on <h1> in page.tsx
- R3: Body copy opacity floor (>= 85) in page.tsx
- R4: Form component opacity standards in idea_submit_form.tsx
- R5: API contract unchanged for all four homepage endpoints
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
GLOBALS_CSS = REPO_ROOT / "web" / "app" / "globals.css"
PAGE_TSX = REPO_ROOT / "web" / "app" / "page.tsx"
FORM_TSX = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"


# ---------------------------------------------------------------------------
# R1 — CSS Token Values (globals.css)
# ---------------------------------------------------------------------------


def test_globals_css_file_exists() -> None:
    """globals.css must exist at the expected path."""
    assert GLOBALS_CSS.is_file(), f"Missing {GLOBALS_CSS}"


def test_foreground_token_value() -> None:
    """--foreground must be 38 32% 93% (warm light tone for dark canvas)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css, (
        "--foreground token not found or has wrong value. Expected '38 32% 93%'"
    )


def test_muted_foreground_token_value() -> None:
    """--muted-foreground must be 34 22% 90%."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--muted-foreground: 34 22% 90%" in css, (
        "--muted-foreground token not found or has wrong value. Expected '34 22% 90%'"
    )


def test_hero_headline_class_in_css() -> None:
    """.hero-headline CSS class must exist in globals.css."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert ".hero-headline" in css, ".hero-headline class missing from globals.css"


def test_hero_headline_uses_foreground_token() -> None:
    """.hero-headline must use hsl(var(--foreground)) for color."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "hsl(var(--foreground))" in css, (
        "hsl(var(--foreground)) not found in globals.css. "
        "hero-headline must use this CSS variable."
    )


def test_bloom_overlay_softened_opacity() -> None:
    """body::before bloom overlay first gradient stop must be hsl(28 92% 74% / 0.05)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "hsl(28 92% 74% / 0.05)" in css, (
        "Bloom overlay not at correct opacity. "
        "Expected 'hsl(28 92% 74% / 0.05)' in body::before gradient."
    )


# ---------------------------------------------------------------------------
# R2 — Hero Headline Class (page.tsx)
# ---------------------------------------------------------------------------


def test_page_tsx_exists() -> None:
    """web/app/page.tsx must exist."""
    assert PAGE_TSX.is_file(), f"Missing {PAGE_TSX}"


def test_hero_headline_class_used_in_page() -> None:
    """page.tsx must apply hero-headline class to the <h1> element."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "hero-headline" in content, (
        "hero-headline class not found in page.tsx. "
        "The <h1> hero headline must use this CSS class."
    )


# ---------------------------------------------------------------------------
# R3 — Body Copy Opacity Floor (page.tsx)
# ---------------------------------------------------------------------------


def test_page_uses_foreground_90_class() -> None:
    """page.tsx must use text-foreground/90 for secondary body copy."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "text-foreground/90" in content, (
        "text-foreground/90 not found in page.tsx. "
        "Secondary body copy must use at least 90% opacity."
    )


def test_page_no_foreground_below_85() -> None:
    """page.tsx must not use text-foreground/<85 on prose text (opacity floor is 85)."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    for match in re.findall(r"text-foreground/(\d+)", content):
        value = int(match)
        assert value >= 85, (
            f"Found text-foreground/{match} in page.tsx — minimum allowed opacity is 85. "
            "Raise to text-foreground/85, /90, or text-foreground (full)."
        )


def test_page_no_foreground_70() -> None:
    """Specifically verify text-foreground/70 is absent from page.tsx."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "text-foreground/70" not in content, (
        "text-foreground/70 found in page.tsx — this violates the 85% opacity floor."
    )


def test_page_no_foreground_60() -> None:
    """Specifically verify text-foreground/60 is absent from page.tsx."""
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "text-foreground/60" not in content, (
        "text-foreground/60 found in page.tsx — this violates the 85% opacity floor."
    )


# ---------------------------------------------------------------------------
# R4 — Form Component Opacity (idea_submit_form.tsx)
# ---------------------------------------------------------------------------


def test_form_tsx_exists() -> None:
    """web/components/idea_submit_form.tsx must exist."""
    assert FORM_TSX.is_file(), f"Missing {FORM_TSX}"


def test_form_placeholder_opacity() -> None:
    """idea_submit_form.tsx must use placeholder:text-foreground/85 on inputs."""
    content = FORM_TSX.read_text(encoding="utf-8")
    assert "placeholder:text-foreground/85" in content, (
        "placeholder:text-foreground/85 not found in idea_submit_form.tsx. "
        "Textarea and input placeholders must use 85% opacity."
    )


def test_form_body_text_opacity() -> None:
    """idea_submit_form.tsx must use text-foreground/90 for form body text."""
    content = FORM_TSX.read_text(encoding="utf-8")
    assert "text-foreground/90" in content, (
        "text-foreground/90 not found in idea_submit_form.tsx. "
        "Form body text must use 90% opacity."
    )


def test_form_no_foreground_70() -> None:
    """idea_submit_form.tsx must not use text-foreground/70."""
    content = FORM_TSX.read_text(encoding="utf-8")
    assert "text-foreground/70" not in content, (
        "text-foreground/70 found in idea_submit_form.tsx — forbidden by R4. "
        "Replace with text-foreground/85 or text-foreground/90."
    )


# ---------------------------------------------------------------------------
# R5 — API Contract Unchanged (homepage data endpoints)
# ---------------------------------------------------------------------------


def test_coherence_score_endpoint_shape() -> None:
    """GET /api/coherence/score must return 200 with required score fields."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data, "Missing 'score' field in /api/coherence/score response"
    assert "signals_with_data" in data, "Missing 'signals_with_data' field"
    assert "total_signals" in data, "Missing 'total_signals' field"
    assert "computed_at" in data, "Missing 'computed_at' field"
    assert 0.0 <= data["score"] <= 1.0, (
        f"score out of range [0.0, 1.0]: got {data['score']}"
    )


def test_ideas_list_endpoint_returns_200() -> None:
    """GET /api/ideas must return 200 (homepage uses this for idea count stats)."""
    response = client.get("/api/ideas")
    assert response.status_code == 200


def test_ideas_list_returns_ideas_key() -> None:
    """GET /api/ideas response must contain 'ideas' key (spec-frozen shape)."""
    response = client.get("/api/ideas")
    assert response.status_code == 200
    data = response.json()
    assert "ideas" in data, (
        "GET /api/ideas missing 'ideas' key — homepage depends on this response shape."
    )


def test_resonance_endpoint_returns_200_list() -> None:
    """GET /api/ideas/resonance?window_hours=72&limit=3 must return 200 with a list."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list), (
        f"Expected list from /api/ideas/resonance, got {type(data).__name__}"
    )


def test_resonance_endpoint_respects_limit() -> None:
    """Resonance endpoint must respect the limit parameter (homepage uses limit=3)."""
    response = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 3, (
        f"Expected at most 3 resonance items with limit=3, got {len(data)}"
    )


def test_federation_nodes_endpoint_returns_200() -> None:
    """GET /api/federation/nodes must return 200 (homepage node count stat)."""
    response = client.get("/api/federation/nodes")
    assert response.status_code == 200


def test_federation_nodes_returns_nodes_key() -> None:
    """GET /api/federation/nodes response must contain a nodes list."""
    response = client.get("/api/federation/nodes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type from /api/federation/nodes: {type(data).__name__}"
    )


# ---------------------------------------------------------------------------
# Regression guards — ensure tokens and classes stay correct together
# ---------------------------------------------------------------------------


def test_css_and_page_both_have_hero_headline() -> None:
    """hero-headline must exist in both globals.css (definition) and page.tsx (usage)."""
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    page = PAGE_TSX.read_text(encoding="utf-8")
    assert ".hero-headline" in css, ".hero-headline class missing from globals.css"
    assert "hero-headline" in page, "hero-headline class not applied in page.tsx"


def test_all_four_spec_assertions_combined() -> None:
    """Single combined test matching the exact spec assertions for all 4 checks."""
    # Test 2 — CSS tokens
    css = GLOBALS_CSS.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css
    assert "--muted-foreground: 34 22% 90%" in css
    assert ".hero-headline" in css
    assert "hsl(28 92% 74% / 0.05)" in css

    # Test 3 — page classes
    content = PAGE_TSX.read_text(encoding="utf-8")
    assert "hero-headline" in content
    assert "text-foreground/90" in content
    for match in re.findall(r"text-foreground/(\d+)", content):
        assert int(match) >= 85, f"Found text-foreground/{match} — minimum allowed is 85"

    # Test 4 — form readability
    form = FORM_TSX.read_text(encoding="utf-8")
    assert "placeholder:text-foreground/85" in form
    assert "text-foreground/90" in form
    assert "text-foreground/70" not in form
