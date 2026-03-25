#!/usr/bin/env python3
"""Coherence Network local runner — join the network from any machine.

Registers this machine as a federation node, auto-detects providers,
picks tasks, executes them via Thompson Sampling, and pushes measurements.

Usage:
  python scripts/local_runner.py --timeout 300
  python scripts/local_runner.py --timeout 300 --loop --interval 120
  python scripts/local_runner.py --dry-run
  python scripts/local_runner.py --stats
"""

import hashlib
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Ensure Gemini CLI can authenticate via Google Cloud Auth (browser OAuth).
# This must be set before the subprocess inherits the environment.
os.environ.setdefault("GOOGLE_GENAI_USE_GCA", "true")

# Force UTF-8 for subprocess I/O on Windows (avoids cp1252 decode errors from
# provider CLIs that emit non-ASCII output like emoji or Unicode box-drawing).
os.environ.setdefault("PYTHONUTF8", "1")

# Ensure WinGet-installed tools (e.g. ripgrep) are on PATH for providers that need them.
_WINGET_LINKS = os.path.expanduser("~/AppData/Local/Microsoft/WinGet/Links")
if os.path.isdir(_WINGET_LINKS) and _WINGET_LINKS not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _WINGET_LINKS + os.pathsep + os.environ.get("PATH", "")

# Resolve paths — this script lives at repo_root/scripts/
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_DIR = _SCRIPT_DIR.parent
_API_DIR = _REPO_DIR / "api"

# Make api/scripts importable so we can delegate to the existing runner
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))
if str(_API_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(_API_DIR / "scripts"))

import local_runner as _runner  # noqa: E402 — api/scripts/local_runner.py

log = logging.getLogger("node_runner")

API_BASE = os.environ.get("AGENT_API_BASE", "https://api.coherencycoin.com")
API_KEY = os.environ.get("COHERENCE_API_KEY", "dev-key")
_HTTP_CLIENT = httpx.Client(timeout=30.0)


def _get_git_info() -> dict[str, str]:
    """Get git version info for this node."""
    repo = str(Path(__file__).resolve().parent.parent)
    info = {"local_sha": "unknown", "origin_sha": "unknown", "branch": "unknown", "dirty": "unknown", "repo": repo}
    git = "/usr/bin/git"  # Use absolute path — launchd may not have git on PATH
    if not os.path.exists(git):
        git = "git"  # Fallback
    try:
        r = subprocess.run([git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5, cwd=repo)
        if r.returncode == 0:
            info["local_sha"] = r.stdout.strip()
        subprocess.run([git, "fetch", "origin", "main", "--quiet"], capture_output=True, timeout=15, cwd=repo)
        r = subprocess.run([git, "rev-parse", "--short", "origin/main"], capture_output=True, text=True, timeout=5, cwd=repo)
        if r.returncode == 0:
            info["origin_sha"] = r.stdout.strip()
        r = subprocess.run([git, "branch", "--show-current"], capture_output=True, text=True, timeout=5, cwd=repo)
        if r.returncode == 0:
            info["branch"] = r.stdout.strip()
        r = subprocess.run([git, "status", "--porcelain"], capture_output=True, text=True, timeout=5, cwd=repo)
        info["dirty"] = "yes" if r.stdout.strip() else "no"
        info["up_to_date"] = "yes" if info["local_sha"] == info["origin_sha"] else "no"
    except Exception as e:
        info["error"] = str(e)
    # Debug: write git info to a temp file so we can diagnose launchd issues
    try:
        Path("/tmp/coherence-git-debug.txt").write_text(
            f"repo={info.get('repo')}\n"
            f"local_sha={info.get('local_sha')}\n"
            f"origin_sha={info.get('origin_sha')}\n"
            f"error={info.get('error','none')}\n"
            f"git_binary={git}\n"
            f"git_exists={os.path.exists(git) if isinstance(git, str) else 'N/A'}\n"
        )
    except Exception:
        pass
    return info


NODE_GIT = _get_git_info()
NODE_SHA = NODE_GIT.get("local_sha", "unknown")


# ── Node identity ─────────────────────────────────────────────────────

def _get_mac_address() -> str:
    """Get a stable MAC address string for node ID generation."""
    mac = uuid.getnode()
    return ":".join(f"{(mac >> i) & 0xFF:02x}" for i in range(0, 48, 8))


def _generate_node_id() -> str:
    """Stable, persistent node ID — same algorithm as api/scripts/local_runner.py.

    Persisted to ~/.coherence-network/node_id so it never changes.
    Generated from hostname:os_type on first run.
    """
    id_file = Path(os.path.expanduser("~")) / ".coherence-network" / "node_id"
    if id_file.exists():
        stored = id_file.read_text().strip()
        if stored:
            return stored

    hostname = socket.gethostname()
    os_type = _detect_os_type()
    raw = f"{hostname}:{os_type}"
    node_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

    id_file.parent.mkdir(parents=True, exist_ok=True)
    id_file.write_text(node_id)
    log.info("NODE_ID generated and persisted: %s → %s", raw, node_id)
    return node_id


def _detect_os_type() -> str:
    """Detect OS type for node registration."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return system


# ── Federation API calls ──────────────────────────────────────────────

def _api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    """Call federation API. Write methods include X-API-Key header."""
    url = f"{API_BASE}{path}"
    headers = {"X-API-Key": API_KEY} if method in ("POST", "PATCH", "PUT", "DELETE") else {}
    try:
        if method == "GET":
            resp = _HTTP_CLIENT.get(url)
        elif method == "POST":
            resp = _HTTP_CLIENT.post(url, json=body, headers=headers)
        elif method == "PATCH":
            resp = _HTTP_CLIENT.patch(url, json=body, headers=headers)
        elif method == "DELETE":
            resp = _HTTP_CLIENT.delete(url, headers=headers)
        else:
            return None
        if resp.status_code >= 400:
            if resp.status_code in (404, 409):
                log.info("API %s %s → %d (expected)", method, path, resp.status_code)
            elif resp.status_code >= 500 or resp.status_code == 429:
                log.warning("API %s %s → %d (server/rate): %s", method, path, resp.status_code, resp.text[:100])
            else:
                log.error("API %s %s → %d: %s", method, path, resp.status_code, resp.text[:200])
            return None
        if not resp.text.strip():
            return None
        return resp.json()
    except Exception as e:
        log.warning("API %s %s network error: %s", method, path, e)
        return None


def register_node(node_id: str, providers: list[str]) -> bool:
    """Register this machine as a federation node."""
    body = {
        "node_id": node_id,
        "hostname": socket.gethostname(),
        "os_type": _detect_os_type(),
        "providers": providers,
        "capabilities": {
            "executors": providers,
            "tools": _detect_tools(),
            "hardware": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python": platform.python_version(),
            },
            "git": NODE_GIT,
        },
    }
    result = _api("POST", "/api/federation/nodes?refresh_capabilities=true", body)
    if result:
        log.info("NODE REGISTERED node_id=%s sha=%s origin=%s up_to_date=%s",
                 node_id, NODE_GIT.get("local_sha"), NODE_GIT.get("origin_sha"),
                 NODE_GIT.get("up_to_date"))
        return True
    log.warning("NODE REGISTRATION FAILED node_id=%s (hub may be unreachable)", node_id)
    return False


def heartbeat(node_id: str, providers: list[str]) -> bool:
    """Send heartbeat to refresh liveness."""
    body = {
        "capabilities": {
            "executors": providers,
            "tools": _detect_tools(),
        },
    }
    result = _api("POST", f"/api/federation/nodes/{node_id}/heartbeat", body)
    if result:
        log.debug("HEARTBEAT ok node_id=%s", node_id)
        return True
    return False


# Track last-pushed sample counts per (decision_point, slot_id) to send deltas only.
_last_pushed_samples: dict[str, int] = {}


def push_measurements(node_id: str) -> int:
    """Push local slot measurements to the federation hub.

    Reads from api/logs/slot_measurements/ and aggregates into
    MeasurementSummary payloads per (decision_point, slot_id).

    Only sends deltas (new samples since last push) to avoid inflating
    cumulative counts on the stats endpoint.
    """
    measurements_dir = _API_DIR / "logs" / "slot_measurements"
    if not measurements_dir.exists():
        return 0

    now = datetime.now(timezone.utc)
    summaries = []

    for f in measurements_dir.glob("*.json"):
        decision_point = f.stem
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(data, list) or not data:
            continue

        # Group by slot_id
        by_slot: dict[str, list[dict]] = {}
        for entry in data:
            slot_id = entry.get("slot_id", "unknown")
            by_slot.setdefault(slot_id, []).append(entry)

        for slot_id, entries in by_slot.items():
            total_count = len(entries)
            tracker_key = f"{decision_point}|{slot_id}"
            last_count = _last_pushed_samples.get(tracker_key, 0)
            delta = total_count - last_count

            if delta <= 0:
                continue

            # Only compute stats over the new (delta) entries
            new_entries = entries[last_count:]
            successes = sum(1 for e in new_entries if e.get("value_score", 0) >= 0.5)
            failures = len(new_entries) - successes
            durations = [e["duration_s"] for e in new_entries if "duration_s" in e]
            mean_duration = sum(durations) / len(durations) if durations else None
            value_scores = [e.get("value_score", 0) for e in new_entries]
            mean_value = sum(value_scores) / len(value_scores) if value_scores else 0.0

            error_classes: dict[str, int] = {}
            for e in new_entries:
                ec = e.get("error_class")
                if ec:
                    error_classes[ec] = error_classes.get(ec, 0) + 1

            timestamps = []
            for e in new_entries:
                ts = e.get("timestamp")
                if ts:
                    try:
                        timestamps.append(datetime.fromisoformat(ts))
                    except Exception:
                        pass

            period_start = min(timestamps) if timestamps else now
            period_end = max(timestamps) if timestamps else now

            summaries.append({
                "node_id": node_id,
                "decision_point": decision_point,
                "slot_id": slot_id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "sample_count": delta,
                "successes": successes,
                "failures": failures,
                "mean_duration_s": mean_duration,
                "mean_value_score": round(mean_value, 4),
                "error_classes_json": error_classes,
                "_total_count": total_count,  # internal: for updating tracker on success
                "_tracker_key": tracker_key,  # internal: for updating tracker on success
            })

    if not summaries:
        return 0

    # Strip internal keys before sending
    payload_summaries = [
        {k: v for k, v in s.items() if not k.startswith("_")}
        for s in summaries
    ]

    result = _api("POST", f"/api/federation/nodes/{node_id}/measurements", {
        "summaries": payload_summaries,
    })
    if result:
        # Update tracker only after successful push
        for s in summaries:
            _last_pushed_samples[s["_tracker_key"]] = s["_total_count"]
        stored = result.get("stored", len(payload_summaries))
        log.info("MEASUREMENTS PUSHED node_id=%s count=%d stored=%d", node_id, len(payload_summaries), stored)
        return stored
    log.warning("MEASUREMENT PUSH FAILED node_id=%s", node_id)
    return 0


_MAX_RETRIES_PER_IDEA_PHASE = 2


def _reap_stale_tasks(max_age_minutes: int = 15) -> int:
    """Time out stale tasks, diagnose the failure, and retry with a different provider.

    For each reaped task:
    1. Mark as timed_out with diagnosis
    2. Check retry count for this idea+phase
    3. If under limit, create a retry task with a different provider hint
    4. If over limit, record a friction event
    """
    tasks_data = _api("GET", "/api/agent/tasks?status=running&limit=100")
    if not tasks_data:
        return 0

    task_list = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
    now = datetime.now(timezone.utc)
    reaped = 0

    for t in task_list:
        created = t.get("created_at", "")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_min = (now - dt).total_seconds() / 60
        except Exception:
            continue

        if age_min <= max_age_minutes:
            continue

        task_id = t.get("id", "")
        task_type = t.get("task_type", "spec")
        ctx = t.get("context", {}) or {}
        idea_id = ctx.get("idea_id", "")
        idea_name = ctx.get("idea_name", idea_id or task_id[:20])
        failed_provider = ctx.get("provider", "unknown")
        retry_count = int(ctx.get("retry_count", 0))

        # Diagnose: check if we have a task log with partial output
        diagnosis = f"Stuck running for {int(age_min)}m (threshold {max_age_minutes}m)"
        log_path = Path(__file__).resolve().parent.parent / "api" / "task_logs" / f"task_{task_id}.log"
        if log_path.exists():
            try:
                log_content = log_path.read_text(errors="replace")[-500:]
                if "error" in log_content.lower() or "timeout" in log_content.lower():
                    diagnosis += f" | Partial log: {log_content[-200:]}"
            except Exception:
                pass

        # Reap the task
        result = _api("PATCH", f"/api/agent/tasks/{task_id}", {
            "status": "timed_out",
            "output": f"Reaped: {diagnosis}",
            "error_summary": diagnosis[:500],
            "error_category": "stale_task_reaped",
        })
        if not result:
            continue

        log.info("REAPER: timed out %s (%s, %dm, provider=%s, retries=%d) — %s",
                 task_id[:16], task_type, int(age_min), failed_provider, retry_count, idea_name[:40])
        reaped += 1

        # Capture checkpoint from worktree if it exists
        checkpoint_summary = ""
        resume_patch_path = ""
        slug = task_id[:16]
        wt_path = _WORKTREE_BASE / f"task-{slug}"
        if wt_path.exists():
            # Read checkpoint file
            checkpoint_file = wt_path / ".task-checkpoint.md"
            if checkpoint_file.exists():
                try:
                    checkpoint_summary = checkpoint_file.read_text(errors="replace")[:2000]
                    log.info("REAPER: captured checkpoint for %s (%d chars)", slug, len(checkpoint_summary))
                except Exception:
                    pass

            # Save git diff as a patch for resume
            import subprocess as _sp
            try:
                diff_result = _sp.run(
                    ["git", "diff", "HEAD"],
                    capture_output=True, text=True, timeout=10, cwd=str(wt_path),
                )
                if diff_result.stdout.strip():
                    patch_dir = Path(__file__).resolve().parent.parent / "api" / "task_patches"
                    patch_dir.mkdir(parents=True, exist_ok=True)
                    patch_file = patch_dir / f"task_{task_id}.patch"
                    patch_file.write_text(diff_result.stdout)
                    resume_patch_path = str(patch_file)
                    log.info("REAPER: saved %d-byte patch for %s", len(diff_result.stdout), slug)
            except Exception:
                pass

        # Retry logic: create a new task for the same idea+phase with checkpoint context
        if idea_id and retry_count < _MAX_RETRIES_PER_IDEA_PHASE:
            direction = t.get("direction", ctx.get("direction", ""))
            if not direction:
                direction = f"Retry: {task_type} for {idea_name}. Previous attempt timed out after {int(age_min)}m."

            retry_ctx = dict(ctx)
            retry_ctx["retry_count"] = retry_count + 1
            retry_ctx["retried_from"] = task_id
            retry_ctx["failed_provider"] = failed_provider
            retry_ctx["seed_source"] = "reaper_retry"
            if checkpoint_summary:
                retry_ctx["checkpoint_summary"] = checkpoint_summary
            if resume_patch_path:
                retry_ctx["resume_patch_path"] = resume_patch_path

            retry_result = _api("POST", "/api/agent/tasks", {
                "direction": direction,
                "task_type": task_type,
                "context": retry_ctx,
                "target_state": t.get("target_state", f"{task_type.title()} completed for: {idea_name}"),
            })
            if retry_result and retry_result.get("id"):
                log.info("REAPER: retried %s → %s (attempt %d/%d, excluding provider %s)",
                         task_id[:16], retry_result["id"][:16], retry_count + 1,
                         _MAX_RETRIES_PER_IDEA_PHASE, failed_provider)
            else:
                log.warning("REAPER: retry failed for %s", task_id[:16])
        elif idea_id:
            log.warning("REAPER: max retries reached for %s (%s/%s) — recording friction",
                        idea_name[:30], task_type, idea_id[:20])
            # Record friction event
            _api("POST", "/api/friction/events", {
                "stage": task_type,
                "block_type": "repeated_timeout",
                "severity": "high",
                "owner": "reaper",
                "notes": f"Task for '{idea_name}' timed out {retry_count + 1} times. Last provider: {failed_provider}.",
            })

    if reaped:
        log.info("REAPER: cleaned %d stale tasks", reaped)
    return reaped


def _detect_tools() -> list[str]:
    """Detect installed dev tools on this machine."""
    import shutil
    tools = []
    for tool in ["python", "python3", "node", "npm", "docker", "git", "pip", "cargo", "go"]:
        if shutil.which(tool):
            tools.append(tool)
    return tools


# ── Remote node messaging ────────────────────────────────────────────

# Safe commands that can be executed remotely without confirmation.
_SAFE_COMMANDS = {
    "update": "git pull origin main",
    "status": None,  # handled inline
    "diagnose": None,  # handled inline
    "restart": None,  # handled inline
    "ping": None,  # handled inline
    "deploy": None,  # handled by _deploy_to_vps()
}


def _process_node_messages(node_id: str) -> int:
    """Check for messages addressed to this node and execute safe commands.

    Returns number of messages processed.
    """
    data = _api("GET", f"/api/federation/nodes/{node_id}/messages?unread_only=true&limit=10")
    if not data:
        return 0
    messages = data.get("messages", [])
    if not messages:
        return 0

    processed = 0
    for msg in messages:
        msg_id = msg.get("id", "?")
        msg_type = msg.get("type", "text")
        from_node = msg.get("from_node", "?")[:16]
        text = msg.get("text", "")
        payload = msg.get("payload", {}) or {}

        log.info("MSG_RECEIVED id=%s type=%s from=%s text=%s",
                 msg_id[:16], msg_type, from_node, text[:80])

        # Note: GET /messages already marks them as read — no separate PATCH needed

        if msg_type == "command":
            response = _execute_node_command(node_id, payload, text)
            # Send response back
            _api("POST", f"/api/federation/nodes/{node_id}/messages", {
                "from_node": node_id,
                "to_node": from_node,
                "type": "command_response",
                "text": response,
                "payload": {"in_reply_to": msg_id},
            })
            processed += 1
        elif msg_type == "text":
            log.info("MSG_TEXT from=%s: %s", from_node, text[:200])
            # Send ack back
            _api("POST", f"/api/federation/nodes/{node_id}/messages", {
                "from_node": node_id,
                "to_node": from_node,
                "type": "ack",
                "text": f"Received: {text[:80]}",
                "payload": {"in_reply_to": msg_id, "ack": True},
            })
            processed += 1
        elif msg_type == "ack":
            # Don't ack an ack
            log.info("MSG_ACK from=%s: %s", from_node, text[:100])
            processed += 1
        elif msg_type == "command_response":
            log.info("MSG_REPLY from=%s: %s", from_node, text[:200])
            processed += 1
        else:
            log.info("MSG_UNKNOWN type=%s from=%s", msg_type, from_node)

    if processed:
        log.info("MSG_PROCESSED %d messages", processed)
    return processed


def _execute_node_command(node_id: str, payload: dict, text: str) -> str:
    """Execute a safe command received from another node.

    Returns a response string describing the result.
    """
    import subprocess as _sp
    import shutil

    command = payload.get("command", "").strip().lower()

    if command == "update":
        # Git pull and report what changed
        try:
            result = _sp.run(
                ["git", "pull", "origin", "main"],
                capture_output=True, text=True, timeout=60,
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            output = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                log.info("CMD_UPDATE: success — %s", output[:200])
                return f"Update successful: {output[:300]}"
            else:
                log.warning("CMD_UPDATE: failed — %s", output[:200])
                return f"Update failed (exit {result.returncode}): {output[:300]}"
        except Exception as e:
            return f"Update error: {e}"

    elif command == "status":
        # Collect node status
        import psutil
        providers = _detect_providers() if callable(globals().get("_detect_providers")) else []
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            status_lines = [
                f"Node: {socket.gethostname()} ({sys.platform})",
                f"CPU: {cpu}% | RAM: {mem.percent}% ({mem.available // (1024**3)}GB free)",
                f"Disk: {disk.percent}% ({disk.free // (1024**3)}GB free)",
                f"Python: {sys.version.split()[0]}",
                f"Providers: {providers}",
                f"PID: {os.getpid()}",
            ]
            return "\n".join(status_lines)
        except ImportError:
            return f"Node: {socket.gethostname()} ({sys.platform}), PID: {os.getpid()}"

    elif command == "diagnose":
        # Run diagnostics: check git status, runner health, recent errors
        lines = [f"=== Diagnostics for {socket.gethostname()} ==="]
        try:
            git_status = _sp.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=10,
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            lines.append(f"Git status: {git_status.stdout.strip()[:200] or 'clean'}")

            git_log = _sp.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True, text=True, timeout=10,
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            lines.append(f"Recent commits:\n{git_log.stdout.strip()}")

            # Check for recent errors in runner log
            err_log = Path("/tmp/coherence-runner.err")
            if err_log.exists():
                recent_errors = [
                    l for l in err_log.read_text().splitlines()[-50:]
                    if "ERROR" in l or "WARNING" in l
                ][-5:]
                if recent_errors:
                    lines.append("Recent errors:\n" + "\n".join(recent_errors))
                else:
                    lines.append("No recent errors")
        except Exception as e:
            lines.append(f"Diagnostic error: {e}")
        return "\n".join(lines)

    elif command == "restart":
        log.info("CMD_RESTART: received restart command — will exit for launchd/systemd to restart")
        # Reply first, then exit — the service manager restarts us
        response = "Restart acknowledged. Exiting for service manager to restart."
        # Schedule exit after a short delay so the response gets sent
        import threading
        threading.Timer(2.0, lambda: os._exit(0)).start()
        return response

    elif command == "deploy":
        return _deploy_to_vps()

    elif command == "ping":
        return f"pong from {socket.gethostname()} at {datetime.now(timezone.utc).isoformat()}"

    else:
        log.warning("CMD_UNKNOWN: %s (not in safe command list)", command)
        return f"Unknown command: {command}. Safe commands: {', '.join(_SAFE_COMMANDS.keys())}"


def _deploy_to_vps() -> str:
    """Deploy latest main to VPS with health gate and automatic rollback.

    Steps:
    1. SSH to VPS, capture current deployed SHA
    2. Git pull on VPS
    3. Docker compose build + up
    4. Wait 30s for startup
    5. Health check — if fails, rollback to previous SHA
    6. Return result
    """
    import subprocess as _sp

    SSH_KEY = os.path.expanduser("~/.ssh/hostinger-openclaw")
    VPS_HOST = "root@187.77.152.42"
    REPO_DIR = "/docker/coherence-network/repo"
    COMPOSE_DIR = "/docker/coherence-network"

    if not os.path.exists(SSH_KEY):
        return "Deploy skipped: SSH key not found at ~/.ssh/hostinger-openclaw"

    def _ssh(cmd: str, timeout: int = 120) -> tuple[int, str]:
        result = _sp.run(
            ["ssh", "-i", SSH_KEY, "-o", "LogLevel=QUIET", "-o", "StrictHostKeyChecking=no",
             VPS_HOST, cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, (result.stdout + result.stderr).strip()

    log.info("DEPLOY: starting VPS deployment")

    # 1. Capture current SHA for rollback
    rc, prev_sha = _ssh(f"cd {REPO_DIR} && git rev-parse --short HEAD", timeout=15)
    if rc != 0:
        return f"Deploy failed: could not get current VPS SHA: {prev_sha}"
    prev_sha = prev_sha.strip()[:10]
    log.info("DEPLOY: current VPS SHA: %s", prev_sha)

    # 2. Git pull
    rc, pull_output = _ssh(f"cd {REPO_DIR} && git pull origin main --ff-only", timeout=30)
    if rc != 0:
        return f"Deploy failed: git pull failed: {pull_output[:200]}"

    new_sha_rc, new_sha = _ssh(f"cd {REPO_DIR} && git rev-parse --short HEAD", timeout=15)
    new_sha = new_sha.strip()[:10]

    if new_sha == prev_sha:
        log.info("DEPLOY: VPS already up to date at %s", new_sha)
        return f"VPS already up to date at {new_sha}"

    log.info("DEPLOY: pulled %s → %s", prev_sha, new_sha)

    # 3. Docker build + up
    rc, build_output = _ssh(
        f"cd {COMPOSE_DIR} && docker compose build --no-cache api web && docker compose up -d api web",
        timeout=300,
    )
    if rc != 0:
        # Rollback
        log.warning("DEPLOY: build/up failed, rolling back to %s", prev_sha)
        _ssh(f"cd {REPO_DIR} && git checkout {prev_sha} && cd {COMPOSE_DIR} && docker compose up -d api web", timeout=120)
        return f"Deploy failed: build error (rolled back to {prev_sha}): {build_output[-200:]}"

    log.info("DEPLOY: containers started, waiting 30s for health check")

    # 4. Wait for startup
    import time
    time.sleep(30)

    # 5. Health check
    try:
        import httpx
        health = httpx.get("https://api.coherencycoin.com/api/health", timeout=15)
        if health.status_code == 200:
            data = health.json()
            deployed_sha = str(data.get("deployed_sha", ""))[:10]
            schema_ok = data.get("schema_ok", False)
            if schema_ok:
                log.info("DEPLOY: health check passed — SHA=%s schema_ok=%s", deployed_sha, schema_ok)
                return f"Deploy successful: {prev_sha} → {new_sha}. Health: OK, schema: OK"
            else:
                log.warning("DEPLOY: schema_ok=False, rolling back")
        else:
            log.warning("DEPLOY: health check returned %d, rolling back", health.status_code)
    except Exception as e:
        log.warning("DEPLOY: health check failed: %s, rolling back", e)

    # 6. Rollback
    log.warning("DEPLOY: rolling back to %s", prev_sha)
    _ssh(f"cd {REPO_DIR} && git checkout {prev_sha} && cd {COMPOSE_DIR} && docker compose build --no-cache api web && docker compose up -d api web", timeout=300)
    return f"Deploy failed health check — rolled back to {prev_sha}"


# ── Parallel worktree execution ───────────────────────────────────────

_MAX_PARALLEL = int(os.environ.get("CC_MAX_PARALLEL", "3"))
_WORKTREE_BASE = Path(__file__).resolve().parent.parent / ".worktrees"


def _create_worktree(task_id: str) -> Path | None:
    """Create a git worktree for isolated task execution."""
    import subprocess as _sp
    slug = task_id[:16]
    wt_path = _WORKTREE_BASE / f"task-{slug}"
    branch = f"task/{slug}"
    try:
        _WORKTREE_BASE.mkdir(parents=True, exist_ok=True)
        _sp.run(
            ["git", "worktree", "add", "-b", branch, str(wt_path), "HEAD"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        if wt_path.exists():
            log.info("WORKTREE_CREATED task=%s path=%s", slug, wt_path)
            return wt_path
    except Exception as e:
        log.warning("WORKTREE_FAILED task=%s error=%s", slug, e)
    return None


def _cleanup_worktree(task_id: str) -> None:
    """Remove a worktree after task completion."""
    import subprocess as _sp
    slug = task_id[:16]
    wt_path = _WORKTREE_BASE / f"task-{slug}"
    branch = f"task/{slug}"
    try:
        _sp.run(
            ["git", "worktree", "remove", "--force", str(wt_path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        _sp.run(
            ["git", "branch", "-D", branch],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        log.info("WORKTREE_CLEANED task=%s", slug)
    except Exception as e:
        log.warning("WORKTREE_CLEANUP_FAILED task=%s error=%s", slug, e)


def _merge_worktree(task_id: str) -> bool:
    """Merge worktree branch back to main if it has changes."""
    import subprocess as _sp
    slug = task_id[:16]
    branch = f"task/{slug}"
    repo_root = str(Path(__file__).resolve().parent.parent)
    try:
        # Check if branch has commits ahead of HEAD
        result = _sp.run(
            ["git", "log", f"HEAD..{branch}", "--oneline"],
            capture_output=True, text=True, timeout=10, cwd=repo_root,
        )
        if not result.stdout.strip():
            return False  # No new commits
        # Merge
        merge = _sp.run(
            ["git", "merge", "--no-ff", branch, "-m", f"Merge task {slug}"],
            capture_output=True, text=True, timeout=30, cwd=repo_root,
        )
        if merge.returncode == 0:
            log.info("WORKTREE_MERGED task=%s", slug)
            return True
        else:
            # Abort failed merge
            _sp.run(["git", "merge", "--abort"], capture_output=True, timeout=10, cwd=repo_root)
            log.warning("WORKTREE_MERGE_CONFLICT task=%s", slug)
            return False
    except Exception as e:
        log.warning("WORKTREE_MERGE_FAILED task=%s error=%s", slug, e)
        return False


def _run_task_in_worktree(task: dict, wt_path: Path) -> bool:
    """Execute a single task inside a worktree directory."""
    task_id = task["id"]
    # Temporarily override the runner's repo dir
    original_repo = _runner._REPO_DIR
    try:
        _runner._REPO_DIR = wt_path
        return _runner.run_one(task, dry_run=False)
    except Exception as e:
        log.error("WORKTREE_EXEC_FAILED task=%s error=%s", task_id[:16], e)
        return False
    finally:
        _runner._REPO_DIR = original_repo


_active_idea_ids: set[str] = set()
_active_lock = __import__("threading").Lock()


def _worker_loop(worker_id: int, dry_run: bool = False) -> None:
    """Independent worker thread: claim one task, execute, repeat."""
    while not _shutdown_event.is_set():
        try:
            # Get a pending task
            pending = _api("GET", "/api/agent/tasks?status=pending&limit=5")
            if not pending:
                _shutdown_event.wait(10)
                continue

            task_list = pending if isinstance(pending, list) else pending.get("tasks", [])
            if not task_list:
                _shutdown_event.wait(10)
                continue

            # Find a task for an idea we're not already working on
            task = None
            for candidate in task_list:
                ctx = candidate.get("context") if isinstance(candidate.get("context"), dict) else {}
                idea_id = ctx.get("idea_id", "")
                with _active_lock:
                    if idea_id and idea_id in _active_idea_ids:
                        continue
                    # Try to claim
                    result = _api("PATCH", f"/api/agent/tasks/{candidate['id']}", {"status": "running"})
                    if result and result.get("status") == "running":
                        if idea_id:
                            _active_idea_ids.add(idea_id)
                        task = result
                        break

            if not task:
                _shutdown_event.wait(15)
                continue

            task_id = task["id"]
            ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
            idea_id = ctx.get("idea_id", "")
            log.info("WORKER[%d] CLAIMED task=%s type=%s idea=%s",
                     worker_id, task_id[:16], task.get("task_type"), (idea_id or "?")[:20])

            # Create worktree and execute
            wt = _create_worktree(task_id)
            try:
                if wt:
                    ok = _run_task_in_worktree(task, wt)
                    if ok:
                        _merge_worktree(task_id)
                else:
                    # Fallback: sequential in main repo (only if no other workers active)
                    log.warning("WORKER[%d] FALLBACK task=%s (no worktree)", worker_id, task_id[:16])
                    ok = _runner.run_one(task, dry_run=dry_run)

                status = "completed" if ok else "failed"
                log.info("WORKER[%d] %s task=%s", worker_id, status.upper(), task_id[:16])
            except Exception as e:
                log.error("WORKER[%d] ERROR task=%s: %s", worker_id, task_id[:16], e)
            finally:
                if wt:
                    _cleanup_worktree(task_id)
                with _active_lock:
                    _active_idea_ids.discard(idea_id)

        except Exception as e:
            log.error("WORKER[%d] LOOP_ERROR: %s", worker_id, e)
            _shutdown_event.wait(30)


_shutdown_event = __import__("threading").Event()


def run_parallel_workers(num_workers: int, dry_run: bool = False) -> None:
    """Start N independent worker threads that each claim and execute tasks."""
    import threading

    log.info("PARALLEL_WORKERS starting %d workers", num_workers)
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=_worker_loop, args=(i, dry_run), daemon=True, name=f"worker-{i}")
        t.start()
        threads.append(t)
        log.info("WORKER[%d] started", i)

    return threads


# ── Main entry point ──────────────────────────────────────────────────

def main():
    # Let the api runner parse its own args and set up providers
    # We intercept to add federation node registration around it
    import argparse

    parser = argparse.ArgumentParser(
        description="Coherence Network node runner — join the network",
        parents=[],
    )
    parser.add_argument("--task", help="Run a specific task ID")
    parser.add_argument("--loop", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=int, default=120, help="Poll interval (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    parser.add_argument("--timeout", type=int, default=300, help="Task timeout (seconds)")
    parser.add_argument("--resume", action="store_true", help="Enable timeout resume flow")
    parser.add_argument("--stats", action="store_true", help="Show provider stats and exit")
    parser.add_argument("--no-register", action="store_true", help="Skip node registration")
    parser.add_argument("--parallel", type=int, default=0, help="Max parallel tasks via worktrees (0=sequential)")
    args = parser.parse_args()

    # Configure the underlying runner
    _runner._TASK_TIMEOUT[0] = args.timeout
    _runner._RESUME_MODE[0] = bool(args.resume)
    _runner.PROVIDERS = _runner._detect_providers()

    if not _runner.PROVIDERS:
        log.error("No provider CLIs found. Install claude, codex, cursor, gemini, or ollama.")
        sys.exit(1)

    provider_names = list(_runner.PROVIDERS.keys())
    node_id = _generate_node_id()

    log.info("=" * 60)
    log.info("Coherence Network — Node Runner")
    log.info("  node_id:   %s", node_id)
    log.info("  hostname:  %s", socket.gethostname())
    log.info("  os:        %s", _detect_os_type())
    log.info("  sha:       %s (origin/main: %s) %s",
             NODE_GIT.get("local_sha"), NODE_GIT.get("origin_sha"),
             "✓ up-to-date" if NODE_GIT.get("up_to_date") == "yes" else "⚠ BEHIND origin/main")
    log.info("  providers: %s", provider_names)
    log.info("  api:       %s", API_BASE)
    log.info("  timeout:   %ds", args.timeout)
    log.info("=" * 60)

    # Register with federation hub
    if not args.no_register and not args.dry_run:
        register_node(node_id, provider_names)

    if args.stats:
        stats = _runner.get_provider_stats()
        print(json.dumps(stats, indent=2, default=str))
        return

    if args.task:
        task = _runner.api("GET", f"/api/agent/tasks/{args.task}")
        if not task:
            log.error("Task %s not found", args.task)
            sys.exit(1)
        ok = _runner.run_one(task, dry_run=args.dry_run)
        if not args.dry_run:
            push_measurements(node_id)
        sys.exit(0 if ok else 1)

    if args.loop:
        log.info("Polling every %ds (Ctrl+C to stop)", args.interval)
        heartbeat_interval = 300  # heartbeat every 5 minutes
        last_heartbeat = 0.0
        reap_interval = 600  # reap stale tasks every 10 minutes
        last_reap = 0.0
        msg_interval = 120  # check messages every 2 minutes
        last_msg_check = 0.0
        try:
            use_parallel = args.parallel > 0
            if use_parallel:
                global _MAX_PARALLEL
                _MAX_PARALLEL = args.parallel
                log.info("PARALLEL MODE: %d independent worker threads", _MAX_PARALLEL)
                worker_threads = run_parallel_workers(_MAX_PARALLEL, dry_run=args.dry_run)

            while True:
                if not use_parallel:
                    results = _runner.run_all_pending(dry_run=args.dry_run)
                else:
                    # Workers run independently — main loop handles housekeeping only
                    results = {"completed": 0, "failed": 0}

                if not args.dry_run:
                    # Push measurements after each batch
                    push_measurements(node_id)

                    now = time.time()

                    # Periodic heartbeat
                    if now - last_heartbeat > heartbeat_interval:
                        heartbeat(node_id, provider_names)
                        last_heartbeat = now

                    # Reap stale tasks (running > 15 min with no update)
                    if now - last_reap > reap_interval:
                        _reap_stale_tasks(max_age_minutes=15)
                        last_reap = now

                    # Check and execute messages from other nodes
                    if now - last_msg_check > msg_interval:
                        _process_node_messages(node_id)
                        last_msg_check = now

                time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Stopped. Pushing final measurements...")
            if not args.dry_run:
                push_measurements(node_id)
    else:
        results = _runner.run_all_pending(dry_run=args.dry_run)
        if not args.dry_run:
            push_measurements(node_id)
        sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
