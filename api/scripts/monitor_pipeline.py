#!/usr/bin/env python3
"""Automated pipeline monitor: detect issues, persist for check/react/improve.

Usage:
  python scripts/monitor_pipeline.py [--once] [--interval 120] [--auto-fix]

Runs detection rules against pipeline-status and metrics. Writes issues to
api/logs/monitor_issues.json (checkable). Optionally creates heal/needs_decision
tasks when --auto-fix and PIPELINE_AUTO_FIX_ENABLED=1.

Detection rules:
  - stale_version: pipeline running old code (git SHA changed); request restart
  - no_task_running: pending 3+ min, no running (analyze why, debug, fix, restart)
  - low_phase_coverage: running < 2 when pending exist (ensure PM creates tasks for all phases)
  - repeated_failures: 3+ consecutive failed
  - low_success_rate: 7d rate < 80% (10+ tasks)
  - api_unreachable: pipeline-status fails
  - orphan_running: running task > 2h (likely stale)

Fallback: when PIPELINE_AUTO_RECOVER=1, write restart_requested (stale_version), PATCH orphan to failed, create heal tasks.
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"), override=True)
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")
LOG_DIR = os.path.join(_api_dir, "logs")
ISSUES_FILE = os.path.join(LOG_DIR, "monitor_issues.json")
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")
STATUS_REPORT_FILE = os.path.join(LOG_DIR, "pipeline_status_report.json")
STATUS_REPORT_TXT = os.path.join(LOG_DIR, "pipeline_status_report.txt")
RESOLUTIONS_FILE = os.path.join(LOG_DIR, "monitor_resolutions.jsonl")
VERSION_FILE = os.path.join(LOG_DIR, "pipeline_version.json")
RESTART_FILE = os.path.join(LOG_DIR, "restart_requested.json")
PROJECT_ROOT = os.path.dirname(_api_dir)

# Priority order: 1 = highest (address first)
SEVERITY_TO_PRIORITY = {"high": 1, "medium": 2, "low": 3}

STUCK_THRESHOLD_SEC = 600   # 10 min
NO_RUNNING_THRESHOLD_SEC = 180  # 3 min — raise issue if pending but no task running
ORPHAN_RUNNING_SEC = 7200  # 2 h
LOW_SUCCESS_RATE = 0.80
MIN_TASKS_FOR_RATE = 10
MIN_RUNNING_WHEN_PENDING = 2  # expect at least 2 tasks running when we have pending (phase coverage)

NO_TASK_RUNNING_ACTION = """ANALYZE why no task is running:
- agent_runner process may have died or crashed
- runner may not be polling (check logs for errors)
- API/runner miscommunication (wrong base URL, timeouts)
- task may be stuck in bad state (orphan running elsewhere)

DEBUG:
1. tail -f api/logs/agent_runner.log
2. ps aux | grep agent_runner
3. curl -s http://localhost:8000/api/agent/pipeline-status | python3 -m json.tool
4. Check pending tasks: any with status=running that never completed?

FIX:
- If runner dead: restart it (see RESTART below)
- If orphan running: PATCH task to failed, or restart pipeline with --reset
- If API down: uvicorn app.main:app --reload --port 8000

RESTART to continue progress:
cd api && ./scripts/run_overnight_pipeline.sh
# Or run components manually:
# 1. uvicorn app.main:app --port 8000
# 2. python scripts/agent_runner.py --interval 10
# 3. python scripts/project_manager.py"""


def _setup_logging(verbose: bool = False) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    log = logging.getLogger("monitor")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not log.handlers:
        h = logging.FileHandler(LOG_FILE, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        if verbose:
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            log.addHandler(sh)
    return log


def _load_issues() -> dict:
    if not os.path.isfile(ISSUES_FILE):
        return {"issues": [], "last_check": None, "history": []}
    try:
        with open(ISSUES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"issues": [], "last_check": None, "history": []}


def _save_issues(data: dict) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(ISSUES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_current_git_sha() -> str:
    """Return current git HEAD SHA, or empty if not a git repo."""
    try:
        import subprocess
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _request_restart(reason: str, log: logging.Logger) -> None:
    """Write restart_requested.json for watchdog to pick up."""
    os.makedirs(LOG_DIR, exist_ok=True)
    payload = {"reason": reason, "at": datetime.now(timezone.utc).isoformat()}
    with open(RESTART_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    log.info("Restart requested: %s", reason)


def _get_pipeline_process_args() -> dict:
    """Inspect running agent_runner and project_manager process args. Return {runner_workers: int|None, pm_parallel: bool|None}."""
    import subprocess
    result = {"runner_workers": None, "pm_parallel": None}
    try:
        # ps aux: works on macOS and most Linux; full cmdline may be truncated
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            return result
        lines = (r.stdout or "").strip().splitlines()
        for line in lines:
            if "agent_runner" in line and "python" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p in ("--workers", "-w") and i + 1 < len(parts):
                        try:
                            result["runner_workers"] = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
                if result["runner_workers"] is None:
                    result["runner_workers"] = 1  # script default when --workers not seen
                break
        for line in lines:
            if "project_manager" in line and "python" in line:
                result["pm_parallel"] = " --parallel " in (" " + line) or line.rstrip().endswith(" --parallel")
                break
    except Exception:
        pass
    return result


def _record_resolution(condition: str, log: logging.Logger) -> None:
    """Append resolution event for effectiveness measurement."""
    os.makedirs(LOG_DIR, exist_ok=True)
    record = {"condition": condition, "resolved_at": datetime.now(timezone.utc).isoformat()}
    try:
        with open(RESOLUTIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        log.debug("Could not record resolution: %s", e)


def _add_issue(data: dict, condition: str, severity: str, message: str, suggested_action: str) -> dict:
    priority = SEVERITY_TO_PRIORITY.get(severity, 2)
    issue = {
        "id": str(uuid.uuid4())[:8],
        "condition": condition,
        "severity": severity,
        "priority": priority,
        "message": message,
        "suggested_action": suggested_action,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
    }
    data["issues"].append(issue)
    data["history"] = (data.get("history") or [])[-99:]  # keep last 100
    data["history"].append({"at": issue["created_at"], "condition": condition, "severity": severity})
    return data


def _build_hierarchical_report(
    data: dict, status: Optional[dict], effectiveness: Optional[dict], proc: dict, now: datetime
) -> dict:
    """Build hierarchical status report (machine + human readable). Layer 0=Goal, 1=Orchestration, 2=Execution, 3=Attention."""
    issues = data.get("issues") or []
    resolved = data.get("resolved_since_last") or []

    # Layer 0: Goal (from effectiveness when available)
    layer0 = {"status": "unknown", "summary": "Data unavailable (API may be down)"}
    if effectiveness:
        gp = effectiveness.get("goal_proximity", 0)
        t = effectiveness.get("throughput", {})
        sr = effectiveness.get("success_rate", 0)
        layer0 = {
            "status": "ok" if gp >= 0.7 and not issues else "needs_attention",
            "goal_proximity": gp,
            "throughput_7d": t.get("completed_7d", 0),
            "tasks_per_day": t.get("tasks_per_day", 0),
            "success_rate": sr,
            "summary": f"{t.get('completed_7d', 0)} tasks (7d), {int((sr or 0) * 100)}% success",
        }

    # Layer 1: Orchestration (PM, runner, monitor)
    pm = (status or {}).get("project_manager") or {}
    inf = pm.get("in_flight") or []
    layer1 = {
        "status": "ok",
        "project_manager": "running" if pm else "unknown",
        "pm_in_flight": len(inf),
        "agent_runner": "unknown",
        "runner_workers": proc.get("runner_workers"),
        "pm_parallel": proc.get("pm_parallel"),
        "summary": f"PM {len(inf)} in_flight, runner workers={proc.get('runner_workers', '?')}",
    }
    if not status and issues:
        layer1["status"] = "unknown"

    # Layer 2: Execution (API, metrics)
    layer2 = {"status": "ok", "api": "reachable", "metrics": "available", "summary": "API and metrics OK"}
    for i in issues:
        if i.get("condition") == "api_unreachable":
            layer2 = {"status": "needs_attention", "api": "unreachable", "metrics": "unknown", "summary": "API down"}
            break
        if i.get("condition") == "metrics_unavailable":
            layer2["metrics"] = "404"
            layer2["status"] = "needs_attention"
            layer2["summary"] = "API OK; metrics endpoint 404 (restart API)"
            break

    # Layer 3: Attention (issues)
    layer3 = {
        "status": "ok" if not issues else "needs_attention",
        "issues_count": len(issues),
        "resolved_since_last": resolved,
        "issues": [
            {"priority": i.get("priority"), "condition": i.get("condition"), "severity": i.get("severity"), "message": (i.get("message") or "")[:120]}
            for i in issues[:10]
        ],
        "summary": "No issues" if not issues else f"{len(issues)} issue(s) need attention",
    }

    # What's going well / needs attention (explicit lists for human + automation)
    going_well = []
    needs_attention = list(dict.fromkeys(i.get("condition", "") for i in issues if i.get("condition")))
    if layer0.get("status") == "ok":
        going_well.append("goal_proximity")
    if layer1.get("status") == "ok":
        going_well.append("orchestration_active")
    if layer2.get("status") == "ok":
        going_well.append("api_and_metrics")
    if layer3.get("status") == "ok":
        going_well.append("no_issues")
    elif resolved:
        going_well.append(f"resolved:{','.join(resolved[:5])}")

    overall_status = "needs_attention" if any(i["status"] == "needs_attention" for i in [layer0, layer1, layer2, layer3]) else "ok"

    return {
        "generated_at": now.isoformat(),
        "overall": {"status": overall_status, "going_well": going_well, "needs_attention": list(dict.fromkeys(needs_attention))},
        "layer_0_goal": layer0,
        "layer_1_orchestration": layer1,
        "layer_2_execution": layer2,
        "layer_3_attention": layer3,
    }


def _write_hierarchical_report(report: dict, log: logging.Logger) -> None:
    """Write report as JSON (machine) and indented text (human)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        with open(STATUS_REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception as e:
        log.debug("Could not write status report JSON: %s", e)
    # Human-readable text: hierarchical, with clear sections
    lines = [
        "=== PIPELINE STATUS REPORT ===",
        f"Generated: {report.get('generated_at', '')}",
        f"Overall: {report.get('overall', {}).get('status', 'unknown').upper()}",
        "",
        "LAYER 0: GOAL",
        f"  status: {report.get('layer_0_goal', {}).get('status', '?')}",
        f"  summary: {report.get('layer_0_goal', {}).get('summary', '')}",
        "",
        "LAYER 1: ORCHESTRATION",
        f"  status: {report.get('layer_1_orchestration', {}).get('status', '?')}",
        f"  summary: {report.get('layer_1_orchestration', {}).get('summary', '')}",
        "",
        "LAYER 2: EXECUTION",
        f"  status: {report.get('layer_2_execution', {}).get('status', '?')}",
        f"  summary: {report.get('layer_2_execution', {}).get('summary', '')}",
        "",
        "LAYER 3: ATTENTION",
        f"  status: {report.get('layer_3_attention', {}).get('status', '?')}",
        f"  summary: {report.get('layer_3_attention', {}).get('summary', '')}",
        "",
        "GOING WELL:",
    ]
    for g in report.get("overall", {}).get("going_well", []):
        lines.append(f"  - {g}")
    lines.append("NEEDS ATTENTION:")
    for n in report.get("overall", {}).get("needs_attention", []):
        lines.append(f"  - {n}")
    lines.append("===")
    try:
        with open(STATUS_REPORT_TXT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        log.debug("Could not write status report TXT: %s", e)


def _log_hierarchical_summary(report: dict, log: logging.Logger) -> None:
    """Emit hierarchical summary to monitor.log (machine parseable, human scannable)."""
    ov = report.get("overall", {})
    sym = "OK" if ov.get("status") == "ok" else "ATTENTION"
    log.info("STATUS %s | L0:%s L1:%s L2:%s L3:%s", sym, _layer_status(report, "layer_0_goal"), _layer_status(report, "layer_1_orchestration"), _layer_status(report, "layer_2_execution"), _layer_status(report, "layer_3_attention"))
    if ov.get("needs_attention"):
        for i, cond in enumerate(ov["needs_attention"][:5], 1):
            log.info("  NEEDS_ATTENTION [%d] %s", i, cond)
    if ov.get("going_well"):
        log.info("  GOING_WELL %s", ", ".join(ov["going_well"][:8]))


def _layer_status(report: dict, key: str) -> str:
    layer = report.get(key, {})
    s = layer.get("status", "?")
    return "ok" if s == "ok" else "!"


def _run_check(client: httpx.Client, log: logging.Logger, auto_fix: bool, auto_recover: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    data = _load_issues()
    prev_conditions = {i["condition"] for i in data.get("issues") or []}
    data["last_check"] = now.isoformat()
    data["issues"] = []  # fresh run; we'll repopulate

    try:
        r = client.get(f"{BASE}/api/agent/pipeline-status", timeout=10)
    except Exception as e:
        log.warning("API unreachable: %s", e)
        _add_issue(data, "api_unreachable", "high", f"API unreachable: {e}", "Restart API; check AGENT_API_BASE")
        data["resolved_since_last"] = []
        _save_issues(data)
        proc = _get_pipeline_process_args()
        eff = None
        report = _build_hierarchical_report(data, None, eff, proc, now)
        _write_hierarchical_report(report, log)
        _log_hierarchical_summary(report, log)
        return data

    # Stale version: pipeline running old code (git SHA changed)
    current_sha = _get_current_git_sha()
    if current_sha:
        try:
            if os.path.isfile(VERSION_FILE):
                with open(VERSION_FILE, encoding="utf-8") as f:
                    v = json.load(f)
                pipeline_sha = v.get("git_sha") or ""
                if pipeline_sha and pipeline_sha != current_sha:
                    action = "Restart pipeline to pick up latest code. Use run_overnight_pipeline_watchdog.sh for auto-restart."
                    auto_recover = os.environ.get("PIPELINE_AUTO_RECOVER") == "1"
                    if auto_recover:
                        _request_restart("stale_version", log)
                        action = "Restart requested (PIPELINE_AUTO_RECOVER=1). Watchdog will restart pipeline."
                    _add_issue(
                        data, "stale_version", "high",
                        f"Pipeline running old code (SHA {pipeline_sha[:8]}); current {current_sha[:8]}",
                        action,
                    )
        except Exception as ex:
            log.debug("Version check failed: %s", ex)

    if r.status_code != 200:
        _add_issue(data, "api_error", "high", f"pipeline-status returned {r.status_code}", "Check API logs")
        data["resolved_since_last"] = []
        _save_issues(data)
        proc = _get_pipeline_process_args()
        report = _build_hierarchical_report(data, None, None, proc, now)
        _write_hierarchical_report(report, log)
        _log_hierarchical_summary(report, log)
        return data

    status = r.json()
    att = status.get("attention") or {}
    running = status.get("running") or []
    pending = status.get("pending") or []
    pm = status.get("project_manager") or {}

    # No task running: pending exists but nothing running for 3+ min — ensure at least one task runs
    wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
    max_wait = max(wait_secs) if wait_secs else 0
    if pending and not running and max_wait >= NO_RUNNING_THRESHOLD_SEC:
        action = NO_TASK_RUNNING_ACTION
        # Runner likely hung: request pipeline restart when stuck 10+ min (auto_recover)
        if max_wait >= STUCK_THRESHOLD_SEC and auto_recover and os.environ.get("PIPELINE_AUTO_RECOVER") == "1":
            _request_restart("no_task_running_stuck", log)
            action = "Restart requested (runner likely hung). " + action
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor: no task running for 3+ min despite pending. Analyze why (runner dead? not polling?); debug per docs/PIPELINE-MONITORING-AUTOMATED.md; fix and restart to continue progress.",
                        "task_type": "heal",
                        "context": {"executor": "cursor"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    action = f"Created heal task {resp.json().get('id', '?')}. " + NO_TASK_RUNNING_ACTION
                    log.info("Auto-fix: created heal task for no_task_running")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "no_task_running", "high",
            f"No task running for {max_wait}s despite {len(pending)} pending. Analyze, debug, fix, restart.",
            action,
        )

    # Low phase coverage: pending exist but few tasks running (want 1+ per phase when backlog allows)
    if pending and len(running) < MIN_RUNNING_WHEN_PENDING:
        proc = _get_pipeline_process_args()
        runner_workers = proc.get("runner_workers")
        pm_parallel = proc.get("pm_parallel")
        need_workers = runner_workers is not None and runner_workers < 5
        need_parallel = pm_parallel is False
        details = []
        if runner_workers is not None:
            details.append(f"agent_runner workers={runner_workers}")
        if pm_parallel is not None:
            details.append(f"PM parallel={str(pm_parallel).lower()}")
        msg_extra = f" Process check: {', '.join(details)}." if details else ""
        action = "Ensure PIPELINE_PARALLEL=1 and --workers 5; PM should create tasks for multiple phases."
        if need_workers or need_parallel:
            action = (
                "Restart pipeline so PM runs with --parallel and agent_runner with --workers 5: "
                "cd api && ./scripts/run_overnight_pipeline.sh"
            )
            if need_workers and not need_parallel:
                action = f"agent_runner has workers={runner_workers} (need 5). " + action
            elif need_parallel and not need_workers:
                action = "PM not in --parallel mode. " + action
            elif need_workers and need_parallel:
                action = f"agent_runner workers={runner_workers}, PM not --parallel. " + action
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor: low phase coverage (few tasks running despite pending). Ensure PM is in --parallel mode and agent_runner has --workers 5. Check pipeline processes.",
                        "task_type": "heal",
                        "context": {"executor": "cursor"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    action = f"Created heal task {resp.json().get('id', '?')}. " + action
                    log.info("Auto-fix: created heal task for low_phase_coverage")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "low_phase_coverage", "medium",
            f"Only {len(running)} task(s) running despite {len(pending)} pending. Need spec/impl/test/review in parallel.{msg_extra}",
            action,
        )

    # Repeated failures
    if att.get("repeated_failures"):
        msg = "3+ consecutive failed tasks (same phase)"
        action = "Review task logs; consider heal task or model/prompt change. If root cause identified, suggest meta-pipeline item for specs/007-meta-pipeline-backlog.md."
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected repeated failures. Investigate last 3 failed tasks; suggest fix or escalate. If root cause identified, add item to specs/007-meta-pipeline-backlog.md.",
                        "task_type": "heal",
                        "context": {"executor": "cursor"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    action = f"Created heal task {resp.json().get('id', '?')}. " + action
                    log.info("Auto-fix: created heal task for repeated_failures")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(data, "repeated_failures", "high", msg, action)

    # Low success rate
    if att.get("low_success_rate"):
        action = "Review metrics; consider prompt/model A/B test"
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected low 7d success rate. Analyze metrics; suggest meta-pipeline improvements, prompt/model changes, or additions to specs/007-meta-pipeline-backlog.md.",
                        "task_type": "heal",
                        "context": {"executor": "cursor"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    action = f"Created heal task {resp.json().get('id', '?')}. " + action
                    log.info("Auto-fix: created heal task for low_success_rate")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "low_success_rate", "medium",
            "7d success rate < 80%",
            action,
        )

    # Orphan running: single running task for > 2h — fallback: PATCH to failed when auto_recover
    for r in running:
        run_sec = r.get("running_seconds")
        if run_sec is not None and run_sec > ORPHAN_RUNNING_SEC:
            tid = r.get("id")
            action = "PATCH task to failed or restart pipeline to clear"
            if auto_recover and tid:
                try:
                    pr = client.patch(
                        f"{BASE}/api/agent/tasks/{tid}",
                        json={"status": "failed", "output": f"Orphan: running > 2h (auto-recover); cleared"},
                        timeout=10,
                    )
                    if pr.status_code == 200:
                        action = f"Auto-recovered: PATCHed {tid} to failed"
                        log.info("Auto-recover: PATCHed orphan %s to failed", tid)
                except Exception as ex:
                    log.warning("Auto-recover orphan failed: %s", ex)
            _add_issue(
                data, "orphan_running", "medium",
                f"Task {tid} running > 2h (likely stale)",
                action,
            )

    # Needs decision blocked
    if pm.get("blocked"):
        _add_issue(
            data, "needs_decision", "medium",
            "PM blocked: task needs human decision",
            "Use /reply or PATCH task with decision",
        )

    # Metrics unavailable (API may need restart)
    try:
        mr = client.get(f"{BASE}/api/agent/metrics", timeout=5)
        if mr.status_code == 404:
            _add_issue(
                data, "metrics_unavailable", "low",
                "GET /api/agent/metrics returns 404",
                "Restart API to load spec 027 metrics route",
            )
    except Exception:
        pass

    # Track resolved issues for effectiveness measurement
    current_conditions = {i["condition"] for i in data["issues"]}
    resolved_this_run = prev_conditions - current_conditions
    for cond in resolved_this_run:
        _record_resolution(cond, log)
    data["resolved_since_last"] = list(resolved_this_run)

    # Sort by priority (1 = highest)
    data["issues"].sort(key=lambda i: (i.get("priority", 2), i.get("created_at", "")))

    _save_issues(data)

    # Fetch effectiveness and write hierarchical report (machine + human readable)
    effectiveness = None
    try:
        er = client.get(f"{BASE}/api/agent/effectiveness", timeout=5)
        if er.status_code == 200:
            effectiveness = er.json()
    except Exception:
        pass
    proc = _get_pipeline_process_args()
    report = _build_hierarchical_report(data, status, effectiveness, proc, now)
    _write_hierarchical_report(report, log)
    _log_hierarchical_summary(report, log)

    if data["issues"]:
        log.info("Detected %d issue(s): %s", len(data["issues"]), [i["condition"] for i in data["issues"]])
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description="Automated pipeline monitor")
    ap.add_argument("--once", action="store_true", help="Run once and exit")
    ap.add_argument("--interval", type=int, default=120, help="Seconds between checks (default 120)")
    ap.add_argument("--auto-fix", action="store_true", help="Enable auto-fix when PIPELINE_AUTO_FIX_ENABLED=1")
    ap.add_argument("--auto-recover", action="store_true", help="Enable fallback recovery when PIPELINE_AUTO_RECOVER=1")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    auto_recover = args.auto_recover or os.environ.get("PIPELINE_AUTO_RECOVER") == "1"
    log = _setup_logging(verbose=args.verbose)
    log.info("Monitor started interval=%ds auto_fix=%s auto_recover=%s", args.interval, args.auto_fix, auto_recover)

    with httpx.Client(timeout=15.0) as client:
        if args.once:
            _run_check(client, log, args.auto_fix, auto_recover)
            return
        while True:
            _run_check(client, log, args.auto_fix, auto_recover)
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
