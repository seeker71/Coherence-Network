"""End-to-end tests for contributor onboarding and governed change flow.

Spec: contributor-onboarding-and-governed-change-flow
Covers:
  1. New contributor can register and appear in contributor list
  2. Human can submit change requests for idea/spec/question updates
  3. Change request stores proposer and vote attribution
  4. Human/machine reviewer can cast yes/no vote via API
  5. Approved request auto-applies by default and records result
  6. Rejected request remains rejected and is not applied
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _register_contributor(c: AsyncClient, handle: str | None = None) -> dict:
    """Register an onboarding contributor and return the response body."""
    h = handle or _uid("contrib")
    r = await c.post("/api/onboarding/register", json={"handle": h, "email": f"{h}@test.dev"})
    assert r.status_code == 200, r.text
    return r.json()


async def _create_graph_contributor(c: AsyncClient, name: str | None = None) -> str:
    """Create a contributor in the graph (for proposer/voter IDs) and return its ID."""
    n = name or _uid("user")
    r = await c.post(
        "/api/contributors",
        json={"type": "HUMAN", "name": n, "email": f"{n}@coherence.network"},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1. Contributor registration and list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_contributor_and_appears_in_list():
    """New contributor registers from web and appears in the contributor list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        handle = _uid("alice")
        reg = await _register_contributor(c, handle)
        assert reg["created"] is True
        assert reg["handle"] == handle
        assert reg["trust_level"] == "tofu"
        assert reg["contributor_id"]
        assert reg["session_token"]

        # Contributor appears in the list
        listing = await c.get("/api/onboarding/contributors")
        assert listing.status_code == 200
        handles = [item["handle"] for item in listing.json()]
        assert handle in handles


@pytest.mark.asyncio
async def test_register_duplicate_handle_returns_409():
    """Registering with an already-taken handle returns 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        handle = _uid("dupe")
        await _register_contributor(c, handle)
        r = await c.post("/api/onboarding/register", json={"handle": handle})
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_session_token_resolves_profile():
    """Session token from registration resolves to the contributor profile."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        reg = await _register_contributor(c)
        token = reg["session_token"]
        sess = await c.get(
            "/api/onboarding/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert sess.status_code == 200
        body = sess.json()
        assert body["contributor_id"] == reg["contributor_id"]
        assert body["handle"] == reg["handle"]


# ---------------------------------------------------------------------------
# 2 + 3. Submit change requests with proposer attribution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_idea_change_request_stores_proposer():
    """Submit an idea_create change request and verify proposer attribution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("proposer"))
        idea_id = _uid("gov-idea")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Create idea {idea_id}",
                "payload": {
                    "id": idea_id,
                    "name": f"Idea {idea_id}",
                    "description": "Created through governance",
                    "potential_value": 50.0,
                    "estimated_cost": 5.0,
                    "confidence": 0.7,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
                "auto_apply_on_approval": True,
            },
            headers=AUTH,
        )
        assert cr.status_code == 201, cr.text
        body = cr.json()
        assert body["proposer_id"] == proposer_id
        assert body["proposer_type"] == "human"
        assert body["status"] == "open"
        assert body["request_type"] == "idea_create"


@pytest.mark.asyncio
async def test_create_spec_change_request():
    """Submit a spec_create change request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("spec-proposer"))
        spec_id = _uid("gov-spec")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "spec_create",
                "title": f"Create spec {spec_id}",
                "payload": {
                    "spec_id": spec_id,
                    "title": f"Spec {spec_id}",
                    "summary": "Created through governance",
                    "created_by_contributor_id": proposer_id,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
            },
            headers=AUTH,
        )
        assert cr.status_code == 201, cr.text
        assert cr.json()["request_type"] == "spec_create"


@pytest.mark.asyncio
async def test_create_question_change_request():
    """Submit an idea_add_question change request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("q-proposer"))
        # First create the idea directly so the question can reference it
        idea_id = _uid("q-idea")
        idea_r = await c.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": f"Idea {idea_id}",
                "description": "For question test",
                "potential_value": 100.0,
                "estimated_cost": 10.0,
            },
        )
        assert idea_r.status_code == 201, idea_r.text

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_add_question",
                "title": f"Add question to {idea_id}",
                "payload": {
                    "idea_id": idea_id,
                    "question": "What is the expected timeline?",
                    "value_to_whole": 0.3,
                    "estimated_cost": 2.0,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
            },
            headers=AUTH,
        )
        assert cr.status_code == 201, cr.text
        assert cr.json()["request_type"] == "idea_add_question"


# ---------------------------------------------------------------------------
# 4. Human/machine reviewer can cast yes/no vote
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_human_reviewer_casts_yes_vote():
    """Human reviewer casts a yes vote and vote attribution is stored."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("prop"))
        reviewer_id = await _create_graph_contributor(c, _uid("reviewer"))
        idea_id = _uid("vote-idea")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Create {idea_id}",
                "payload": {
                    "id": idea_id,
                    "name": f"Idea {idea_id}",
                    "description": "Vote test",
                    "potential_value": 20.0,
                    "estimated_cost": 2.0,
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
                "rationale": "Looks reasonable",
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert body["approvals"] >= 1
        # Vote attribution stored
        assert len(body["votes"]) >= 1
        v = body["votes"][0]
        assert v["voter_id"] == reviewer_id
        assert v["voter_type"] == "human"
        assert v["decision"] == "yes"
        assert v["rationale"] == "Looks reasonable"


@pytest.mark.asyncio
async def test_machine_reviewer_casts_no_vote():
    """Machine reviewer casts a no vote via API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("m-prop"))
        idea_id = _uid("m-vote")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Create {idea_id}",
                "payload": {
                    "id": idea_id,
                    "name": f"Idea {idea_id}",
                    "description": "Machine review test",
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
                "voter_id": "auto-reviewer-bot",
                "voter_type": "machine",
                "decision": "no",
                "rationale": "Insufficient detail",
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert body["rejections"] >= 1
        assert body["status"] == "rejected"
        v = body["votes"][0]
        assert v["voter_type"] == "machine"
        assert v["decision"] == "no"


@pytest.mark.asyncio
async def test_proposer_cannot_self_vote():
    """Proposer's own vote on their change request is rejected (400)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("self-v"))

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": "Self-vote attempt",
                "payload": {
                    "id": _uid("self"),
                    "name": "Self idea",
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
                "voter_id": proposer_id,
                "voter_type": "human",
                "decision": "yes",
            },
            headers=AUTH,
        )
        assert vote.status_code == 400


# ---------------------------------------------------------------------------
# 5. Approved request auto-applies and records result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approved_idea_create_auto_applies():
    """Approved idea_create request auto-applies and records the result."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("ap-prop"))
        reviewer_id = await _create_graph_contributor(c, _uid("ap-rev"))
        idea_id = _uid("auto-apply")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Auto-apply idea {idea_id}",
                "payload": {
                    "id": idea_id,
                    "name": f"Idea {idea_id}",
                    "description": "Should auto-apply on approval",
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

        # Verify the idea actually exists now
        idea = await c.get(f"/api/ideas/{idea_id}")
        assert idea.status_code == 200, f"Idea {idea_id} should exist after auto-apply"


@pytest.mark.asyncio
async def test_approved_spec_create_auto_applies():
    """Approved spec_create request auto-applies and the spec is created."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("sp-prop"))
        reviewer_id = await _create_graph_contributor(c, _uid("sp-rev"))
        spec_id = _uid("auto-spec")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "spec_create",
                "title": f"Auto-apply spec {spec_id}",
                "payload": {
                    "spec_id": spec_id,
                    "title": f"Spec {spec_id}",
                    "summary": "Auto-applied spec",
                    "created_by_contributor_id": proposer_id,
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
                "rationale": "Good spec",
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert body["status"] == "applied"
        assert body["applied_result"]["kind"] == "spec"
        assert body["applied_result"]["action"] == "created"

        # Verify the spec exists
        spec = await c.get(f"/api/spec-registry/{spec_id}")
        assert spec.status_code == 200


@pytest.mark.asyncio
async def test_approved_question_add_auto_applies():
    """Approved idea_add_question request auto-applies."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("qa-prop"))
        reviewer_id = await _create_graph_contributor(c, _uid("qa-rev"))
        idea_id = _uid("qa-idea")

        # Create the idea first
        await c.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": f"Idea {idea_id}",
                "description": "For question add test",
                "potential_value": 100.0,
                "estimated_cost": 10.0,
            },
        )

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_add_question",
                "title": f"Add question to {idea_id}",
                "payload": {
                    "idea_id": idea_id,
                    "question": "How will we measure success?",
                    "value_to_whole": 0.5,
                    "estimated_cost": 3.0,
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
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert body["status"] == "applied"
        assert body["applied_result"]["kind"] == "idea_question"
        assert body["applied_result"]["action"] == "added"


# ---------------------------------------------------------------------------
# 6. Rejected request stays rejected and is not applied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rejected_request_stays_rejected_not_applied():
    """A rejected change request stays rejected and the resource is not created."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("rej-prop"))
        idea_id = _uid("rej-idea")

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": f"Rejected idea {idea_id}",
                "payload": {
                    "id": idea_id,
                    "name": f"Idea {idea_id}",
                    "description": "Should be rejected",
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
                "voter_id": "strict-reviewer",
                "voter_type": "machine",
                "decision": "no",
                "rationale": "Not ready",
            },
            headers=AUTH,
        )
        assert vote.status_code == 200
        body = vote.json()
        assert body["status"] == "rejected"
        assert body["applied_result"] is None

        # The idea should NOT exist
        idea = await c.get(f"/api/ideas/{idea_id}")
        assert idea.status_code == 404


# ---------------------------------------------------------------------------
# 7. List and get change requests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_change_requests():
    """Governance change requests can be listed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("list-prop"))

        await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": "Listed idea",
                "payload": {
                    "id": _uid("listed"),
                    "name": "Listed",
                    "description": "x",
                    "potential_value": 1.0,
                    "estimated_cost": 0.1,
                    "confidence": 0.5,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
            },
            headers=AUTH,
        )

        listing = await c.get("/api/governance/change-requests")
        assert listing.status_code == 200
        items = listing.json()
        assert len(items) >= 1
        assert any(item["title"] == "Listed idea" for item in items)


@pytest.mark.asyncio
async def test_get_change_request_by_id():
    """Governance change request can be fetched by ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _create_graph_contributor(c, _uid("get-prop"))

        cr = await c.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": "Fetched idea",
                "payload": {
                    "id": _uid("fetched"),
                    "name": "Fetched",
                    "description": "x",
                    "potential_value": 1.0,
                    "estimated_cost": 0.1,
                    "confidence": 0.5,
                },
                "proposer_id": proposer_id,
                "proposer_type": "human",
            },
            headers=AUTH,
        )
        assert cr.status_code == 201
        cr_id = cr.json()["id"]

        fetched = await c.get(f"/api/governance/change-requests/{cr_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == cr_id
        assert fetched.json()["proposer_id"] == proposer_id


@pytest.mark.asyncio
async def test_get_nonexistent_change_request_returns_404():
    """Fetching a nonexistent change request returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/governance/change-requests/nonexistent-id")
        assert r.status_code == 404
