"""Ux Homepage Readability — spec 150 (ux-homepage-readability).

Acceptance criteria: minimum body-copy opacity ≥ 0.85, design tokens + toned bloom,
hero headline prominence, unchanged public API shapes for homepage data.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]

AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _assert_text_foreground_opacity_min(content: str, source_label: str, minimum: int = 85) -> None:
    """R1: body copy uses text-foreground/N only when N >= minimum."""
    for match in re.findall(r"text-foreground/(\d+)", content):
        value = int(match)
        assert value >= minimum, (
            f"{source_label}: text-foreground/{match} is below minimum {minimum}"
        )


def test_homepage_readability_contract_files() -> None:
    """Spec 150 acceptance: homepage + form sources meet static readability contract."""
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    form_path = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
    for path in (page_path, css_path, form_path):
        assert path.is_file(), f"Missing contract file: {path}"

    page_src = page_path.read_text(encoding="utf-8")
    _assert_text_foreground_opacity_min(page_src, "web/app/page.tsx")
    assert "hero-headline" in page_src
    assert "text-foreground/90" in page_src

    form_src = form_path.read_text(encoding="utf-8")
    _assert_text_foreground_opacity_min(form_src, "web/components/idea_submit_form.tsx")
    assert "placeholder:text-foreground/85" in form_src
    assert "text-foreground/70" not in form_src

    css_src = css_path.read_text(encoding="utf-8")
    assert "--foreground: 38 32% 93%" in css_src
    assert "--muted-foreground: 34 22% 90%" in css_src
    assert ".hero-headline" in css_src
    assert "hsl(28 92% 74% / 0.05)" in css_src


def test_ux_homepage_readability_r3_hero_headline_full_opacity() -> None:
    """R3: hero headline uses full-opacity foreground (CSS), not reduced opacity classes."""
    css_path = REPO_ROOT / "web" / "app" / "globals.css"
    css = css_path.read_text(encoding="utf-8")
    assert ".hero-headline" in css
    assert "color: hsl(var(--foreground))" in css
    page_path = REPO_ROOT / "web" / "app" / "page.tsx"
    page = page_path.read_text(encoding="utf-8")
    for line in page.splitlines():
        stripped = line.strip()
        if "<h1" in stripped and "hero-headline" in stripped:
            assert "text-foreground/" not in stripped, "Hero H1 must not use reduced text-foreground opacity"
            break
    else:
        pytest.fail("Expected <h1> with hero-headline on homepage")


def test_ux_homepage_readability_r4_coherence_score_endpoint() -> None:
    """R4: GET /api/coherence/score shape unchanged for homepage."""
    response = client.get("/api/coherence/score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "signals_with_data" in data
    assert "total_signals" in data
    assert "computed_at" in data
    assert 0.0 <= float(data["score"]) <= 1.0


def test_ux_homepage_readability_r4_ideas_and_resonance_endpoints() -> None:
    """R4: ideas list + resonance feed used on / remain compatible."""
    listed = client.get("/api/ideas")
    assert listed.status_code == 200
    payload = listed.json()
    assert "ideas" in payload

    resonance = client.get("/api/ideas/resonance?window_hours=72&limit=3")
    assert resonance.status_code == 200
    res_data = resonance.json()
    assert isinstance(res_data, list)


def test_ux_homepage_readability_r4_federation_nodes_endpoint() -> None:
    """R4: GET /api/federation/nodes returns a list (homepage node count)."""
    response = client.get("/api/federation/nodes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_ux_homepage_readability_scenario_create_read_patch_list() -> None:
    """Verification scenario 1: idea lifecycle used by landing form stays intact."""
    idea_id = f"ux-hr-{uuid.uuid4().hex[:12]}"
    body = {
        "id": idea_id,
        "name": "Ux homepage readability",
        "description": "Spec 150 ux-homepage-readability contract test.",
        "potential_value": 10.0,
        "estimated_cost": 1.0,
        "confidence": 0.5,
        "manifestation_status": "none",
    }
    create = client.post("/api/ideas", json=body)
    assert create.status_code == 201, create.text
    dup = client.post("/api/ideas", json=body)
    assert dup.status_code == 409
    got = client.get(f"/api/ideas/{idea_id}")
    assert got.status_code == 200
    patched = client.patch(
        f"/api/ideas/{idea_id}",
        json={"manifestation_status": "partial"},
        headers=AUTH_HEADERS,
    )
    assert patched.status_code == 200
    listed = client.get("/api/ideas")
    assert listed.status_code == 200
    ids = {str(i.get("id")) for i in listed.json().get("ideas", [])}
    assert idea_id in ids


def test_ux_homepage_readability_resonance_invalid_window_422() -> None:
    """Scenario 4 edge: invalid window is rejected (not 500)."""
    response = client.get("/api/ideas/resonance?window_hours=-1&limit=3")
    assert response.status_code == 422
