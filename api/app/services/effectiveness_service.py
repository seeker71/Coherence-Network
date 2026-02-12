"""Pipeline effectiveness: throughput, issue resolution, goal proximity. Composes metrics + monitor data."""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(_api_dir)
LOG_DIR = os.path.join(_api_dir, "logs")
ISSUES_FILE = os.path.join(LOG_DIR, "monitor_issues.json")
RESOLUTIONS_FILE = os.path.join(LOG_DIR, "monitor_resolutions.jsonl")
STATE_FILES = [
    os.path.join(LOG_DIR, "project_manager_state_overnight.json"),
    os.path.join(LOG_DIR, "project_manager_state.json"),
]
BACKLOG_FILE = os.path.join(PROJECT_ROOT, "specs", "006-overnight-backlog.md")
WINDOW_DAYS = 7

# Phase boundaries per specs/006-overnight-backlog.md (0-based backlog index)
# Phase 6: Product-Critical = items 56–57 (0-based 55–56). Phase 7: Remaining = items 58–74 (0-based 57–73).
PHASE_6_START_IDX = 55
PHASE_6_TOTAL = 2
PHASE_7_START_IDX = 57
PHASE_7_TOTAL = 17


def _plan_progress() -> dict[str, Any]:
    """Derive plan progress from PM state and backlog. Returns {index, total, pct, phase_6, phase_7, backlog_alignment}."""
    index = 0
    state_file = None
    for p in STATE_FILES:
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    s = json.load(f)
                idx = s.get("backlog_index")
                if idx is not None:
                    index = int(idx)
                    state_file = p
                    break
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
    total = 0
    if os.path.isfile(BACKLOG_FILE):
        with open(BACKLOG_FILE, encoding="utf-8") as f:
            for line in f:
                if re.match(r"^\d+\.\s+.+$", line.strip()) and not line.strip().startswith("#"):
                    total += 1
    pct = round(100 * index / total, 1) if total else 0
    out: dict[str, Any] = {
        "index": index,
        "total": total,
        "pct": pct,
        "state_file": (state_file or "").split("/")[-1],
    }
    # Phase 6/7 completion (spec 045): completed = number of phase items already passed (index past that item)
    phase_6_completed = max(0, min(PHASE_6_TOTAL, index - PHASE_6_START_IDX))
    phase_7_completed = max(0, min(PHASE_7_TOTAL, index - PHASE_7_START_IDX))
    out["phase_6"] = {
        "completed": phase_6_completed,
        "total": PHASE_6_TOTAL,
        "pct": round(100 * phase_6_completed / PHASE_6_TOTAL, 1) if PHASE_6_TOTAL else 0,
    }
    out["phase_7"] = {
        "completed": phase_7_completed,
        "total": PHASE_7_TOTAL,
        "pct": round(100 * phase_7_completed / PHASE_7_TOTAL, 1) if PHASE_7_TOTAL else 0,
    }
    # Backlog alignment (spec 007 item 4): flag if Phase 6/7 items not being worked
    if index < PHASE_6_START_IDX:
        phase_6_7_status = "not_reached"
        phase_6_7_not_worked = True
    elif phase_6_completed >= PHASE_6_TOTAL and phase_7_completed >= PHASE_7_TOTAL:
        phase_6_7_status = "complete"
        phase_6_7_not_worked = False
    else:
        phase_6_7_status = "in_progress"
        phase_6_7_not_worked = False
    out["backlog_alignment"] = {
        "phases_from_backlog": True,
        "phase_6_7_status": phase_6_7_status,
        "phase_6_7_not_worked": phase_6_7_not_worked,
    }
    return out


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
    heal_resolved_count = 0
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
                            if rec.get("heal_task_id"):
                                heal_resolved_count += 1
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

    plan_progress = _plan_progress()

    return {
        "throughput": {"completed_7d": completed, "tasks_per_day": throughput_per_day},
        "success_rate": rate,
        "issues": {"open": issues_open, "resolved_7d": resolved_7d},
        "progress": progress,
        "plan_progress": plan_progress,
        "goal_proximity": goal_proximity,
        "heal_resolved_count": heal_resolved_count,
        "top_issues_by_priority": [
            {"condition": i.get("condition"), "severity": i.get("severity"), "message": (i.get("message") or "")[:80]}
            for i in (issues or [])[:5]
        ],
    }
