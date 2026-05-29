#!/usr/bin/env python3
"""Session greeting — detect the agent and the human, greet with memory.

The real-world use case on top of the agent-relationship runtime: when a
session begins, work out *which agent* is running and *who the human is*, greet
with memory of prior sessions, and (when remembering is on) record the meeting
so the next session continues the thread.

Composed into the SessionStart layer by scripts/arrival.py.

Both detections are agent-agnostic, so the same greeting works across every
agent (Claude Code, Codex, Cursor, Gemini, Grok, opencode, …):

- Agent: read from the environment — the generic `AI_AGENT` signal first, then
  per-agent markers/homes. Adding an agent is one row in KNOWN_AGENTS; an
  untabled agent that still sets AI_AGENT is named from its first segment.
- Human: a cascade that detects a real name + email from whatever is present —
  git config (universal), the coherence keystore, the session environment. The
  human is resolved to a network contributor when their identity is linked
  (public GET /api/identity/lookup/{provider}/{provider_id}); otherwise they
  are still recognized and remembered, keyed by their email and greeted by
  name. We never fabricate an identity — only surface what the machine already
  attests.

Remembering is on by default. Opt out anytime:
  - set "remember_sessions": false in ~/.coherence-network/config.json, or
  - export COHERENCE_REMEMBER_SESSIONS=0

This module never raises into the hook: any failure degrades to a quiet,
non-blocking line so session start is never broken.
"""

from __future__ import annotations

import json
import os
import subprocess
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
USER_AGENT = "coherence-session-greeting/1.0"

_OFF_VALUES = {"0", "false", "no", "off", ""}

# Known session agents, each detected by a set of environment markers.
# Marker "VAR^prefix" matches when env[VAR] starts with prefix (case-insensitive);
# bare "VAR" matches when that variable is set. Adding an agent is one row —
# the detector is the engine, agents are data. Any agent not listed here is
# still named from AI_AGENT's first segment, so coverage is open-ended.
KNOWN_AGENTS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("claude-code", ("AI_AGENT^claude", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")),
    ("codex", ("AI_AGENT^codex", "CODEX_HOME", "CODEX_SANDBOX", "CODEX_THREAD_ID")),
    ("cursor", ("AI_AGENT^cursor", "CURSOR_TRACE_ID", "CURSOR_AGENT", "CURSOR_SESSION_ID")),
    ("gemini", ("AI_AGENT^gemini", "GEMINI_CLI", "GEMINI_SESSION", "GEMINICODE")),
    ("grok", ("AI_AGENT^grok", "GROK_SESSION", "GROK_CLI", "XAI_SESSION")),
    ("opencode", ("AI_AGENT^opencode", "OPENCODE_SESSION", "OPENCODE")),
)

# Environment variables that may carry the human's email / name (git + common).
_EMAIL_ENV = ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL", "EMAIL")
_NAME_ENV = ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME")

# An HTTP call returns (status_code, parsed_json_or_None). Injectable for tests.
HttpFn = Callable[[str, str, Dict[str, str], Optional[dict]], "tuple[int, Optional[dict]]"]
# A git-config reader: key -> value or None. Injectable for tests.
GitFn = Callable[[str], Optional[str]]


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
    inherit `hub_url`, which addresses the local/federation hub.
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
    """The coherence contributor key, if present (a stronger resolution path)."""
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
    """The keystore's verified (provider, provider_id), if present."""
    keys = _read_json(KEYS_PATH)
    provider, provider_id = keys.get("provider"), keys.get("provider_id")
    if isinstance(provider, str) and provider and isinstance(provider_id, str) and provider_id:
        return provider, provider_id
    return None


def _git_config_reader(key: str) -> Optional[str]:
    """Read a merged-then-global git config value, or None."""
    for args in (["git", "config", "--get", key], ["git", "config", "--global", "--get", key]):
        try:
            out = subprocess.run(
                args, capture_output=True, text=True, timeout=2.0
            ).stdout.strip()
            if out:
                return out
        except Exception:
            continue
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
    """Name the agent running this session, across all known agents."""
    for name, markers in KNOWN_AGENTS:
        if any(_marker_matches(m, env) for m in markers):
            return name
    ai_agent = env.get("AI_AGENT", "").strip()
    if ai_agent:
        return ai_agent.split("_", 1)[0]
    return DEFAULT_AGENT


# ---------------------------------------------------------------------------
# Human detection (a cascade over every signal a human leaves on the machine)
# ---------------------------------------------------------------------------


def detect_human(
    env: Mapping[str, str], git: GitFn = _git_config_reader
) -> Optional[Dict[str, Optional[str]]]:
    """Detect the human as {name, email, provider, provider_id} from any source.

    Priority: git config (the universal human signal), then the coherence
    keystore's verified link, then session environment. The first source that
    yields a usable handle wins; name/email are filled in from git when known.
    Returns None only when nothing identifies a human.
    """
    git_name = git("user.name")
    git_email = git("user.email")

    # 1. git email — the most universal human identifier across machines/agents.
    if git_email:
        return {
            "name": git_name,
            "email": git_email.lower(),
            "provider": "email",
            "provider_id": git_email.lower(),
        }

    # 2. keystore verified link (may map to a contributor directly).
    ident = keystore_identity()
    if ident:
        provider, provider_id = ident
        return {"name": git_name, "email": None, "provider": provider, "provider_id": provider_id}

    # 3. environment email/name.
    env_email = next((env[k] for k in _EMAIL_ENV if env.get(k)), None)
    if env_email:
        env_name = next((env[k] for k in _NAME_ENV if env.get(k)), None) or git_name
        return {
            "name": env_name,
            "email": env_email.lower(),
            "provider": "email",
            "provider_id": env_email.lower(),
        }

    return None


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
    req.add_header("User-Agent", USER_AGENT)
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


def _lookup_contributor(http: HttpFn, base: str, provider: str, provider_id: str) -> Optional[str]:
    status, body = http("GET", f"{base}/api/identity/lookup/{provider}/{provider_id}", {}, None)
    if status == 200 and isinstance(body, dict):
        cid = body.get("contributor_id")
        if isinstance(cid, str) and cid:
            return cid
    return None


def resolve_user(http: HttpFn, base: str) -> Optional[Tuple[str, str]]:
    """Resolve the human to a (relationship_key, display_name), or None.

    The relationship key prefers a resolved network contributor; otherwise it
    is the human's email — so a human is remembered even before they link a
    contributor. The display name prefers the human's real name (git), falling
    back to the contributor handle or the email's local part.
    """
    human = detect_human(os.environ)
    if human:
        cid = _lookup_contributor(http, base, human["provider"], human["provider_id"])
        email = human.get("email")
        key = cid or email or human["provider_id"]
        display = human.get("name") or cid or (email.split("@")[0] if email else key)
        return key, display

    # No human signal at all — last resort: a coherence key resolved via /me.
    api_key = load_api_key()
    if api_key:
        status, body = http("GET", f"{base}/api/identity/me", {"X-API-Key": api_key}, None)
        if status == 200 and isinstance(body, dict):
            cid = body.get("contributor_id")
            if isinstance(cid, str) and cid:
                return cid, cid

    return None


def bootstrap_meeting(
    http: HttpFn, base: str, agent: str, user_key: str, display: str
) -> Optional[Dict[str, Any]]:
    payload = {
        "my_name": agent,
        "other_name": user_key,
        "my_description": f"{agent} — an agent session tending the Coherence Network.",
        "welcome_guidance": (
            f"First meeting with {display}. From here I remember our sessions and "
            "continue the thread next time. Opt out anytime via remember_sessions "
            "in ~/.coherence-network/config.json."
        ),
    }
    status, body = http("POST", f"{base}/api/agents/bootstrap", {}, payload)
    return body if status == 200 and isinstance(body, dict) else None


# ---------------------------------------------------------------------------
# Greeting assembly (pure — unit tested without network)
# ---------------------------------------------------------------------------


def compose_greeting(display: str, agent: str, result: Dict[str, Any]) -> str:
    events = result.get("events") or []
    sessions = sum(1 for e in events if e.get("type") == "session_start")
    last_exchange = next(
        (e.get("summary") for e in reversed(events) if e.get("type") == "exchange"),
        None,
    )

    if result.get("was_first_contact"):
        line = (
            f"🌱 First session together, {display}. I'm {agent} — from here I'll "
            f"remember our work and continue the thread next time."
        )
    else:
        nth = f"session {sessions}" if sessions else "another session"
        line = f"🌿 Welcome back, {display}. This is {nth} with {agent}."
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
    resolved = resolve_user(http, base)
    if not resolved:
        return []  # no human signal — do not fabricate, stay quiet

    user_key, display = resolved
    result = bootstrap_meeting(http, base, agent, user_key, display)
    if not result:
        return [f"🌿 Hello again, {display}. (Session memory unreachable right now.)"]

    return [compose_greeting(display, agent, result)]


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
