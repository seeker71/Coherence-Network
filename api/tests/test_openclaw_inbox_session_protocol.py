"""Tests for OpenClaw skill session protocol (inbox first) and federation inbox API.

Spec: specs/149-openclaw-inbox-session-protocol.md
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "coherence-network" / "SKILL.md"


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def _register_node(client: TestClient, node_id: str, hostname: str) -> None:
    resp = client.post(
        "/api/federation/nodes",
        json={
            "node_id": node_id,
            "hostname": hostname,
            "os_type": "linux",
            "providers": ["openai"],
            "capabilities": {},
        },
    )
    assert resp.status_code == 201, resp.text


def test_skill_md_openclaw_session_lists_inbox_before_status():
    """Published skill must tell OpenClaw to run `cc inbox` before `cc status` at session start."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "## OpenClaw session protocol (bidirectional messaging)" in text

    start = text.index("## OpenClaw session protocol (bidirectional messaging)")
    end = text.index("## Two ways to use it", start)
    section = text[start:end]
    assert "**Start of every session (in order):**" in section
    inbox_pos = section.find("`cc inbox`")
    status_pos = section.find("`cc status`")
    assert inbox_pos != -1, "Skill must document `cc inbox` in the session-start list"
    assert status_pos != -1, "Skill must document `cc status` in the session-start list"
    assert inbox_pos < status_pos, "`cc inbox` must be ordered before `cc status`"

    assert "GET /api/federation/nodes/{node_id}/messages" in text
    assert "unread_only=false" in text


def test_federation_inbox_delivers_message_from_peer(client):
    """POST from sender → GET recipient matches `cc inbox` data path (API side)."""
    node_a = "a1b2c3d4e5f67001"
    node_b = "b2c3d4e5f67001a2"
    _register_node(client, node_a, "recv.example.internal")
    _register_node(client, node_b, "send.example.internal")

    body = {
        "from_node": node_b,
        "to_node": node_a,
        "type": "text",
        "text": "qa-openclaw-inbox-149",
        "payload": {},
    }
    post = client.post(f"/api/federation/nodes/{node_b}/messages", json=body)
    assert post.status_code == 201, post.text
    created = post.json()
    assert created["id"].startswith("msg_")
    assert created["text"] == "qa-openclaw-inbox-149"

    get1 = client.get(f"/api/federation/nodes/{node_a}/messages?unread_only=true&limit=20")
    assert get1.status_code == 200
    data1 = get1.json()
    assert data1["count"] >= 1
    texts = [m["text"] for m in data1["messages"]]
    assert "qa-openclaw-inbox-149" in texts

    # Second unread-only fetch: messages were marked read by the first GET
    get2 = client.get(f"/api/federation/nodes/{node_a}/messages?unread_only=true&limit=20")
    assert get2.status_code == 200
    data2 = get2.json()
    assert data2["count"] == 0


def test_post_message_missing_from_node_is_422(client):
    _register_node(client, "c1d2e3f405060708", "n1.example")
    _register_node(client, "d2e3f40506070809", "n2.example")
    bad = client.post(
        "/api/federation/nodes/d2e3f40506070809/messages",
        json={
            "to_node": "c1d2e3f405060708",
            "type": "text",
            "text": "missing-from-node",
            "payload": {},
        },
    )
    assert bad.status_code == 422


def test_get_inbox_for_unregistered_node_returns_empty_messages(client):
    """No crash when querying inbox for a node that never registered."""
    r = client.get("/api/federation/nodes/zzzzzzzzzzzzzzzz/messages?unread_only=true&limit=20")
    assert r.status_code == 200
    data = r.json()
    assert data["messages"] == []
    assert data["count"] == 0
