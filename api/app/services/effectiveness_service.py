"""Pipeline effectiveness: throughput, issue resolution, goal proximity. Composes metrics + monitor data."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(_api_dir, "logs")
ISSUES_FILE = os.path.join(LOG_DIR, "monitor_issues.json")
RESOLUTIONS_FILE = os.path.join(LOG_DIR, "monitor_resolutions.jsonl")
WINDOW_DAYS = 7


def get_effectiveness() -> dict[str, Any]:
    """Pipeline effectiveness: throughput, success rate, issue tracking, progress, goal proximity."""
    from app.services.metrics_service import get_aggregates

    metrics = get_aggregates()
    sr = metrics.get("success_rate", {})
    completed = sr.get("completed", 0)
    total = sr.get("total", 0)
    rate = sr.get("rate", 0.0)

    # Issues: open count, resolved in 7d
    issues_open = 0
    issues: list = []
    if os.path.isfile(ISSUES_FILE):
        try:
            with open(ISSUES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            issues = data.get("issues") or []
            issues_open = len(issues)
        except Exception:
            pass

    resolved_7d = 0
    if os.path.isfile(RESOLUTIONS_FILE):
        cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
        try:
            with open(RESOLUTIONS_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        ts = datetime.fromisoformat(rec.get("resolved_at", "").replace("Z", "+00:00"))
                        if ts >= cutoff:
                            resolved_7d += 1
                    except (ValueError, KeyError, json.JSONDecodeError):
                        continue
        except Exception:
            pass

    # Throughput: tasks/day over 7d
    days = max(1, WINDOW_DAYS)
    throughput_per_day = round(completed / days, 1)

    # Progress: by phase from metrics
    by_type = metrics.get("by_task_type", {})
    progress = {
        "spec": by_type.get("spec", {}).get("completed", 0),
        "impl": by_type.get("impl", {}).get("completed", 0),
        "test": by_type.get("test", {}).get("completed", 0),
        "review": by_type.get("review", {}).get("completed", 0),
        "heal": by_type.get("heal", {}).get("completed", 0),
    }

    # Goal proximity: simple score 0–1 (success rate × throughput factor × low-issue bonus)
    throughput_factor = min(1.0, throughput_per_day / 10) if throughput_per_day else 0
    issue_penalty = max(0, 1 - (issues_open * 0.15))  # -15% per open issue
    goal_proximity = round(min(1.0, rate * (0.5 + 0.5 * throughput_factor) * issue_penalty), 2)

    return {
        "throughput": {"completed_7d": completed, "tasks_per_day": throughput_per_day},
        "success_rate": rate,
        "issues": {"open": issues_open, "resolved_7d": resolved_7d},
        "progress": progress,
        "goal_proximity": goal_proximity,
        "top_issues_by_priority": [
            {"condition": i.get("condition"), "severity": i.get("severity"), "message": (i.get("message") or "")[:80]}
            for i in (issues or [])[:5]
        ],
    }
