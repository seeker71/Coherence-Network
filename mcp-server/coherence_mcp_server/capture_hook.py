#!/usr/bin/env python3
"""Claude Code Stop hook — the flywheel inside every session.

On every completed turn, capture the (request, response) pair into the form-cli
training catalog. Usage becomes capability: the corpus this fills is what trains
the form-native lane the router (form-cli-router.fk) graduates to over time.

Transmutation (fear/control -> discernment/opportunity) is a separate ROUTED
step — a hook cannot reason — so the raw turn is captured with transmuted left
pending (outcome "turn-raw"); a transmute pass fills it later. Carrier only: the
catalog shape is training-catalog.fk. Never blocks the agent — any error is
swallowed and the hook exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # mcp-server/


def _text(record: dict) -> str:
    msg = record.get("message", record)
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _last_turn(transcript_path: str) -> tuple[str, str]:
    try:
        lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return "", ""
    records = []
    for ln in lines:
        try:
            records.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            pass
    assistant, user = "", ""
    for rec in reversed(records):
        if not assistant and rec.get("type") == "assistant":
            assistant = _text(rec)
        elif assistant and rec.get("type") == "user":
            user = _text(rec)
            break
    return user, assistant


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return 0
    user, assistant = _last_turn(transcript_path)
    if not (user.strip() and assistant.strip()):
        return 0
    try:
        from coherence_mcp_server import form_cli_tools as fct
        fct.catalog_capture(user, assistant, "", "agent-cli:claude-code", "turn-raw")
    except Exception:  # noqa: BLE001 — never block the agent
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
