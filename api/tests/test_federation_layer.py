"""Acceptance tests for spec: federation-network-layer (idea: federation-and-nodes).

Covers done_when criteria:
  - POST /api/federation/nodes registers a node
  - POST /api/federation/nodes/{id}/heartbeat updates status
  - GET /api/federation/nodes lists nodes
  - GET /api/federation/strategies returns list
  - POST /api/federation/nodes/{id}/messages sends targeted message
  - POST /api/federation/broadcast sends to all nodes
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _node_id() -> str:
    """Generate a 16-char node ID (model requires min_length=16, max_length=16)."""
    return uuid4().hex[:16]


# ---------------------------------------------------------------------------
# 1. POST /api/federation/nodes registers a node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_node():
    """Node registration returns 201 with node_id and status."""
    nid = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "test-machine.local",
            "os_type": "linux",
            "providers": ["openai"],
            "capabilities": {"models": ["gpt-4"]},
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["node_id"] == nid
        assert body["status"] == "online"
        assert "registered_at" in body


@pytest.mark.asyncio
async def test_register_node_duplicate_returns_200():
    """Re-registering an existing node returns 200 (update)."""
    nid = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r1 = await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "dupe.local",
            "os_type": "macos",
        })
        assert r1.status_code == 201

        r2 = await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "dupe.local",
            "os_type": "macos",
        })
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# 2. POST /api/federation/nodes/{id}/heartbeat updates status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heartbeat_updates_status():
    """Heartbeat refreshes node liveness and returns updated info."""
    nid = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Register first
        await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "hb-test.local",
            "os_type": "linux",
        })

        r = await c.post(f"/api/federation/nodes/{nid}/heartbeat", json={
            "status": "online",
            "git_sha": "abc1234",
            "system_metrics": {"cpu_pct": 42.0, "mem_pct": 60.0},
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["node_id"] == nid
        assert "last_seen_at" in body


@pytest.mark.asyncio
async def test_heartbeat_unknown_node_returns_404():
    """Heartbeat for an unregistered node returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/nodes/unknown_node_xxxx/heartbeat", json={
            "status": "online",
        })
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3. GET /api/federation/nodes lists nodes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_nodes():
    """Listing nodes returns an array including registered nodes."""
    nid = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "list-test.local",
            "os_type": "linux",
        })

        r = await c.get("/api/federation/nodes")
        assert r.status_code == 200, r.text
        nodes = r.json()
        assert isinstance(nodes, list)
        node_ids = [n["node_id"] for n in nodes]
        assert nid in node_ids


# ---------------------------------------------------------------------------
# 4. GET /api/federation/strategies returns list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strategies_returns_list():
    """Strategies endpoint returns a paginated list structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/federation/strategies")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "strategies" in body
        assert isinstance(body["strategies"], list)
        assert "total" in body


# ---------------------------------------------------------------------------
# 5. POST /api/federation/nodes/{id}/messages sends targeted message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_node_message():
    """Sending a message from a node returns 201 with message data."""
    sender = _node_id()
    target = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Register both nodes
        await c.post("/api/federation/nodes", json={
            "node_id": sender,
            "hostname": "sender.local",
            "os_type": "linux",
        })
        await c.post("/api/federation/nodes", json={
            "node_id": target,
            "hostname": "target.local",
            "os_type": "linux",
        })

        r = await c.post(f"/api/federation/nodes/{sender}/messages", json={
            "from_node": sender,
            "to_node": target,
            "type": "text",
            "text": "Hello from federation test",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["from_node"] == sender
        assert body["to_node"] == target
        assert body["text"] == "Hello from federation test"
        assert "id" in body
        assert "timestamp" in body


# ---------------------------------------------------------------------------
# 6. POST /api/federation/broadcast sends to all nodes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_message():
    """Broadcasting a message returns 201 with to_node=null."""
    sender = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/federation/nodes", json={
            "node_id": sender,
            "hostname": "broadcast.local",
            "os_type": "linux",
        })

        r = await c.post("/api/federation/broadcast", json={
            "from_node": sender,
            "type": "status_request",
            "text": "Status check broadcast",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["from_node"] == sender
        assert body["to_node"] is None
        assert body["text"] == "Status check broadcast"
