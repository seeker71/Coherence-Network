"""Accessible ontology — non-technical contributors extend the shared model naturally.

Verification Contract
=====================
Proves that someone without graph-theory vocabulary can: record an idea in plain language,
tag domains they understand, see it in card-oriented surfaces, discover where it resonates
with peers, and (optionally) attach ontology edges when IDs are known. Technical users keep
full graph access via concepts + edges APIs.

Open questions (observability hooks exercised by these tests):
  - **Is it working?** Counts from GET /api/concepts/stats and non-empty resonance/card
    feeds provide concrete signals; refinement over time can track rising ``total`` matches
    and card visibility for the same slug.
  - **Clearer proof over time:** Re-run scenario 3 after portfolio growth; ``matches`` and
    ``GET /api/ideas/cards`` totals should move with real contributions (not asserted here,
    but the endpoints are the measurement surface).

Endpoints under test
--------------------
  - POST /api/ideas — plain-language contribution (requires API key in dev)
  - GET /api/ideas/cards — “gardens / cards” style browse
  - PATCH /api/ideas/{id} — update text after initial capture
  - GET /api/ideas/{id}/concept-resonance — inferred cross-idea relationships
  - GET /api/concepts/search — locate ontology nodes by everyday words
  - GET /api/concepts/stats — human-scale ontology footprint
  - GET /api/concepts/axes — list axes (domains of meaning) without loading the graph
  - GET /api/concepts/{id}/edges — technical graph view
  - POST /api/concepts/{id}/edges — extend ontology when endpoints are known

Verification Scenarios
----------------------
1. Plain-language idea appears on the cards feed
   Setup: Isolated idea portfolio (temp file), no prior ``aocf-plain-*`` ideas.
   Action: POST /api/ideas with everyday description + ``tags`` + ``interfaces``;
           GET /api/ideas/cards?q=<distinct substring>
   Expected: POST 201; cards ``items`` contains an entry whose ``id`` matches the new idea.
   Edge: POST same ``id`` again → 409 Conflict.

2. Ontology search without knowing concept IDs
   Setup: Default ontology bundle loaded at import time.
   Action: GET /api/concepts/search?q=activity
   Expected: 200, JSON list non-empty, first hit has ``id`` and ``name``.
   Edge: GET /api/concepts/search?q= (empty) → 422 validation error.

3. Create → read resonance → patch → read (lifecycle)
   Setup: Isolated portfolio; POST two ideas that share conceptual tokens across domains.
   Action: GET /api/ideas/{id}/concept-resonance?limit=5&min_score=0.05;
           PATCH first idea description; GET concept-resonance again.
   Expected: Both GETs return 200; first response has ``total`` >= 1 and a cross-domain
             match when two domains differ; second GET still 200 after patch.
   Edge: GET /api/ideas/missing-aocf/concept-resonance → 404.

4. Stats and axes are readable proof surfaces
   Setup: None.
   Action: GET /api/concepts/stats; GET /api/concepts/axes? (actually no query - list_axes)
   Expected: stats shows ``concepts`` >= 1, ``axes`` >= 1; axes list non-empty with ``id`` keys.
   Edge: GET /api/concepts/this-id-does-not-exist-999 → 404.

5. Technical path: list edges and add a user edge between known concepts
   Setup: GET /api/concepts/search?q=activity and another query to get two distinct ids.
   Action: GET /api/concepts/{a}/edges; POST /api/concepts/{a}/edges with body
           {from_id, to_id, relationship_type, created_by}
   Expected: POST 200 with edge ``id``; subsequent GET edges includes new edge for ``a``.
   Edge: POST edge to missing ``to_id`` → 404.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_plain_language_idea_surfaces_on_idea_cards(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Scenario 1: cards feed exposes contributor-friendly view of a new idea."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    plain_id = "aocf-plain-community-kitchen"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": plain_id,
                "name": "Neighborhood community kitchen schedule",
                "description": (
                    "Folks should share meals without worrying about spreadsheets. "
                    "We need a simple way to coordinate who brings what, when."
                ),
                "potential_value": 35.0,
                "estimated_cost": 6.0,
                "confidence": 0.65,
                "tags": ["food", "community", "scheduling"],
                "interfaces": ["domain:civic", "domain:social"],
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201, created.text

        dup = await client.post(
            "/api/ideas",
            json={
                "id": plain_id,
                "name": "Duplicate",
                "description": "Should not land.",
                "potential_value": 1.0,
                "estimated_cost": 1.0,
                "confidence": 0.5,
            },
            headers=AUTH_HEADERS,
        )
        assert dup.status_code == 409, dup.text

        cards = await client.get("/api/ideas/cards", params={"q": "community kitchen", "limit": 30})
        assert cards.status_code == 200, cards.text
        body = cards.json()
        ids = {item.get("id") for item in body.get("items", [])}
        assert plain_id in ids


@pytest.mark.asyncio
async def test_concepts_search_finds_nodes_without_prior_ids() -> None:
    """Scenario 2: search bridges everyday language to ontology entries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.get("/api/concepts/search", params={"q": "activity"})
        assert ok.status_code == 200
        hits = ok.json()
        assert isinstance(hits, list)
        assert len(hits) >= 1
        assert "id" in hits[0] and "name" in hits[0]

        bad = await client.get("/api/concepts/search", params={"q": ""})
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_create_read_resonance_patch_reread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Scenario 3: resonance stays queryable through a simple update cycle."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "aocf-garden-water",
                "name": "Rain barrels for school garden",
                "description": "Capture rainwater to irrigate beds through dry weeks.",
                "potential_value": 40.0,
                "estimated_cost": 8.0,
                "confidence": 0.7,
                "tags": ["water", "garden", "school"],
                "interfaces": ["domain:civic"],
            },
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "aocf-code-pipeline",
                "name": "Buffer rainwater data pipeline",
                "description": "Capture upstream events to irrigate downstream services during dry traffic spells.",
                "potential_value": 42.0,
                "estimated_cost": 9.0,
                "confidence": 0.72,
                "tags": ["water", "pipeline", "events"],
                "interfaces": ["domain:software"],
            },
            headers=AUTH_HEADERS,
        )

        first = await client.get(
            "/api/ideas/aocf-garden-water/concept-resonance",
            params={"limit": 5, "min_score": 0.05},
        )
        assert first.status_code == 200, first.text
        body1 = first.json()
        assert body1["idea_id"] == "aocf-garden-water"
        assert body1["total"] >= 1
        assert body1["matches"][0]["idea_id"] == "aocf-code-pipeline"
        assert body1["matches"][0]["cross_domain"] is True

        patched = await client.patch(
            "/api/ideas/aocf-garden-water",
            json={"description": "Capture rainwater; also document soil moisture for science class."},
            headers=AUTH_HEADERS,
        )
        assert patched.status_code == 200, patched.text

        second = await client.get(
            "/api/ideas/aocf-garden-water/concept-resonance",
            params={"limit": 5, "min_score": 0.05},
        )
        assert second.status_code == 200
        assert second.json()["total"] >= 1

        missing = await client.get("/api/ideas/no-such-aocf-idea/concept-resonance")
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_concepts_stats_and_axes_are_non_empty() -> None:
    """Scenario 4: lightweight metrics for demos and dashboards."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stats = await client.get("/api/concepts/stats")
        assert stats.status_code == 200
        s = stats.json()
        assert s["concepts"] >= 1
        assert s["axes"] >= 1

        axes = await client.get("/api/concepts/axes")
        assert axes.status_code == 200
        ax = axes.json()
        assert isinstance(ax, list)
        assert len(ax) >= 1
        assert "id" in ax[0]

        missing = await client.get("/api/concepts/concept-missing-aocf-999")
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_post_concept_edge_requires_existing_target() -> None:
    """Scenario 5: graph-level extension validates endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.get("/api/concepts/search", params={"q": "activity"})
        b = await client.get("/api/concepts/search", params={"q": "adaptation"})
        assert a.status_code == 200 and b.status_code == 200
        id_a = a.json()[0]["id"]
        id_b = b.json()[0]["id"]
        if id_a == id_b:
            pytest.skip("Need two distinct ontology concepts for edge test")

        before = await client.get(f"/api/concepts/{id_a}/edges")
        assert before.status_code == 200

        created = await client.post(
            f"/api/concepts/{id_a}/edges",
            json={
                "from_id": id_a,
                "to_id": id_b,
                "relationship_type": "related",
                "created_by": "test:aocf",
            },
        )
        assert created.status_code == 200, created.text
        eid = created.json().get("id")
        assert eid

        after = await client.get(f"/api/concepts/{id_a}/edges")
        assert after.status_code == 200
        assert any(e.get("id") == eid for e in after.json())

        bad = await client.post(
            f"/api/concepts/{id_a}/edges",
            json={
                "from_id": id_a,
                "to_id": "missing-target-concept-aocf",
                "relationship_type": "related",
                "created_by": "test",
            },
        )
        assert bad.status_code == 404
