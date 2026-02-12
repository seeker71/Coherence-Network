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
  - executor_fail: failed task with 0 output (executor crash / command not found)
  - low_success_rate: 7d rate < 80% (10+ tasks)
  - api_unreachable: pipeline-status fails
  - runner_log_errors: ERROR or "API not reachable" in agent_runner.log (last 2h)
  - orphan_running: running task > 2h (likely stale)
  - phase_6_7_not_worked: backlog has not reached Phase 6 (006); Phase 6/7 product-critical items not being worked

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
from typing import Any, Optional, Tuple

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
META_QUESTIONS_FILE = os.path.join(LOG_DIR, "meta_questions.json")
META_QUESTIONS_LAST_RUN_FILE = os.path.join(LOG_DIR, "meta_questions_last_run.json")
META_QUESTIONS_INTERVAL_SEC = 86400  # run meta-questions at most once per 24h
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


def _runner_log_has_recent_errors() -> Tuple[bool, str]:
    """Check agent_runner.log for ERROR or 'API not reachable' in last 100 lines. Returns (has_errors, sample_message)."""
    path = os.path.join(LOG_DIR, "agent_runner.log")
    if not os.path.isfile(path):
        return False, ""
    cutoff = datetime.now(timezone.utc).timestamp() - 7200  # 2 hours
    errors = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-100:]:
            line = line.strip()
            if not line:
                continue
            # Parse timestamp: "2026-02-12 02:06:11,032 INFO ..." or "2026-02-12 02:06:11,032 ERROR ..."
            parts = line.split(None, 3)
            if len(parts) >= 4:
                try:
                    ts_str = f"{parts[0]} {parts[1].split(',')[0]}"
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    ts = ts.replace(tzinfo=timezone.utc)
                    if ts.timestamp() < cutoff:
                        continue
                except (ValueError, IndexError):
                    pass
            if "ERROR" in line or "API not reachable" in line or "command not found" in line.lower():
                errors.append(line[:120])
        if errors:
            return True, errors[-1] if errors else ""
    except (OSError, IOError):
        pass
    return False, ""


def _get_pipeline_process_args() -> dict:
    """Inspect running agent_runner and project_manager. Return {runner_workers, pm_parallel, runner_seen, pm_seen}."""
    import subprocess
    result = {"runner_workers": None, "pm_parallel": None, "runner_seen": False, "pm_seen": False}
    try:
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
            if "agent_runner" in line and "python" in line and "grep" not in line:
                result["runner_seen"] = True
                parts = line.split()
                for i, p in enumerate(parts):
                    if p in ("--workers", "-w") and i + 1 < len(parts):
                        try:
                            result["runner_workers"] = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
                if result["runner_workers"] is None:
                    result["runner_workers"] = 1
                break
        for line in lines:
            if "project_manager" in line and "python" in line and "grep" not in line:
                result["pm_seen"] = True
                result["pm_parallel"] = " --parallel " in (" " + line) or line.rstrip().endswith(" --parallel")
                break
    except Exception:
        pass
    return result


def _record_resolution(
    condition: str, log: logging.Logger, heal_task_id: Optional[str] = None
) -> None:
    """Append resolution event for effectiveness measurement. Optionally attribute to heal task."""
    os.makedirs(LOG_DIR, exist_ok=True)
    record = {"condition": condition, "resolved_at": datetime.now(timezone.utc).isoformat()}
    if heal_task_id:
        record["heal_task_id"] = heal_task_id
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


def _load_meta_questions() -> Optional[dict]:
    """Load meta_questions.json if present. Returns None if missing or invalid."""
    if not os.path.isfile(META_QUESTIONS_FILE):
        return None
    try:
        with open(META_QUESTIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _run_meta_questions_if_due(log: logging.Logger) -> None:
    """Run run_meta_questions.py if last run older than META_QUESTIONS_INTERVAL_SEC (or never)."""
    now_ts = time.time()
    last_run_ts = None
    if os.path.isfile(META_QUESTIONS_LAST_RUN_FILE):
        try:
            with open(META_QUESTIONS_LAST_RUN_FILE, encoding="utf-8") as f:
                j = json.load(f)
            last_run_ts = j.get("at")
            if last_run_ts is not None:
                last_run_ts = float(last_run_ts)
        except Exception:
            pass
    if last_run_ts is not None and (now_ts - last_run_ts) < META_QUESTIONS_INTERVAL_SEC:
        return
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "run_meta_questions.py"), "--once"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "AGENT_API_BASE": BASE},
        )
        if r.returncode == 0:
            with open(META_QUESTIONS_LAST_RUN_FILE, "w", encoding="utf-8") as f:
                json.dump({"at": now_ts}, f)
            log.debug("Meta-questions checklist run completed")
        else:
            log.debug("Meta-questions script exited %s: %s", r.returncode, (r.stderr or r.stdout or "")[:200])
    except Exception as e:
        log.debug("Meta-questions script failed: %s", e)


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
    runner_seen = proc.get("runner_seen", False)
    pm_seen = proc.get("pm_seen", False)
    layer1 = {
        "status": "ok",
        "project_manager": "running" if pm_seen else ("unknown" if not pm else "not_seen"),
        "pm_in_flight": len(inf),
        "agent_runner": "running" if runner_seen else "not_seen",
        "runner_workers": proc.get("runner_workers"),
        "pm_parallel": proc.get("pm_parallel"),
        "summary": f"PM {'running' if pm_seen else 'not seen'}, runner {'workers=' + str(proc.get('runner_workers', '?')) if runner_seen else 'not seen'}",
    }
    if not runner_seen and not pm_seen:
        layer1["status"] = "needs_attention"
        layer1["summary"] = "PROCESSES: agent_runner not seen, PM not seen"
    elif not status and issues:
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

    report = {
        "generated_at": now.isoformat(),
        "overall": {"status": overall_status, "going_well": going_well, "needs_attention": list(dict.fromkeys(needs_attention))},
        "layer_0_goal": layer0,
        "layer_1_orchestration": layer1,
        "layer_2_execution": layer2,
        "layer_3_attention": layer3,
    }
    # Merge meta_questions from api/logs/meta_questions.json; surface unanswered/failed in status-report
    mq = _load_meta_questions()
    if mq:
        summary = mq.get("summary") or {}
        unanswered = summary.get("unanswered") or []
        failed = summary.get("failed") or []
        mq_status = "ok" if not unanswered and not failed else "needs_attention"
        report["meta_questions"] = {
            "status": mq_status,
            "last_run": mq.get("run_at"),
            "unanswered": unanswered,
            "failed": failed,
        }
        if mq_status == "needs_attention":
            report["overall"]["needs_attention"] = list(dict.fromkeys(report["overall"]["needs_attention"] + ["meta_questions"]))
            if report["overall"]["status"] != "needs_attention":
                report["overall"]["status"] = "needs_attention"
    return report


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
    mq = report.get("meta_questions")
    if mq:
        lines.append("META QUESTIONS:")
        lines.append(f"  status: {mq.get('status', '?')}")
        lines.append(f"  last_run: {mq.get('last_run', '')}")
        if mq.get("unanswered"):
            lines.append(f"  unanswered: {', '.join(mq['unanswered'])}")
        if mq.get("failed"):
            lines.append(f"  failed: {', '.join(mq['failed'])}")
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
    prev_issues = data.get("issues") or []
    prev_conditions = {i["condition"] for i in prev_issues}
    prev_condition_to_heal_task = {
        i["condition"]: i["heal_task_id"] for i in prev_issues if i.get("heal_task_id")
    }
    data["last_check"] = now.isoformat()
    data["issues"] = []  # fresh run; we'll repopulate

    try:
        r = client.get(f"{BASE}/api/agent/pipeline-status", timeout=10)
    except Exception as e:
        log.warning("API unreachable: %s", e)
        action = "Restart API; check AGENT_API_BASE. Use run_autonomous.sh for auto API restart."
        if auto_recover:
            _request_restart("api_unreachable", log)
            action = "Restart requested (PIPELINE_AUTO_RECOVER=1). run_autonomous.sh will restart API; watchdog restarts pipeline."
        _add_issue(data, "api_unreachable", "high", f"API unreachable: {e}", action)
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
    proc = _get_pipeline_process_args()

    # Runner and PM not seen: pipeline processes down — critical
    if not proc.get("runner_seen") and not proc.get("pm_seen"):
        action = "Start or restart pipeline: cd api && ./scripts/run_overnight_pipeline.sh (or run_autonomous.sh)"
        if auto_recover and os.environ.get("PIPELINE_AUTO_RECOVER") == "1":
            _request_restart("runner_pm_not_seen", log)
            action = "Restart requested (PIPELINE_AUTO_RECOVER=1). Watchdog will restart pipeline. " + action
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor: agent_runner and PM processes not seen. Pipeline may have crashed. Restart pipeline; check logs.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "runner_pm_not_seen"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for runner_pm_not_seen")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "runner_pm_not_seen", "high",
            "PROCESSES: agent_runner not seen, PM not seen. Pipeline processes down.",
            action,
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

    # No task running: pending exists but nothing running for 3+ min — ensure at least one task runs
    wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
    max_wait = max(wait_secs) if wait_secs else 0
    if pending and not running and max_wait >= NO_RUNNING_THRESHOLD_SEC:
        action = NO_TASK_RUNNING_ACTION
        # Runner likely hung: request pipeline restart when stuck 10+ min (auto_recover)
        if max_wait >= STUCK_THRESHOLD_SEC and auto_recover and os.environ.get("PIPELINE_AUTO_RECOVER") == "1":
            _request_restart("no_task_running_stuck", log)
            action = "Restart requested (runner likely hung). " + action
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor: no task running for 3+ min despite pending. Analyze why (runner dead? not polling?); debug per docs/PIPELINE-MONITORING-AUTOMATED.md; fix and restart to continue progress.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "no_task_running"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + NO_TASK_RUNNING_ACTION
                    log.info("Auto-fix: created heal task for no_task_running")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "no_task_running", "high",
            f"No task running for {max_wait}s despite {len(pending)} pending. Analyze, debug, fix, restart.",
            action,
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

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
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor: low phase coverage (few tasks running despite pending). Ensure PM is in --parallel mode and agent_runner has --workers 5. Check pipeline processes.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "low_phase_coverage"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for low_phase_coverage")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "low_phase_coverage", "medium",
            f"Only {len(running)} task(s) running despite {len(pending)} pending. Need spec/impl/test/review in parallel.{msg_extra}",
            action,
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

    # Repeated failures
    if att.get("repeated_failures"):
        msg = "3+ consecutive failed tasks (same phase)"
        action = "Review task logs; consider heal task or model/prompt change. If root cause identified, suggest meta-pipeline item for specs/007-meta-pipeline-backlog.md."
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected repeated failures. Investigate last 3 failed tasks; suggest fix or escalate. If root cause identified, add item to specs/007-meta-pipeline-backlog.md.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "repeated_failures"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for repeated_failures")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(data, "repeated_failures", "high", msg, action)
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

    # Output empty: completed task with 0 chars output (capture failure or silent crash)
    if att.get("output_empty"):
        action = "Agent runner now marks completed-with-zero-output as failed. Check recent task logs for capture issues; consider heal task."
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected completed task with 0 chars output. Investigate capture/stream; check agent_runner.log and task logs.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "output_empty"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for output_empty")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "output_empty", "high",
            "Recent completed task has 0 chars output (capture failure or silent crash)",
            action,
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

    # Executor fail: failed task with 0 output (executor crash, command not found)
    if att.get("executor_fail"):
        action = "Check AGENT_EXECUTOR_DEFAULT, cursor/agent path; verify executor is installed. Check agent_runner.log for 'command not found' or similar."
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected failed task with 0 output (executor crash). Check executor path, AGENT_EXECUTOR_DEFAULT; verify agent/cursor CLI is installed and in PATH. See docs/AGENT-DEBUGGING.md.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "executor_fail"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for executor_fail")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "executor_fail", "high",
            "Recent failed task has 0 output (executor crash or command not found)",
            action,
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

    # Low success rate
    if att.get("low_success_rate"):
        action = "Review metrics; consider prompt/model A/B test"
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected low 7d success rate. Analyze metrics; suggest meta-pipeline improvements, prompt/model changes, or additions to specs/007-meta-pipeline-backlog.md.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "low_success_rate"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for low_success_rate")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        _add_issue(
            data, "low_success_rate", "medium",
            "7d success rate < 80%",
            action,
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

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

    # Runner log errors: ERROR or "API not reachable" in agent_runner.log (last 2h)
    has_runner_errors, sample = _runner_log_has_recent_errors()
    if has_runner_errors:
        action = "Check AGENT_API_BASE; ensure API is running; verify runner and API use same base URL. tail -f api/logs/agent_runner.log"
        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1":
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": "Monitor detected ERROR/API unreachable in agent_runner.log. Check AGENT_API_BASE matches API URL; restart runner if needed. See docs/AGENT-DEBUGGING.md.",
                        "task_type": "heal",
                        "context": {"executor": "cursor", "monitor_condition": "runner_log_errors"},
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action = f"Created heal task {heal_task_id}. " + action
                    log.info("Auto-fix: created heal task for runner_log_errors")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)
        msg = f"Recent ERROR in agent_runner.log: {(sample[:77] + '...') if len(sample) > 80 else sample}"
        _add_issue(data, "runner_log_errors", "medium", msg, action)
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

    # Backlog alignment (spec 007 item 4): flag if Phase 6/7 items not being worked (from 006, PLAN phases)
    try:
        er = client.get(f"{BASE}/api/agent/effectiveness", timeout=5)
        if er.status_code == 200:
            eff = er.json()
            pp = (eff.get("plan_progress") or {})
            alignment = pp.get("backlog_alignment") or {}
            if alignment.get("phase_6_7_not_worked"):
                idx = pp.get("index", "?")
                total = pp.get("total", "?")
                action = (
                    "Backlog (006) has not reached Phase 6 (Product-Critical). "
                    "Prioritize advancing to item 56+ so Phase 6/7 (GitHub API, Contributor/Org, polish) get worked. "
                    "See specs/006-overnight-backlog.md and docs/PLAN.md."
                )
                _add_issue(
                    data, "phase_6_7_not_worked", "medium",
                    f"Phase 6/7 items not being worked (backlog index {idx}/{total}); product-critical work pending.",
                    action,
                )
    except Exception:
        pass

    # Track resolved issues for effectiveness measurement; attribute to heal when we have heal_task_id
    current_conditions = {i["condition"] for i in data["issues"]}
    resolved_this_run = prev_conditions - current_conditions
    for cond in resolved_this_run:
        _record_resolution(cond, log, heal_task_id=prev_condition_to_heal_task.get(cond))
    data["resolved_since_last"] = list(resolved_this_run)

    # Sort by priority (1 = highest)
    data["issues"].sort(key=lambda i: (i.get("priority", 2), i.get("created_at", "")))

    _save_issues(data)

    # Run meta-questions checklist periodically (throttled to once per META_QUESTIONS_INTERVAL_SEC)
    _run_meta_questions_if_due(log)

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
