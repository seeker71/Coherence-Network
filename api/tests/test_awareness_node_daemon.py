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
        wake_reason="test wake",
        dry_run=False,
    )

    assert result["profile"] == "codex"
    assert result["identity"]["wake_reason"] == "test wake"
    assert result["identity"]["origin_profile"]["agent_id"] == "codex"
    assert result["identity"]["life_state"]["dynamic"] is True
    assert result["live_data"]["wake_reason"] == "test wake"
    assert result["messages"]["count"] == 1
    assert calls[0][0:2] == ("POST", "/api/federation/nodes")
    assert calls[1][0:2] == ("POST", "/api/federation/nodes/codex-node-local/heartbeat")
    assert calls[2][0:2] == ("POST", "/api/federation/nodes/codex-node-local/messages")
    assert calls[3][0:2] == ("GET", "/api/federation/nodes/codex-node-local/messages")


def test_each_profile_can_identify_where_when_and_why_it_woke() -> None:
    profiles = daemon.load_profiles(ROOT / "config" / "agent_profiles.json")

    for profile in profiles.values():
        card = daemon.build_identity_card(
            profile,
            api_base="https://api.example.test",
            wake_reason="asked to identify itself",
            woke_at="2026-04-27T00:00:00Z",
            repo_root=ROOT,
        )
        text = daemon.render_identity_text(card)

        assert card["who"]["agent_id"] == profile.agent_id
        assert card["origin_profile"]["agent_id"] == profile.agent_id
        assert card["life_state"]["kind"] == "runtime_presence"
        assert card["life_state"]["model_calls"] == 0
        assert card["where"]["node_id"] == profile.node_id[:16]
        assert card["where"]["api_base"] == "https://api.example.test"
        assert card["woke_at"] == "2026-04-27T00:00:00Z"
        assert card["wake_reason"] == "asked to identify itself"
        assert card["memory"]["persistent"] == "coherence-network"
        assert profile.display_name in text
        assert "asked to identify itself" in text
        assert "profile is origin" in text
