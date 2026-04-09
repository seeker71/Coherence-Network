"""Acceptance tests for spec: contributor-journey (idea: contributor-experience).

Covers done_when criteria:
  - POST /api/onboarding/register creates session in under 1 second
  - GET /api/onboarding/contributors lists registered contributors
  - POST /api/governance/change-requests stores proposer attribution
  - POST /api/governance/change-requests/{id}/votes records vote with rationale
  - Approved change requests auto-apply
  - GET /api/messages/inbox/{contributor_id} returns messages

Focused on spec done_when only; detailed governance/membership/message tests
live in test_governance_change_flow.py, test_flow_memberships.py, test_flow_messages.py.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "cj") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _register(c: AsyncClient, handle: str | None = None) -> dict:
    h = handle or _uid("contrib")
    r = await c.post("/api/onboarding/register", json={"handle": h, "email": f"{h}@test.dev"})
    assert r.status_code == 200, r.text
    return r.json()


async def _create_graph_contributor(c: AsyncClient, name: str | None = None) -> str:
    n = name or _uid("user")
    r = await c.post(
        "/api/contributors",
        json={"type": "HUMAN", "name": n, "email": f"{n}@coherence.network"},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1. POST /api/onboarding/register creates session in under 1 second
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_session_under_1s():
    """Registration returns a session token in under 1 second (TOFU)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        handle = _uid("fast")
        t0 = time.perf_counter()
        reg = await _register(c, handle)
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"Registration took {elapsed:.2f}s (limit 1s)"
        assert reg["created"] is True
        assert reg["session_token"]
        assert reg["contributor_id"]
        assert reg["trust_level"] == "tofu"


# ---------------------------------------------------------------------------
# 2. GET /api/onboarding/contributors lists registered contributors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contributors_list_includes_registered():
    """Registered contributor appears in the contributor list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        handle = _uid("listed")
        await _register(c, handle)

        r = await c.get("/api/onboarding/contributors")
        assert r.status_code == 200
        handles = [item["handle"] for item in r.json()]
        assert handle in handles


# ---------------------------------------------------------------------------
# 3. POST /api/governance/change-requests stores proposer attribution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_request_stores_proposer():
    """Change request records proposer_id and proposer_type."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c)
        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Journey test {_uid()}",
                "payload": {
                    "id": _uid("idea"),
                    "name": "Journey Idea",
                    "description": "Proposer attribution test",
                    "potential_value": 50.0,
                    "estimated_cost": 5.0,
                    "confidence": 0.7,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
            },
            headers=AUTH,
        )
        assert cr.status_code == 201, cr.text
        body = cr.json()
        assert body["proposer_id"] == proposer_id
        assert body["proposer_type"] == "human"
        assert body["status"] == "open"


# ---------------------------------------------------------------------------
# 4. POST /api/governance/change-requests/{id}/votes records vote with rationale
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vote_records_rationale():
    """Vote stores voter attribution and rationale text."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("prop"))
        reviewer_id = await _create_graph_contributor(c, _uid("rev"))

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": "Vote rationale test",
                "payload": {
                    "id": _uid("idea"),
                    "name": "Vote Idea",
                    "description": "desc",
                    "potential_value": 10.0,
                    "estimated_cost": 1.0,
                    "confidence": 0.5,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
            },
            headers=AUTH,
        )
        assert cr.status_code == 201
        cr_id = cr.json()["id"]

        vote = await c.post(
            f"/api/governance/change-requests/{cr_id}/votes",
            json={
                "voter_id": reviewer_id,
                "voter_type": "human",
                "decision": "yes",
                "rationale": "Well-structured proposal",
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert len(body["votes"]) >= 1
        v = body["votes"][0]
        assert v["voter_id"] == reviewer_id
        assert v["rationale"] == "Well-structured proposal"


# ---------------------------------------------------------------------------
# 5. Approved change requests auto-apply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approved_request_auto_applies():
    """Approved idea_create with auto_apply_on_approval creates the idea."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("ap"))
        reviewer_id = await _create_graph_contributor(c, _uid("ar"))
        idea_id = _uid("auto")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Auto-apply {idea_id}",
                "payload": {
                    "id": idea_id,
                    "name": f"Idea {idea_id}",
                    "description": "Auto-apply journey test",
                    "potential_value": 80.0,
                    "estimated_cost": 8.0,
                    "confidence": 0.9,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
                "auto_apply_on_approval": True,
            },
            headers=AUTH,
        )
        assert cr.status_code == 201
        cr_id = cr.json()["id"]

        vote = await c.post(
            f"/api/governance/change-requests/{cr_id}/votes",
            json={
                "voter_id": reviewer_id,
                "voter_type": "human",
                "decision": "yes",
                "rationale": "Approved",
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert body["status"] == "applied"
        assert body["applied_result"] is not None
        assert body["applied_result"]["kind"] == "idea"
        assert body["applied_result"]["action"] == "created"

        # Verify idea exists
        idea = await c.get(f"/api/ideas/{idea_id}")
        assert idea.status_code == 200


# ---------------------------------------------------------------------------
# 6. GET /api/messages/inbox/{contributor_id} returns messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inbox_returns_messages():
    """Contributor inbox endpoint returns messages structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sender = _uid("sender")
        recipient = _uid("recip")

        # Send a message
        r = await c.post("/api/messages", headers=AUTH, json={
            "from_contributor_id": sender,
            "to_contributor_id": recipient,
            "subject": "Journey test",
            "body": "Hello from the contributor journey",
        })
        assert r.status_code == 201, r.text

        # Check inbox
        r2 = await c.get(f"/api/messages/inbox/{recipient}")
        assert r2.status_code == 200
        inbox = r2.json()
        assert inbox["contributor_id"] == recipient
        assert inbox["total"] >= 1
        assert isinstance(inbox["messages"], list)
