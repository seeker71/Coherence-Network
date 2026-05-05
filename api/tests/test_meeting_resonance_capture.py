"""Meeting resonance capture flow tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _seed_concept(c: AsyncClient, cid: str) -> None:
    response = await c.post(
        "/api/graph/nodes",
        json={
            "id": cid,
            "type": "concept",
            "name": f"Concept {cid}",
            "description": "A concept with parts that meetings can resonate with.",
            "properties": {"domains": ["living-collective"]},
        },
    )
    assert response.status_code in (200, 201), response.text


@pytest.mark.asyncio
async def test_capture_meeting_resonance_for_people_and_agents() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        concept_id = _uid("lc-meeting-resonance")
        meeting_id = _uid("meeting")
        await _seed_concept(c, concept_id)

        create = await c.post(
            "/api/meetings/captures",
            json={
                "meeting_id": meeting_id,
                "title": "Concept attunement",
                "channel": "voice",
                "source": "api-test",
                "participants": [
                    {"id": "person:ana", "name": "Ana", "kind": "person"},
                    {"id": "agent:codex", "name": "Codex", "kind": "agent"},
                ],
                "concept_resonances": [
                    {
                        "participant_id": "person:ana",
                        "concept_id": concept_id,
                        "concept_part_id": "opening",
                        "concept_part_label": "Opening movement",
                        "resonance": "expansion",
                        "strength": 0.86,
                        "note": "Ana lit up around the first invitation.",
                    },
                    {
                        "participant_id": "agent:codex",
                        "concept_id": concept_id,
                        "concept_part_id": "api-callback",
                        "concept_part_label": "Recall interface",
                        "resonance": "implementation",
                        "strength": 0.91,
                        "note": "Codex connected the concept to queryable graph edges.",
                    },
                ],
            },
        )
        assert create.status_code == 201, create.text
        created = create.json()
        assert created["meeting"]["id"] == meeting_id
        assert {p["kind"] for p in created["participants"]} == {"person", "agent"}
        assert len(created["concept_resonances"]) == 2
        assert all(r["concept_part_node_id"] for r in created["concept_resonances"])

        recall = await c.get(
            "/api/meetings/resonance",
            params={"concept_id": concept_id},
        )
        assert recall.status_code == 200, recall.text
        body = recall.json()
        assert body["total"] == 2

        by_part = {item["concept_part"]["id"]: item for item in body["items"]}
        assert by_part["opening"]["participant"]["id"] == "person:ana"
        assert by_part["opening"]["participant"]["kind"] == "person"
        assert by_part["api-callback"]["participant"]["id"] == "agent:codex"
        assert by_part["api-callback"]["participant"]["kind"] == "agent"

        agent_only = await c.get(
            "/api/meetings/resonance",
            params={"concept_id": concept_id, "participant_kind": "agent"},
        )
        assert agent_only.status_code == 200, agent_only.text
        agent_body = agent_only.json()
        assert agent_body["total"] == 1
        assert agent_body["items"][0]["participant"]["id"] == "agent:codex"
        assert agent_body["items"][0]["concept_part"]["id"] == "api-callback"
        assert agent_body["summary"][0]["participant_id"] == "agent:codex"
