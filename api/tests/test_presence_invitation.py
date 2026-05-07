"""Acceptance tests for the graph-backed Presence invitation surface."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.asyncio
async def test_invite_presence_creates_graph_backed_presence():
    payload = {
        "name": "Mira's Healing Garden",
        "kind": "place",
        "story": "A garden for herbal integration and quiet circles.",
        "steward": "Mira",
        "location": "Ubud",
        "offerings": ["herbal integration"],
        "needs": ["shade cloth"],
        "ways_to_connect": ["hello@example.org"],
        "visibility": "public",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        created = await c.post("/api/presences/invite", json=payload)
        assert created.status_code == 201, created.text
        body = created.json()
        presence = body["presence"]

        assert body["created"] is True
        assert presence["id"] == "presence:place:miras-healing-garden"
        assert presence["kind"] == "place"
        assert presence["type"] == "scene"
        assert presence["name"] == payload["name"]
        assert presence["story"] == payload["story"]
        assert presence["steward"] == "Mira"
        assert presence["offerings"] == ["herbal integration"]
        assert presence["needs"] == ["shade cloth"]
        assert presence["visibility"] == "public"
        assert presence["internal_path"] == "/people/presence%3Aplace%3Amiras-healing-garden"
        assert presence["external_path"] == "/people/presence%3Aplace%3Amiras-healing-garden"

        read_back = await c.get(f"/api/presences/{presence['id']}")
        assert read_back.status_code == 200
        assert read_back.json()["presence"] == presence

        listed = await c.get("/api/presences?kind=place")
        assert listed.status_code == 200
        listed_body = listed.json()
        assert listed_body["count"] == 1
        assert listed_body["items"][0]["id"] == presence["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "expected_type"),
    [
        ("person", "contributor"),
        ("event", "event"),
        ("service", "service"),
        ("plant", "asset"),
        ("animal", "asset"),
        ("thing", "asset"),
        ("offering", "service"),
        ("need", "story"),
        ("community", "community"),
        ("practice", "practice"),
    ],
)
async def test_invited_presence_kind_mapping_keeps_living_kind(kind: str, expected_type: str):
    payload = {
        "name": f"{kind.title()} Presence",
        "kind": kind,
        "story": f"A {kind} that can be met inside the network.",
        "steward": "Test Steward",
        "visibility": "network",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        created = await c.post("/api/presences/invite", json=payload)
        assert created.status_code == 201, created.text
        presence = created.json()["presence"]

        assert presence["kind"] == kind
        assert presence["type"] == expected_type
        assert presence["visibility"] == "network"


@pytest.mark.asyncio
async def test_invite_presence_rejects_unknown_kind():
    payload = {
        "name": "Unknown Shape",
        "kind": "spaceship",
        "story": "This kind is not in the invitation vocabulary.",
        "steward": "Test Steward",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        rejected = await c.post("/api/presences/invite", json=payload)
        assert rejected.status_code == 422
        assert "Unsupported presence kind" in rejected.json()["detail"]
