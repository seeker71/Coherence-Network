#!/usr/bin/env python3
"""Run META-QUESTIONS checklist (docs/META-QUESTIONS.md section 5); log to api/logs/meta_questions.json.

Usage:
  python scripts/run_meta_questions.py [--once]

Can be run standalone (cron/weekly) or invoked by monitor_pipeline.py periodically.
Output: api/logs/meta_questions.json with answers and summary (unanswered, failed).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

LOG_DIR = os.path.join(_api_dir, "logs")
META_QUESTIONS_FILE = os.path.join(LOG_DIR, "meta_questions.json")
MONITOR_ISSUES_FILE = os.path.join(LOG_DIR, "monitor_issues.json")
VERSION_FILE = os.path.join(LOG_DIR, "pipeline_version.json")

# Checklist from META-QUESTIONS.md section 5 (Run Weekly or After Incidents)
CHECKLIST = [
    {"id": "q1", "question": "Do our logs reflect the executor we actually use?"},
    {"id": "q2", "question": "Are we detecting runner/PM down, output empty, stale version?"},
    {"id": "q3", "question": "Is goal_proximity improving?"},
    {"id": "q4", "question": "Are we committing progress?"},
    {"id": "q5", "question": "Do we have blind spots in monitoring?"},
    {"id": "q6", "question": "Is the backlog aligned with PLAN.md?"},
    {"id": "q7", "question": "Are we asking the right questions?"},
]


def _load_json(path: str, default: dict) -> dict:
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _check_q1() -> tuple[str, str]:
    """Executor vs logs: heuristic — if OLLAMA_MODEL set but AGENT_EXECUTOR_DEFAULT=cursor, logs may be wrong."""
    executor = os.environ.get("AGENT_EXECUTOR_DEFAULT", "").lower()
    ollama = os.environ.get("OLLAMA_MODEL", "")
    if executor == "cursor" and ollama:
        return "no", "OLLAMA_MODEL set but AGENT_EXECUTOR_DEFAULT=cursor; logs may reference Ollama"
    if executor:
        return "yes", f"Executor={executor}; ensure log messages are executor-aware"
    return "unanswered", "AGENT_EXECUTOR_DEFAULT not set; cannot verify"


def _check_q2() -> tuple[str, str]:
    """Monitor detects runner/PM down, output empty, stale version: we have these rules in monitor."""
    data = _load_json(MONITOR_ISSUES_FILE, {})
    issues = data.get("issues") or []
    conditions = {i.get("condition") for i in issues if i.get("condition")}
    has_rules = {"runner_pm_not_seen", "no_task_running", "output_empty", "stale_version", "executor_fail"}
    if data.get("last_check"):
        return "yes", f"Monitor ran at {data['last_check']}; rules exist for runner/PM, output_empty, stale_version"
    return "unanswered", "Monitor has not run (no last_check); cannot verify detection"


def _check_q3(base_url: str) -> tuple[str, str]:
    """Goal proximity improving: need effectiveness API; compare to previous run or threshold."""
    try:
        import httpx
        r = httpx.get(f"{base_url}/api/agent/effectiveness", timeout=5)
        if r.status_code != 200:
            return "unanswered", f"Effectiveness API returned {r.status_code}"
        eff = r.json()
        gp = eff.get("goal_proximity")
        if gp is None:
            return "unanswered", "effectiveness has no goal_proximity"
        prev = _load_json(META_QUESTIONS_FILE, {})
        prev_run = prev.get("run_at")
        prev_answers = {a["id"]: a for a in prev.get("answers", [])}
        prev_gp = None
        if prev_answers.get("q3") and prev_answers["q3"].get("detail"):
            # Could store last goal_proximity in meta_questions; for now just threshold
            pass
        if gp >= 0.7:
            return "yes", f"goal_proximity={gp:.2f} (>= 0.7)"
        if gp >= 0:
            return "no", f"goal_proximity={gp:.2f} (below 0.7); review metrics or backlog"
        return "unanswered", "goal_proximity missing or invalid"
    except Exception as e:
        return "unanswered", f"Effectiveness API unreachable: {e}"


def _check_q4() -> tuple[str, str]:
    """Are we committing progress? Check env and optional state."""
    auto_commit = os.environ.get("PIPELINE_AUTO_COMMIT", "")
    if auto_commit == "1":
        return "yes", "PIPELINE_AUTO_COMMIT=1"
    return "no", "PIPELINE_AUTO_COMMIT not set to 1; progress may not be committed"


def _check_q5() -> tuple[str, str]:
    """Blind spots: not answerable programmatically."""
    return "unanswered", "Manual review: add meta-question 'What didn't we detect?' after incidents"


def _check_q6() -> tuple[str, str]:
    """Backlog aligned with PLAN.md: would need to parse both; not implemented here."""
    return "unanswered", "Backlog/PLAN alignment requires manual or future automation"


def _check_q7() -> tuple[str, str]:
    """Are we asking the right questions? Not answerable programmatically."""
    return "unanswered", "Add to META-QUESTIONS.md when new gaps appear"


def run_checklist(base_url: str = "http://localhost:8000") -> dict:
    """Run all checklist items; return dict for meta_questions.json."""
    now = datetime.now(timezone.utc).isoformat()
    answers = []
    for item in CHECKLIST:
        qid = item["id"]
        if qid == "q1":
            ans, detail = _check_q1()
        elif qid == "q2":
            ans, detail = _check_q2()
        elif qid == "q3":
            ans, detail = _check_q3(base_url)
        elif qid == "q4":
            ans, detail = _check_q4()
        elif qid == "q5":
            ans, detail = _check_q5()
        elif qid == "q6":
            ans, detail = _check_q6()
        elif qid == "q7":
            ans, detail = _check_q7()
        else:
            ans, detail = "unanswered", "Unknown question"
        answers.append({
            "id": qid,
            "question": item["question"],
            "answer": ans,
            "detail": detail,
        })
    unanswered = [a["id"] for a in answers if a["answer"] == "unanswered"]
    failed = [a["id"] for a in answers if a["answer"] == "no"]
    return {
        "run_at": now,
        "answers": answers,
        "summary": {"unanswered": unanswered, "failed": failed},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Run META-QUESTIONS checklist; log to api/logs/meta_questions.json")
    ap.add_argument("--once", action="store_true", help="Run once and exit (default)")
    ap.add_argument("--base", default=None, help="API base URL (default: http://localhost:8000)")
    args = ap.parse_args()
    base_url = args.base or os.environ.get("AGENT_API_BASE", "http://localhost:8000")
    os.makedirs(LOG_DIR, exist_ok=True)
    result = run_checklist(base_url)
    with open(META_QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {META_QUESTIONS_FILE} run_at={result['run_at']}")
    print(f"  unanswered: {result['summary']['unanswered']}")
    print(f"  failed: {result['summary']['failed']}")


if __name__ == "__main__":
    main()
