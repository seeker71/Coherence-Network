"""Session greeting — detect agent + user, greet with memory, across all agents.

The greeting logic is a script (scripts/session_greeting.py) wired into
arrival.py. These tests pin agent detection, the agent-independent user
resolution, the pure assembly, and opt-out gating — all with injected env /
HTTP, so no network or real environment is touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import session_greeting as sg  # noqa: E402


# --- agent detection: one row per known agent, plus generic + unknown --------


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"AI_AGENT": "claude-code_2-1-156_agent", "CLAUDECODE": "1"}, "claude-code"),
        ({"CLAUDECODE": "1"}, "claude-code"),
        ({"CODEX_HOME": "/x/codex"}, "codex"),
        ({"AI_AGENT": "codex_1-2-3"}, "codex"),
        ({"CURSOR_TRACE_ID": "abc"}, "cursor"),
        ({"GEMINI_CLI": "1"}, "gemini"),
        ({"AI_AGENT": "windsurf_9_agent"}, "windsurf"),  # generic AI_AGENT fallback
        ({}, sg.DEFAULT_AGENT),
    ],
)
def test_detect_agent(env, expected) -> None:
    assert sg.detect_agent(env) == expected


# --- user resolution: provider lookup primary, /me fallback, agent-free ------


def test_resolve_user_via_provider_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "keystore_identity", lambda: ("github", "urs-muff"))

    def http(method, url, headers, body):
        assert url.endswith("/api/identity/lookup/github/urs-muff")
        return 200, {"contributor_id": "milestone-agent"}

    assert sg.resolve_user(http, "https://api.test") == "milestone-agent"


def test_resolve_user_falls_back_to_me_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "keystore_identity", lambda: None)
    monkeypatch.setattr(sg, "load_api_key", lambda: "key-123")

    def http(method, url, headers, body):
        if url.endswith("/api/identity/me"):
            assert headers.get("X-API-Key") == "key-123"
            return 200, {"contributor_id": "urs"}
        raise AssertionError(f"unexpected {url}")

    assert sg.resolve_user(http, "https://api.test") == "urs"


def test_resolve_user_none_when_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "keystore_identity", lambda: None)
    monkeypatch.setattr(sg, "load_api_key", lambda: None)
    assert sg.resolve_user(lambda *a: (0, None), "https://api.test") is None


# --- greeting assembly (pure) ------------------------------------------------


def test_compose_first_contact() -> None:
    line = sg.compose_greeting("urs", "claude-code", {"was_first_contact": True, "events": [
        {"type": "welcome"}, {"type": "session_start"},
    ]})
    assert "First session together, urs" in line
    assert "claude-code" in line


def test_compose_returning_counts_sessions_and_names_agent() -> None:
    events = [{"type": "session_start"}] * 3
    line = sg.compose_greeting("urs", "codex", {"was_first_contact": False, "events": events})
    assert "Welcome back, urs" in line
    assert "session 3 with codex" in line


def test_compose_returning_surfaces_last_exchange() -> None:
    events = [
        {"type": "exchange", "summary": "first thing"},
        {"type": "session_start"},
        {"type": "exchange", "summary": "shipped the greeting"},
    ]
    line = sg.compose_greeting("urs", "claude-code", {"was_first_contact": False, "events": events})
    assert "shipped the greeting" in line  # the most recent, not the first


# --- opt-out gating ----------------------------------------------------------


def test_remembering_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    assert sg.remembering_enabled() is True


def test_remembering_env_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERENCE_REMEMBER_SESSIONS", "0")
    assert sg.remembering_enabled() is False


def test_greeting_lines_opted_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERENCE_REMEMBER_SESSIONS", "off")
    assert "off" in sg.greeting_lines(http=lambda *a: (0, None))[0].lower()


# --- end-to-end greeting line (env + http injected) --------------------------


def test_greeting_lines_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg, "keystore_identity", lambda: ("github", "urs-muff"))
    monkeypatch.setattr(sg.os, "environ", {"AI_AGENT": "claude-code_2_agent", "CLAUDECODE": "1"})

    def fake_http(method, url, headers, body):
        if url.endswith("/api/identity/lookup/github/urs-muff"):
            return 200, {"contributor_id": "urs"}
        if url.endswith("/api/agents/bootstrap"):
            assert body["my_name"] == "claude-code"  # agent detected, not hardcoded
            assert body["other_name"] == "urs"
            return 200, {"was_first_contact": True, "events": [
                {"type": "welcome"}, {"type": "session_start"},
            ]}
        raise AssertionError(f"unexpected url {url}")

    lines = sg.greeting_lines(http=fake_http)
    assert len(lines) == 1
    assert "First session together, urs" in lines[0]
    assert "claude-code" in lines[0]


def test_greeting_lines_quiet_when_no_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg, "keystore_identity", lambda: None)
    monkeypatch.setattr(sg, "load_api_key", lambda: None)
    assert sg.greeting_lines(http=lambda *a: (0, None)) == []
