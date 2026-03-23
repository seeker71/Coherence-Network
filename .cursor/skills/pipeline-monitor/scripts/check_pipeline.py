#!/usr/bin/env python3
"""Pipeline health monitor — surfaces blockers and remarkable events.

Checks task statuses, provider health, idea progress, and surfaces
anything that needs human attention or is worth celebrating.

Usage:
  python .cursor/skills/pipeline-monitor/scripts/check_pipeline.py
  python .cursor/skills/pipeline-monitor/scripts/check_pipeline.py --json
  python .cursor/skills/pipeline-monitor/scripts/check_pipeline.py --telegram
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

API_BASE = os.environ.get("AGENT_API_BASE", "https://api.coherencycoin.com")
STALE_THRESHOLD_MINUTES = 10
BLIND_SPOT_PRIORITY = "HIGH"

_client = httpx.Client(timeout=30.0)


def _api(path: str) -> dict | list | None:
    try:
        r = _client.get(f"{API_BASE}{path}")
        if r.status_code >= 400:
            return None
        return r.json() if r.text.strip() else None
    except Exception:
        return None


def _tasks_by_status() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for s in ("pending", "running", "completed", "failed", "timed_out", "needs_decision"):
        data = _api(f"/api/agent/tasks?status={s}&limit=50")
        tasks = data.get("tasks", data) if isinstance(data, dict) else (data or [])
        result[s] = tasks if isinstance(tasks, list) else []
    return result


def _check_blockers(tasks: dict[str, list[dict]]) -> list[dict]:
    blockers = []
    now = datetime.now(timezone.utc)

    # Stale running tasks
    for t in tasks.get("running", []):
        claimed_at = t.get("claimed_at") or t.get("updated_at") or ""
        if claimed_at:
            try:
                dt = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                age_min = (now - dt).total_seconds() / 60
                if age_min > STALE_THRESHOLD_MINUTES:
                    blockers.append({
                        "type": "stale_running",
                        "severity": "HIGH",
                        "task_id": t["id"],
                        "task_type": t.get("task_type", "?"),
                        "age_minutes": round(age_min, 1),
                        "message": f"Task {t['id'][:16]} stuck running for {age_min:.0f}min",
                    })
            except Exception:
                pass

    # Needs decision tasks
    for t in tasks.get("needs_decision", []):
        blockers.append({
            "type": "needs_decision",
            "severity": "MEDIUM",
            "task_id": t["id"],
            "task_type": t.get("task_type", "?"),
            "message": f"Task {t['id'][:16]} needs human decision",
        })

    # Blind timeouts (check recent failed/timed_out)
    for t in tasks.get("timed_out", []):
        output = (t.get("output") or t.get("error_summary") or "").lower()
        if "blind timeout" in output:
            blockers.append({
                "type": "blind_timeout",
                "severity": "HIGH",
                "task_id": t["id"],
                "task_type": t.get("task_type", "?"),
                "message": f"Blind timeout: {t['id'][:16]} — zero diagnostic output",
            })

    # High failure count
    failed = tasks.get("failed", [])
    timed_out = tasks.get("timed_out", [])
    if len(failed) + len(timed_out) > 5:
        blockers.append({
            "type": "high_failure_rate",
            "severity": "MEDIUM",
            "message": f"{len(failed)} failed + {len(timed_out)} timed out tasks",
        })

    return blockers


def _check_provider_health() -> list[dict]:
    alerts = []
    stats_data = _api("/api/automation/exec-stats")
    if not isinstance(stats_data, dict):
        return alerts

    providers = stats_data.get("providers", {})
    if isinstance(providers, list):
        providers = {p.get("provider", str(i)): p for i, p in enumerate(providers)}

    for name, info in providers.items():
        if not isinstance(info, dict):
            continue
        last_5_rate = info.get("last_5_rate")
        if isinstance(last_5_rate, (int, float)) and last_5_rate == 0 and info.get("sample_count", 0) >= 3:
            alerts.append({
                "type": "provider_blocked",
                "severity": "HIGH",
                "provider": name,
                "message": f"Provider {name} has 0% recent success — likely blocked",
            })
        elif isinstance(last_5_rate, (int, float)) and last_5_rate >= 1.0 and info.get("sample_count", 0) >= 5:
            alerts.append({
                "type": "provider_streak",
                "severity": "GOOD",
                "provider": name,
                "message": f"Provider {name} on a perfect streak ({info.get('sample_count', '?')} tasks)",
            })

    return alerts


def _check_remarkable(tasks: dict[str, list[dict]]) -> list[dict]:
    remarkable = []
    completed = tasks.get("completed", [])
    pending = tasks.get("pending", [])

    # Completion velocity
    if len(completed) > 0:
        remarkable.append({
            "type": "completion_count",
            "severity": "INFO",
            "message": f"{len(completed)} tasks completed, {len(pending)} pending",
        })

    # Check for idea phase advancements (look for auto_phase_advanced_from in context)
    for t in completed[-20:]:  # Last 20 completed
        ctx = t.get("context") if isinstance(t.get("context"), dict) else {}
        advanced_from = ctx.get("auto_phase_advanced_from")
        idea_id = ctx.get("idea_id")
        if advanced_from and idea_id:
            remarkable.append({
                "type": "phase_advance",
                "severity": "GOOD",
                "idea_id": idea_id,
                "from_phase": advanced_from,
                "to_phase": t.get("task_type", "?"),
                "message": f"Idea {idea_id[:20]} advanced: {advanced_from} -> {t.get('task_type', '?')}",
            })

    return remarkable


def _check_idea_progress() -> list[dict]:
    events = []
    ideas = _api("/api/ideas?limit=30")
    if not ideas:
        return events

    idea_list = ideas.get("ideas", ideas) if isinstance(ideas, dict) else ideas
    if not isinstance(idea_list, list):
        return events

    validated = 0
    partial = 0
    none_count = 0
    for idea in idea_list:
        ms = idea.get("manifestation_status", "none")
        if ms == "validated":
            validated += 1
        elif ms == "partial":
            partial += 1
        else:
            none_count += 1

    events.append({
        "type": "idea_portfolio",
        "severity": "INFO",
        "message": f"Ideas: {validated} validated, {partial} partial, {none_count} not started ({len(idea_list)} total)",
    })

    # Flag ideas that are validated (remarkable)
    for idea in idea_list:
        if idea.get("manifestation_status") == "validated":
            events.append({
                "type": "idea_validated",
                "severity": "GOOD",
                "idea_id": idea["id"],
                "message": f"Idea validated: {idea['name'][:50]}",
            })

    return events


def generate_report() -> dict[str, Any]:
    tasks = _tasks_by_status()
    blockers = _check_blockers(tasks)
    provider_alerts = _check_provider_health()
    remarkable = _check_remarkable(tasks)
    idea_progress = _check_idea_progress()

    # Separate blockers from good news
    all_blockers = [b for b in blockers if b["severity"] in ("HIGH", "MEDIUM")]
    all_blockers.extend([a for a in provider_alerts if a["severity"] in ("HIGH", "MEDIUM")])

    all_good = [r for r in remarkable if r["severity"] == "GOOD"]
    all_good.extend([a for a in provider_alerts if a["severity"] == "GOOD"])
    all_good.extend([e for e in idea_progress if e["severity"] == "GOOD"])

    all_info = [r for r in remarkable if r["severity"] == "INFO"]
    all_info.extend([e for e in idea_progress if e["severity"] == "INFO"])

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blockers": all_blockers,
        "remarkable": all_good,
        "info": all_info,
        "has_blockers": len(all_blockers) > 0,
        "has_remarkable": len(all_good) > 0,
    }


def format_console(report: dict) -> str:
    lines = []
    ts = report["timestamp"][:19]

    if report["blockers"]:
        lines.append(f"BLOCKERS ({ts})")
        lines.append("=" * 50)
        for b in report["blockers"]:
            lines.append(f"  [{b['severity']}] {b['message']}")
        lines.append("")

    if report["remarkable"]:
        lines.append(f"REMARKABLE ({ts})")
        lines.append("=" * 50)
        for r in report["remarkable"]:
            lines.append(f"  {r['message']}")
        lines.append("")

    if report["info"]:
        lines.append(f"STATUS ({ts})")
        lines.append("-" * 50)
        for i in report["info"]:
            lines.append(f"  {i['message']}")
        lines.append("")

    if not report["blockers"] and not report["remarkable"]:
        lines.append(f"Pipeline quiet ({ts}) — no blockers, no remarkable events")

    return "\n".join(lines)


def format_telegram(report: dict) -> str:
    parts = []

    if report["blockers"]:
        parts.append("*BLOCKERS*")
        for b in report["blockers"]:
            emoji = "\u26a0\ufe0f" if b["severity"] == "HIGH" else "\u26a1"
            parts.append(f"{emoji} {b['message']}")

    if report["remarkable"]:
        parts.append("\n*REMARKABLE*" if parts else "*REMARKABLE*")
        for r in report["remarkable"]:
            parts.append(f"\u2728 {r['message']}")

    if report["info"]:
        parts.append("")
        for i in report["info"]:
            parts.append(f"\u2139\ufe0f {i['message']}")

    if not parts:
        parts.append("\u2705 Pipeline clear — nothing to report")

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Pipeline health monitor")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--telegram", action="store_true", help="Output Telegram markdown")
    parser.add_argument("--quiet", action="store_true", help="Only output if blockers or remarkable events")
    args = parser.parse_args()

    report = generate_report()

    if args.quiet and not report["has_blockers"] and not report["has_remarkable"]:
        return

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif args.telegram:
        print(format_telegram(report))
    else:
        print(format_console(report))


if __name__ == "__main__":
    main()
