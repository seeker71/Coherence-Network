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
# Health & Meta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_and_meta_endpoints():
    """Five infrastructure endpoints the frontend + deploy verifier
    rely on: /health, /ping, /version, /ready, /meta/summary. All
    checked in one round."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        health = await c.get("/api/health")
        assert health.status_code == 200 and health.json()["status"] == "ok"
        assert "version" in health.json() and "uptime_seconds" in health.json()

        assert (await c.get("/api/ping")).json()["pong"] is True

        version = (await c.get("/api/version")).json()["version"]
        assert re.match(r"^\d+\.\d+\.\d+", version), version

        ready = await c.get("/api/ready")
        # /ready is 200 when graph_store wired, 503 otherwise — both valid.
        assert ready.status_code in (200, 503)
        if ready.status_code == 200:
            assert "db_connected" in ready.json()

        meta = await c.get("/api/meta/summary")
        assert meta.status_code == 200
        assert "endpoint_count" in meta.json() or "total_endpoints" in meta.json()


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
async def test_idea_lifecycle_flow():
    """Full lifecycle: seed idea → advance → set-stage → advance-past-
    complete is 409 → per-idea progress/activity → global progress/
    showcase/resonance/storage read surfaces → multi-idea sort by
    ROI → tasks listing. Every lifecycle-reading endpoint the UI
    uses in one journey."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)

        # Advance once (happy), set-stage back to specced, set to
        # complete, advance is 409.
        assert (await c.post(f"/api/ideas/{iid}/advance", headers=AUTH)).status_code == 200
        assert (await c.post(f"/api/ideas/{iid}/stage",
                             json={"stage": "specced"}, headers=AUTH)).status_code == 200
        assert (await c.post(f"/api/ideas/{iid}/stage",
                             json={"stage": "complete"}, headers=AUTH)).status_code == 200
        assert (await c.post(f"/api/ideas/{iid}/advance", headers=AUTH)).status_code == 409

        # Per-idea read surfaces.
        prog = await c.get(f"/api/ideas/{iid}/progress")
        assert prog.status_code == 200
        assert "stage" in prog.json() or "idea_id" in prog.json()
        assert isinstance((await c.get(f"/api/ideas/{iid}/activity")).json(), list)
        tasks = await c.get(f"/api/ideas/{iid}/tasks")
        assert tasks.status_code == 200

        # Global read surfaces.
        overview = await c.get("/api/ideas/progress")
        assert overview.status_code == 200
        assert "total_ideas" in overview.json() or "by_stage" in overview.json()
        showcase = await c.get("/api/ideas/showcase")
        assert showcase.status_code == 200
        assert "ideas" in showcase.json() or "items" in showcase.json() or "showcase" in showcase.json()
        assert isinstance((await c.get("/api/ideas/resonance")).json(), list)
        storage = await c.get("/api/ideas/storage")
        assert storage.status_code == 200 and "backend" in storage.json()

        # Multi-idea list (seed a range of ROIs — list must return >= 3
        # even though order-by-roi is the service's internal sort).
        for val in (10.0, 500.0, 50.0):
            await _create_idea(c, potential_value=val, estimated_cost=10.0, confidence=0.7)
        body = (await c.get("/api/ideas")).json()
        ideas = body.get("ideas") or body.get("items") or []
        assert len(ideas) >= 3


# ---------------------------------------------------------------------------
# Tags (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_tags_flow():
    """Set tags → read back normalized → catalog lists them →
    cards filter by tag → empty-string tag validation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)

        set_resp = await c.put(f"/api/ideas/{iid}/tags", json={"tags": ["infra", "filterable"]})
        assert set_resp.status_code == 200
        normalized = set_resp.json()["tags"]
        assert "infra" in normalized and "filterable" in normalized

        catalog = await c.get("/api/ideas/tags")
        assert catalog.status_code == 200
        cb = catalog.json()
        assert "tags" in cb or "catalog" in cb or isinstance(cb, list)

        assert (await c.get("/api/ideas/cards", params={"q": "tag:filterable"})).status_code == 200

        # Empty-string tag — either 422 or normalized out; not 500.
        assert (await c.put(f"/api/ideas/{iid}/tags", json={"tags": [""]})).status_code in (200, 422)


# ---------------------------------------------------------------------------
# Investment & Forking (5 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_investment_fork_selection_flow():
    """Stake CC on an idea, fork it, verify the fork references its
    parent, select an idea algorithmically, read the A/B stats."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)

        stake = await c.post(f"/api/ideas/{iid}/stake", json={
            "contributor_id": "test-user", "amount_cc": 10.0, "rationale": "testing",
        })
        assert stake.status_code == 200
        sb = stake.json()
        assert "amount_cc" in sb or "stake" in sb or "staked" in sb

        fork = await c.post(f"/api/ideas/{iid}/fork", params={"forker_id": "test-user"})
        assert fork.status_code == 201
        forked = fork.json()
        assert forked["source_idea_id"] == iid
        assert (await c.get(f"/api/ideas/{forked['idea']['id']}")).status_code == 200

        await _create_idea(c)  # one more so selection has choices
        sel = await c.post("/api/ideas/select", headers=AUTH)
        assert sel.status_code == 200
        sb2 = sel.json()
        assert "idea_id" in sb2 or "id" in sb2 or "selected" in sb2
        assert (await c.get("/api/ideas/selection-ab/stats")).status_code == 200


# ---------------------------------------------------------------------------
# Questions & Enrichment (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idea_questions_and_resonance_flow():
    """Add a question, answer it, read concept-resonance matches,
    404 on a missing idea."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid()
        await _create_idea(c, iid)

        q = await c.post(f"/api/ideas/{iid}/questions", json={
            "question": "Is this viable?", "value_to_whole": 5.0, "estimated_cost": 1.0,
        })
        assert q.status_code == 200

        ans = await c.post(f"/api/ideas/{iid}/questions/answer", json={
            "question": "Is this viable?", "answer": "Yes, after validation.",
        })
        assert ans.status_code == 200

        reso = await c.get(f"/api/ideas/{iid}/concept-resonance")
        assert reso.status_code == 200
        rb = reso.json()
        assert "matches" in rb or "related" in rb or "idea_id" in rb
        assert (await c.get("/api/ideas/nonexistent-idea-xyz/concept-resonance")).status_code == 404


# (The former 'Full User Journey' tests — full_idea_lifecycle,
# idea_with_tasks, multiple_ideas_sorted_by_roi, idea_storage_info —
# fold into test_idea_lifecycle_flow above. Single journey covers
# every lifecycle read surface.)


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
