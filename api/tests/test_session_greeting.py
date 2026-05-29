"""Session greeting — the SessionStart recognition of user + agent with memory.

The greeting logic is a script (scripts/session_greeting.py) wired into
arrival.py. These tests pin the pure assembly and the opt-in/auth gating with
an injected HTTP function, so no network is touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import session_greeting as sg  # noqa: E402


def test_compose_first_contact() -> None:
    line = sg.compose_greeting("urs", "claude-code", {"was_first_contact": True, "events": [
        {"type": "welcome"}, {"type": "session_start"},
    ]})
    assert "First session together, urs" in line
    assert "claude-code" in line


def test_compose_returning_counts_sessions() -> None:
    events = [
        {"type": "welcome"},
        {"type": "session_start"},
        {"type": "session_start"},
        {"type": "session_start"},
    ]
    line = sg.compose_greeting("urs", "claude-code", {"was_first_contact": False, "events": events})
    assert "Welcome back, urs" in line
    assert "session 3" in line


def test_compose_returning_surfaces_last_exchange() -> None:
    events = [
        {"type": "session_start"},
        {"type": "exchange", "summary": "first thing"},
        {"type": "session_start"},
        {"type": "exchange", "summary": "shipped the greeting"},
    ]
    line = sg.compose_greeting("urs", "claude-code", {"was_first_contact": False, "events": events})
    assert "shipped the greeting" in line  # the most recent exchange, not the first


def test_remembering_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    # No config file at the patched HOME → default True.
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    assert sg.remembering_enabled() is True


def test_remembering_env_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERENCE_REMEMBER_SESSIONS", "0")
    assert sg.remembering_enabled() is False


def test_greeting_lines_opted_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERENCE_REMEMBER_SESSIONS", "off")
    lines = sg.greeting_lines(http=lambda *a: (0, None))
    assert lines and "off" in lines[0].lower()


def test_greeting_lines_no_api_key_is_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg, "load_api_key", lambda: None)
    assert sg.greeting_lines(http=lambda *a: (0, None)) == []


def test_greeting_lines_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg, "load_api_key", lambda: "key-123")
    monkeypatch.setattr(sg, "api_base", lambda: "https://api.test")

    def fake_http(method, url, headers, body):
        if url.endswith("/api/identity/me"):
            assert headers.get("X-API-Key") == "key-123"
            return 200, {"contributor_id": "urs", "source": "api_key"}
        if url.endswith("/api/agents/bootstrap"):
            assert body["other_name"] == "urs"
            assert body["my_name"] == sg.AGENT_NAME
            return 200, {"was_first_contact": True, "events": [
                {"type": "welcome"}, {"type": "session_start"},
            ]}
        raise AssertionError(f"unexpected url {url}")

    lines = sg.greeting_lines(http=fake_http)
    assert len(lines) == 1
    assert "First session together, urs" in lines[0]


def test_greeting_lines_auth_fails_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg, "load_api_key", lambda: "bad-key")
    monkeypatch.setattr(sg, "api_base", lambda: "https://api.test")
    # Key present but 401 from /me → no fabrication, but say why and how to fix.
    lines = sg.greeting_lines(http=lambda m, u, h, b: (401, None))
    assert len(lines) == 1
    assert "isn't recognized" in lines[0]
    assert "coherence.api_key" in lines[0]
