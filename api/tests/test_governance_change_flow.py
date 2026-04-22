"""Contributor onboarding + governed change flow (spec:
contributor-onboarding-and-governed-change-flow).

Four flows cover the surface:

  · Onboarding (register → list → 409 on duplicate → session_token
    resolves profile)
  · Change request creation across types (idea_create, spec_create,
    idea_add_question) with proposer attribution
  · Voting semantics (human yes, machine no, proposer-self-vote 400)
  · Approval lifecycle + queries (approved idea/spec/question
    auto-apply; rejected stays rejected and doesn't write; list +
    get-by-id + 404)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _register(c: AsyncClient, handle: str | None = None) -> dict:
    h = handle or _uid("contrib")
    r = await c.post("/api/onboarding/register",
                     json={"handle": h, "email": f"{h}@test.dev"})
    assert r.status_code == 200, r.text
    return r.json()


async def _graph_contributor(c: AsyncClient, name: str | None = None) -> str:
    n = name or _uid("user")
    r = await c.post("/api/contributors",
                     json={"type": "HUMAN", "name": n,
                           "email": f"{n}@coherence.network"},
                     headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _idea_create_cr(
    c: AsyncClient, proposer_id: str, idea_id: str,
    *, auto_apply: bool = False, title: str | None = None,
) -> str:
    cr = await c.post("/api/governance/change-requests", json={
        "request_type": "idea_create",
        "title": title or f"Create {idea_id}",
        "payload": {
            "id": idea_id, "name": f"Idea {idea_id}",
            "description": "Governance-created",
            "potential_value": 50.0, "estimated_cost": 5.0, "confidence": 0.7,
        },
        "proposer_id": proposer_id, "proposer_type": "human",
        "auto_apply_on_approval": auto_apply,
    }, headers=AUTH)
    assert cr.status_code == 201, cr.text
    return cr.json()["id"]


@pytest.mark.asyncio
async def test_onboarding_flow():
    """Register contributor → appears in list → duplicate handle 409
    → session_token resolves back to the profile."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        handle = _uid("alice")
        reg = await _register(c, handle)
        assert reg["created"] is True
        assert reg["handle"] == handle
        assert reg["trust_level"] == "tofu"
        assert reg["contributor_id"] and reg["session_token"]

        listing = (await c.get("/api/onboarding/contributors")).json()
        assert handle in [item["handle"] for item in listing]

        # Duplicate handle → 409.
        dup = await c.post("/api/onboarding/register", json={"handle": handle})
        assert dup.status_code == 409

        # Session token round-trips to profile.
        sess = (await c.get("/api/onboarding/session",
                            headers={"Authorization": f"Bearer {reg['session_token']}"})).json()
        assert sess["contributor_id"] == reg["contributor_id"]
        assert sess["handle"] == handle


@pytest.mark.asyncio
async def test_change_request_creation_across_types():
    """Three change-request shapes (idea_create, spec_create,
    idea_add_question) create with proposer attribution and status
    'open'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer_id = await _graph_contributor(c)

        # idea_create with proposer attribution.
        idea_id = _uid("gov-idea")
        cr = await c.post("/api/governance/change-requests", json={
            "request_type": "idea_create",
            "title": f"Create {idea_id}",
            "payload": {
                "id": idea_id, "name": f"Idea {idea_id}",
                "description": "Created through governance",
                "potential_value": 50.0, "estimated_cost": 5.0, "confidence": 0.7,
            },
            "proposer_id": proposer_id, "proposer_type": "human",
            "auto_apply_on_approval": True,
        }, headers=AUTH)
        body = cr.json()
        assert cr.status_code == 201
        assert body["proposer_id"] == proposer_id
        assert body["proposer_type"] == "human"
        assert body["status"] == "open"
        assert body["request_type"] == "idea_create"

        # spec_create.
        spec_id = _uid("gov-spec")
        spec_cr = await c.post("/api/governance/change-requests", json={
            "request_type": "spec_create",
            "title": f"Create {spec_id}",
            "payload": {"spec_id": spec_id, "title": f"Spec {spec_id}",
                        "summary": "Created through governance",
                        "created_by_contributor_id": proposer_id},
            "proposer_id": proposer_id, "proposer_type": "human",
        }, headers=AUTH)
        assert spec_cr.status_code == 201
        assert spec_cr.json()["request_type"] == "spec_create"

        # idea_add_question — needs the parent idea first.
        q_idea_id = _uid("q-idea")
        await c.post("/api/ideas", json={
            "id": q_idea_id, "name": f"Idea {q_idea_id}",
            "description": "For question test",
            "potential_value": 100.0, "estimated_cost": 10.0,
        })
        q_cr = await c.post("/api/governance/change-requests", json={
            "request_type": "idea_add_question",
            "title": f"Add Q to {q_idea_id}",
            "payload": {"idea_id": q_idea_id,
                        "question": "What is the expected timeline?",
                        "value_to_whole": 0.3, "estimated_cost": 2.0},
            "proposer_id": proposer_id, "proposer_type": "human",
        }, headers=AUTH)
        assert q_cr.status_code == 201
        assert q_cr.json()["request_type"] == "idea_add_question"


@pytest.mark.asyncio
async def test_voting_semantics_flow():
    """Human reviewer casts yes → approvals ≥ 1, attribution stored.
    Machine reviewer casts no → rejections ≥ 1, status 'rejected'.
    Proposer self-vote → 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer = await _graph_contributor(c)
        human_reviewer = await _graph_contributor(c)

        # Human yes vote.
        cr_id = await _idea_create_cr(c, proposer, _uid("yes-idea"))
        yes = await c.post(f"/api/governance/change-requests/{cr_id}/votes", json={
            "voter_id": human_reviewer, "voter_type": "human",
            "decision": "yes", "rationale": "Looks reasonable",
        }, headers=AUTH)
        assert yes.status_code == 200
        yb = yes.json()
        assert yb["approvals"] >= 1
        v = yb["votes"][0]
        assert v["voter_id"] == human_reviewer
        assert v["voter_type"] == "human"
        assert v["decision"] == "yes"
        assert v["rationale"] == "Looks reasonable"

        # Machine no vote → rejected.
        no_cr = await _idea_create_cr(c, proposer, _uid("no-idea"))
        no = await c.post(f"/api/governance/change-requests/{no_cr}/votes", json={
            "voter_id": "auto-reviewer-bot", "voter_type": "machine",
            "decision": "no", "rationale": "Insufficient detail",
        }, headers=AUTH)
        nb = no.json()
        assert no.status_code == 200
        assert nb["rejections"] >= 1 and nb["status"] == "rejected"
        assert nb["votes"][0]["voter_type"] == "machine"
        assert nb["votes"][0]["decision"] == "no"

        # Proposer self-vote → 400.
        self_cr = await _idea_create_cr(c, proposer, _uid("self-idea"))
        self_vote = await c.post(f"/api/governance/change-requests/{self_cr}/votes",
                                 json={"voter_id": proposer, "voter_type": "human",
                                       "decision": "yes"},
                                 headers=AUTH)
        assert self_vote.status_code == 400


@pytest.mark.asyncio
async def test_approval_lifecycle_and_queries_flow():
    """Approved idea_create / spec_create / idea_add_question all
    auto-apply and create the underlying resource. Rejected requests
    stay rejected with applied_result None and no resource created.
    List + get-by-id + 404 surfaces."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        proposer = await _graph_contributor(c)
        reviewer = await _graph_contributor(c)

        # Approved idea_create → auto-applies, idea visible.
        idea_id = _uid("auto-idea")
        idea_cr_id = await _idea_create_cr(c, proposer, idea_id, auto_apply=True)
        idea_vote = await c.post(f"/api/governance/change-requests/{idea_cr_id}/votes",
                                 json={"voter_id": reviewer, "voter_type": "human",
                                       "decision": "yes", "rationale": "Approved"},
                                 headers=AUTH)
        ib = idea_vote.json()
        assert ib["status"] == "applied"
        assert ib["applied_result"]["kind"] == "idea"
        assert ib["applied_result"]["action"] == "created"
        assert (await c.get(f"/api/ideas/{idea_id}")).status_code == 200

        # Approved spec_create → auto-applies.
        spec_id = _uid("auto-spec")
        spec_cr = await c.post("/api/governance/change-requests", json={
            "request_type": "spec_create",
            "title": f"Auto-apply spec {spec_id}",
            "payload": {"spec_id": spec_id, "title": f"Spec {spec_id}",
                        "summary": "Auto-applied",
                        "created_by_contributor_id": proposer},
            "proposer_id": proposer, "proposer_type": "human",
            "auto_apply_on_approval": True,
        }, headers=AUTH)
        spec_cr_id = spec_cr.json()["id"]
        spec_vote = await c.post(f"/api/governance/change-requests/{spec_cr_id}/votes",
                                 json={"voter_id": reviewer, "voter_type": "human",
                                       "decision": "yes"},
                                 headers=AUTH)
        sb = spec_vote.json()
        assert sb["status"] == "applied"
        assert sb["applied_result"]["kind"] == "spec"
        assert (await c.get(f"/api/spec-registry/{spec_id}")).status_code == 200

        # Approved idea_add_question → auto-applies.
        parent_idea = _uid("qa-idea")
        await c.post("/api/ideas", json={
            "id": parent_idea, "name": f"Idea {parent_idea}",
            "description": "parent", "potential_value": 100.0, "estimated_cost": 10.0,
        })
        q_cr = await c.post("/api/governance/change-requests", json={
            "request_type": "idea_add_question",
            "title": f"Add Q to {parent_idea}",
            "payload": {"idea_id": parent_idea,
                        "question": "How will we measure success?",
                        "value_to_whole": 0.5, "estimated_cost": 3.0},
            "proposer_id": proposer, "proposer_type": "human",
            "auto_apply_on_approval": True,
        }, headers=AUTH)
        q_cr_id = q_cr.json()["id"]
        q_vote = await c.post(f"/api/governance/change-requests/{q_cr_id}/votes",
                              json={"voter_id": reviewer, "voter_type": "human",
                                    "decision": "yes"},
                              headers=AUTH)
        qb = q_vote.json()
        assert qb["status"] == "applied"
        assert qb["applied_result"]["kind"] == "idea_question"
        assert qb["applied_result"]["action"] == "added"

        # Rejected request stays rejected and does NOT write the resource.
        rej_idea = _uid("rej-idea")
        rej_cr = await _idea_create_cr(c, proposer, rej_idea)
        rej_vote = await c.post(f"/api/governance/change-requests/{rej_cr}/votes",
                                json={"voter_id": "strict-reviewer",
                                      "voter_type": "machine",
                                      "decision": "no", "rationale": "Not ready"},
                                headers=AUTH)
        rb = rej_vote.json()
        assert rb["status"] == "rejected"
        assert rb["applied_result"] is None
        assert (await c.get(f"/api/ideas/{rej_idea}")).status_code == 404

        # List surfaces all change requests (at minimum ours).
        listing = (await c.get("/api/governance/change-requests")).json()
        assert len(listing) >= 1

        # Get-by-id round-trips; unknown id → 404.
        fetched = (await c.get(f"/api/governance/change-requests/{idea_cr_id}")).json()
        assert fetched["id"] == idea_cr_id
        assert fetched["proposer_id"] == proposer
        unknown = await c.get("/api/governance/change-requests/does-not-exist")
        assert unknown.status_code == 404
