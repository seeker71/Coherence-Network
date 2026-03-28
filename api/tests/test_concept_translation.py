"""Tests for conceptual framing translation (worldview lenses) — ideas and ontology concepts.

Verification Contract
=====================
Proves cross-view synthesis: an idea is reframed through scientific, economic, spiritual,
artistic, or philosophical lenses using ontology bridges and resonance (not machine translation).

Endpoints under test:
  - GET /api/ideas/{id}/translate?view=<lens>
  - GET /api/concepts/{id}/translate?from=<lens>&to=<lens>

Verification Scenarios
----------------------
1. Idea translate — spiritual lens after create
   Setup: POST /api/ideas with physics/network vocabulary (energy, flow, system).
   Action: GET /api/ideas/{id}/translate?view=spiritual
   Expected: 200, translation_kind == concept_framing, view == spiritual, non-empty summary,
             bridging_concepts list with scored ontology refs (id, name, score, axes).
   Edge: GET /api/ideas/missing-id/translate?view=spiritual → 404

2. Concept translate — scientific to artistic
   Setup: GET /api/concepts/activity (seeded ontology) to confirm concept exists.
   Action: GET /api/concepts/activity/translate?from=scientific&to=artistic
   Expected: 200, from_lens scientific, to_lens artistic, target_bridging_concepts non-empty
             or valid summary when graph is sparse.
   Edge: same from and to → 400

3. Create–read–update–retranslate (idea lifecycle)
   Setup: POST idea "ctr-lifecycle", GET translate?view=scientific.
   Action: PATCH idea description to add "beauty" and "form", GET translate?view=artistic
   Expected: both translate calls 200; second response summary or bridging reflects artistic lens.
   Edge: duplicate POST same id → 409 if API enforces uniqueness

4. Invalid lens query
   Action: GET /api/ideas/some-id/translate?view=not-a-lens
   Expected: 422 (validation error)

5. Missing concept
   Action: GET /api/concepts/this-concept-does-not-exist-999/translate?from=scientific&to=spiritual
   Expected: 404
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_translate_idea_spiritual_lens_returns_framing() -> None:
    """Scenario 1: create idea with structural tokens, spiritual translate returns ontology bridges."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "id": "ctr-spiritual-network",
            "name": "Energy flow in open systems",
            "description": (
                "Thermodynamic flows and feedback loops connect parts into a resilient whole. "
                "Measurement tracks entropy and order across the network structure."
            ),
            "potential_value": 50.0,
            "estimated_cost": 10.0,
            "confidence": 0.8,
            "tags": ["physics", "flow", "system", "feedback"],
            "interfaces": ["domain:physics"],
        }
        cr = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        tr = await client.get(
            "/api/ideas/ctr-spiritual-network/translate",
            params={"view": "spiritual"},
        )
        assert tr.status_code == 200, tr.text
        data = tr.json()
        assert data["idea_id"] == "ctr-spiritual-network"
        assert data["view"] == "spiritual"
        assert data["translation_kind"] == "concept_framing"
        assert "spiritual" in data["lens_description"].lower() or "meaning" in data["lens_description"].lower()
        assert len(data["summary"]) > 20
        assert isinstance(data["bridging_concepts"], list)
        assert isinstance(data["analogous_ideas"], list)
        for b in data["bridging_concepts"][:3]:
            assert "id" in b and "name" in b and "score" in b


@pytest.mark.asyncio
async def test_translate_idea_missing_returns_404() -> None:
    """Scenario 1 edge: missing idea → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/ideas/idea-missing-ctr-xyz/translate",
            params={"view": "economic"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_translate_concept_scientific_to_artistic() -> None:
    """Scenario 2: ontology concept translate between lenses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pre = await client.get("/api/concepts/activity")
        assert pre.status_code == 200, "ontology must include activity"

        r = await client.get(
            "/api/concepts/activity/translate",
            params={"from": "scientific", "to": "artistic"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["concept_id"] == "activity"
        assert data["from_lens"] == "scientific"
        assert data["to_lens"] == "artistic"
        assert data["translation_kind"] == "concept_framing"
        assert len(data["summary"]) > 10
        assert isinstance(data["target_bridging_concepts"], list)
        assert isinstance(data["source_axes"], list)


@pytest.mark.asyncio
async def test_translate_concept_same_lens_returns_400() -> None:
    """Scenario 2 edge: from == to → 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/concepts/activity/translate",
            params={"from": "scientific", "to": "scientific"},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_read_patch_retranslate_artistic() -> None:
    """Scenario 3: mutating idea text then re-query artistic lens."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = {
            "id": "ctr-lifecycle-art",
            "name": "Composable pipelines",
            "description": "Data moves through stages with causal dependencies and measurable throughput.",
            "potential_value": 40.0,
            "estimated_cost": 8.0,
            "confidence": 0.7,
            "tags": ["pipeline", "data", "causal"],
        }
        c1 = await client.post("/api/ideas", json=body, headers=AUTH_HEADERS)
        assert c1.status_code == 201

        t1 = await client.get("/api/ideas/ctr-lifecycle-art/translate", params={"view": "scientific"})
        assert t1.status_code == 200
        first_summary = t1.json()["summary"]

        patch = await client.patch(
            "/api/ideas/ctr-lifecycle-art",
            json={
                "description": (
                    "Data moves through stages; composition, rhythm, and visual balance matter "
                    "for how operators perceive the system — form follows function in interface design."
                )
            },
            headers=AUTH_HEADERS,
        )
        assert patch.status_code == 200, patch.text

        t2 = await client.get("/api/ideas/ctr-lifecycle-art/translate", params={"view": "artistic"})
        assert t2.status_code == 200
        second = t2.json()
        assert second["view"] == "artistic"
        assert second["summary"] != first_summary or "artistic" in second["lens_description"].lower()


@pytest.mark.asyncio
async def test_invalid_view_query_returns_422() -> None:
    """Scenario 4: bad enum for view."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/ideas/ctr-spiritual-network/translate",
            params={"view": "klingon"},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_missing_concept_translate_returns_404() -> None:
    """Scenario 5: unknown concept id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/concepts/no-such-concept-ctr/translate",
            params={"from": "philosophical", "to": "economic"},
        )
        assert r.status_code == 404
