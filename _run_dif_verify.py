import json, sys, urllib.request
from pathlib import Path

base = Path("/Users/ursmuff/source/Coherence-Network/.worktrees/task-task_07d6b785d58")
files = [
    (base / "api/tests/test_local_runner.py", "python"),
    (base / "api/scripts/local_runner.py", "python"),
]
url = "https://coherency-network.merly-mentor.ai/api/v2/dif/verify"


def verify_code(fp, lang, code):
    body = json.dumps({"language": lang, "code": code, "response_mode": "script", "sensitivity": 0}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode()
    d = json.loads(raw)
    print(fp.name, "|", "trust=", d.get("trust_signal"), "verify=", d.get("scores", {}).get("verification"), "eventId=", d.get("eventId"))


def excerpt_local_runner():
    p = base / "api/scripts/local_runner.py"
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    # 1-based line numbers: 3059-3195 and 1866-1910
    a = "".join(lines[3058:3195])
    b = "".join(lines[1865:1910])
    return (
        "# --- excerpt local_runner.py lines 3059-3195 ---\n"
        + a
        + "\n# --- excerpt local_runner.py lines 1866-1910 ---\n"
        + b
    )


def main():
    for fp, lang in files:
        try:
            code = fp.read_text(encoding="utf-8")
            verify_code(fp, lang, code)
        except Exception as e:
            print(f"ERROR {fp.name}: {e!r}", file=sys.stderr)
            if fp.name == "local_runner.py":
                code = excerpt_local_runner()
                verify_code(fp, lang, code)
            else:
                raise


if __name__ == "__main__":
    main()
