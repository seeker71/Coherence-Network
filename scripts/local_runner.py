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
_HTTP_CLIENT = httpx.Client(timeout=30.0)


# ── Node identity ─────────────────────────────────────────────────────

def _get_mac_address() -> str:
    """Get a stable MAC address string for node ID generation."""
    mac = uuid.getnode()
    return ":".join(f"{(mac >> i) & 0xFF:02x}" for i in range(0, 48, 8))


def _generate_node_id() -> str:
    """16-char SHA256 hash of hostname + MAC address (spec 132)."""
    hostname = socket.gethostname()
    mac = _get_mac_address()
    raw = f"{hostname}:{mac}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


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
    """Call federation API."""
    url = f"{API_BASE}{path}"
    try:
        if method == "GET":
            resp = _HTTP_CLIENT.get(url)
        elif method == "POST":
            resp = _HTTP_CLIENT.post(url, json=body)
        else:
            return None
        if resp.status_code >= 400:
            log.error("API %s %s → %d: %s", method, path, resp.status_code, resp.text[:200])
            return None
        if not resp.text.strip():
            return None
        return resp.json()
    except Exception as e:
        log.error("API %s %s error: %s", method, path, e)
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
        },
    }
    result = _api("POST", "/api/federation/nodes", body)
    if result:
        log.info("NODE REGISTERED node_id=%s status=%s", node_id, result.get("status"))
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


def _detect_tools() -> list[str]:
    """Detect installed dev tools on this machine."""
    import shutil
    tools = []
    for tool in ["python", "python3", "node", "npm", "docker", "git", "pip", "cargo", "go"]:
        if shutil.which(tool):
            tools.append(tool)
    return tools


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
        try:
            while True:
                results = _runner.run_all_pending(dry_run=args.dry_run)

                if not args.dry_run:
                    # Push measurements after each batch
                    push_measurements(node_id)

                    # Periodic heartbeat
                    now = time.time()
                    if now - last_heartbeat > heartbeat_interval:
                        heartbeat(node_id, provider_names)
                        last_heartbeat = now

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
