from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import awareness_node_daemon as daemon  # noqa: E402


def test_load_profiles_contains_expected_agent_guidance() -> None:
    profiles = daemon.load_profiles(ROOT / "config" / "agent_profiles.json")

    assert {"codex", "claude", "grok"} <= set(profiles)
    assert profiles["codex"].agent_id == "codex"
    assert "heartbeat" in profiles["codex"].no_model_actions
    assert profiles["claude"].memory["persistent"] == "coherence-network"


def test_run_once_registers_heartbeats_announces_and_polls() -> None:
    calls: list[tuple[str, str, dict | None, dict | None]] = []

    def fake_request(method: str, path: str, *, body: dict | None = None, params: dict | None = None):
        calls.append((method, path, body, params))
        if method == "GET" and path.endswith("/messages"):
            return {"messages": [{"id": "msg_a", "text": "hello"}]}
        return {"ok": True}

    profile = daemon.AgentProfile(
        agent_id="codex",
        display_name="Codex",
        node_id="codex-node-local",
        providers=["codex"],
        voice="plain",
        memory={"temp": "thread", "persistent": "coherence-network", "static": "repo"},
        no_model_actions=["register", "heartbeat", "announce", "poll_messages"],
    )

    result = daemon.run_once(
        profile,
        api_base="https://example.test",
        request_json=fake_request,
        announce="Codex is online.",
        dry_run=False,
    )

    assert result["profile"] == "codex"
    assert result["messages"]["count"] == 1
    assert calls[0][0:2] == ("POST", "/api/federation/nodes")
    assert calls[1][0:2] == ("POST", "/api/federation/nodes/codex-node-local/heartbeat")
    assert calls[2][0:2] == ("POST", "/api/federation/nodes/codex-node-local/messages")
    assert calls[3][0:2] == ("GET", "/api/federation/nodes/codex-node-local/messages")
