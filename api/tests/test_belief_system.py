"""Integration tests for the belief system API — spec-169.

12 tests covering:
 1. GET empty belief profile
 2. PATCH worldview axes
 3. GET updated profile after patch
 4. PATCH additive interest_tags
 5. PATCH replace=true interest_tags
 6. PATCH invalid axis name → 422
 7. PATCH weight out of range → 422
 8. PATCH unknown field → 422
 9. GET resonance match → score 0.0–1.0
10. GET resonance missing idea_id → 422
11. GET beliefs for non-existent contributor → 404
12. GET /api/beliefs/roi → stats + spec_ref
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_contributor_node(name: str = "test_belief_user", extra_props: dict | None = None):
    """Build a minimal contributor node dict for mocking."""
    props = extra_props or {}
    return {
        "id": f"contributor:{name}",
        "type": "contributor",
        "name": name,
        "properties": props,
    }


def _make_idea_node(idea_id: str = "idea_test_001", tags: list[str] | None = None):
    return {
        "id": idea_id,
        "type": "idea",
        "name": "Test Idea",
        "properties": {"tags": tags or [], "worldview_axes": {"systemic": 0.8, "scientific": 0.7}},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_empty_belief_profile():
    """GET /api/contributors/{id}/beliefs — empty profile returns default zeros."""
    node = _make_contributor_node()
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/test_belief_user/beliefs")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contributor_id"] == "test_belief_user"
    assert isinstance(body["worldview_axes"], dict)
    assert isinstance(body["concept_resonances"], list)
    assert isinstance(body["interest_tags"], list)
    # All 6 axes should be present at 0.0 by default
    for axis in ("scientific", "spiritual", "pragmatic", "holistic", "relational", "systemic"):
        assert axis in body["worldview_axes"]
        assert body["worldview_axes"][axis] == 0.0


@pytest.mark.asyncio
async def test_patch_worldview_axes():
    """PATCH /api/contributors/{id}/beliefs — worldview_axes merge."""
    node = _make_contributor_node()
    updated_node = _make_contributor_node(extra_props={
        "worldview_axes": {"scientific": 0.9, "systemic": 0.8},
        "interest_tags": [],
        "concept_resonances": [],
    })

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=updated_node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/test_belief_user/beliefs",
                json={"worldview_axes": {"scientific": 0.9, "systemic": 0.8}},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["worldview_axes"]["scientific"] == 0.9
    assert body["worldview_axes"]["systemic"] == 0.8


@pytest.mark.asyncio
async def test_get_updated_profile_after_patch():
    """GET after PATCH — persisted changes returned."""
    props = {
        "worldview_axes": {"scientific": 0.9},
        "interest_tags": ["entropy"],
        "concept_resonances": [],
    }
    node = _make_contributor_node(extra_props=props)
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/test_belief_user/beliefs")
    assert r.status_code == 200
    body = r.json()
    assert body["worldview_axes"]["scientific"] == 0.9
    assert "entropy" in body["interest_tags"]


@pytest.mark.asyncio
async def test_patch_additive_interest_tags():
    """PATCH without replace=true appends interest_tags."""
    node = _make_contributor_node(extra_props={"interest_tags": ["entropy"]})
    updated_node = _make_contributor_node(extra_props={"interest_tags": ["entropy", "emergence"]})

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/test_belief_user/beliefs",
                json={"interest_tags": ["emergence"]},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "entropy" in body["interest_tags"]
    assert "emergence" in body["interest_tags"]


@pytest.mark.asyncio
async def test_patch_replace_true_interest_tags():
    """PATCH with replace=true replaces interest_tags entirely."""
    node = _make_contributor_node(extra_props={"interest_tags": ["entropy", "emergence"]})
    updated_node = _make_contributor_node(extra_props={"interest_tags": ["coherence"]})

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/test_belief_user/beliefs",
                json={"interest_tags": ["coherence"], "replace": True},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["interest_tags"] == ["coherence"]


@pytest.mark.asyncio
async def test_patch_invalid_axis_name_returns_422():
    """PATCH with invalid axis name returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/test_belief_user/beliefs",
            json={"worldview_axes": {"astral": 0.5}},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_patch_weight_out_of_range_returns_422():
    """PATCH with weight > 1.0 returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/test_belief_user/beliefs",
            json={"worldview_axes": {"scientific": 1.5}},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_patch_unknown_field_returns_422():
    """PATCH with unknown field returns 422 (extra=forbid)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/test_belief_user/beliefs",
            json={"unknown_field": "value"},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_get_resonance_returns_score():
    """GET /api/contributors/{id}/beliefs/resonance?idea_id=X returns 0.0–1.0 score."""
    contributor_node = _make_contributor_node(extra_props={
        "worldview_axes": {"systemic": 0.9, "scientific": 0.8},
        "interest_tags": ["entropy", "emergence"],
        "concept_resonances": [{"concept_id": "entropy", "weight": 0.95}],
    })
    idea_node = _make_idea_node(tags=["entropy"])

    def _get_node(nid: str):
        if "contributor" in nid or nid == "test_belief_user":
            return contributor_node
        return idea_node

    with patch("app.services.belief_service.graph_service.get_node", side_effect=_get_node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/contributors/test_belief_user/beliefs/resonance?idea_id=idea_test_001"
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "resonance_score" in body
    assert 0.0 <= body["resonance_score"] <= 1.0
    assert "breakdown" in body
    breakdown = body["breakdown"]
    for key in ("concept_overlap", "worldview_alignment", "tag_match"):
        assert key in breakdown
        assert 0.0 <= breakdown[key] <= 1.0
    assert isinstance(body["matched_concepts"], list)


@pytest.mark.asyncio
async def test_get_resonance_missing_idea_id_returns_422():
    """GET /api/contributors/{id}/beliefs/resonance without idea_id → 422."""
    node = _make_contributor_node()
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/test_belief_user/beliefs/resonance")
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_get_beliefs_nonexistent_contributor_returns_404():
    """GET /api/contributors/ghost999/beliefs → 404."""
    with patch("app.services.belief_service.graph_service.get_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/ghost999/beliefs")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Contributor not found"


@pytest.mark.asyncio
async def test_get_beliefs_roi_returns_network_stats():
    """GET /api/beliefs/roi → aggregate stats with spec_ref."""
    nodes_result = {
        "nodes": [
            _make_contributor_node("user_a", extra_props={
                "worldview_axes": {"scientific": 0.8, "systemic": 0.9},
                "interest_tags": ["entropy"],
                "concept_resonances": [{"concept_id": "entropy", "weight": 0.9}],
            }),
            _make_contributor_node("user_b", extra_props={}),
        ],
        "total": 2,
    }
    with patch("app.services.belief_service.graph_service.list_nodes", return_value=nodes_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/beliefs/roi")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["spec_ref"] == "spec-169"
    assert body["contributors_total"] == 2
    assert body["contributors_with_profiles"] >= 1
    assert 0.0 <= body["profile_adoption_rate"] <= 1.0
    assert isinstance(body["top_worldview_axes"], list)
    assert body["concept_resonances_total"] >= 0
