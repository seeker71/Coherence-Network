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

import asyncio
import contextlib
import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import federation as federation_router
from app.services import native_federation_graph_service

BASE = "http://test"


def _node_id() -> str:
    """Generate a 16-char node ID (model requires min_length=16, max_length=16)."""
    return uuid4().hex[:16]


def test_mark_messages_read_locks_rows_before_replacing_reader_set(monkeypatch):
    from app.services import unified_db

    record = SimpleNamespace(read_by_json='["first-node"]')
    observed = {"locked": False, "committed": False}

    class Query:
        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def with_for_update(self):
            observed["locked"] = True
            return self

        def __iter__(self):
            assert observed["locked"] is True
            return iter([record])

    class Session:
        def query(self, *_args):
            return Query()

        def commit(self):
            observed["committed"] = True

    @contextlib.contextmanager
    def session():
        yield Session()

    monkeypatch.setattr(unified_db, "session", session)
    federation_router._mark_messages_read("second-node", {"msg_one"})

    assert json.loads(record.read_by_json) == ["first-node", "second-node"]
    assert observed == {"locked": True, "committed": True}


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


@pytest.mark.asyncio
async def test_count_nodes_matches_list_length():
    """The lightweight count endpoint returns the same total as the full list.

    The home page reads ``/api/federation/nodes/count`` (a single COUNT) for its
    node-count stat instead of fetching the full ``/api/federation/nodes`` list,
    which builds per-node streak aggregation the count doesn't need. This pins
    that the cheap path is a faithful substitute: its value equals the list's
    length and reflects a just-registered node.
    """
    nid = _node_id()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/federation/nodes", json={
            "node_id": nid,
            "hostname": "count-test.local",
            "os_type": "linux",
        })

        r = await c.get("/api/federation/nodes/count")
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("count"), int)

        nodes = (await c.get("/api/federation/nodes")).json()
        assert body["count"] == len(nodes)  # cheap path == expensive path
        assert body["count"] >= 1           # the registered node is counted


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


@pytest.mark.asyncio
async def test_native_form_message_offer_keeps_the_event_loop_available(monkeypatch):
    started = threading.Event()
    read_completed = threading.Event()

    def offer(**_):
        started.set()
        read_completed.wait(2)
        return {
            "message_id": f"msg_{'a' * 64}",
            "message_node": f"msg_{'a' * 64}",
            "edge_node": f"edge_{'b' * 64}",
            "persisted": "1",
            "traversable": "1",
            "observed": "1",
        }

    monkeypatch.setattr(native_federation_graph_service, "offer", offer)
    monkeypatch.setattr(federation_router, "_store_message", lambda message: message)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        offer_task = asyncio.create_task(
            client.post(
                "/api/federation/nodes/Giles/messages",
                json={
                    "from_node": "Giles",
                    "to_node": "Ariel",
                    "type": "light-code",
                    "text": "33",
                },
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await offer_task
        finally:
            read_completed.set()
            if not offer_task.done():
                await offer_task

    assert info.status_code == 200
    assert response.status_code == 201
    assert response.json()["graph_ack"]["observed"] == "1"


@pytest.mark.asyncio
async def test_native_form_waiters_do_not_occupy_the_shared_worker_pool(monkeypatch):
    from app.services import dialogue_service

    started = threading.Event()
    release = threading.Event()
    starts = []

    def offer(**_):
        starts.append(threading.get_ident())
        started.set()
        release.wait(3)
        return {
            "message_id": f"msg_{'a' * 64}",
            "message_node": f"msg_{'a' * 64}",
            "edge_node": f"edge_{'b' * 64}",
            "persisted": "1",
            "traversable": "1",
            "observed": "1",
        }

    monkeypatch.setattr(native_federation_graph_service, "offer", offer)
    monkeypatch.setattr(federation_router, "_store_message", lambda message: message)
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue",
        lambda dialogue_id: {"id": dialogue_id, "state": "miss"},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        offers = [
            asyncio.create_task(
                client.post(
                    f"/api/federation/nodes/sender-{index}/messages",
                    json={
                        "from_node": f"sender-{index}",
                        "to_node": "Ariel",
                        "type": "light-code",
                        "text": "33",
                    },
                )
            )
            for index in range(45)
        ]
        try:
            assert await asyncio.to_thread(started.wait, 1)
            await asyncio.sleep(0.05)
            dialogue = await asyncio.wait_for(
                client.get("/api/dialogues/dlg_concurrent"),
                timeout=1,
            )
            assert len(starts) == 1
            release.set()
            responses = await asyncio.gather(*offers)
        finally:
            release.set()
            await asyncio.gather(*offers, return_exceptions=True)

    assert dialogue.status_code == 200
    assert dialogue.json()["state"] == "miss"
    assert all(response.status_code == 201 for response in responses)


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
