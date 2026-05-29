"""Session greeting — detect agent + human, greet with memory, across all agents.

The greeting logic is a script (scripts/session_greeting.py) wired into
arrival.py. These tests pin agent detection across the roster, the human
detection cascade (git config / keystore / env), the contributor-or-email
resolution, the pure assembly, and opt-out gating — all with injected env /
git / HTTP, so no network or real environment is touched.
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
        ({"AI_AGENT": "grok_4_agent"}, "grok"),
        ({"OPENCODE_SESSION": "x"}, "opencode"),
        ({"AI_AGENT": "windsurf_9_agent"}, "windsurf"),  # generic AI_AGENT fallback
        ({}, sg.DEFAULT_AGENT),
    ],
)
def test_detect_agent(env, expected) -> None:
    assert sg.detect_agent(env) == expected


# --- human detection cascade: git → keystore → env --------------------------


def test_detect_human_prefers_git() -> None:
    git = {"user.name": "Urs Muff", "user.email": "urs@Example.COM"}.get
    human = sg.detect_human({}, git=git)
    assert human == {
        "name": "Urs Muff",
        "email": "urs@example.com",  # normalized
        "provider": "email",
        "provider_id": "urs@example.com",
    }


def test_detect_human_falls_back_to_keystore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "keystore_identity", lambda: ("github", "urs-muff"))
    human = sg.detect_human({}, git=lambda k: None)
    assert human["provider"] == "github"
    assert human["provider_id"] == "urs-muff"


def test_detect_human_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "keystore_identity", lambda: None)
    human = sg.detect_human({"GIT_AUTHOR_EMAIL": "a@b.io", "GIT_AUTHOR_NAME": "A B"}, git=lambda k: None)
    assert human["email"] == "a@b.io"
    assert human["name"] == "A B"


def test_detect_human_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "keystore_identity", lambda: None)
    assert sg.detect_human({}, git=lambda k: None) is None


# --- user resolution: contributor when linked, else email; display = name ----


def test_resolve_user_links_contributor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sg, "detect_human",
        lambda env: {"name": "Urs", "email": "u@x.io", "provider": "email", "provider_id": "u@x.io"},
    )

    def http(method, url, headers, body):
        assert url.endswith("/api/identity/lookup/email/u@x.io")
        return 200, {"contributor_id": "urs-contrib"}

    key, display = sg.resolve_user(http, "https://api.test")
    assert key == "urs-contrib"  # keyed on the resolved contributor
    assert display == "Urs"      # greeted by the human name


def test_resolve_user_unlinked_keys_on_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sg, "detect_human",
        lambda env: {"name": "Urs", "email": "u@x.io", "provider": "email", "provider_id": "u@x.io"},
    )
    # 404 from lookup → not linked → remember by email, still greet by name.
    key, display = sg.resolve_user(lambda m, u, h, b: (404, None), "https://api.test")
    assert key == "u@x.io"
    assert display == "Urs"


def test_resolve_user_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "detect_human", lambda env: None)
    monkeypatch.setattr(sg, "load_api_key", lambda: None)
    assert sg.resolve_user(lambda *a: (0, None), "https://api.test") is None


# --- greeting assembly (pure) ------------------------------------------------


def test_compose_first_contact() -> None:
    line = sg.compose_greeting("Urs", "claude-code", {"was_first_contact": True, "events": [
        {"type": "welcome"}, {"type": "session_start"},
    ]})
    assert "First session together, Urs" in line
    assert "claude-code" in line


def test_compose_returning_counts_sessions_and_names_agent() -> None:
    events = [{"type": "session_start"}] * 3
    line = sg.compose_greeting("Urs", "codex", {"was_first_contact": False, "events": events})
    assert "Welcome back, Urs" in line
    assert "session 3 with codex" in line


def test_compose_returning_surfaces_last_exchange() -> None:
    events = [
        {"type": "exchange", "summary": "first thing"},
        {"type": "session_start"},
        {"type": "exchange", "summary": "shipped the greeting"},
    ]
    line = sg.compose_greeting("Urs", "claude-code", {"was_first_contact": False, "events": events})
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


# --- end-to-end greeting line (env + git + http injected) --------------------


def test_greeting_lines_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg.os, "environ", {"AI_AGENT": "grok_4_agent"})
    monkeypatch.setattr(
        sg, "detect_human",
        lambda env: {"name": "Urs", "email": "u@x.io", "provider": "email", "provider_id": "u@x.io"},
    )

    def fake_http(method, url, headers, body):
        if "/api/identity/lookup/" in url:
            return 404, None  # unlinked → key on email
        if url.endswith("/api/agents/bootstrap"):
            assert body["my_name"] == "grok"      # agent detected
            assert body["other_name"] == "u@x.io"  # keyed on email
            return 200, {"was_first_contact": True, "events": [
                {"type": "welcome"}, {"type": "session_start"},
            ]}
        raise AssertionError(f"unexpected url {url}")

    lines = sg.greeting_lines(http=fake_http)
    assert len(lines) == 1
    assert "First session together, Urs" in lines[0]
    assert "grok" in lines[0]


def test_greeting_lines_quiet_when_no_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERENCE_REMEMBER_SESSIONS", raising=False)
    monkeypatch.setattr(sg, "CONFIG_PATH", Path("/nonexistent/config.json"))
    monkeypatch.setattr(sg, "detect_human", lambda env: None)
    monkeypatch.setattr(sg, "load_api_key", lambda: None)
    assert sg.greeting_lines(http=lambda *a: (0, None)) == []
