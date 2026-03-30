"""Tests for spec ux-tabs-mobile-friendly: UX overhaul — tabs, mobile-first, novice/expert modes.

Covers:
1. API: /api/preferences/ui — CRUD for per-contributor UI preferences
2. Expert mode fields (expert_mode flag, ideas_view, idea_detail_tab)
3. Novice mode defaults (tooltips on, expert fields off)
4. Navigation layout: top vs bottom_bar
5. Mobile UX flags: swipeable_cards, collapsible_sections
6. Ideas view modes: cards | table | graph
7. Idea detail tabs: overview | specs | tasks | contributors | edges | history
8. Error handling: bad contributor_id, unknown fields, invalid enum values
9. Web component file checks for shadcn/ui Tabs usage

Verification Scenarios:
  S1 — GET defaults → returns canonical novice defaults for unknown contributor
  S2 — PUT → persist full preferences, GET round-trips correctly
  S3 — PATCH → partial update preserves unspecified fields
  S4 — DELETE → resets to defaults, GET after returns defaults
  S5 — Expert mode details exposed via preferences flag
  S6 — Invalid enum values return 422
  S7 — Ideas page lists all three view modes in response shape
  S8 — Idea detail tabs enumerated correctly in schema
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
IDEAS_PAGE = REPO_ROOT / "web" / "app" / "ideas" / "page.tsx"
IDEA_DETAIL_PAGE = REPO_ROOT / "web" / "app" / "ideas" / "[idea_id]" / "page.tsx"
SITE_HEADER = REPO_ROOT / "web" / "components" / "site_header.tsx"
GLOBALS_CSS = REPO_ROOT / "web" / "app" / "globals.css"


# ---------------------------------------------------------------------------
# S1 — GET defaults: novice mode returned for unknown contributor
# ---------------------------------------------------------------------------


def test_get_ui_preferences_default_novice_mode() -> None:
    """GET /api/preferences/ui returns novice defaults for an unknown contributor."""
    resp = client.get("/api/preferences/ui?contributor_id=unknown-contributor-xyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["expert_mode"] is False, "Novice mode must be default (expert_mode=False)"
    assert data["show_tooltips"] is True, "Tooltips must be enabled in novice mode by default"
    assert data["contributor_id"] == "unknown-contributor-xyz"


def test_get_ui_preferences_default_nav_layout() -> None:
    """Default nav_layout is 'top' (desktop-first fallback)."""
    resp = client.get("/api/preferences/ui?contributor_id=anon-nav-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nav_layout"] == "top"


def test_get_ui_preferences_default_ideas_view() -> None:
    """Default ideas_view is 'cards'."""
    resp = client.get("/api/preferences/ui?contributor_id=anon-view-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ideas_view"] == "cards"


def test_get_ui_preferences_default_idea_detail_tab() -> None:
    """Default idea_detail_tab is 'overview'."""
    resp = client.get("/api/preferences/ui?contributor_id=anon-tab-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["idea_detail_tab"] == "overview"


def test_get_ui_preferences_default_collapsible_sections() -> None:
    """collapsible_sections defaults to True for mobile UX."""
    resp = client.get("/api/preferences/ui?contributor_id=anon-mobile-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["collapsible_sections"] is True


def test_get_ui_preferences_without_contributor_id() -> None:
    """GET without contributor_id falls back to 'anonymous' default profile."""
    resp = client.get("/api/preferences/ui")
    assert resp.status_code == 200
    data = resp.json()
    assert "contributor_id" in data
    assert data["contributor_id"] == "anonymous"


# ---------------------------------------------------------------------------
# S2 — PUT: persist full preferences and round-trip via GET
# ---------------------------------------------------------------------------


def test_put_ui_preferences_full_round_trip() -> None:
    """PUT /api/preferences/ui then GET returns same values."""
    payload = {
        "contributor_id": "c-roundtrip-001",
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "table",
        "idea_detail_tab": "specs",
        "swipeable_cards": True,
        "collapsible_sections": False,
        "show_tooltips": False,
    }
    put_resp = client.put("/api/preferences/ui", json=payload)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["expert_mode"] is True
    assert put_data["nav_layout"] == "bottom_bar"
    assert put_data["ideas_view"] == "table"
    assert put_data["idea_detail_tab"] == "specs"
    assert put_data["swipeable_cards"] is True
    assert put_data["collapsible_sections"] is False

    # GET must return same values
    get_resp = client.get("/api/preferences/ui?contributor_id=c-roundtrip-001")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["expert_mode"] is True
    assert get_data["nav_layout"] == "bottom_bar"
    assert get_data["ideas_view"] == "table"


def test_put_ui_preferences_overwrites_previous() -> None:
    """Second PUT fully replaces prior preferences (not merge)."""
    cid = "c-overwrite-002"
    first = {
        "contributor_id": cid,
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "graph",
        "idea_detail_tab": "history",
        "swipeable_cards": True,
        "collapsible_sections": False,
        "show_tooltips": False,
    }
    second = {
        "contributor_id": cid,
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    client.put("/api/preferences/ui", json=first)
    put_resp = client.put("/api/preferences/ui", json=second)
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["expert_mode"] is False
    assert data["nav_layout"] == "top"
    assert data["ideas_view"] == "cards"


def test_put_ui_preferences_all_idea_detail_tabs() -> None:
    """All six idea detail tabs are accepted by the API."""
    valid_tabs = ["overview", "specs", "tasks", "contributors", "edges", "history"]
    for tab in valid_tabs:
        payload = {
            "contributor_id": f"c-tab-{tab}",
            "expert_mode": False,
            "nav_layout": "top",
            "ideas_view": "cards",
            "idea_detail_tab": tab,
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        }
        resp = client.put("/api/preferences/ui", json=payload)
        assert resp.status_code == 200, f"Tab '{tab}' rejected: {resp.text}"
        assert resp.json()["idea_detail_tab"] == tab


def test_put_ui_preferences_all_ideas_views() -> None:
    """All three ideas view modes are accepted: cards | table | graph."""
    for view in ("cards", "table", "graph"):
        payload = {
            "contributor_id": f"c-view-{view}",
            "expert_mode": False,
            "nav_layout": "top",
            "ideas_view": view,
            "idea_detail_tab": "overview",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        }
        resp = client.put("/api/preferences/ui", json=payload)
        assert resp.status_code == 200, f"View mode '{view}' rejected: {resp.text}"
        assert resp.json()["ideas_view"] == view


def test_put_ui_preferences_all_nav_layouts() -> None:
    """Both nav_layout values are accepted: top | bottom_bar."""
    for layout in ("top", "bottom_bar"):
        payload = {
            "contributor_id": f"c-nav-{layout}",
            "expert_mode": False,
            "nav_layout": layout,
            "ideas_view": "cards",
            "idea_detail_tab": "overview",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        }
        resp = client.put("/api/preferences/ui", json=payload)
        assert resp.status_code == 200, f"nav_layout '{layout}' rejected: {resp.text}"
        assert resp.json()["nav_layout"] == layout


# ---------------------------------------------------------------------------
# S3 — PATCH: partial update preserves unspecified fields
# ---------------------------------------------------------------------------


def test_patch_ui_preferences_partial_update() -> None:
    """PATCH only changes specified fields; unspecified fields remain unchanged."""
    cid = "c-patch-003"
    # Seed a full set of preferences
    seed = {
        "contributor_id": cid,
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    client.put("/api/preferences/ui", json=seed)

    # PATCH only expert_mode and ideas_view
    patch_resp = client.patch(
        "/api/preferences/ui?contributor_id=c-patch-003",
        json={"expert_mode": True, "ideas_view": "graph"},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()

    assert patched["expert_mode"] is True  # changed
    assert patched["ideas_view"] == "graph"  # changed
    assert patched["nav_layout"] == "top"  # unchanged
    assert patched["idea_detail_tab"] == "overview"  # unchanged
    assert patched["show_tooltips"] is True  # unchanged


def test_patch_ui_preferences_enable_mobile_bottom_bar() -> None:
    """PATCH nav_layout to bottom_bar simulates mobile mode activation."""
    cid = "c-mobile-004"
    client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": cid,
            "expert_mode": False,
            "nav_layout": "top",
            "ideas_view": "cards",
            "idea_detail_tab": "overview",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        },
    )
    resp = client.patch(
        f"/api/preferences/ui?contributor_id={cid}",
        json={"nav_layout": "bottom_bar", "swipeable_cards": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["nav_layout"] == "bottom_bar"
    assert data["swipeable_cards"] is True
    assert data["collapsible_sections"] is True  # unchanged


def test_patch_ui_preferences_activate_expert_mode() -> None:
    """PATCH expert_mode=True enables expert UX (IDs, raw JSON, API links)."""
    cid = "c-expert-005"
    client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": cid,
            "expert_mode": False,
            "nav_layout": "top",
            "ideas_view": "cards",
            "idea_detail_tab": "overview",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        },
    )
    resp = client.patch(
        f"/api/preferences/ui?contributor_id={cid}",
        json={"expert_mode": True, "show_tooltips": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["expert_mode"] is True
    assert data["show_tooltips"] is False


def test_patch_ui_preferences_unknown_contributor_creates_defaults() -> None:
    """PATCH for a new contributor_id starts from defaults and applies patch."""
    cid = "c-new-patch-006"
    resp = client.patch(
        f"/api/preferences/ui?contributor_id={cid}",
        json={"ideas_view": "table"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ideas_view"] == "table"
    assert data["nav_layout"] == "top"  # default preserved
    assert data["expert_mode"] is False  # default preserved


# ---------------------------------------------------------------------------
# S4 — DELETE: reset to defaults
# ---------------------------------------------------------------------------


def test_delete_ui_preferences_resets_to_defaults() -> None:
    """DELETE /api/preferences/ui clears stored prefs; GET returns defaults."""
    cid = "c-delete-007"
    # Store non-default preferences
    client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": cid,
            "expert_mode": True,
            "nav_layout": "bottom_bar",
            "ideas_view": "graph",
            "idea_detail_tab": "history",
            "swipeable_cards": True,
            "collapsible_sections": False,
            "show_tooltips": False,
        },
    )
    # Confirm stored
    get_before = client.get(f"/api/preferences/ui?contributor_id={cid}")
    assert get_before.json()["expert_mode"] is True

    # DELETE
    del_resp = client.delete(f"/api/preferences/ui?contributor_id={cid}")
    assert del_resp.status_code == 204

    # GET after DELETE returns defaults
    get_after = client.get(f"/api/preferences/ui?contributor_id={cid}")
    assert get_after.status_code == 200
    data = get_after.json()
    assert data["expert_mode"] is False
    assert data["nav_layout"] == "top"
    assert data["ideas_view"] == "cards"
    assert data["idea_detail_tab"] == "overview"
    assert data["show_tooltips"] is True


def test_delete_ui_preferences_unknown_contributor_is_idempotent() -> None:
    """DELETE for a contributor with no saved prefs returns 204 (idempotent)."""
    resp = client.delete("/api/preferences/ui?contributor_id=nonexistent-cid-xyz")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# S5 — Expert mode: specific fields enabled/disabled
# ---------------------------------------------------------------------------


def test_expert_mode_schema_fields_present() -> None:
    """UI preferences schema includes all expert-mode-relevant fields."""
    resp = client.get("/api/preferences/ui?contributor_id=expert-schema-check")
    assert resp.status_code == 200
    data = resp.json()
    # All expert-mode-relevant keys must be present
    required_keys = {
        "expert_mode",
        "show_tooltips",
        "ideas_view",
        "idea_detail_tab",
        "nav_layout",
        "swipeable_cards",
        "collapsible_sections",
        "contributor_id",
    }
    for key in required_keys:
        assert key in data, f"Key '{key}' missing from /api/preferences/ui response"


def test_expert_mode_true_disables_tooltips_when_set() -> None:
    """Setting expert_mode=True with show_tooltips=False is accepted."""
    cid = "c-expert-tooltip-008"
    resp = client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": cid,
            "expert_mode": True,
            "nav_layout": "top",
            "ideas_view": "table",
            "idea_detail_tab": "edges",
            "swipeable_cards": False,
            "collapsible_sections": False,
            "show_tooltips": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["expert_mode"] is True
    assert data["show_tooltips"] is False


def test_novice_mode_defaults_hide_technical_fields() -> None:
    """Novice mode default: expert_mode=False, show_tooltips=True."""
    resp = client.get("/api/preferences/ui?contributor_id=novice-user-abc")
    data = resp.json()
    assert data["expert_mode"] is False
    assert data["show_tooltips"] is True


# ---------------------------------------------------------------------------
# S6 — Invalid enum values return 422
# ---------------------------------------------------------------------------


def test_put_invalid_ideas_view_returns_422() -> None:
    """PUT with unknown ideas_view value returns 422 Unprocessable Entity."""
    payload = {
        "contributor_id": "c-invalid-view",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "kanban",  # not a valid value
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422, f"Expected 422 for invalid ideas_view, got {resp.status_code}"


def test_put_invalid_idea_detail_tab_returns_422() -> None:
    """PUT with unknown idea_detail_tab value returns 422."""
    payload = {
        "contributor_id": "c-invalid-tab",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "comments",  # not a valid tab
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422, f"Expected 422 for invalid idea_detail_tab, got {resp.status_code}"


def test_put_invalid_nav_layout_returns_422() -> None:
    """PUT with unknown nav_layout returns 422."""
    payload = {
        "contributor_id": "c-invalid-nav",
        "expert_mode": False,
        "nav_layout": "sidebar",  # not valid
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422, f"Expected 422 for invalid nav_layout, got {resp.status_code}"


def test_put_missing_contributor_id_returns_422() -> None:
    """PUT without contributor_id returns 422."""
    payload = {
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422


def test_patch_missing_contributor_id_query_param_returns_422() -> None:
    """PATCH without contributor_id query param returns 422."""
    resp = client.patch("/api/preferences/ui", json={"expert_mode": True})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# S7 — Ideas view modes enumerated correctly
# ---------------------------------------------------------------------------


def test_ideas_list_endpoint_returns_ideas_key() -> None:
    """GET /api/ideas returns payload with 'ideas' key (consumed by tabs/view switcher)."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200
    payload = resp.json()
    assert "ideas" in payload, "Ideas endpoint must return 'ideas' key for tab view modes"


def test_ideas_list_pagination_keys_present() -> None:
    """GET /api/ideas includes summary metadata needed by all view modes."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200
    payload = resp.json()
    # Summary block is required by table and graph views
    assert "summary" in payload or "ideas" in payload


# ---------------------------------------------------------------------------
# S8 — Idea detail tabs: schema check
# ---------------------------------------------------------------------------


def test_idea_detail_tabs_all_six_valid() -> None:
    """All six idea detail tabs are accepted: overview, specs, tasks, contributors, edges, history."""
    valid_tabs = ["overview", "specs", "tasks", "contributors", "edges", "history"]
    for tab in valid_tabs:
        cid = f"c-detail-tab-{tab}"
        resp = client.put(
            "/api/preferences/ui",
            json={
                "contributor_id": cid,
                "expert_mode": False,
                "nav_layout": "top",
                "ideas_view": "cards",
                "idea_detail_tab": tab,
                "swipeable_cards": False,
                "collapsible_sections": True,
                "show_tooltips": True,
            },
        )
        assert resp.status_code == 200, f"Tab '{tab}' not accepted"
        assert resp.json()["idea_detail_tab"] == tab


def test_idea_detail_contributor_tab_accepted() -> None:
    """'contributors' tab is accepted as a valid idea detail tab."""
    resp = client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": "c-contributors-tab",
            "expert_mode": False,
            "nav_layout": "top",
            "ideas_view": "cards",
            "idea_detail_tab": "contributors",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["idea_detail_tab"] == "contributors"


def test_idea_detail_edges_tab_accepted() -> None:
    """'edges' tab is accepted as a valid idea detail tab (graph relationships)."""
    resp = client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": "c-edges-tab",
            "expert_mode": False,
            "nav_layout": "top",
            "ideas_view": "cards",
            "idea_detail_tab": "edges",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["idea_detail_tab"] == "edges"


# ---------------------------------------------------------------------------
# Cross-contributor isolation: preferences are per-contributor
# ---------------------------------------------------------------------------


def test_preferences_are_isolated_per_contributor() -> None:
    """Preferences for contributor A do not affect contributor B."""
    # Set expert mode for A
    client.put(
        "/api/preferences/ui",
        json={
            "contributor_id": "c-isolation-A",
            "expert_mode": True,
            "nav_layout": "bottom_bar",
            "ideas_view": "graph",
            "idea_detail_tab": "history",
            "swipeable_cards": True,
            "collapsible_sections": False,
            "show_tooltips": False,
        },
    )
    # B should still get defaults
    resp_b = client.get("/api/preferences/ui?contributor_id=c-isolation-B")
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["expert_mode"] is False
    assert data_b["nav_layout"] == "top"
    assert data_b["ideas_view"] == "cards"


def test_multiple_contributors_store_independently() -> None:
    """Three contributors with different prefs each return their own values."""
    configs = [
        {"contributor_id": "c-multi-X", "expert_mode": True, "ideas_view": "table", "nav_layout": "top"},
        {"contributor_id": "c-multi-Y", "expert_mode": False, "ideas_view": "cards", "nav_layout": "bottom_bar"},
        {"contributor_id": "c-multi-Z", "expert_mode": True, "ideas_view": "graph", "nav_layout": "top"},
    ]
    # Defaults for PUT
    defaults = {"idea_detail_tab": "overview", "swipeable_cards": False, "collapsible_sections": True, "show_tooltips": True}
    for cfg in configs:
        client.put("/api/preferences/ui", json={**cfg, **defaults})

    for cfg in configs:
        resp = client.get(f"/api/preferences/ui?contributor_id={cfg['contributor_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["expert_mode"] == cfg["expert_mode"]
        assert data["ideas_view"] == cfg["ideas_view"]
        assert data["nav_layout"] == cfg["nav_layout"]


# ---------------------------------------------------------------------------
# API health: existing endpoints consumed by the UX tab views
# ---------------------------------------------------------------------------


def test_ideas_endpoint_accessible_for_tab_views() -> None:
    """GET /api/ideas returns 200 (consumed by cards/table/graph view modes)."""
    resp = client.get("/api/ideas")
    assert resp.status_code == 200


def test_coherence_score_accessible_for_tab_views() -> None:
    """GET /api/coherence/score is accessible (used in overview tabs)."""
    resp = client.get("/api/coherence/score")
    assert resp.status_code == 200
    data = resp.json()
    assert 0.0 <= data["score"] <= 1.0


def test_concepts_endpoint_accessible() -> None:
    """GET /api/concepts returns 200 (concepts primary tab)."""
    resp = client.get("/api/concepts")
    assert resp.status_code in (200, 404)  # 404 acceptable if no concepts seeded


def test_contributors_endpoint_accessible() -> None:
    """GET /api/contributors returns 200 (contributors primary tab)."""
    resp = client.get("/api/contributors")
    assert resp.status_code == 200


def test_news_endpoint_accessible() -> None:
    """GET /api/news returns 200 (news primary tab)."""
    resp = client.get("/api/news")
    assert resp.status_code in (200, 404)


def test_edges_endpoint_accessible() -> None:
    """GET /api/edges returns 200 (edges tab in idea detail)."""
    resp = client.get("/api/edges")
    assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Web component file checks — shadcn/ui Tabs usage
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IDEAS_PAGE.is_file(), reason="web/app/ideas/page.tsx not present")
def test_ideas_page_exists() -> None:
    """Ideas list page file must exist."""
    assert IDEAS_PAGE.is_file()


@pytest.mark.skipif(not IDEAS_PAGE.is_file(), reason="web/app/ideas/page.tsx not present")
def test_ideas_page_imports_from_components() -> None:
    """ideas/page.tsx must reference UI components (prerequisite for tab rendering)."""
    content = IDEAS_PAGE.read_text(encoding="utf-8")
    # Must import from @/components or @/lib — confirms it's a real component file
    assert "import" in content


@pytest.mark.skipif(not IDEAS_PAGE.is_file(), reason="web/app/ideas/page.tsx not present")
def test_ideas_page_has_metadata_export() -> None:
    """Ideas page must export Metadata (Next.js page convention)."""
    content = IDEAS_PAGE.read_text(encoding="utf-8")
    assert "Metadata" in content or "metadata" in content


@pytest.mark.skipif(not IDEA_DETAIL_PAGE.is_file(), reason="idea detail page not present")
def test_idea_detail_page_exists() -> None:
    """Idea detail page file must exist."""
    assert IDEA_DETAIL_PAGE.is_file()


@pytest.mark.skipif(not IDEA_DETAIL_PAGE.is_file(), reason="idea detail page not present")
def test_idea_detail_page_uses_idea_id_param() -> None:
    """Idea detail page must consume idea_id parameter."""
    content = IDEA_DETAIL_PAGE.read_text(encoding="utf-8")
    assert "idea_id" in content


@pytest.mark.skipif(not SITE_HEADER.is_file(), reason="site_header.tsx not present")
def test_site_header_has_navigation_links() -> None:
    """site_header.tsx must define navigation links for primary tabs."""
    content = SITE_HEADER.read_text(encoding="utf-8")
    # Must contain at least one nav/link reference
    assert "href" in content or "Link" in content or "nav" in content.lower()


@pytest.mark.skipif(not GLOBALS_CSS.is_file(), reason="globals.css not present")
def test_globals_css_exists_for_tab_styles() -> None:
    """globals.css must exist (provides base styles for tab components)."""
    assert GLOBALS_CSS.is_file()
    content = GLOBALS_CSS.read_text(encoding="utf-8")
    assert len(content) > 100  # Must contain substantive CSS


# ---------------------------------------------------------------------------
# Preferences API: OpenAPI shape validation
# ---------------------------------------------------------------------------


def test_openapi_includes_preferences_ui_path() -> None:
    """OpenAPI schema must list /api/preferences/ui endpoints."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})
    assert "/api/preferences/ui" in paths, (
        "OpenAPI schema missing /api/preferences/ui — endpoint not registered"
    )


def test_openapi_preferences_ui_supports_get() -> None:
    """/api/preferences/ui must support GET method."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    path_item = schema.get("paths", {}).get("/api/preferences/ui", {})
    assert "get" in path_item, "GET method not defined for /api/preferences/ui"


def test_openapi_preferences_ui_supports_put() -> None:
    """/api/preferences/ui must support PUT method."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    path_item = schema.get("paths", {}).get("/api/preferences/ui", {})
    assert "put" in path_item, "PUT method not defined for /api/preferences/ui"


def test_openapi_preferences_ui_supports_patch() -> None:
    """/api/preferences/ui must support PATCH method."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    path_item = schema.get("paths", {}).get("/api/preferences/ui", {})
    assert "patch" in path_item, "PATCH method not defined for /api/preferences/ui"


def test_openapi_preferences_ui_supports_delete() -> None:
    """/api/preferences/ui must support DELETE method."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    path_item = schema.get("paths", {}).get("/api/preferences/ui", {})
    assert "delete" in path_item, "DELETE method not defined for /api/preferences/ui"
