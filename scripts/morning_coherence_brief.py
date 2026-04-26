#!/usr/bin/env python3
"""Collect a morning Coherence brief from live network signals.

This is the concrete path for "show me in the morning": it reads the
same public health, federation node, and node-message channels that MCP
awareness streaming exposes, then prints a compact human or JSON brief.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_API_BASE = "https://api.coherencycoin.com"
DEFAULT_NODE_IDS = ["8160aa905ac5881e"]

Fetch = Callable[[str, dict[str, Any] | None], Any]


def fetch_json(api_base: str, path: str, params: dict[str, Any] | None = None) -> Any:
    query = ""
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            query = "?" + urlencode(filtered)
    url = f"{api_base.rstrip('/')}{path}{query}"
    request = Request(url, headers={"User-Agent": "coherence-morning-brief/1.0"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _message_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("messages", [])
        return rows if isinstance(rows, list) else []
    if isinstance(payload, list):
        return payload
    return []


def collect_brief(
    api_base: str = DEFAULT_API_BASE,
    node_ids: list[str] | None = None,
    *,
    limit: int = 20,
    fetch: Fetch | None = None,
) -> dict[str, Any]:
    fetcher = fetch or (lambda path, params=None: fetch_json(api_base, path, params))
    health = fetcher("/api/health", None)
    nodes = fetcher("/api/federation/nodes", None)
    node_rows = nodes if isinstance(nodes, list) else []
    selected_node_ids = node_ids or [str(n.get("node_id")) for n in node_rows if n.get("node_id")]
    if not selected_node_ids:
        selected_node_ids = list(DEFAULT_NODE_IDS)

    messages_by_node: dict[str, list[dict[str, Any]]] = {}
    for node_id in selected_node_ids:
        payload = fetcher(
            f"/api/federation/nodes/{node_id}/messages",
            {"unread_only": "false", "limit": limit},
        )
        messages_by_node[node_id] = _message_rows(payload)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base.rstrip("/"),
        "health": health,
        "nodes": node_rows,
        "node_ids_checked": selected_node_ids,
        "messages_by_node": messages_by_node,
        "path": {
            "worktree": "/Users/ursmuff/.claude-worktrees/Coherence-Network/mcp-awareness-streaming-20260427",
            "branch": "codex/mcp-awareness-streaming-20260427",
            "collector": "scripts/morning_coherence_brief.py",
            "mcp_spec": "specs/mcp-awareness-streaming.md",
        },
    }


def render_text(brief: dict[str, Any]) -> str:
    health = brief.get("health") if isinstance(brief.get("health"), dict) else {}
    nodes = brief.get("nodes") if isinstance(brief.get("nodes"), list) else []
    messages_by_node = brief.get("messages_by_node") if isinstance(brief.get("messages_by_node"), dict) else {}

    lines = [
        "COHERENCE MORNING BRIEF",
        f"generated_at: {brief.get('generated_at')}",
        f"api: {health.get('status', 'unknown')} version={health.get('version', '?')}",
        f"nodes_seen: {len(nodes)}",
        "",
        "AWARE NODES",
    ]
    for node in nodes:
        providers = ", ".join(node.get("providers", [])) if isinstance(node.get("providers"), list) else ""
        lines.append(
            f"- {node.get('hostname', node.get('node_id'))} id={node.get('node_id')} "
            f"status={node.get('status')} providers={providers} last_seen={node.get('last_seen_at')}"
        )

    lines.extend(["", "REAL MESSAGES"])
    for node_id, messages in messages_by_node.items():
        lines.append(f"- node {node_id}: {len(messages)} messages")
        for message in messages[:10]:
            text = str(message.get("text") or message.get("payload") or "").replace("\n", " ")
            lines.append(
                f"  [{message.get('timestamp', '?')}] from={message.get('from_node', '?')} "
                f"type={message.get('type', '?')} text={text[:180]}"
            )

    path = brief.get("path") if isinstance(brief.get("path"), dict) else {}
    lines.extend([
        "",
        "PATH",
        f"- worktree: {path.get('worktree')}",
        f"- branch: {path.get('branch')}",
        f"- collector: {path.get('collector')}",
        f"- mcp_spec: {path.get('mcp_spec')}",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a morning Coherence Network status/message brief.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--node-id", action="append", dest="node_ids")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    brief = collect_brief(args.api_base, args.node_ids, limit=args.limit)
    if args.json:
        print(json.dumps(brief, indent=2, sort_keys=True))
    else:
        print(render_text(brief))


if __name__ == "__main__":
    main()
