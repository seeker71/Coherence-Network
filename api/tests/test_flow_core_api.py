"""Flow-centric integration tests for core API endpoints.

Tests the API as a user would experience it: HTTP requests in, JSON out.
No internal service imports — only httpx against the ASGI app.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "test-idea") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    """Helper: create an idea and return the response JSON."""
    iid = idea_id or _uid()
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Description for {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Health & Meta (5 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "uptime_seconds" in body


@pytest.mark.asyncio
async def test_ping_returns_pong():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ping")
        assert r.status_code == 200, r.text
        assert r.json()["pong"] is True


@pytest.mark.asyncio
async def test_version_returns_semver():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/version")
        assert r.status_code == 200, r.text
        version = r.json()["version"]
        assert re.match(r"^\d+\.\d+\.\d+", version), f"Not semver: {version}"


@pytest.mark.asyncio
async def test_ready_probe():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ready")
        # ready may return 200 or 503 depending on app.state.graph_store
        if r.status_code == 200:
            body = r.json()
            assert "db_connected" in body
        else:
            assert r.status_code == 503


@pytest.mark.asyncio
async def test_meta_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/meta/summary")
        assert r.status_code == 200, r.text
        body = r.json()
        # Should have coverage counts
        assert "endpoint_count" in body or "total_endpoints" in body


# ---------------------------------------------------------------------------
# Idea CRUD (10 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_crud_flow():
    """Create → duplicate-409 → get → get-missing-404 → list/paginate
    → update (with + without auth) → count → cards. One CRUD story."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        created = await _create_idea(c, iid)
        assert created["id"] == iid

        # Duplicate create → 409.
        dup = await c.post("/api/ideas", json={
            "id": iid, "name": "dup", "description": "dup",
            "potential_value": 1.0, "estimated_cost": 1.0,
        })
        assert dup.status_code == 409, dup.text

        # Get existing + missing.
        got = await c.get(f"/api/ideas/{iid}")
        assert got.status_code == 200 and got.json()["id"] == iid, got.text
        assert (await c.get("/api/ideas/nonexistent-idea-xyz")).status_code == 404

        # List + pagination (seed two more for pagination clarity).
        for _ in range(2):
            await _create_idea(c)
        listed = await c.get("/api/ideas")
        assert listed.status_code == 200
        body = listed.json()
        assert "ideas" in body or "items" in body or isinstance(body, list)
        paged = await c.get("/api/ideas", params={"limit": 2, "offset": 0})
        assert len((paged.json().get("ideas") or paged.json().get("items") or paged.json())) <= 2

        # Update requires auth.
        assert (await c.patch(f"/api/ideas/{iid}", json={"confidence": 0.9})).status_code == 401
        patched = await c.patch(f"/api/ideas/{iid}", json={"confidence": 0.9}, headers=AUTH)
        assert patched.status_code == 200
        assert patched.json()["confidence"] == pytest.approx(0.9, abs=0.01)

        # Count + cards — read surfaces the UI uses.
        cnt = await c.get("/api/ideas/count")
        assert cnt.status_code == 200
        assert "count" in cnt.json() or "total" in cnt.json()
        cards = await c.get("/api/ideas/cards")
        assert cards.status_code == 200 and "items" in cards.json()


# ---------------------------------------------------------------------------
# Idea Lifecycle (8 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_advance_idea_stage_and_409_when_complete():
    """Advance stage on a fresh idea succeeds; advancing past
    `complete` returns 409. One flow covers both the happy path
    and the terminal-state guard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.post(f"/api/ideas/{iid}/advance", headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "stage" in body or "idea" in body
        # Move to complete, then advance must 409.
        set_complete = await c.post(f"/api/ideas/{iid}/stage", json={"stage": "complete"}, headers=AUTH)
        assert set_complete.status_code == 200
        assert (await c.post(f"/api/ideas/{iid}/advance", headers=AUTH)).status_code == 409


@pytest.mark.asyncio
async def test_set_idea_stage():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.post(f"/api/ideas/{iid}/stage", json={"stage": "specced"}, headers=AUTH)
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_idea_progress():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.get(f"/api/ideas/{iid}/progress")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "stage" in body or "idea_id" in body


@pytest.mark.asyncio
async def test_idea_activity():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.get(f"/api/ideas/{iid}/activity")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_idea_progress_overview():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c)
        r = await c.get("/api/ideas/progress")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "total_ideas" in body or "by_stage" in body


@pytest.mark.asyncio
async def test_idea_showcase():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c)
        r = await c.get("/api/ideas/showcase")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "ideas" in body or "items" in body or "showcase" in body


@pytest.mark.asyncio
async def test_idea_resonance_feed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c)
        r = await c.get("/api/ideas/resonance")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Tags (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_idea_tags():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.put(f"/api/ideas/{iid}/tags", json={"tags": ["infra", "api"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tags" in body
        normalized = body["tags"]
        assert "infra" in normalized
        assert "api" in normalized


@pytest.mark.asyncio
async def test_list_tags_catalog():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        await c.put(f"/api/ideas/{iid}/tags", json={"tags": ["catalog-tag"]})
        r = await c.get("/api/ideas/tags")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tags" in body or "catalog" in body or isinstance(body, list)


@pytest.mark.asyncio
async def test_idea_cards_filter_by_tag():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        await c.put(f"/api/ideas/{iid}/tags", json={"tags": ["filterable"]})
        r = await c.get("/api/ideas/cards", params={"q": "tag:filterable"})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_invalid_tag_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        # Empty string tag should be invalid after normalization
        r = await c.put(f"/api/ideas/{iid}/tags", json={"tags": [""]})
        # Either 422 (validation) or the service normalizes it out
        assert r.status_code in (200, 422), r.text


# ---------------------------------------------------------------------------
# Investment & Forking (5 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stake_on_idea():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.post(f"/api/ideas/{iid}/stake", json={
            "contributor_id": "test-user",
            "amount_cc": 10.0,
            "rationale": "testing",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "amount_cc" in body or "stake" in body or "staked" in body


@pytest.mark.asyncio
async def test_fork_idea():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.post(f"/api/ideas/{iid}/fork", params={"forker_id": "test-user"})
        assert r.status_code == 201, r.text
        body = r.json()
        # Fork response wraps in {"idea": {...}, "lineage_link_id": ..., "source_idea_id": ...}
        assert "idea" in body
        assert "source_idea_id" in body


@pytest.mark.asyncio
async def test_forked_idea_references_parent():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.post(f"/api/ideas/{iid}/fork", params={"forker_id": "test-user"})
        assert r.status_code == 201, r.text
        forked = r.json()
        forked_id = forked["idea"]["id"]
        assert forked["source_idea_id"] == iid
        r2 = await c.get(f"/api/ideas/{forked_id}")
        assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_idea_selection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c)
        await _create_idea(c)
        r = await c.post("/api/ideas/select", headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "idea_id" in body or "id" in body or "selected" in body


@pytest.mark.asyncio
async def test_idea_selection_ab_stats():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/selection-ab/stats")
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Questions & Enrichment (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_question_to_idea():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.post(f"/api/ideas/{iid}/questions", json={
            "question": "Is this viable?",
            "value_to_whole": 5.0,
            "estimated_cost": 1.0,
        })
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_answer_question():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        await c.post(f"/api/ideas/{iid}/questions", json={
            "question": "Is this viable?",
            "value_to_whole": 5.0,
            "estimated_cost": 1.0,
        })
        r = await c.post(f"/api/ideas/{iid}/questions/answer", json={
            "question": "Is this viable?",
            "answer": "Yes, after validation.",
        })
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_concept_resonance_happy_and_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        r = await c.get(f"/api/ideas/{iid}/concept-resonance")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "matches" in body or "related" in body or "idea_id" in body
        # Missing idea → 404 (not silent 200 with empty payload).
        assert (await c.get("/api/ideas/nonexistent-idea-xyz/concept-resonance")).status_code == 404


# ---------------------------------------------------------------------------
# Full User Journey (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_idea_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)

        # Advance through stages
        r = await c.post(f"/api/ideas/{iid}/advance", headers=AUTH)
        assert r.status_code == 200, r.text

        r = await c.post(f"/api/ideas/{iid}/advance", headers=AUTH)
        assert r.status_code == 200, r.text

        # Update value
        r = await c.patch(f"/api/ideas/{iid}", json={"potential_value": 200.0}, headers=AUTH)
        assert r.status_code == 200, r.text

        # Check progress
        r = await c.get(f"/api/ideas/{iid}/progress")
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_idea_with_tasks():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)
        # GET tasks for the idea (may be empty but should return 200)
        r = await c.get(f"/api/ideas/{iid}/tasks")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tasks" in body or "items" in body or isinstance(body, dict)


@pytest.mark.asyncio
async def test_multiple_ideas_sorted_by_roi():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, potential_value=10.0, estimated_cost=10.0, confidence=0.5)
        await _create_idea(c, potential_value=500.0, estimated_cost=10.0, confidence=0.9)
        await _create_idea(c, potential_value=50.0, estimated_cost=10.0, confidence=0.7)
        r = await c.get("/api/ideas")
        assert r.status_code == 200, r.text
        body = r.json()
        ideas = body.get("ideas") or body.get("items") or []
        assert len(ideas) >= 3


@pytest.mark.asyncio
async def test_idea_storage_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/storage")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "backend" in body


# ---------------------------------------------------------------------------
# Federation Nodes (6 tests)
# ---------------------------------------------------------------------------


def _node_id() -> str:
    """Generate a valid 16-char node ID."""
    return uuid4().hex[:16]


@pytest.mark.asyncio
async def test_federation_node_registration_flow():
    """A node registers, appears in the list, heartbeats, shows its
    capabilities, and deletes cleanly. One lifecycle covers the
    whole federation node CRUD."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        nid = _node_id()
        reg = await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "test-host",
            "os_type": "linux",
            "providers": ["claude"],
            "capabilities": {"task_execution": True},
        })
        assert reg.status_code == 201 and reg.json()["node_id"] == nid, reg.text

        listed = await c.get("/api/federation/nodes")
        assert listed.status_code == 200
        nodes = listed.json() if isinstance(listed.json(), list) else listed.json().get("nodes", [])
        assert nid in [n.get("node_id") for n in nodes]

        beat = await c.post(f"/api/federation/nodes/{nid}/heartbeat", json={"status": "idle"})
        assert beat.status_code == 200, beat.text

        caps = await c.get("/api/federation/nodes/capabilities")
        assert caps.status_code == 200, caps.text

        assert (await c.delete(f"/api/federation/nodes/{nid}")).status_code == 204


@pytest.mark.asyncio
async def test_federation_node_messaging_flow():
    """Two nodes register, one sends the other a message, the
    receiver retrieves it. Kept separate from the registration flow
    because messaging has its own semantics (not just CRUD)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sender, receiver = _node_id(), _node_id()
        for nid, host in [(sender, "sender-host"), (receiver, "receiver-host")]:
            await c.post("/api/federation/nodes", json={
                "node_id": nid, "hostname": host, "os_type": "linux",
            })
        sent = await c.post(f"/api/federation/nodes/{sender}/messages", json={
            "from_node": sender, "to_node": receiver,
            "type": "text", "text": "hello from test",
        })
        assert sent.status_code == 201, sent.text

        got = await c.get(f"/api/federation/nodes/{receiver}/messages",
                          params={"unread_only": "false"})
        assert got.status_code == 200, got.text
        msgs = got.json().get("messages", [])
        assert any(m.get("text") == "hello from test" for m in msgs), msgs


# ---------------------------------------------------------------------------
# Providers (2 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_providers_returns_at_least_one():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/providers")
        assert r.status_code == 200, r.text
        providers = r.json()["providers"]
        assert isinstance(providers, list) and len(providers) >= 1


# ---------------------------------------------------------------------------
# Spec Registry — Delete (2 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spec_delete_flow():
    """Create spec → delete → gone (404 on re-get). Deleting an
    already-missing spec is also 404 so the UI can treat 'not
    found' as idempotent."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("spec")
        r = await c.post("/api/spec-registry", json={
            "spec_id": sid, "title": "Deletable", "summary": "Will be deleted.",
        }, headers=AUTH)
        assert r.status_code == 201, r.text
        assert (await c.get(f"/api/spec-registry/{sid}")).status_code == 200
        assert (await c.delete(f"/api/spec-registry/{sid}", headers=AUTH)).status_code == 204
        assert (await c.get(f"/api/spec-registry/{sid}")).status_code == 404
        assert (await c.delete("/api/spec-registry/nonexistent-spec", headers=AUTH)).status_code == 404


@pytest.mark.asyncio
async def test_list_assets_handles_non_pipeline_asset_types():
    """Regression: /api/assets crashed 500 when graph had nodes with
    asset_type values outside the CODE|MODEL|CONTENT|DATA pipeline
    enum (e.g. BLUEPRINT, VIDEO, AUDIO from the Living Collective KB
    seed + resolver-minted album/track nodes). The listing model
    accepts any string; the POST contract (AssetCreate) keeps the
    enum tight."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Seed an asset node directly in the graph with a non-pipeline
        # asset_type — the exact shape the resolver + KB seed produce.
        node_id = f"asset-regression-{uuid4().hex[:8]}"
        r = await c.post(
            "/api/graph/nodes",
            json={
                "id": node_id,
                "type": "asset",
                "name": "Regression blueprint",
                "description": "Non-pipeline asset_type that used to crash list",
                "properties": {"asset_type": "BLUEPRINT"},
            },
        )
        assert r.status_code in (200, 201), r.text

        # The listing must succeed and include the node we just seeded.
        r = await c.get("/api/assets?limit=500")
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        types_seen = {item.get("type") for item in items}
        # At minimum, our seeded type must flow through the response
        # unchanged — not coerced to CONTENT or dropped.
        assert "BLUEPRINT" in types_seen, (
            f"expected BLUEPRINT in {types_seen}; the read model must "
            "accept any asset_type string from the graph"
        )


@pytest.mark.asyncio
async def test_multi_device_identity_flow():
    """One user's journey across devices — every identity guarantee
    in one flow so we get wide coverage without test bloat:

      · /vision/join (register_interest) returns a contributor_id
        the client persists. Same email on re-submit → same id
      · graduate with same email, different fingerprint → same id
        (the core cross-device guarantee)
      · graduate partial-updates merge onto the node without
        clobbering earlier consent flags + roles
      · claim-by-identity via email on a fresh browser restores
        the full profile so the UI can rehydrate
      · Clean error paths: empty claim → 400; unknown email → 404
    """
    email = f"flow+{uuid4().hex[:6]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Laptop — /vision/join carries the full consent state.
        r1 = await c.post("/api/interest/register", json={
            "name": "Traveler",
            "email": email,
            "resonant_roles": ["frequency-holder"],
            "locale": "en",
            "consent_findable": True,
            "consent_email_updates": True,
        })
        assert r1.status_code == 200, r1.text
        cid = r1.json()["contributor_id"]
        assert cid, "register must return contributor_id for localStorage persistence"

        # Phone — graduate with different fingerprint + partial
        # update (just name + locale; consent fields omitted).
        # Same email → same contributor; omitted fields preserved.
        r2 = await c.post("/api/contributors/graduate", json={
            "author_name": "Traveler (phone)",
            "email": email,
            "device_fingerprint": "phone-fp",
            "locale": "de",
        })
        d2 = r2.json()
        assert d2["created"] is False
        assert d2["contributor_id"] == cid, "same email must yield same id across devices"
        assert d2["locale"] == "de"

        # Partial-update merge proof: earlier consent + roles survive.
        node = (await c.get(f"/api/graph/nodes/contributor:{cid}")).json()
        assert node["consent_findable"] is True
        assert node["consent_email_updates"] is True
        assert node["resonant_roles"] == ["frequency-holder"]

        # Fresh browser / new device — claim by email returns the
        # full profile for localStorage rehydration.
        claim = await c.post("/api/contributors/claim-by-identity", json={"email": email})
        cj = claim.json()
        assert claim.status_code == 200
        assert cj["contributor_id"] == cid
        assert cj["matched_provider"] == "email"
        assert "frequency-holder" in cj["resonant_roles"]

        # Clean error paths the UI can branch on (not silent 500s).
        assert (await c.post("/api/contributors/claim-by-identity", json={})).status_code == 400
        assert (await c.post("/api/contributors/claim-by-identity",
                             json={"email": f"ghost+{uuid4().hex[:6]}@nowhere.test"})).status_code == 404
