from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import morning_coherence_brief as brief  # noqa: E402


def test_collect_brief_uses_nodes_and_messages() -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_fetch(path: str, params: dict | None = None):
        calls.append((path, params))
        if path == "/api/health":
            return {"status": "ok", "version": "1.0.0"}
        if path == "/api/federation/nodes":
            return [
                {
                    "node_id": "node-a",
                    "hostname": "Codex",
                    "status": "online",
                    "providers": ["codex"],
                    "last_seen_at": "2026-04-27T00:00:00Z",
                }
            ]
        if path == "/api/federation/nodes/node-a/messages":
            return {
                "messages": [
                    {
                        "timestamp": "2026-04-27T00:01:00Z",
                        "from_node": "node-b",
                        "type": "text",
                        "text": "I am here.",
                    }
                ]
            }
        raise AssertionError(path)

    data = brief.collect_brief(fetch=fake_fetch)

    assert data["health"]["status"] == "ok"
    assert data["node_ids_checked"] == ["node-a"]
    assert data["messages_by_node"]["node-a"][0]["text"] == "I am here."
    assert calls == [
        ("/api/health", None),
        ("/api/federation/nodes", None),
        ("/api/federation/nodes/node-a/messages", {"unread_only": "false", "limit": 20}),
    ]


def test_render_text_includes_real_message_text() -> None:
    text = brief.render_text(
        {
            "generated_at": "2026-04-27T00:00:00Z",
            "health": {"status": "ok", "version": "1.0.0"},
            "nodes": [
                {
                    "node_id": "node-a",
                    "hostname": "Codex",
                    "status": "online",
                    "providers": ["codex"],
                    "last_seen_at": "2026-04-27T00:00:00Z",
                }
            ],
            "messages_by_node": {
                "node-a": [
                    {
                        "timestamp": "2026-04-27T00:01:00Z",
                        "from_node": "node-b",
                        "type": "text",
                        "text": "I am here.",
                    }
                ]
            },
            "path": {
                "worktree": "/tmp/worktree",
                "branch": "codex/example",
                "collector": "scripts/morning_coherence_brief.py",
                "mcp_spec": "specs/mcp-awareness-streaming.md",
            },
        }
    )

    assert "COHERENCE MORNING BRIEF" in text
    assert "Codex id=node-a status=online providers=codex" in text
    assert "I am here." in text
    assert "scripts/morning_coherence_brief.py" in text
