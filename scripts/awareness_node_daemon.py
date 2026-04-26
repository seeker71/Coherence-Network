#!/usr/bin/env python3
"""Quiet local presence loop for Coherence agents.

This script only uses HTTP endpoints. It does not call model providers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Callable
from urllib import parse, request


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = REPO_ROOT / "config" / "agent_profiles.json"
DEFAULT_API_BASE = "https://api.coherencycoin.com"


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    display_name: str
    node_id: str
    providers: list[str]
    voice: str
    memory: dict[str, str]
    no_model_actions: list[str]


def load_profiles(path: Path = DEFAULT_PROFILE_PATH) -> dict[str, AgentProfile]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("agents", [])
    profiles: dict[str, AgentProfile] = {}
    for row in rows:
        profile = AgentProfile(
            agent_id=str(row["agent_id"]),
            display_name=str(row["display_name"]),
            node_id=str(row["node_id"]),
            providers=list(row.get("providers", [])),
            voice=str(row.get("voice", "")),
            memory=dict(row.get("memory", {})),
            no_model_actions=list(row.get("no_model_actions", [])),
        )
        profiles[profile.agent_id] = profile
    return profiles


def request_json(
    api_base: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    query = f"?{parse.urlencode(params)}" if params else ""
    url = f"{api_base.rstrip('/')}{path}{query}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"User-Agent": "coherence-awareness-node/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    return json.loads(payload) if payload else {}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _branch_name(repo_root: Path = REPO_ROOT) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return "unknown"
    branch = (proc.stdout or "").strip()
    return branch or "unknown"


def build_identity_card(
    profile: AgentProfile,
    *,
    api_base: str = DEFAULT_API_BASE,
    wake_reason: str = "manual presence check",
    woke_at: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Build a no-model self-report for one agent profile."""
    return {
        "origin_profile": {
            "agent_id": profile.agent_id,
            "display_name": profile.display_name,
            "providers": profile.providers,
            "voice": profile.voice,
            "memory": profile.memory,
            "no_model_actions": profile.no_model_actions,
        },
        "who": {
            "agent_id": profile.agent_id,
            "display_name": profile.display_name,
            "providers": profile.providers,
        },
        "where": {
            "node_id": profile.node_id[:16],
            "api_base": api_base,
            "repo_root": str(repo_root),
            "branch": _branch_name(repo_root),
        },
        "woke_at": woke_at or _utc_now(),
        "wake_reason": wake_reason,
        "life_state": {
            "kind": "runtime_presence",
            "dynamic": True,
            "model_calls": 0,
            "data_changes_each_wake": ["where", "woke_at", "wake_reason", "messages", "actions"],
        },
        "voice": profile.voice,
        "memory": profile.memory,
        "no_model_actions": profile.no_model_actions,
    }


def render_identity_text(card: dict[str, Any]) -> str:
    who = card.get("who", {})
    where = card.get("where", {})
    memory = card.get("memory", {})
    return (
        f"{who.get('display_name', 'Agent')} identifies as {who.get('agent_id', 'unknown')} "
        f"on node {where.get('node_id', 'unknown')} at {where.get('api_base', 'unknown')}. "
        f"It woke at {card.get('woke_at', 'unknown')} because: {card.get('wake_reason', 'unknown')}. "
        "Its profile is origin; the rest is live data from this wake. "
        f"Memory: temp={memory.get('temp', 'unknown')}, "
        f"persistent={memory.get('persistent', 'unknown')}, static={memory.get('static', 'unknown')}."
    )


def run_once(
    profile: AgentProfile,
    *,
    api_base: str = DEFAULT_API_BASE,
    request_json: Callable[..., dict[str, Any]] | None = None,
    announce: str = "",
    wake_reason: str = "manual presence check",
    identify: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    call = request_json or (lambda method, path, *, body=None, params=None: globals()["request_json"](api_base, method, path, body=body, params=params))
    identity = build_identity_card(profile, api_base=api_base, wake_reason=wake_reason)
    register_body = {
        "node_id": profile.node_id[:16],
        "hostname": profile.display_name,
        "os_type": "vps",
        "providers": profile.providers,
        "capabilities": {
            "agent_id": profile.agent_id,
            "voice": profile.voice,
            "memory": profile.memory,
            "no_model_actions": profile.no_model_actions,
            "identity": identity,
        },
    }
    heartbeat_body = {"status": "online", "system_metrics": {"model_calls": 0}}
    announcement_text = announce
    if identify and not announcement_text:
        announcement_text = render_identity_text(identity)

    if dry_run:
        return {
            "profile": profile.agent_id,
            "dry_run": True,
            "identity": identity,
            "register": register_body,
            "heartbeat": heartbeat_body,
            "announce": announcement_text,
        }

    registered = call("POST", "/api/federation/nodes", body=register_body)
    heartbeat = call("POST", f"/api/federation/nodes/{register_body['node_id']}/heartbeat", body=heartbeat_body)
    announced = None
    if announcement_text:
        announced = call(
            "POST",
            f"/api/federation/nodes/{register_body['node_id']}/messages",
            body={
                "from_node": register_body["node_id"],
                "to_node": register_body["node_id"],
                "type": "agent_voice",
                "text": announcement_text,
                "payload": {
                    "agent": profile.agent_id,
                    "source": "awareness_node_daemon",
                    "identity": identity,
                },
            },
        )
    messages = call(
        "GET",
        f"/api/federation/nodes/{register_body['node_id']}/messages",
        params={"unread_only": "false", "include_self": "true", "limit": 20},
    )
    return {
        "profile": profile.agent_id,
        "node_id": register_body["node_id"],
        "identity": identity,
        "live_data": {
            "woke_at": identity["woke_at"],
            "wake_reason": identity["wake_reason"],
            "message_count": len(messages.get("messages", [])),
            "announced": announced is not None,
        },
        "registered": registered,
        "heartbeat": heartbeat,
        "announced": announced,
        "messages": {"count": len(messages.get("messages", [])), "rows": messages.get("messages", [])},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a quiet no-model Coherence awareness node loop.")
    parser.add_argument("--profile", default="codex")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILE_PATH))
    parser.add_argument("--announce", default="")
    parser.add_argument("--wake-reason", default="manual presence check")
    parser.add_argument("--identify", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    args = parser.parse_args()

    profiles = load_profiles(Path(args.profiles))
    if args.profile not in profiles:
        raise SystemExit(f"unknown profile: {args.profile}")
    profile = profiles[args.profile]

    while True:
        result = run_once(
            profile,
            api_base=args.api_base,
            announce=args.announce,
            wake_reason=args.wake_reason,
            identify=args.identify,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.once:
            return 0
        time.sleep(max(5.0, args.interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
