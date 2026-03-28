"""Accessible ontology — non-technical contributors extend it naturally.

Specification (verification contract)
=====================================
**Goal:** Contributors add ideas in plain language and tag domains they know; the
system surfaces relationships (concept resonance) and browseable ontology surfaces
(cards, concepts) without requiring graph-theory vocabulary.

**Open questions (measurement / proof over time):**
- Track resonance match counts and average ``resonance_score`` per idea cohort.
- Expose ``GET /api/ideas/{id}/concept-resonance`` in dashboards or health checks.
- Compare tag catalog growth (``GET /api/ideas/tags``) against ontology search hits.

**API / Web surfaces (network contract):**
- ``POST /api/ideas``, ``GET /api/ideas/{id}``, ``PUT /api/ideas/{id}/tags``
- ``GET /api/ideas/{id}/concept-resonance``
- ``GET /api/ideas/cards`` (card / garden surface)
- ``GET /api/concepts``, ``GET /api/concepts/search``, ``POST /api/concepts/{id}/edges``
- Web: ``/concepts/[id]`` (concept detail; server-rendered against API)

Verification Scenarios (runnable)
---------------------------------
1. **Plain language → inferred relationships**
   - Setup: Two new ideas with overlapping descriptive vocabulary and domain tags.
   - Action: ``GET /api/ideas/{source}/concept-resonance?min_score=0.05``
   - Expected: HTTP 200; at least one match lists the other idea; ``shared_concepts``
     non-empty; ``cross_domain`` true when domain tags differ.
   - Edge: Unknown idea id → 404.

2. **Full create–read–update (tags) cycle**
   - Setup: No prior idea with generated id.
   - Action: ``POST /api/ideas`` → ``GET /api/ideas/{id}`` → ``PUT /api/ideas/{id}/tags``
     → ``GET /api/ideas/{id}`` again.
   - Expected: tags reflect updated normalized set.
   - Edge: ``PUT`` with invalid tag payload → 422.

3. **Ontology discovery without knowing IDs**
   - Setup: Ontology loaded (``GET /api/concepts`` returns ``total > 0``).
   - Action: ``GET /api/concepts/search?q=<substring of a known name>``
   - Expected: HTTP 200; list contains that concept.
   - Edge: If no ontology data, scenario is skipped (documented).

4. **Card / garden feed**
   - Setup: Isolated portfolio paths via env (temp dir).
   - Action: ``GET /api/ideas/cards?limit=10``
   - Expected: HTTP 200; ``items`` list; each item has ``idea_id``, ``state``, ``attention_level``.

5. **User extends ontology with an edge**
   - Setup: At least two concepts in ``GET /api/concepts``.
   - Action: ``POST /api/concepts/{from}/edges`` with JSON body linking to ``to_id``.
   - Expected: HTTP 200; response includes ``from``, ``to``, ``type``.
   - Edge: Unknown ``to_id`` → 404.

6. **Duplicate idea**
   - Action: ``POST /api/ideas`` twice with same id.
   - Expected: second call returns 409.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}

_BASE_IDEA = {
    "potential_value": 42.0,
    "estimated_cost": 9.0,
    "confidence": 0.75,
}


@pytest.mark.asyncio
async def test_plain_language_ideas_surface_concept_resonance() -> None:
    """Non-technical contributors describe ideas in prose; system finds related ideas."""
    uid = uuid.uuid4().hex[:12]
    src = f"a11y-plain-src-{uid}"
    dst = f"a11y-plain-dst-{uid}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post(
            "/api/ideas",
            json={
                "id": src,
                "name": "Community watering schedule",
                "description": (
                    "Neighbors coordinate watering and soil care for shared garden beds. "
                    "We track rainfall and soil moisture together."
                ),
                "tags": ["gardening", "water", "soil", "community"],
                "interfaces": ["domain:urban-gardening"],
                **_BASE_IDEA,
            },
            headers=AUTH_HEADERS,
        )
        assert r1.status_code == 201, r1.text

        r2 = await client.post(
            "/api/ideas",
            json={
                "id": dst,
                "name": "School irrigation club",
                "description": (
                    "Students learn soil science and watering cycles. "
                    "Shared responsibility for garden beds and water use."
                ),
                "tags": ["education", "water", "soil", "community"],
                "interfaces": ["domain:education"],
                **_BASE_IDEA,
            },
            headers=AUTH_HEADERS,
        )
        assert r2.status_code == 201, r2.text

        res = await client.get(
            f"/api/ideas/{src}/concept-resonance",
            params={"min_score": 0.05},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["idea_id"] == src
        match_ids = [m["idea_id"] for m in body["matches"]]
        assert dst in match_ids, f"Expected resonance with {dst}, got {match_ids}"

        hit = next(m for m in body["matches"] if m["idea_id"] == dst)
        assert hit["shared_concepts"], (
            "shared_concepts must list overlapping tokens (e.g. water, soil)"
        )
        assert hit["cross_domain"] is True

        missing = await client.get("/api/ideas/a11y-missing-idea-xyz/concept-resonance")
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_create_read_update_tags_cycle() -> None:
    """Full CRU on tags: create idea, read, replace tags, read again."""
    uid = uuid.uuid4().hex[:12]
    iid = f"a11y-tags-{uid}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post(
            "/api/ideas",
            json={
                "id": iid,
                "name": "Tag cycle test",
                "description": "Plain language description for tagging.",
                "tags": ["alpha", "beta"],
                **_BASE_IDEA,
            },
            headers=AUTH_HEADERS,
        )
        assert c.status_code == 201

        g1 = await client.get(f"/api/ideas/{iid}")
        assert g1.status_code == 200
        assert g1.json()["tags"] == ["alpha", "beta"]

        u = await client.put(
            f"/api/ideas/{iid}/tags",
            json={"tags": ["gamma", "  Delta  "]},
        )
        assert u.status_code == 200

        g2 = await client.get(f"/api/ideas/{iid}")
        assert g2.status_code == 200
        assert g2.json()["tags"] == ["delta", "gamma"]

        bad = await client.put(f"/api/ideas/{iid}/tags", json={"tags": ["@@@"]})
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_concepts_list_and_search_plain_language_query() -> None:
    """Browse ontology without knowing graph internals: list + search."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/concepts", params={"limit": 5})
        assert listing.status_code == 200
        data = listing.json()
        total = data.get("total", 0)
        items = data.get("items", [])
        if total == 0 or not items:
            pytest.skip("No ontology concepts loaded — cannot run search scenario")

        first = items[0]
        name = first.get("name") or ""
        if len(name) < 2:
            pytest.skip("First concept has no searchable name")

        q = name.strip().lower()[: min(6, len(name.strip()))]
        search = await client.get("/api/concepts/search", params={"q": q, "limit": 20})
        assert search.status_code == 200
        found = search.json()
        assert isinstance(found, list)
        ids = {c.get("id") for c in found}
        assert first["id"] in ids, (
            f"Search for {q!r} should find concept {first['id']}"
        )


@pytest.mark.asyncio
async def test_ideas_cards_garden_surface_structure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-technical 'cards' feed exposes ideas without graph jargon."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("VALUE_LINEAGE_PATH", str(tmp_path / "value_lineage.json"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    uid = uuid.uuid4().hex[:10]
    iid = f"a11y-cards-{uid}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post = await client.post(
            "/api/ideas",
            json={
                "id": iid,
                "name": "Cards surface idea",
                "description": "Readable card row for contributors.",
                **_BASE_IDEA,
            },
            headers=AUTH_HEADERS,
        )
        assert post.status_code == 201

        cards = await client.get(
            "/api/ideas/cards",
            params={"limit": 10, "state": "all", "sort": "attention_desc"},
        )
        assert cards.status_code == 200
        payload = cards.json()
        assert isinstance(payload.get("items"), list)
        assert payload["pagination"]["limit"] == 10
        assert isinstance(payload.get("change_token"), str) and payload["change_token"]
        first = payload["items"][0]
        assert "idea_id" in first and "state" in first and "attention_level" in first


@pytest.mark.asyncio
async def test_user_created_edge_links_two_concepts() -> None:
    """Technical graph view: contributor adds an edge between known concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/concepts", params={"limit": 50})
        assert listing.status_code == 200
        items = listing.json().get("items", [])
        if len(items) < 2:
            pytest.skip("Need at least two ontology concepts to create an edge")

        a, b = items[0]["id"], items[1]["id"]
        if a == b:
            pytest.skip("Distinct concepts required")

        body = {
            "from_id": a,
            "to_id": b,
            "relationship_type": "relates_to",
            "created_by": "pytest-accessible-ontology",
        }
        ok = await client.post(f"/api/concepts/{a}/edges", json=body)
        assert ok.status_code == 200
        edge = ok.json()
        assert edge["from"] == a
        assert edge["to"] == b
        assert edge["type"] == "relates_to"

        edges = await client.get(f"/api/concepts/{a}/edges")
        assert edges.status_code == 200
        assert any(e.get("to") == b for e in edges.json())

        miss = await client.post(
            f"/api/concepts/{a}/edges",
            json={**body, "to_id": "no-such-concept-xyz-123"},
        )
        assert miss.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_idea_post_returns_409() -> None:
    """Error handling: duplicate create must not silently overwrite."""
    uid = uuid.uuid4().hex[:12]
    iid = f"a11y-dup-{uid}"
    payload = {
        "id": iid,
        "name": "Duplicate probe",
        "description": "First write wins; second must conflict.",
        **_BASE_IDEA,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
        assert first.status_code == 201
        second = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
        assert second.status_code == 409
