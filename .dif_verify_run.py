#!/usr/bin/env python3
import json
import urllib.request

BASE = "https://coherency-network.merly-mentor.ai/api/v2/dif/verify"
ROOT = "/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_a4a68aeedbd"

jobs = [
    ("typescript", "web/app/page.tsx"),
    ("javascript", "web/app/globals.css"),
    ("typescript", "web/components/idea_submit_form.tsx"),
]


def extract(obj):
    trust = obj.get("trust_signal")
    verify = obj.get("verification_score")
    eid = obj.get("eventId") or obj.get("event_id")
    if trust is None and isinstance(obj.get("data"), dict):
        d = obj["data"]
        trust = d.get("trust_signal", trust)
        verify = d.get("verification_score", verify)
        eid = d.get("eventId") or d.get("event_id") or eid
    if trust is None:
        trust = obj.get("trust")
    if verify is None:
        verify = obj.get("verify") or obj.get("verification")
    return trust, verify, eid


def main():
    lines_out = []
    curl_errors = []

    for lang, rel in jobs:
        path = f"{ROOT}/{rel}"
        with open(path, encoding="utf-8") as f:
            code = f.read()
        body = json.dumps(
            {
                "language": lang,
                "code": code,
                "response_mode": "script",
                "sensitivity": 0,
            }
        )
        req = urllib.request.Request(
            BASE,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
            obj = json.loads(raw)
            trust, verify, eid = extract(obj)
            lines_out.append(f"DIF: trust={trust}, verify={verify}, eventId={eid}")
        except Exception as ex:
            curl_errors.append(f"{rel}: {ex!r}")

    for line in lines_out:
        print(line)
    for err in curl_errors:
        print(err)


if __name__ == "__main__":
    main()
