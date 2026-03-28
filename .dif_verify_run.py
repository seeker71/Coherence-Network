#!/usr/bin/env python3
"""One-shot: POST file contents to DIF verify API. Remove after use."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://coherency-network.merly-mentor.ai/api/v2/dif/verify"
FILES = [
    "api/app/services/collective_health_service.py",
    "api/app/routers/agent_issues_routes.py",
    "api/tests/test_agent_collective_health_api.py",
]


def main() -> None:
    root = Path(__file__).resolve().parent
    for rel in FILES:
        path = root / rel
        code = path.read_text(encoding="utf-8")
        body = json.dumps(
            {
                "language": "python",
                "code": code,
                "response_mode": "script",
                "sensitivity": 0,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {e.read().decode()[:500]}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(raw)
        trust = data.get("trust")
        verify = data.get("verify")
        event_id = data.get("eventId") or data.get("event_id")
        print(f"DIF: trust={trust}, verify={verify}, eventId={event_id}")


if __name__ == "__main__":
    main()
