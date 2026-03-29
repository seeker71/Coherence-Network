#!/usr/bin/env python3
"""POST each listed file to DIF verify API; print filename, trust_signal, scores.verification, eventId."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

URL = "https://coherency-network.merly-mentor.ai/api/v2/dif/verify"

FILES = [
    "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_bb397edb548/api/app/models/graph_health.py",
    "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_bb397edb548/api/app/services/graph_health_service.py",
    "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_bb397edb548/api/app/routers/graph_health.py",
    "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_bb397edb548/api/app/db/graph_health_repo.py",
    "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_bb397edb548/api/tests/test_172_graph_health.py",
    "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_bb397edb548/api/tests/test_fractal_self_balance.py",
]


def main() -> int:
    for path in FILES:
        try:
            code = open(path, encoding="utf-8").read()
        except OSError as e:
            print(f"{path}\n  ERROR read: {e}", file=sys.stderr)
            continue
        body = {
            "language": "python",
            "code": code,
            "response_mode": "script",
            "sensitivity": 0,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"{path}\n  HTTP {e.code}: {err_body}", file=sys.stderr)
            continue
        except urllib.error.URLError as e:
            print(f"{path}\n  URL error: {e}", file=sys.stderr)
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print(f"{path}\n  Non-JSON response: {raw[:500]}", file=sys.stderr)
            continue
        trust = parsed.get("trust_signal")
        scores = parsed.get("scores") or {}
        verification = scores.get("verification")
        event_id = parsed.get("eventId")
        print(f"filename: {path}")
        print(f"  trust_signal: {trust}")
        print(f"  scores.verification: {verification}")
        print(f"  eventId: {event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
