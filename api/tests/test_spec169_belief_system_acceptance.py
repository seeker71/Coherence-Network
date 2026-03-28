"""Spec-169 (belief-system-interface) — acceptance-criteria tests.

Maps to `specs/169-belief-system.md` Acceptance Criteria §1–8. Uses ASGI + mocked
graph_service like `test_belief_system.py`.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from app.main import app

_BELIEF_AXES = (
    "scientific",
    "spiritual",
    "pragmatic",
    "holistic",
    "relational",
    "systemic",
)


def _contributor(cid: str = "ac_user", props: dict | None = None):
    return {
        "id": f"contributor:{cid}",
        "type": "contributor",
        "name": cid,
        "properties": props or {},
    }


def _idea(iid: str = "idea_ac", tags: list | None = None, axes: dict | None = None):
    return {
        "id": iid,
        "type": "idea",
        "name": "AC Idea",
        "properties": {
            "tags": tags or [],
            "worldview_axes": axes or {"systemic": 0.9, "scientific": 0.85},
        },
    }


# --- AC1: GET full profile shape ---


@pytest.mark.asyncio
async def test_ac1_get_beliefs_includes_required_fields_and_updated_at():
    """AC1: GET beliefs returns worldview_axes, concept_resonances, interest_tags, updated_at."""
    node = _contributor(
        "ac_user",
        {
            "worldview_axes": {"pragmatic": 0.6},
            "concept_resonances": [{"concept_id": "entropy", "weight": 0.5}],
            "interest_tags": ["flow"],
            "beliefs_updated_at": "2026-03-28T12:00:00+00:00",
        },
    )
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/ac_user/beliefs")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contributor_id"] == "ac_user"
    assert "worldview_axes" in body and isinstance(body["worldview_axes"], dict)
    assert "concept_resonances" in body and isinstance(body["concept_resonances"], list)
    assert "interest_tags" in body and isinstance(body["interest_tags"], list)
    assert "updated_at" in body
    assert "T" in body["updated_at"] or body["updated_at"].endswith("Z")
    for axis in _BELIEF_AXES:
        assert axis in body["worldview_axes"]


# --- AC2: PATCH unknown fields → 422 ---


@pytest.mark.asyncio
async def test_ac2_patch_unknown_field_returns_422():
    """AC2: PATCH rejects unknown fields with 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/ac_user/beliefs",
            json={"not_a_real_field": 1},
        )
    assert r.status_code == 422, r.text


# --- AC3: Resonance score, breakdown, matched lists ---


@pytest.mark.asyncio
async def test_ac3_resonance_returns_score_breakdown_and_matches():
    """AC3: resonance endpoint returns score in [0,1], breakdown, matched_concepts/axes."""
    contrib = _contributor(
        "ac_user",
        {
            "worldview_axes": {"systemic": 0.95, "scientific": 0.88},
            "interest_tags": ["entropy"],
            "concept_resonances": [{"concept_id": "entropy", "weight": 0.9}],
        },
    )
    idea = _idea(tags=["entropy"], axes={"systemic": 0.9, "scientific": 0.8})

    def _get(nid: str):
        if nid == "contributor:ac_user" or nid == "ac_user":
            return contrib
        return idea

    with patch("app.services.belief_service.graph_service.get_node", side_effect=_get):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/contributors/ac_user/beliefs/resonance?idea_id=idea_ac"
            )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["contributor_id"] == "ac_user"
    assert data["idea_id"] == "idea_ac"
    assert 0.0 <= data["resonance_score"] <= 1.0
    bd = data["breakdown"]
    for k in ("concept_overlap", "worldview_alignment", "tag_match"):
        assert k in bd
        assert 0.0 <= bd[k] <= 1.0
    assert "entropy" in data["matched_concepts"]
    assert isinstance(data["matched_axes"], list)


# --- AC4: Non-existent contributor → 404 on all belief endpoints ---


@pytest.mark.asyncio
async def test_ac4_nonexistent_contributor_404_on_get_patch_resonance():
    """AC4: missing contributor yields 404 on GET, PATCH, and resonance."""
    with patch("app.services.belief_service.graph_service.get_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            g = await client.get("/api/contributors/missing_user/beliefs")
            p = await client.patch(
                "/api/contributors/missing_user/beliefs",
                json={"interest_tags": ["x"]},
            )
            res = await client.get(
                "/api/contributors/missing_user/beliefs/resonance?idea_id=idea_ac"
            )
    for resp in (g, p, res):
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"] == "Contributor not found"


# --- AC5: Worldview enum validation ---


@pytest.mark.asyncio
async def test_ac5_invalid_worldview_axis_returns_422():
    """AC5: invalid axis name returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/ac_user/beliefs",
            json={"worldview_axes": {"not_an_axis": 0.5}},
        )
    assert r.status_code == 422, r.text


# --- AC6: Weights outside [0,1] → 422 (worldview and concept resonance) ---


@pytest.mark.asyncio
async def test_ac6_worldview_weight_above_one_returns_422():
    """AC6: worldview axis weight > 1.0 returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/ac_user/beliefs",
            json={"worldview_axes": {"scientific": 1.01}},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_ac6_concept_resonance_weight_above_one_returns_422():
    """AC6: concept resonance weight > 1.0 returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/ac_user/beliefs",
            json={"concept_resonances": [{"concept_id": "x", "weight": 1.5}]},
        )
    assert r.status_code == 422, r.text


# --- AC7: Additive PATCH for interest_tags ---


@pytest.mark.asyncio
async def test_ac7_interest_tags_patch_appends_without_replace():
    """AC7: PATCH appends interest_tags when replace is false (default)."""
    node = _contributor("ac_user", {"interest_tags": ["alpha"]})
    updated = _contributor("ac_user", {"interest_tags": ["alpha", "beta"]})
    with patch(
        "app.services.belief_service.graph_service.get_node", side_effect=[node, updated]
    ), patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/ac_user/beliefs",
                json={"interest_tags": ["beta"]},
            )
    assert r.status_code == 200, r.text
    assert "alpha" in r.json()["interest_tags"]
    assert "beta" in r.json()["interest_tags"]


@pytest.mark.asyncio
async def test_ac7_interest_tags_replace_true_replaces_list():
    """AC7: replace:true replaces interest_tags entirely."""
    node = _contributor("ac_user", {"interest_tags": ["old"]})
    updated = _contributor("ac_user", {"interest_tags": ["new_only"]})
    with patch(
        "app.services.belief_service.graph_service.get_node", side_effect=[node, updated]
    ), patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/ac_user/beliefs",
                json={"interest_tags": ["new_only"], "replace": True},
            )
    assert r.status_code == 200, r.text
    assert r.json()["interest_tags"] == ["new_only"]


# --- AC8: ROI aggregate stats + spec_ref ---


@pytest.mark.asyncio
async def test_ac8_roi_returns_aggregate_fields_and_spec_ref():
    """AC8: GET /api/beliefs/roi includes adoption, axes, match rate, spec_ref."""
    nodes_result = {
        "nodes": [
            _contributor("a", {"worldview_axes": {"systemic": 0.7}, "interest_tags": ["t"]}),
            _contributor("b", {}),
        ],
        "total": 2,
    }
    with patch("app.services.belief_service.graph_service.list_nodes", return_value=nodes_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/beliefs/roi")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["spec_ref"] == "spec-169"
    assert b["contributors_total"] == 2
    assert b["contributors_with_profiles"] >= 1
    assert 0.0 <= b["profile_adoption_rate"] <= 1.0
    assert isinstance(b["top_worldview_axes"], list)
    assert "avg_resonance_match_rate" in b
    assert "concept_resonances_total" in b

