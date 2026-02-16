from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_change_request_vote_applies_idea_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("CHANGE_REQUEST_MIN_APPROVALS", "1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        contributor = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"},
        )
        assert contributor.status_code == 201
        contributor_id = contributor.json()["id"]

        created = await client.post(
            "/api/governance/change-requests",
            json={
                "request_type": "idea_create",
                "title": "Create idea from governance pipeline",
                "payload": {
                    "id": "governance-idea",
                    "name": "Governance idea",
                    "description": "Created after yes vote",
                    "potential_value": 40.0,
                    "estimated_cost": 9.0,
                    "confidence": 0.65,
                },
                "proposer_id": contributor_id,
                "proposer_type": "human",
                "auto_apply_on_approval": True,
            },
        )
        assert created.status_code == 201
        request_id = created.json()["id"]

        voted = await client.post(
            f"/api/governance/change-requests/{request_id}/votes",
            json={
                "voter_id": contributor_id,
                "voter_type": "human",
                "decision": "yes",
                "rationale": "Looks good",
            },
        )
        assert voted.status_code == 200
        voted_payload = voted.json()
        assert voted_payload["status"] == "applied"
        assert voted_payload["approvals"] == 1
        assert voted_payload["applied_result"]["kind"] == "idea"

        idea = await client.get("/api/ideas/governance-idea")
        assert idea.status_code == 200


@pytest.mark.asyncio
async def test_change_request_vote_rejects_spec_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("CHANGE_REQUEST_MIN_APPROVALS", "1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        contributor = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Bob", "email": "bob@example.com"},
        )
        assert contributor.status_code == 201
        contributor_id = contributor.json()["id"]

        seeded_spec = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": "spec-reject",
                "title": "Seed spec",
                "summary": "Seed summary",
                "created_by_contributor_id": contributor_id,
            },
        )
        assert seeded_spec.status_code == 201

        created = await client.post(
            "/api/governance/change-requests",
            json={
                "request_type": "spec_update",
                "title": "Attempt risky spec update",
                "payload": {
                    "spec_id": "spec-reject",
                    "summary": "Risky summary update",
                    "updated_by_contributor_id": contributor_id,
                },
                "proposer_id": contributor_id,
                "proposer_type": "human",
            },
        )
        assert created.status_code == 201
        request_id = created.json()["id"]

        voted = await client.post(
            f"/api/governance/change-requests/{request_id}/votes",
            json={
                "voter_id": "machine-reviewer-1",
                "voter_type": "machine",
                "decision": "no",
                "rationale": "Insufficient evidence",
            },
        )
        assert voted.status_code == 200
        payload = voted.json()
        assert payload["status"] == "rejected"
        assert payload["rejections"] == 1
