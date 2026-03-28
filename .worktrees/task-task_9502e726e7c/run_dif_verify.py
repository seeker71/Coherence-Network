#!/usr/bin/env python3
"""One-off DIF verification for review task."""
import json
import sys
import urllib.request


def dif_verify(path: str, lang: str = "python") -> dict:
    with open(path, encoding="utf-8") as f:
        code = f.read()
    if len(code) > 120000:
        code = code[:120000] + "\n# ... truncated for DIF verify ..."
    payload = {"language": lang, "code": code, "response_mode": "script", "sensitivity": 0}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://coherency-network.merly-mentor.ai/api/v2/dif/verify",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode()
    return json.loads(body)


def main() -> None:
    base = "/Users/ursmuff/source/Coherence-Network/api"
    files = [
        (f"{base}/app/services/pipeline_advance_service.py", "python"),
        (f"{base}/app/routers/pipeline.py", "python"),
        (f"{base}/app/models/idea.py", "python"),
    ]
    for path, lang in files:
        try:
            d = dif_verify(path, lang)
        except Exception as e:
            print(f"FILE: {path.split('/')[-1]}")
            print(f"DIF: trust=error, verify=error, eventId=error ({e})")
            print()
            continue
        ts = d.get("trust_signal", "?")
        ver = d.get("scores", {}).get("verification", "?")
        eid = d.get("eventId", "?")
        print(f"FILE: {path.split('/')[-1]}")
        print(f"DIF: trust={ts}, verify={ver}, eventId={eid}")
        print()


if __name__ == "__main__":
    main()
