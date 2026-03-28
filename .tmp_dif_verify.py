import json
import urllib.request
from pathlib import Path

base = Path(__file__).resolve().parent
url = "https://coherency-network.merly-mentor.ai/api/v2/dif/verify"

files = [
    ("web/app/page.tsx", "typescript"),
    ("web/components/idea_submit_form.tsx", "typescript"),
    ("web/app/globals.css", "javascript"),
    ("api/tests/test_ui_readability.py", "python"),
]

for rel, lang in files:
    path = base / rel
    code = path.read_text(encoding="utf-8")
    body = {
        "language": lang,
        "code": code,
        "response_mode": "script",
        "sensitivity": 0,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    j = json.loads(raw)
    trust = j.get("trust_signal")
    scores = j.get("scores") or {}
    verify = scores.get("verification") if isinstance(scores, dict) else None
    event_id = j.get("eventId")
    print(f"{rel}: DIF: trust={trust}, verify={verify}, eventId={event_id}")
