#!/usr/bin/env python3
"""Session greeting — detect the agent and the user, greet with memory.

The real-world use case on top of the agent-relationship runtime: when a
session begins, work out *which agent* is running and *who the human is*, greet
with memory of prior sessions, and (when remembering is on) record the meeting
so the next session continues the thread.

Composed into the SessionStart layer by scripts/arrival.py — a peer of the
orientation and wellness layers.

Detection is agent-agnostic, so the same greeting works across all known
agents (Claude Code, Codex, Cursor, Gemini, …):

- Agent: read from the environment — the generic `AI_AGENT` signal first, then
  per-agent markers and homes. Adding an agent is one row in KNOWN_AGENTS.
- User: the human's verified identity travels in the keystore as
  (provider, provider_id) regardless of agent. We resolve it to a contributor
  via the public GET /api/identity/lookup/{provider}/{provider_id} — no key
  required. A coherence API key, when present, is a stronger fallback (/me).

Remembering is on by default. Opt out anytime:
  - set "remember_sessions": false in ~/.coherence-network/config.json, or
  - export COHERENCE_REMEMBER_SESSIONS=0

This module never raises into the hook: any failure (offline, no identity, API
down) degrades to a quiet, non-blocking line so session start is never broken.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

HOME = Path(os.path.expanduser("~"))
KEYS_PATH = HOME / ".coherence-network" / "keys.json"
CONFIG_PATH = HOME / ".coherence-network" / "config.json"

DEFAULT_API_BASE = "https://api.coherencycoin.com"
DEFAULT_AGENT = "unknown-agent"
HTTP_TIMEOUT = 4.0

_OFF_VALUES = {"0", "false", "no", "off", ""}

# Known session agents, each detected by a set of environment markers.
# A marker "VAR^prefix" matches when env[VAR] starts with prefix (case-insensitive);
# a bare "VAR" matches when that variable is set to anything truthy.
# Adding an agent is one row — the detector is the engine, agents are data.
KNOWN_AGENTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("claude-code", ("AI_AGENT^claude", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")),
    ("codex", ("AI_AGENT^codex", "CODEX_HOME", "CODEX_SANDBOX", "CODEX_THREAD_ID")),
    ("cursor", ("AI_AGENT^cursor", "CURSOR_TRACE_ID", "CURSOR_AGENT", "CURSOR_SESSION_ID")),
    ("gemini", ("AI_AGENT^gemini", "GEMINI_CLI", "GEMINI_SESSION", "GEMINICODE")),
)

# An HTTP call returns (status_code, parsed_json_or_None). Injectable for tests.
HttpFn = Callable[[str, str, Dict[str, str], Optional[dict]], "tuple[int, Optional[dict]]"]


# ---------------------------------------------------------------------------
# Local config / credentials
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def api_base() -> str:
    """Where session memory lives — the production substrate by default.

    Honors an explicit override (env or a dedicated config key) but does not
    inherit `hub_url`, which addresses the local/federation hub, not the
    durable relationship store.
    """
    override = os.environ.get("COHERENCE_API_BASE") or _read_json(CONFIG_PATH).get(
        "session_api_base"
    )
    return (override or DEFAULT_API_BASE).rstrip("/")


def remembering_enabled() -> bool:
    """Default on. Off only when explicitly opted out (config key or env)."""
    env = os.environ.get("COHERENCE_REMEMBER_SESSIONS")
    if env is not None:
        return env.strip().lower() not in _OFF_VALUES
    return bool(_read_json(CONFIG_PATH).get("remember_sessions", True))


def load_api_key() -> Optional[str]:
    """The coherence contributor key, if present (used as a stronger fallback).

    Order: env override, keystore `coherence.api_key`, top-level `api_key`.
    """
    env = os.environ.get("COHERENCE_API_KEY")
    if env and env.strip():
        return env.strip()
    keys = _read_json(KEYS_PATH)
    coherence = keys.get("coherence")
    candidates = []
    if isinstance(coherence, dict):
        candidates.append(coherence.get("api_key"))
    candidates.append(keys.get("api_key"))
    for key in candidates:
        if isinstance(key, str) and key.strip():
            return key.strip()
    return None


def keystore_identity() -> Optional[Tuple[str, str]]:
    """The human's verified (provider, provider_id) from the keystore.

    This is agent-independent — every agent on this machine reads the same
    identity. It is what lets us look the user up without an API key.
    """
    keys = _read_json(KEYS_PATH)
    provider, provider_id = keys.get("provider"), keys.get("provider_id")
    if isinstance(provider, str) and provider and isinstance(provider_id, str) and provider_id:
        return provider, provider_id
    return None


# ---------------------------------------------------------------------------
# Agent detection (pure — unit tested)
# ---------------------------------------------------------------------------


def _marker_matches(marker: str, env: Mapping[str, str]) -> bool:
    if "^" in marker:
        var, prefix = marker.split("^", 1)
        return env.get(var, "").lower().startswith(prefix.lower())
    return bool(env.get(marker))


def detect_agent(env: Mapping[str, str]) -> str:
    """Name the agent running this session, across all known agents.

    Explicit markers win; an unrecognized agent that still sets AI_AGENT is
    named from its first segment (e.g. "claude-code_2-1-156_agent" →
    "claude-code"); otherwise DEFAULT_AGENT.
    """
    for name, markers in KNOWN_AGENTS:
        if any(_marker_matches(m, env) for m in markers):
            return name
    ai_agent = env.get("AI_AGENT", "").strip()
    if ai_agent:
        return ai_agent.split("_", 1)[0]
    return DEFAULT_AGENT


# ---------------------------------------------------------------------------
# HTTP (stdlib, short timeout, never raises out)
# ---------------------------------------------------------------------------


def _http_json(
    method: str, url: str, headers: Dict[str, str], body: Optional[dict]
) -> "tuple[int, Optional[dict]]":
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    # A real User-Agent: the edge (Cloudflare) blocks the default Python-urllib
    # agent with 403 before the request ever reaches the API.
    req.add_header("User-Agent", "coherence-session-greeting/1.0")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


# ---------------------------------------------------------------------------
# User resolution + relationship
# ---------------------------------------------------------------------------


def resolve_user(http: HttpFn, base: str) -> Optional[str]:
    """The contributor id for the human at this machine, or None.

    Primary path (agent-independent, no key): the keystore (provider,
    provider_id) resolved via the public identity lookup. Stronger fallback:
    the coherence API key resolved via /me, when a key is present.
    """
    ident = keystore_identity()
    if ident:
        provider, provider_id = ident
        status, body = http(
            "GET", f"{base}/api/identity/lookup/{provider}/{provider_id}", {}, None
        )
        if status == 200 and isinstance(body, dict):
            cid = body.get("contributor_id")
            if isinstance(cid, str) and cid:
                return cid

    api_key = load_api_key()
    if api_key:
        status, body = http("GET", f"{base}/api/identity/me", {"X-API-Key": api_key}, None)
        if status == 200 and isinstance(body, dict):
            cid = body.get("contributor_id")
            if isinstance(cid, str) and cid:
                return cid

    return None


def bootstrap_meeting(
    http: HttpFn, base: str, agent: str, user: str
) -> Optional[Dict[str, Any]]:
    payload = {
        "my_name": agent,
        "other_name": user,
        "my_description": f"{agent} — an agent session tending the Coherence Network.",
        "welcome_guidance": (
            "First meeting. From here I remember our sessions and continue the "
            "thread next time. Opt out anytime via remember_sessions in "
            "~/.coherence-network/config.json."
        ),
    }
    status, body = http("POST", f"{base}/api/agents/bootstrap", {}, payload)
    return body if status == 200 and isinstance(body, dict) else None


# ---------------------------------------------------------------------------
# Greeting assembly (pure — unit tested without network)
# ---------------------------------------------------------------------------


def compose_greeting(user: str, agent: str, result: Dict[str, Any]) -> str:
    events = result.get("events") or []
    sessions = sum(1 for e in events if e.get("type") == "session_start")
    last_exchange = next(
        (e.get("summary") for e in reversed(events) if e.get("type") == "exchange"),
        None,
    )

    if result.get("was_first_contact"):
        line = (
            f"🌱 First session together, {user}. I'm {agent} — from here I'll "
            f"remember our work and continue the thread next time."
        )
    else:
        nth = f"session {sessions}" if sessions else "another session"
        line = f"🌿 Welcome back, {user}. This is {nth} with {agent}."
        if last_exchange:
            line += f" Last we noted: {last_exchange}"

    return line


def greeting_lines(http: HttpFn = _http_json) -> list[str]:
    """The lines to print at session start. Empty list = nothing to say."""
    if not remembering_enabled():
        return [
            "🔕 Session memory is off (remember_sessions). "
            "Re-enable in ~/.coherence-network/config.json."
        ]

    base = api_base()
    agent = detect_agent(os.environ)
    user = resolve_user(http, base)
    if not user:
        return []  # no resolvable identity — do not fabricate a user, stay quiet

    result = bootstrap_meeting(http, base, agent, user)
    if not result:
        return [f"🌿 Hello again, {user}. (Session memory unreachable right now.)"]

    return [compose_greeting(user, agent, result)]


def main() -> int:
    try:
        for line in greeting_lines():
            print(line)
    except Exception:
        pass  # a greeting must never break session start
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
