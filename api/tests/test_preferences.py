"""Tests for UI Preferences API — spec ux-tabs-mobile-friendly.

Covers acceptance criteria from specs/task_f0b27e390a5aa4ee.md:
- F7: GET/PUT/PATCH /api/preferences/ui endpoints
- Idempotency of PUT
- Partial update via PATCH
- Default values when no preferences stored
- Reset/DELETE
- Field validation (invalid values → 422)
- Model schema correctness (UIPreferences, UIPreferencesUpdate)
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ui_preferences import (
    UIPreferences,
    UIPreferencesUpdate,
    router,
    _STORE,
)


# ---------------------------------------------------------------------------
# Isolated test app using only the ui_preferences router
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(router)


@pytest.fixture(autouse=True)
def clear_store():
    """Reset in-memory store between tests to prevent cross-test contamination."""
    _STORE.clear()
    yield
    _STORE.clear()


@pytest.fixture()
def client():
    return TestClient(_test_app)


# ---------------------------------------------------------------------------
# GET /api/preferences/ui — default values when nothing stored
# ---------------------------------------------------------------------------


def test_get_preferences_returns_defaults_for_new_contributor(client):
    resp = client.get("/api/preferences/ui", params={"contributor_id": "alice"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["contributor_id"] == "alice"
    assert data["expert_mode"] is False
    assert data["nav_layout"] == "top"
    assert data["ideas_view"] == "cards"
    assert data["idea_detail_tab"] == "overview"
    assert data["swipeable_cards"] is False
    assert data["collapsible_sections"] is True
    assert data["show_tooltips"] is True


def test_get_preferences_anonymous_contributor_returns_defaults(client):
    resp = client.get("/api/preferences/ui")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contributor_id"] == "anonymous"
    assert data["expert_mode"] is False


# ---------------------------------------------------------------------------
# PUT /api/preferences/ui — full upsert
# ---------------------------------------------------------------------------


def test_put_preferences_creates_new_preferences(client):
    payload = {
        "contributor_id": "bob",
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "table",
        "idea_detail_tab": "tasks",
        "swipeable_cards": True,
        "collapsible_sections": False,
        "show_tooltips": False,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["contributor_id"] == "bob"
    assert data["expert_mode"] is True
    assert data["nav_layout"] == "bottom_bar"
    assert data["ideas_view"] == "table"
    assert data["idea_detail_tab"] == "tasks"
    assert data["swipeable_cards"] is True
    assert data["collapsible_sections"] is False
    assert data["show_tooltips"] is False


def test_put_preferences_is_idempotent(client):
    """Calling PUT twice with the same body returns 200 both times, no error."""
    payload = {
        "contributor_id": "carol",
        "expert_mode": True,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": False,
    }
    resp1 = client.put("/api/preferences/ui", json=payload)
    assert resp1.status_code == 200

    resp2 = client.put("/api/preferences/ui", json=payload)
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


def test_put_preferences_overwrites_previous_values(client):
    initial = {
        "contributor_id": "dave",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    client.put("/api/preferences/ui", json=initial)

    updated = dict(initial)
    updated["expert_mode"] = True
    updated["ideas_view"] = "graph"
    resp = client.put("/api/preferences/ui", json=updated)
    assert resp.status_code == 200
    data = resp.json()
    assert data["expert_mode"] is True
    assert data["ideas_view"] == "graph"


def test_put_preferences_reads_back_correctly(client):
    """PUT then GET returns the persisted values (Scenario 1 from spec)."""
    payload = {
        "contributor_id": "eve",
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "table",
        "idea_detail_tab": "specs",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": False,
    }
    client.put("/api/preferences/ui", json=payload)

    resp = client.get("/api/preferences/ui", params={"contributor_id": "eve"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["expert_mode"] is True
    assert data["ideas_view"] == "table"
    assert data["idea_detail_tab"] == "specs"


# ---------------------------------------------------------------------------
# PATCH /api/preferences/ui — partial update
# ---------------------------------------------------------------------------


def test_patch_preferences_updates_only_specified_fields(client):
    initial = {
        "contributor_id": "frank",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    client.put("/api/preferences/ui", json=initial)

    patch_resp = client.patch(
        "/api/preferences/ui",
        params={"contributor_id": "frank"},
        json={"expert_mode": True},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    # Updated field
    assert data["expert_mode"] is True
    # Unchanged fields
    assert data["nav_layout"] == "top"
    assert data["ideas_view"] == "cards"
    assert data["idea_detail_tab"] == "overview"
    assert data["show_tooltips"] is True


def test_patch_preferences_ideas_view_mode(client):
    """Partial update of ideas_view doesn't touch other fields."""
    initial = {
        "contributor_id": "grace",
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "cards",
        "idea_detail_tab": "history",
        "swipeable_cards": True,
        "collapsible_sections": False,
        "show_tooltips": False,
    }
    client.put("/api/preferences/ui", json=initial)

    patch_resp = client.patch(
        "/api/preferences/ui",
        params={"contributor_id": "grace"},
        json={"ideas_view": "table"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["ideas_view"] == "table"
    assert data["expert_mode"] is True  # unchanged
    assert data["nav_layout"] == "bottom_bar"  # unchanged


def test_patch_creates_defaults_for_new_contributor(client):
    """PATCH on unknown contributor starts from defaults then applies patch."""
    resp = client.patch(
        "/api/preferences/ui",
        params={"contributor_id": "newbie"},
        json={"expert_mode": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["contributor_id"] == "newbie"
    assert data["expert_mode"] is True
    assert data["nav_layout"] == "top"  # default


# ---------------------------------------------------------------------------
# DELETE /api/preferences/ui — reset to defaults
# ---------------------------------------------------------------------------


def test_delete_preferences_removes_stored_preferences(client):
    payload = {
        "contributor_id": "henry",
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "graph",
        "idea_detail_tab": "contributors",
        "swipeable_cards": True,
        "collapsible_sections": False,
        "show_tooltips": False,
    }
    client.put("/api/preferences/ui", json=payload)

    del_resp = client.delete("/api/preferences/ui", params={"contributor_id": "henry"})
    assert del_resp.status_code == 204

    # After delete, GET should return defaults
    get_resp = client.get("/api/preferences/ui", params={"contributor_id": "henry"})
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["expert_mode"] is False
    assert data["nav_layout"] == "top"
    assert data["ideas_view"] == "cards"


def test_delete_nonexistent_contributor_is_safe(client):
    """Deleting preferences for a contributor that has none should not error."""
    resp = client.delete("/api/preferences/ui", params={"contributor_id": "nobody"})
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Validation — invalid field values (Scenario 3 from spec)
# ---------------------------------------------------------------------------


def test_put_invalid_nav_layout_returns_422(client):
    payload = {
        "contributor_id": "ivan",
        "expert_mode": False,
        "nav_layout": "sidebar",  # invalid
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422


def test_put_invalid_ideas_view_returns_422(client):
    payload = {
        "contributor_id": "julia",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "super-ultra-expert",  # invalid
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422


def test_put_invalid_idea_detail_tab_returns_422(client):
    payload = {
        "contributor_id": "karen",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "doesnotexist",  # invalid
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422


def test_put_missing_contributor_id_returns_422(client):
    payload = {
        "expert_mode": True,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    }
    resp = client.put("/api/preferences/ui", json=payload)
    assert resp.status_code == 422


def test_put_empty_contributor_id_returns_422(client):
    payload = {
        "contributor_id": "   ",  # blank/whitespace
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


def test_patch_invalid_ideas_view_returns_422(client):
    resp = client.patch(
        "/api/preferences/ui",
        params={"contributor_id": "leo"},
        json={"ideas_view": "list"},  # not in cards|table|graph
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Model schema tests — UIPreferences defaults
# ---------------------------------------------------------------------------


def test_ui_preferences_model_defaults():
    prefs = UIPreferences(contributor_id="test-user")
    assert prefs.expert_mode is False
    assert prefs.nav_layout == "top"
    assert prefs.ideas_view == "cards"
    assert prefs.idea_detail_tab == "overview"
    assert prefs.swipeable_cards is False
    assert prefs.collapsible_sections is True
    assert prefs.show_tooltips is True


def test_ui_preferences_model_expert_mode():
    prefs = UIPreferences(contributor_id="expert-user", expert_mode=True)
    assert prefs.expert_mode is True
    assert prefs.contributor_id == "expert-user"


def test_ui_preferences_model_all_valid_ideas_views():
    for view in ("cards", "table", "graph"):
        prefs = UIPreferences(contributor_id="u", ideas_view=view)
        assert prefs.ideas_view == view


def test_ui_preferences_model_all_valid_nav_layouts():
    for layout in ("top", "bottom_bar"):
        prefs = UIPreferences(contributor_id="u", nav_layout=layout)
        assert prefs.nav_layout == layout


def test_ui_preferences_model_all_valid_idea_detail_tabs():
    valid_tabs = ("overview", "specs", "tasks", "contributors", "edges", "history")
    for tab in valid_tabs:
        prefs = UIPreferences(contributor_id="u", idea_detail_tab=tab)
        assert prefs.idea_detail_tab == tab


def test_ui_preferences_update_model_all_none_by_default():
    update = UIPreferencesUpdate()
    assert update.expert_mode is None
    assert update.nav_layout is None
    assert update.ideas_view is None
    assert update.idea_detail_tab is None
    assert update.swipeable_cards is None
    assert update.collapsible_sections is None
    assert update.show_tooltips is None


# ---------------------------------------------------------------------------
# Multi-contributor isolation
# ---------------------------------------------------------------------------


def test_preferences_are_isolated_per_contributor(client):
    """Different contributors have independent preferences."""
    client.put("/api/preferences/ui", json={
        "contributor_id": "user-a",
        "expert_mode": True,
        "nav_layout": "bottom_bar",
        "ideas_view": "table",
        "idea_detail_tab": "tasks",
        "swipeable_cards": True,
        "collapsible_sections": False,
        "show_tooltips": False,
    })
    client.put("/api/preferences/ui", json={
        "contributor_id": "user-b",
        "expert_mode": False,
        "nav_layout": "top",
        "ideas_view": "cards",
        "idea_detail_tab": "overview",
        "swipeable_cards": False,
        "collapsible_sections": True,
        "show_tooltips": True,
    })

    resp_a = client.get("/api/preferences/ui", params={"contributor_id": "user-a"})
    resp_b = client.get("/api/preferences/ui", params={"contributor_id": "user-b"})

    assert resp_a.json()["expert_mode"] is True
    assert resp_a.json()["ideas_view"] == "table"
    assert resp_b.json()["expert_mode"] is False
    assert resp_b.json()["ideas_view"] == "cards"


def test_deleting_one_contributor_does_not_affect_another(client):
    for uid in ("x1", "x2"):
        client.put("/api/preferences/ui", json={
            "contributor_id": uid,
            "expert_mode": True,
            "nav_layout": "top",
            "ideas_view": "table",
            "idea_detail_tab": "overview",
            "swipeable_cards": False,
            "collapsible_sections": True,
            "show_tooltips": False,
        })

    client.delete("/api/preferences/ui", params={"contributor_id": "x1"})

    resp = client.get("/api/preferences/ui", params={"contributor_id": "x2"})
    assert resp.status_code == 200
    assert resp.json()["expert_mode"] is True  # x2 unaffected
