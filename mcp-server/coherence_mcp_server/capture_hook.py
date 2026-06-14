#!/usr/bin/env python3
"""Claude Code Stop hook — TRAINING-CORPUS capture (not reply attunement).

A Stop hook fires AFTER the reply is shown, so it cannot attune what the human
already saw. Reply attunement is synchronous and lives elsewhere: the voice
(docs/coherence-substrate/voice-attunement.md) prevents fear at generation, and
the cheap freq-check (form-freq-check.fk) gates a synchronous transmute in the
form-cli loop / the agent's own draft-check.

What this hook does is fill the TRAINING CORPUS: on every completed turn it hands
the (request, raw) pair to a DETACHED worker (capture_worker.py) that produces a
transmuted counterpart and records the pair (training-catalog.fk). That corpus is
what trains the freq-check and the transmuter cheaper over time — so usage becomes
capability. Because it is training, not the live reply, it runs async: the hook
spawns the worker and returns immediately. The agent is never slowed; any error is
swallowed; the hook exits 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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
        # hand the turn to a detached worker that reasons (transmutes) + captures,
        # so the agent is never blocked by the reasoner's latency.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"request": user, "raw": assistant, "lane": "agent-cli:claude-code"}, f)
            tmp = f.name
        worker = Path(__file__).resolve().parent / "capture_worker.py"
        subprocess.Popen(
            [sys.executable, str(worker), tmp],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,  # detach so it survives the hook returning
        )
    except Exception:  # noqa: BLE001 — never block the agent
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
