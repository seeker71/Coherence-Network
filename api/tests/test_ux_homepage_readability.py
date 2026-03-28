"""Acceptance tests for specs/ux-homepage-readability.md (UX Homepage Readability).

Verifies R1–R4 (CSS tokens, hero headline, opacity floor, form readability) and R5
homepage data endpoints used by `/`. Does not modify `test_ui_readability.py`; mirrors
the spec's required assertions and adds focused checks for each requirement.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]

_CSS_PATH = REPO_ROOT / "web" / "app" / "globals.css"
_PAGE_PATH = REPO_ROOT / "web" / "app" / "page.tsx"
_FORM_PATH = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"


# --- Spec "Exact Test Assertions" (ux-homepage-readability) ---


def test_ux_coherence_score_endpoint() -> None:
    """Test 1 — homepage stat source healthy (GET /api/coherence/score)."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "signals_with_data" in data
    assert "total_signals" in data
    assert "computed_at" in data
    assert 0.0 <= data["score"] <= 1.0


def test_ux_homepage_readability_css_tokens() -> None:
    """Test 2 — globals.css tokens, .hero-headline, body::before bloom stop."""
    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    assert css_path.is_file()
    css = css_path.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css
    assert "--muted-foreground: 34 22% 90%" in css
    assert ".hero-headline" in css
    assert "hsl(28 92% 74% / 0.05)" in css


def test_ux_homepage_readability_page_classes() -> None:
    """Test 3 — hero-headline present; no text-foreground/N below 85 in page.tsx."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    assert page_path.is_file()
    content = page_path.read_text(encoding="utf-8")
    assert "hero-headline" in content
    assert "text-foreground/90" in content
    for match in re.findall(r"text-foreground/(\d+)", content):
        assert int(match) >= 85, f"Found text-foreground/{match} — minimum allowed is 85"


def test_ux_idea_submit_form_readability() -> None:
    """Test 4 — idea form: placeholder /85, body /90, no /70."""
    form_path = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
    assert form_path.is_file()
    content = form_path.read_text(encoding="utf-8")
    assert "placeholder:text-foreground/85" in content
    assert "text-foreground/90" in content
    assert "text-foreground/70" not in content


# --- R2 — Hero H1 uses hero-headline ---


def test_ux_r2_h1_has_hero_headline_class() -> None:
    content = _PAGE_PATH.read_text(encoding="utf-8")
    assert re.search(
        r"<h1[^>]*\bhero-headline\b",
        content,
        re.DOTALL,
    ), "Hero <h1> must include class hero-headline"


# --- R1 — granular CSS (spec prose) ---


@pytest.mark.parametrize(
    "required_substring",
    [
        "color: hsl(var(--foreground))",
        "text-shadow: 0 2px 28px hsl(20 40% 6% / 0.55)",
    ],
)
def test_ux_r1_hero_headline_rule_contains(required_substring: str) -> None:
    css = _CSS_PATH.read_text(encoding="utf-8")
    assert required_substring in css


def test_ux_r1_body_before_bloom_includes_spec_first_stop() -> None:
    css = _CSS_PATH.read_text(encoding="utf-8")
    assert "body::before" in css
    assert "radial-gradient(520px 340px at 14% 24%, hsl(28 92% 74% / 0.05)" in css


# --- R4 — form fields explicitly ---


def test_ux_r4_textarea_includes_placeholder_and_body_opacity_classes() -> None:
    content = _FORM_PATH.read_text(encoding="utf-8")
    m = re.search(r"<textarea\b[\s\S]*?className=\"([^\"]+)\"", content)
    assert m, "textarea with className must exist"
    cls = m.group(1)
    assert "placeholder:text-foreground/85" in cls
    assert "text-foreground/90" in cls


def test_ux_r4_name_input_includes_placeholder_and_body_opacity_classes() -> None:
    content = _FORM_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"<input\b[\s\S]*?type=\"text\"[\s\S]*?className=\"([^\"]+)\"",
        content,
    )
    assert m, "text input with className must exist"
    cls = m.group(1)
    assert "placeholder:text-foreground/85" in cls
    assert "text-foreground/90" in cls


# --- R5 — homepage API contract (unchanged shapes) ---


def test_ux_r5_get_ideas_matches_homepage_contract() -> None:
    r = client.get("/api/ideas")
    assert r.status_code == 200
    data = r.json()
    assert "ideas" in data
    assert "summary" in data
    assert isinstance(data["ideas"], list)


def test_ux_r5_get_resonance_homepage_query() -> None:
    r = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert r.status_code == 200
    data = r.json()
    if isinstance(data, dict) and "ideas" in data:
        assert isinstance(data["ideas"], list)
    else:
        assert isinstance(data, list)


def test_ux_r5_get_federation_nodes() -> None:
    r = client.get("/api/federation/nodes")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


# --- Verification scenarios (scripted equivalents) ---


def test_ux_scenario1_grep_foreground_lines_match_spec() -> None:
    """Scenario 1 — exact :root token lines for dark canvas (line numbers may drift)."""
    lines = _CSS_PATH.read_text(encoding="utf-8").splitlines()
    fg_lines = [ln for ln in lines if "--foreground:" in ln and "muted" not in ln.lower()]
    muted_lines = [ln for ln in lines if "--muted-foreground:" in ln]
    assert any("38 32% 93%" in ln for ln in fg_lines)
    assert any("34 22% 90%" in ln for ln in muted_lines)


def test_ux_scenario2_no_disallowed_text_foreground_slash_in_page() -> None:
    """Scenario 2 — any text-foreground/N in page must be N >= 85 (same as Test 3, explicit)."""
    content = _PAGE_PATH.read_text(encoding="utf-8")
    bad = [m for m in re.findall(r"text-foreground/(\d+)", content) if int(m) < 85]
    assert not bad, f"Disallowed opacity modifiers: {bad}"


def test_ux_scenario3_form_no_text_foreground_7x_placeholder() -> None:
    """Scenario 3 — no text-foreground/7x in form (e.g. /70)."""
    content = _FORM_PATH.read_text(encoding="utf-8")
    assert not re.search(r"text-foreground/7\d", content)


def test_ux_page_loads_resonance_url_matches_implementation() -> None:
    """Homepage loader uses the same resonance URL as the spec table."""
    content = _PAGE_PATH.read_text(encoding="utf-8")
    assert "/api/ideas/resonance?window_hours=72&limit=3" in content

