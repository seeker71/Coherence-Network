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
  - expensive_failed_task: recent failed tasks wasted significant time (cost without gain)
  - executor_fail: failed task with 0 output (executor crash / command not found)
  - low_success_rate: 7d rate < 80% (10+ tasks)
  - api_unreachable: pipeline-status fails
  - runner_log_errors: ERROR or "API not reachable" in agent_runner.log (last 2h)
  - orphan_running: running task over stale threshold (default 30m)
  - phase_6_7_not_worked: backlog has not reached Phase 6 (006); Phase 6/7 product-critical items not being worked

Fallback: when PIPELINE_AUTO_RECOVER=1, write restart_requested (stale_version/stale_running), PATCH orphan to failed, create heal tasks.
"""

import argparse
import json
import logging
import os
import re
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
GITHUB_ACTIONS_HEALTH_FILE = os.path.join(LOG_DIR, "github_actions_health.json")
VERSION_FILE = os.path.join(LOG_DIR, "pipeline_version.json")
RESTART_FILE = os.path.join(LOG_DIR, "restart_requested.json")
META_QUESTIONS_FILE = os.path.join(LOG_DIR, "meta_questions.json")
META_QUESTIONS_LAST_RUN_FILE = os.path.join(LOG_DIR, "meta_questions_last_run.json")
META_QUESTIONS_INTERVAL_SEC = 86400  # run meta-questions at most once per 24h
MAINTAINABILITY_AUDIT_FILE = os.path.join(LOG_DIR, "maintainability_audit.json")
MAINTAINABILITY_AUDIT_LAST_RUN_FILE = os.path.join(LOG_DIR, "maintainability_audit_last_run.json")
MAINTAINABILITY_AUDIT_INTERVAL_SEC = 43200  # run maintainability audit at most once per 12h
PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE = os.path.join(LOG_DIR, "public_deploy_contract_block_state.json")
PROJECT_ROOT = os.path.dirname(_api_dir)

# Priority order: 1 = highest (address first)
SEVERITY_TO_PRIORITY = {"high": 1, "medium": 2, "low": 3}

STUCK_THRESHOLD_SEC = 600   # 10 min
NO_RUNNING_THRESHOLD_SEC = 180  # 3 min — raise issue if pending but no task running
try:
    ORPHAN_RUNNING_SEC = max(
        60,
        int(
            os.environ.get(
                "PIPELINE_ORPHAN_RUNNING_SECONDS",
                os.environ.get("PIPELINE_STALE_RUNNING_SECONDS", "1800"),
            )
        ),
    )
except (TypeError, ValueError):
    ORPHAN_RUNNING_SEC = 1800
LOW_SUCCESS_RATE = 0.80
MIN_TASKS_FOR_RATE = 10
MIN_RUNNING_WHEN_PENDING = 2  # expect at least 2 tasks running when we have pending (phase coverage)
EXPENSIVE_FAIL_LOOKBACK_SEC = int(os.environ.get("PIPELINE_EXPENSIVE_FAIL_LOOKBACK_SEC", "7200"))  # 2h
EXPENSIVE_FAIL_THRESHOLD_SEC = float(os.environ.get("PIPELINE_EXPENSIVE_FAIL_THRESHOLD_SEC", "120"))  # 2m
GITHUB_ACTIONS_FAIL_RATE_THRESHOLD = float(os.environ.get("GITHUB_ACTIONS_FAIL_RATE_THRESHOLD", "0.35"))
GITHUB_ACTIONS_MIN_COMPLETED = int(os.environ.get("GITHUB_ACTIONS_MIN_COMPLETED", "8"))
GITHUB_ACTIONS_LOOKBACK_DAYS = int(os.environ.get("GITHUB_ACTIONS_LOOKBACK_DAYS", "7"))

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


def _env_to_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


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


def _load_public_deploy_contract_state() -> dict[str, Any]:
    if not os.path.isfile(PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE):
        return {}
    try:
        with open(PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _save_public_deploy_contract_state(state: dict[str, Any]) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _clear_public_deploy_contract_state() -> None:
    if os.path.isfile(PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE):
        try:
            os.remove(PUBLIC_DEPLOY_CONTRACT_BLOCK_STATE_FILE)
        except OSError:
            return


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


def _github_repo_slug() -> str:
    repo = str(os.environ.get("GITHUB_REPOSITORY", "")).strip()
    if repo and "/" in repo:
        return repo
    try:
        import subprocess

        raw = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return ""
    url = (raw.stdout or "").strip()
    if not url:
        return ""
    # Supports:
    # - git@github.com:owner/repo.git
    # - https://github.com/owner/repo.git
    # - https://github.com/owner/repo
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", url)
    if not match:
        return ""
    return f"{match.group('owner')}/{match.group('repo')}"


def _parse_ts_iso(raw: str | None) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _collect_github_actions_health(log: logging.Logger) -> dict[str, Any]:
    health: dict[str, Any] = {
        "provider": "github-actions",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "available": False,
        "repo": "",
        "lookback_days": GITHUB_ACTIONS_LOOKBACK_DAYS,
        "completed_runs": 0,
        "failed_runs": 0,
        "failure_rate": 0.0,
        "wasted_minutes_failed": 0.0,
        "top_failed_workflows": [],
        "sample_failed_run_links": [],
        "official_records": [
            "https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository",
        ],
        "note": "",
    }
    repo = _github_repo_slug()
    health["repo"] = repo
    if not repo:
        health["note"] = "missing repo slug; set GITHUB_REPOSITORY=owner/repo or configure git remote origin"
        return health

    try:
        import subprocess

        probe = subprocess.run(
            ["gh", "auth", "status"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if probe.returncode != 0:
            health["note"] = "gh auth not available"
            return health
        args = [
            "gh",
            "api",
            f"repos/{repo}/actions/runs",
            "-f",
            "per_page=100",
        ]
        response = subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        health["note"] = f"gh api failed to execute: {exc}"
        return health

    if response.returncode != 0:
        health["note"] = f"gh api error: {(response.stderr or response.stdout or '').strip()[:200]}"
        return health

    try:
        payload = json.loads(response.stdout or "{}")
    except json.JSONDecodeError:
        health["note"] = "gh api returned invalid json"
        return health

    rows = payload.get("workflow_runs") if isinstance(payload, dict) else []
    runs = rows if isinstance(rows, list) else []
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - max(1, GITHUB_ACTIONS_LOOKBACK_DAYS) * 86400
    failed_conclusions = {"failure", "timed_out", "cancelled", "startup_failure", "stale", "action_required"}
    completed = 0
    failed = 0
    wasted_seconds = 0.0
    failed_workflow_counts: dict[str, int] = {}
    failed_links: list[str] = []

    for run in runs:
        if not isinstance(run, dict):
            continue
        created_at = _parse_ts_iso(run.get("created_at"))
        if created_at is None or created_at.timestamp() < cutoff:
            continue
        status = str(run.get("status") or "").strip().lower()
        if status != "completed":
            continue
        completed += 1
        conclusion = str(run.get("conclusion") or "").strip().lower()
        if conclusion not in failed_conclusions:
            continue
        failed += 1
        name = str(run.get("name") or "unknown_workflow")
        failed_workflow_counts[name] = failed_workflow_counts.get(name, 0) + 1
        html_url = str(run.get("html_url") or "").strip()
        if html_url and len(failed_links) < 3:
            failed_links.append(html_url)
        started = _parse_ts_iso(run.get("run_started_at"))
        updated = _parse_ts_iso(run.get("updated_at"))
        if started and updated:
            wasted_seconds += max(0.0, (updated - started).total_seconds())

    health["available"] = True
    health["completed_runs"] = completed
    health["failed_runs"] = failed
    health["failure_rate"] = round((failed / completed), 4) if completed > 0 else 0.0
    health["wasted_minutes_failed"] = round(wasted_seconds / 60.0, 2)
    health["top_failed_workflows"] = [
        {"workflow": name, "failed_runs": count}
        for name, count in sorted(failed_workflow_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    ]
    health["sample_failed_run_links"] = failed_links
    health["official_records"].append(f"https://github.com/{repo}/actions")
    health["official_records"].append(f"https://api.github.com/repos/{repo}/actions/runs")
    return health


def _load_recent_failed_task_durations(now: datetime) -> list[dict]:
    """Scan local api/logs/metrics.jsonl for recent failed tasks with durations."""
    metrics_file = os.path.join(LOG_DIR, "metrics.jsonl")
    if not os.path.isfile(metrics_file):
        return []
    cutoff = now.timestamp() - max(60, int(EXPENSIVE_FAIL_LOOKBACK_SEC))
    out: list[dict] = []
    try:
        with open(metrics_file, encoding="utf-8") as f:
            for line in f:
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("status") != "failed":
                    continue
                created_at = rec.get("created_at") or ""
                try:
                    ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                dur = rec.get("duration_seconds")
                if not isinstance(dur, (int, float)):
                    continue
                out.append(
                    {
                        "task_id": rec.get("task_id", ""),
                        "task_type": rec.get("task_type", ""),
                        "model": rec.get("model", ""),
                        "duration_seconds": float(dur),
                        "created_at": created_at,
                    }
                )
    except (OSError, IOError):
        return []
    out.sort(key=lambda r: float(r.get("duration_seconds") or 0.0), reverse=True)
    return out


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


def _load_maintainability_audit() -> Optional[dict]:
    if not os.path.isfile(MAINTAINABILITY_AUDIT_FILE):
        return None
    try:
        with open(MAINTAINABILITY_AUDIT_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except Exception:
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


def _run_maintainability_audit_if_due(log: logging.Logger) -> Optional[dict]:
    now_ts = time.time()
    last_run_ts = None
    if os.path.isfile(MAINTAINABILITY_AUDIT_LAST_RUN_FILE):
        try:
            with open(MAINTAINABILITY_AUDIT_LAST_RUN_FILE, encoding="utf-8") as f:
                j = json.load(f)
            val = j.get("at")
            if val is not None:
                last_run_ts = float(val)
        except Exception:
            pass
    if last_run_ts is not None and (now_ts - last_run_ts) < MAINTAINABILITY_AUDIT_INTERVAL_SEC:
        return _load_maintainability_audit()

    try:
        import subprocess

        r = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "run_maintainability_audit.py"),
                "--json",
                "--output",
                MAINTAINABILITY_AUDIT_FILE,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
            env=os.environ.copy(),
        )
        if r.returncode == 0:
            with open(MAINTAINABILITY_AUDIT_LAST_RUN_FILE, "w", encoding="utf-8") as f:
                json.dump({"at": now_ts}, f)
            log.debug("Maintainability audit run completed")
        else:
            log.debug(
                "Maintainability audit exited %s: %s",
                r.returncode,
                (r.stderr or r.stdout or "")[:200],
            )
    except Exception as e:
        log.debug("Maintainability audit run failed: %s", e)
    return _load_maintainability_audit()


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
    effectiveness = None  # filled by backlog-alignment fetch or report fetch below
    contract_block_state = _load_public_deploy_contract_state()

    # Public deploy contract health: escalate if blocked long enough to avoid burning effort on unstable releases.
    try:
        contract_resp = client.get(f"{BASE}/api/gates/public-deploy-contract", timeout=10)
        if contract_resp.status_code == 200:
            contract_payload = contract_resp.json()
        else:
            contract_payload = {
                "result": "blocked",
                "reason": f"public_deploy_contract endpoint status_code={contract_resp.status_code}",
            }
    except Exception as ex:
        log.debug("Could not check public deploy contract: %s", ex)
        contract_payload = {}
    contract_result = str(contract_payload.get("result") or "blocked").strip().lower()
    contract_blocked = contract_result != "public_contract_passed"

    if contract_result == "public_contract_passed":
        _clear_public_deploy_contract_state()
    elif contract_blocked:
        now_iso = now.isoformat()
        blocked_since = str(contract_block_state.get("blocked_since", "")).strip()
        if not blocked_since:
            blocked_since = now_iso
        contract_block_state.update(
            blocked_since=blocked_since,
            last_checked=now_iso,
            last_status=contract_payload.get("result"),
            failing_checks=contract_payload.get("failing_checks"),
        )
        _save_public_deploy_contract_state(contract_block_state)
        threshold = _env_to_int("PUBLIC_DEPLOY_CONTRACT_BLOCK_THRESHOLD_SECONDS", 600)
        started_ts = _parse_ts_iso(contract_block_state.get("blocked_since"))
        blocked_seconds = (now - started_ts).total_seconds() if started_ts else 0.0
        if blocked_seconds >= threshold:
            fail_checks = contract_payload.get("failing_checks") or []
            checks_hint = ""
            if isinstance(fail_checks, list) and fail_checks:
                checks_hint = f" Failing checks: {', '.join(str(item) for item in fail_checks[:5])}."
            condition = "public_deploy_contract_blocked"
            action = (
                "Stop rollout actions, investigate contract blockers immediately, and execute rollback/recovery plan "
                "before resuming tasks."
            ) + checks_hint
            heal_task_id = None
            can_auto_fix = (
                auto_fix
                and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1"
                and condition not in prev_conditions
            )
            if can_auto_fix:
                try:
                    resp = client.post(
                        f"{BASE}/api/agent/tasks",
                        json={
                            "direction": (
                                "Monitor detected public deploy contract blocked beyond escalation threshold. "
                                "Pause rollout, investigate failing deploy checks, and execute rollback/recovery if needed."
                            ),
                            "task_type": "heal",
                            "context": {
                                "executor": "cursor",
                                "monitor_condition": "public_deploy_contract_blocked",
                            },
                        },
                        timeout=10,
                    )
                    if resp.status_code == 201:
                        heal_task_id = resp.json().get("id")
                        action = f"Created heal task {heal_task_id}. " + action
                        log.info("Auto-fix: created heal task for public_deploy_contract_blocked")
                except Exception as e:
                    log.warning("Auto-fix heal task failed: %s", e)
            _add_issue(
                data,
                condition,
                "high",
                f"Public deploy contract blocked for ~{int(blocked_seconds)}s. Escalate before release proceeds. "
                f"First check: {contract_payload.get('result', 'blocked')}.",
                action,
            )
            if heal_task_id:
                data["issues"][-1]["heal_task_id"] = heal_task_id

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

    # Expensive failed tasks: cost without gain (time burned on failures).
    recent_failed = _load_recent_failed_task_durations(now)
    expensive = [
        r
        for r in recent_failed
        if float(r.get("duration_seconds") or 0.0) >= float(EXPENSIVE_FAIL_THRESHOLD_SEC)
    ]
    if expensive:
        top = expensive[:3]
        msg = "Recent failed tasks wasted significant time: " + ", ".join(
            f"{r.get('task_id','?')}({round(float(r.get('duration_seconds') or 0.0),1)}s)" for r in top
        )
        action = (
            "Inspect task logs for these failures; fix root cause (auth/deps/tooling). "
            "If recurring, add a meta-pipeline item to prevent future waste."
        )
        _add_issue(data, "expensive_failed_task", "high", msg, action)

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

    # Orphan running: one or more running tasks over stale threshold (default 30m).
    stale_running: list[dict[str, Any]] = []
    for r in running:
        run_sec = r.get("running_seconds")
        if run_sec is None:
            continue
        try:
            run_sec_num = float(run_sec)
        except (TypeError, ValueError):
            continue
        if run_sec_num > ORPHAN_RUNNING_SEC:
            stale_running.append({"id": r.get("id"), "running_seconds": run_sec_num})

    if stale_running:
        stale_ids = [str(row.get("id") or "").strip() for row in stale_running if str(row.get("id") or "").strip()]
        stale_minutes = max(1, int(round(ORPHAN_RUNNING_SEC / 60)))
        longest_sec = int(max((row.get("running_seconds") or 0.0) for row in stale_running))
        action_parts: list[str] = []
        healed_ids: list[str] = []

        if auto_recover:
            for tid in stale_ids:
                try:
                    pr = client.patch(
                        f"{BASE}/api/agent/tasks/{tid}",
                        json={
                            "status": "failed",
                            "output": (
                                f"Orphan: running exceeded stale threshold "
                                f"{ORPHAN_RUNNING_SEC}s (~{stale_minutes}m); auto-recovered"
                            ),
                        },
                        timeout=10,
                    )
                    if pr.status_code == 200:
                        healed_ids.append(tid)
                        log.info("Auto-recover: PATCHed orphan %s to failed", tid)
                except Exception as ex:
                    log.warning("Auto-recover orphan failed: %s", ex)
            _request_restart("stale_running_orphan", log)
            action_parts.append(
                "Restart requested (PIPELINE_AUTO_RECOVER=1). Watchdog will restart pipeline."
            )
            if healed_ids:
                preview = ", ".join(healed_ids[:5])
                if len(healed_ids) > 5:
                    preview += ", ..."
                action_parts.append(f"Auto-recovered stale tasks by PATCH to failed: {preview}.")

        heal_task_id = None
        if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1" and "orphan_running" not in prev_conditions:
            try:
                resp = client.post(
                    f"{BASE}/api/agent/tasks",
                    json={
                        "direction": (
                            "Monitor detected stale running tasks older than threshold. "
                            "Investigate runner deadlock/orphaned claims, clear stale tasks, and ensure pipeline resumes."
                        ),
                        "task_type": "heal",
                        "context": {
                            "executor": "cursor",
                            "monitor_condition": "orphan_running",
                            "stale_threshold_seconds": ORPHAN_RUNNING_SEC,
                            "stale_task_count": len(stale_running),
                        },
                    },
                    timeout=10,
                )
                if resp.status_code == 201:
                    heal_task_id = resp.json().get("id")
                    action_parts.append(f"Created heal task {heal_task_id}.")
                    log.info("Auto-fix: created heal task for orphan_running")
            except Exception as e:
                log.warning("Auto-fix heal task failed: %s", e)

        if not action_parts:
            action_parts.append("PATCH stale task(s) to failed or restart pipeline to clear orphaned runs.")

        stale_preview = ", ".join(stale_ids[:5]) if stale_ids else "unknown"
        if len(stale_ids) > 5:
            stale_preview += ", ..."
        _add_issue(
            data,
            "orphan_running",
            "high",
            (
                f"{len(stale_running)} running task(s) exceeded stale threshold "
                f"{ORPHAN_RUNNING_SEC}s (~{stale_minutes}m); longest={longest_sec}s; ids={stale_preview}"
            ),
            " ".join(action_parts),
        )
        if heal_task_id:
            data["issues"][-1]["heal_task_id"] = heal_task_id

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

    # GitHub Actions failure-rate tracking: reduce wasted CI runs when failure rates spike.
    gha_health = _collect_github_actions_health(log)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(GITHUB_ACTIONS_HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(gha_health, f, indent=2)
    except Exception as ex:
        log.debug("Could not write github actions health file: %s", ex)

    if gha_health.get("available"):
        completed_runs = int(gha_health.get("completed_runs") or 0)
        failed_runs = int(gha_health.get("failed_runs") or 0)
        failure_rate = float(gha_health.get("failure_rate") or 0.0)
        if completed_runs >= GITHUB_ACTIONS_MIN_COMPLETED and failure_rate >= GITHUB_ACTIONS_FAIL_RATE_THRESHOLD:
            wasted_minutes = float(gha_health.get("wasted_minutes_failed") or 0.0)
            action = (
                "Review recent failed GitHub Actions runs and fix the highest-frequency workflow first. "
                "Reduce repeated failures before adding more CI workload."
            )
            links = gha_health.get("sample_failed_run_links") if isinstance(gha_health.get("sample_failed_run_links"), list) else []
            if links:
                action = f"{action} Runs: {' | '.join(str(url) for url in links[:3])}"
            heal_task_id = None
            if (
                auto_fix
                and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1"
                and "github_actions_high_failure_rate" not in prev_conditions
            ):
                try:
                    resp = client.post(
                        f"{BASE}/api/agent/tasks",
                        json={
                            "direction": (
                                "Monitor detected high GitHub Actions failure rate. Triage failing workflows, "
                                "fix root causes, and re-run checks to reduce CI waste."
                            ),
                            "task_type": "heal",
                            "context": {
                                "executor": "cursor",
                                "monitor_condition": "github_actions_high_failure_rate",
                                "repo": gha_health.get("repo"),
                                "completed_runs": completed_runs,
                                "failed_runs": failed_runs,
                                "failure_rate": failure_rate,
                                "wasted_minutes_failed": wasted_minutes,
                            },
                        },
                        timeout=10,
                    )
                    if resp.status_code == 201:
                        heal_task_id = resp.json().get("id")
                        action = f"Created heal task {heal_task_id}. " + action
                        log.info("Auto-fix: created heal task for github_actions_high_failure_rate")
                except Exception as e:
                    log.warning("Auto-fix heal task failed: %s", e)
            _add_issue(
                data,
                "github_actions_high_failure_rate",
                "high" if failure_rate >= 0.5 else "medium",
                (
                    f"GitHub Actions failure rate {round(failure_rate * 100.0, 1)}% "
                    f"({failed_runs}/{completed_runs} completed runs, "
                    f"wasted_minutes_failed={round(wasted_minutes, 2)})."
                ),
                action,
            )
            if heal_task_id:
                data["issues"][-1]["heal_task_id"] = heal_task_id

    # Backlog alignment (spec 007 item 4): flag if Phase 6/7 items not being worked (from 006, PLAN phases)
    # Also: effectiveness 404 means API has stale routes — request restart so watchdog restarts API
    try:
        er = client.get(f"{BASE}/api/agent/effectiveness", timeout=5)
        if er.status_code == 404 and auto_recover and os.environ.get("PIPELINE_AUTO_RECOVER") == "1":
            _request_restart("effectiveness_404", log)
            _add_issue(
                data, "effectiveness_404", "high",
                "GET /api/agent/effectiveness returned 404 — API has stale routes (restart to load current code).",
                "Restart requested. Watchdog will restart API.",
            )
        elif er.status_code == 200:
            effectiveness = er.json()
            pp = (effectiveness.get("plan_progress") or {})
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

    # Maintainability architecture + placeholder audit (scheduled within monitor loop).
    maintainability = _run_maintainability_audit_if_due(log)
    if isinstance(maintainability, dict):
        summary = maintainability.get("summary") if isinstance(maintainability.get("summary"), dict) else {}
        baseline = maintainability.get("baseline") if isinstance(maintainability.get("baseline"), dict) else {}
        recommended = (
            maintainability.get("recommended_tasks")
            if isinstance(maintainability.get("recommended_tasks"), list)
            else []
        )
        risk_score = int(summary.get("risk_score") or 0)
        severity = str(summary.get("severity") or "low").lower()
        regression = bool(summary.get("regression"))
        blocking_gap = bool(summary.get("blocking_gap"))
        placeholder_count = int(summary.get("placeholder_count") or 0)
        baseline_placeholder = int(baseline.get("max_placeholder_count") or 0)
        placeholder_regressed = placeholder_count > baseline_placeholder

        if regression or blocking_gap:
            action = (
                "Run maintainability cleanup before adding new features. "
                "Review api/logs/maintainability_audit.json and execute the top ROI recommendation."
            )
            heal_task_id = None
            if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1" and "architecture_maintainability_drift" not in prev_conditions:
                direction = (
                    "Monitor detected maintainability drift. Refactor architecture hotspots and reduce complexity "
                    "before new feature work. Re-run maintainability audit and update baseline only after verified improvements."
                )
                if recommended and isinstance(recommended[0], dict):
                    top = recommended[0]
                    direction = (
                        f"{top.get('title', 'Maintainability cleanup')}: {top.get('direction', direction)} "
                        f"(estimated_cost_hours={top.get('estimated_cost_hours')}, "
                        f"value_to_whole={top.get('value_to_whole')}, roi_estimate={top.get('roi_estimate')})."
                    )
                try:
                    resp = client.post(
                        f"{BASE}/api/agent/tasks",
                        json={
                            "direction": direction,
                            "task_type": "heal",
                            "context": {
                                "executor": "cursor",
                                "monitor_condition": "architecture_maintainability_drift",
                                "risk_score": risk_score,
                                "severity": severity,
                                "regression": regression,
                            },
                        },
                        timeout=10,
                    )
                    if resp.status_code == 201:
                        heal_task_id = resp.json().get("id")
                        action = f"Created heal task {heal_task_id}. " + action
                        log.info("Auto-fix: created heal task for architecture_maintainability_drift")
                except Exception as e:
                    log.warning("Auto-fix heal task failed: %s", e)
            _add_issue(
                data,
                "architecture_maintainability_drift",
                "high" if blocking_gap else "medium",
                (
                    f"Maintainability audit drift detected (risk_score={risk_score}, severity={severity}, "
                    f"regression={str(regression).lower()})."
                ),
                action,
            )
            if heal_task_id:
                data["issues"][-1]["heal_task_id"] = heal_task_id

        if placeholder_regressed:
            action = (
                "Runtime placeholder/mock markers increased beyond baseline. "
                "Replace with production-grade implementation or tracked backlog items."
            )
            heal_task_id = None
            if auto_fix and os.environ.get("PIPELINE_AUTO_FIX_ENABLED") == "1" and "runtime_placeholder_debt" not in prev_conditions:
                try:
                    resp = client.post(
                        f"{BASE}/api/agent/tasks",
                        json={
                            "direction": (
                                "Monitor detected new runtime placeholder/mock debt. Remove fake/mock/stub runtime markers "
                                "and validate with maintainability audit."
                            ),
                            "task_type": "heal",
                            "context": {
                                "executor": "cursor",
                                "monitor_condition": "runtime_placeholder_debt",
                                "placeholder_count": placeholder_count,
                                "baseline_placeholder_count": baseline_placeholder,
                            },
                        },
                        timeout=10,
                    )
                    if resp.status_code == 201:
                        heal_task_id = resp.json().get("id")
                        action = f"Created heal task {heal_task_id}. " + action
                        log.info("Auto-fix: created heal task for runtime_placeholder_debt")
                except Exception as e:
                    log.warning("Auto-fix heal task failed: %s", e)
            _add_issue(
                data,
                "runtime_placeholder_debt",
                "high",
                (
                    f"Runtime placeholder/mock findings increased (current={placeholder_count}, "
                    f"baseline={baseline_placeholder})."
                ),
                action,
            )
            if heal_task_id:
                data["issues"][-1]["heal_task_id"] = heal_task_id

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

    # Fetch effectiveness for report if not already from backlog-alignment check
    if effectiveness is None:
        try:
            er = client.get(f"{BASE}/api/agent/effectiveness", timeout=5)
            if er.status_code == 404 and auto_recover and os.environ.get("PIPELINE_AUTO_RECOVER") == "1":
                _request_restart("effectiveness_404", log)
            elif er.status_code == 200:
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
