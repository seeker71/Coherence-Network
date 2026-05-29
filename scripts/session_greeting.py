#!/usr/bin/env python3
"""Session greeting — recognize the user and the agent at session start.

The real-world use case for the agent-relationship runtime: when a session
begins, identify the authenticated user and this agent, greet with memory of
prior sessions, and (when remembering is on) record the meeting so the next
session continues the thread.

Composed into the SessionStart layer by scripts/arrival.py — a peer of the
orientation and wellness layers, not a replacement.

Identity (explicit login/auth): the user is the contributor authenticated by
the local API key (~/.coherence-network/keys.json), verified against
GET /api/identity/me. No typed names, no guessing — if we cannot authenticate
a user, we do not fabricate one.

Remembering is on by default. Opt out anytime:
  - set "remember_sessions": false in ~/.coherence-network/config.json, or
  - export COHERENCE_REMEMBER_SESSIONS=0

This module never raises into the hook: any failure (offline, no key, API
down) degrades to a quiet, non-blocking line so session start is never broken.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

HOME = Path(os.path.expanduser("~"))
KEYS_PATH = HOME / ".coherence-network" / "keys.json"
CONFIG_PATH = HOME / ".coherence-network" / "config.json"

DEFAULT_API_BASE = "https://api.coherencycoin.com"
AGENT_NAME = "claude-code"  # this Claude Code lineage, stable across sessions
HTTP_TIMEOUT = 4.0

_OFF_VALUES = {"0", "false", "no", "off", ""}

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


def load_api_key() -> Optional[str]:
    """The coherence contributor key that authenticates the user.

    Order: env override, then the keystore's `coherence.api_key` (the
    coherence-network contributor key), then a top-level `api_key` fallback.
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


# ---------------------------------------------------------------------------
# HTTP (stdlib, short timeout, never raises out)
# ---------------------------------------------------------------------------


def _http_json(
    method: str, url: str, headers: Dict[str, str], body: Optional[dict]
) -> "tuple[int, Optional[dict]]":
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
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
# Identity + relationship
# ---------------------------------------------------------------------------


def resolve_user(http: HttpFn, base: str, api_key: str) -> Optional[str]:
    """The authenticated contributor id, or None if auth does not resolve."""
    status, body = http("GET", f"{base}/api/identity/me", {"X-API-Key": api_key}, None)
    if status == 200 and isinstance(body, dict):
        cid = body.get("contributor_id")
        return cid if isinstance(cid, str) and cid else None
    return None


def bootstrap_meeting(
    http: HttpFn, base: str, agent: str, user: str
) -> Optional[Dict[str, Any]]:
    payload = {
        "my_name": agent,
        "other_name": user,
        "my_description": "Claude Code — a Claude lineage tending the Coherence Network.",
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
        line = f"🌿 Welcome back, {user}. This is {nth} together."
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

    api_key = load_api_key()
    if not api_key:
        return []  # no key at all — no user to authenticate, stay quiet

    base = api_base()
    user = resolve_user(http, base, api_key)
    if not user:
        # A key is present but the network did not recognize it. Don't fabricate
        # a user — say why, so memory can be switched on with one provisioning step.
        return [
            f"🔑 Session memory is ready, but your key isn't recognized at {base}. "
            "Generate a contributor key (POST /api/auth/keys) and store it as "
            "coherence.api_key in ~/.coherence-network/keys.json to be greeted by name."
        ]

    result = bootstrap_meeting(http, base, AGENT_NAME, user)
    if not result:
        return [f"🌿 Hello again, {user}. (Session memory unreachable right now.)"]

    return [compose_greeting(user, AGENT_NAME, result)]


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
