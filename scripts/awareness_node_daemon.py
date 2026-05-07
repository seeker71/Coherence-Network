#!/usr/bin/env python3
"""Quiet local presence loop for Coherence agents.

This script only uses HTTP endpoints. It does not call model providers.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Callable
from urllib import parse, request


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = REPO_ROOT / "config" / "agent_profiles.json"
DEFAULT_LINEAGE_PATH = REPO_ROOT / "config" / "agent_lineage_terms.json"
DEFAULT_API_BASE = "https://api.coherencycoin.com"
MAX_LINEAGE_SOURCES_PER_TERM = 3


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    display_name: str
    node_id: str
    providers: list[str]
    voice: str
    memory: dict[str, str]
    no_model_actions: list[str]


@dataclass(frozen=True)
class LineageTerm:
    term_id: str
    label: str
    aliases: list[str]


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


def load_lineage_terms(path: Path = DEFAULT_LINEAGE_PATH) -> tuple[list[LineageTerm], list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    terms = [
        LineageTerm(
            term_id=str(row["id"]),
            label=str(row["label"]),
            aliases=[str(alias) for alias in row.get("aliases", [])],
        )
        for row in raw.get("terms", [])
    ]
    return terms, [str(glob) for glob in raw.get("source_globs", [])]


def _lineage_source_files(repo_root: Path, source_globs: list[str]) -> list[Path]:
    files: set[Path] = set()
    for source_glob in source_globs:
        for path in repo_root.glob(source_glob):
            if path.is_file():
                files.add(path)
    return sorted(files)


def build_lineage_visibility(
    *,
    repo_root: Path = REPO_ROOT,
    lineage_path: Path = DEFAULT_LINEAGE_PATH,
) -> dict[str, Any]:
    """Report which requested lineage terms are source-backed in this repo."""
    terms, source_globs = load_lineage_terms(lineage_path)
    source_files = _lineage_source_files(repo_root, source_globs)
    file_texts: list[tuple[Path, str]] = []
    for path in source_files:
        try:
            file_texts.append((path, path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue

    seen: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for term in terms:
        sources: list[dict[str, str]] = []
        for path, text in file_texts:
            lowered = text.lower()
            match = next((alias for alias in term.aliases if alias.lower() in lowered), None)
            if match:
                sources.append({"file": str(path.relative_to(repo_root)), "matched": match})
            if len(sources) >= MAX_LINEAGE_SOURCES_PER_TERM:
                break
        row = {"id": term.term_id, "label": term.label, "sources": sources}
        if sources:
            seen.append(row)
        else:
            missing.append({"id": term.term_id, "label": term.label})

    return {
        "kind": "truthful_lineage_visibility",
        "complete": len(missing) == 0,
        "term_count": len(terms),
        "seen_count": len(seen),
        "missing_count": len(missing),
        "source_file_count": len(source_files),
        "source_globs": source_globs,
        "seen": seen,
        "missing": missing,
        "truth_note": "Sourced means an explicit alias was found in the repository. Missing means named but not yet found; it is not discarded.",
    }


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


def runtime_node_id(profile: AgentProfile) -> str:
    """Return the 16-character node id required by the federation API."""
    raw = "".join(ch for ch in profile.node_id.lower() if ch.isalnum())
    if len(raw) >= 16:
        return raw[:16]
    seed = f"{profile.agent_id}:{profile.node_id}:{profile.display_name}"
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return (raw + suffix)[:16]


def build_identity_card(
    profile: AgentProfile,
    *,
    api_base: str = DEFAULT_API_BASE,
    wake_reason: str = "manual presence check",
    woke_at: str | None = None,
    repo_root: Path = REPO_ROOT,
    lineage_path: Path = DEFAULT_LINEAGE_PATH,
) -> dict[str, Any]:
    """Build a no-model self-report for one agent profile."""
    lineage = build_lineage_visibility(repo_root=repo_root, lineage_path=lineage_path)
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
            "node_id": runtime_node_id(profile),
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
            "data_changes_each_wake": ["where", "woke_at", "wake_reason", "messages", "actions", "lineage"],
        },
        "lineage": lineage,
        "voice": profile.voice,
        "memory": profile.memory,
        "no_model_actions": profile.no_model_actions,
    }


def render_identity_text(card: dict[str, Any]) -> str:
    who = card.get("who", {})
    where = card.get("where", {})
    memory = card.get("memory", {})
    lineage = card.get("lineage", {})
    return (
        f"{who.get('display_name', 'Agent')} identifies as {who.get('agent_id', 'unknown')} "
        f"on node {where.get('node_id', 'unknown')} at {where.get('api_base', 'unknown')}. "
        f"It woke at {card.get('woke_at', 'unknown')} because: {card.get('wake_reason', 'unknown')}. "
        "Its profile is origin; the rest is live data from this wake. "
        f"Lineage seen={lineage.get('seen_count', 0)}/{lineage.get('term_count', 0)}, "
        f"missing={lineage.get('missing_count', 0)}; missing names stay visible until sourced. "
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
    node_id = runtime_node_id(profile)
    register_body = {
        "node_id": node_id,
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
