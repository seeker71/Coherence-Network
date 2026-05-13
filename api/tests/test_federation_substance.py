"""Federation substance payload — round-trip test.

Proves the substance layer of FederatedPayload (concept_proposals,
spec_proposals, idea_proposals, teaching_proposals) lands as governance
change requests that:

  - require ≥ 2 approvals (FEDERATION_IMPORT default)
  - do NOT auto-apply (substance wants a maintainer's eye + a PR)
  - apply, when manually triggered, to a "stored" result whose id matches
    the proposal id (the proposal body is held in the change request
    payload until someone walks it into the repo)

This is the symmetric companion to the existing telemetry layer
(lineage_links + usage_events) which already auto-applies after vote.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.governance import (
    ActorType,
    ChangeRequestStatus,
    ChangeRequestVoteCreate,
    VoteDecision,
)
from app.services import federation_service, governance_service
from app.services.governance_service import (
    _apply_approved_change_request,
    cast_vote,
)


BASE = "http://test"


def _instance_id() -> str:
    return f"peer_{uuid4().hex[:10]}"


async def _register_peer(client: AsyncClient, instance_id: str) -> None:
    body = {
        "instance_id": instance_id,
        "name": f"Peer {instance_id}",
        "endpoint_url": f"https://{instance_id}.example",
        "registered_at": "2026-05-13T00:00:00Z",
        "trust_level": "pending",
    }
    r = await client.post("/api/federation/instances", json=body)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_substance_payload_creates_governance_proposals():
    """A payload with all four substance types creates one OPEN change
    request per item, each with auto_apply_on_approval=False and
    required_approvals=2.
    """
    instance_id = _instance_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _register_peer(c, instance_id)

        payload = {
            "source_instance_id": instance_id,
            "timestamp": "2026-05-13T00:00:00Z",
            "lineage_links": [],
            "usage_events": [],
            "concept_proposals": [
                {
                    "id": "lc-shared-breath",
                    "title": "Shared breath",
                    "body_markdown": "# Shared breath\n\nA teaching on co-weaving.",
                    "origin_url": f"https://{instance_id}.example/vision/lc-shared-breath",
                }
            ],
            "spec_proposals": [
                {
                    "id": "peer-spec-example",
                    "title": "Peer-authored spec",
                    "body_markdown": "---\nstatus: draft\n---\n\nA spec from a peer.",
                }
            ],
            "idea_proposals": [
                {
                    "id": "peer-idea-example",
                    "title": "Peer-authored idea",
                    "body_markdown": "An idea proposed by a federated peer.",
                }
            ],
            "teaching_proposals": [
                {
                    "id": "teaching-on-tending",
                    "title": "On tending",
                    "body_markdown": "A teaching observed in the peer's body.",
                }
            ],
        }

        r = await c.post("/api/federation/sync", json=payload)
        assert r.status_code == 200, r.text
        result = r.json()

    assert result["source_instance_id"] == instance_id
    assert result["proposals_received"] == 4
    assert result["links_received"] == 0
    assert result["events_received"] == 0
    assert result["governance_requests_created"] == 4
    assert result["accepted"] == 4
    assert result["rejected"] == 0
    assert result["errors"] == []

    # Each proposal becomes a governance ChangeRequest tagged with the peer.
    all_crs = governance_service.list_change_requests(limit=500)
    peer_proposer = f"federation:{instance_id}"
    peer_crs = [cr for cr in all_crs if cr.proposer_id == peer_proposer]
    assert len(peer_crs) == 4

    federation_types = {cr.payload.get("federation_type") for cr in peer_crs}
    assert federation_types == {
        "concept_proposal",
        "spec_proposal",
        "idea_proposal",
        "teaching_proposal",
    }

    # Substance wants a maintainer's eye: required_approvals=2, no auto-apply.
    for cr in peer_crs:
        assert cr.required_approvals >= 2, (
            f"federation substance must require ≥2 approvals, got {cr.required_approvals}"
        )
        assert cr.auto_apply_on_approval is False, (
            "substance proposals must not auto-apply — a maintainer walks "
            "them into the repo as a PR"
        )
        assert cr.status == ChangeRequestStatus.OPEN
        # Full proposal body is held in the change request payload.
        assert "data" in cr.payload
        assert isinstance(cr.payload["data"], dict)
        assert cr.payload["data"].get("body_markdown")


@pytest.mark.asyncio
async def test_substance_proposal_approves_but_does_not_auto_apply():
    """Two YES votes flip a substance proposal to APPROVED but the applier
    is NOT auto-invoked. The proposal waits for a maintainer."""
    instance_id = _instance_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _register_peer(c, instance_id)

        payload = {
            "source_instance_id": instance_id,
            "timestamp": "2026-05-13T00:00:00Z",
            "concept_proposals": [
                {
                    "id": "lc-approve-no-apply",
                    "title": "Approve without auto-apply",
                    "body_markdown": "# Held by governance",
                }
            ],
        }
        r = await c.post("/api/federation/sync", json=payload)
        assert r.status_code == 200, r.text

    peer_proposer = f"federation:{instance_id}"
    crs = [
        cr
        for cr in governance_service.list_change_requests(limit=500)
        if cr.proposer_id == peer_proposer
    ]
    assert len(crs) == 1
    cr_id = crs[0].id

    cast_vote(
        cr_id,
        ChangeRequestVoteCreate(
            voter_id="maintainer-a",
            voter_type=ActorType.HUMAN,
            decision=VoteDecision.YES,
        ),
    )
    final = cast_vote(
        cr_id,
        ChangeRequestVoteCreate(
            voter_id="maintainer-b",
            voter_type=ActorType.HUMAN,
            decision=VoteDecision.YES,
        ),
    )
    assert final is not None
    # Two YES votes meet the threshold but auto_apply_on_approval=False
    # means the status stays APPROVED, not APPLIED. The body is held.
    assert final.status == ChangeRequestStatus.APPROVED
    assert final.applied_result is None


@pytest.mark.asyncio
async def test_substance_applier_records_stored_with_proposal_id():
    """When a maintainer manually applies a substance proposal, the
    applier returns kind=federation_{type} action=stored id=<proposal id>.
    The proposal body remains in the change request payload — the API
    never writes to the repo."""
    instance_id = _instance_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _register_peer(c, instance_id)

        payload = {
            "source_instance_id": instance_id,
            "timestamp": "2026-05-13T00:00:00Z",
            "teaching_proposals": [
                {
                    "id": "teaching-applier-shape",
                    "title": "Applier shape",
                    "body_markdown": "Substance is stored, not applied.",
                }
            ],
        }
        r = await c.post("/api/federation/sync", json=payload)
        assert r.status_code == 200, r.text

    peer_proposer = f"federation:{instance_id}"
    crs = [
        cr
        for cr in governance_service.list_change_requests(limit=500)
        if cr.proposer_id == peer_proposer
    ]
    assert len(crs) == 1
    cr = crs[0]

    cast_vote(
        cr.id,
        ChangeRequestVoteCreate(
            voter_id="maintainer-a",
            voter_type=ActorType.HUMAN,
            decision=VoteDecision.YES,
        ),
    )
    cast_vote(
        cr.id,
        ChangeRequestVoteCreate(
            voter_id="maintainer-b",
            voter_type=ActorType.HUMAN,
            decision=VoteDecision.YES,
        ),
    )

    approved = governance_service.get_change_request(cr.id)
    assert approved is not None
    assert approved.status == ChangeRequestStatus.APPROVED

    applied = _apply_approved_change_request(cr.id, approved)
    assert applied.status == ChangeRequestStatus.APPLIED
    assert applied.applied_result is not None
    assert applied.applied_result.get("kind") == "federation_teaching_proposal"
    assert applied.applied_result.get("action") == "stored"
    assert applied.applied_result.get("id") == "teaching-applier-shape"
    assert applied.applied_result.get("source") == instance_id


@pytest.mark.asyncio
async def test_substance_payload_from_unknown_instance_is_rejected():
    """A payload from an unregistered peer rejects all items (telemetry
    AND substance) without creating any change requests."""
    unknown = f"unknown_{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        payload = {
            "source_instance_id": unknown,
            "timestamp": "2026-05-13T00:00:00Z",
            "concept_proposals": [{"id": "lc-x", "body_markdown": "x"}],
            "spec_proposals": [{"id": "y", "body_markdown": "y"}],
        }
        r = await c.post("/api/federation/sync", json=payload)
        assert r.status_code == 200, r.text
        result = r.json()

    assert result["rejected"] == 2
    assert result["accepted"] == 0
    assert result["governance_requests_created"] == 0
    assert any("not registered" in e for e in result["errors"])
