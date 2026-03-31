#!/usr/bin/env python3
"""Overnight orchestrator: impl-only task creation (legacy).

Polls every 60s; when queue empty, creates impl tasks. CONFLICTS with
project_manager.py — do not run both. For the full spec→impl→test→review
pipeline, use run_overnight_pipeline.sh (which runs project_manager, not this).

Usage:
  python scripts/overnight_orchestrator.py [--interval 60] [--hours 8] [--verbose]
"""

import argparse
import logging
import os
import sys
import time

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
LOG_FILE = os.path.join(LOG_DIR, "overnight_orchestrator.log")

# Backlog of directions (impl tasks). Rotate through these when queue is empty.
DIRECTIONS = [
    "Implement the next item from docs/PLAN.md Sprint 0-1: graph foundation, indexer, basic API. Pick highest-priority uncompleted work.",
    "Implement the next item from docs/PLAN.md: 5K+ npm packages, API returns real data, search works. Work from specs/ as source of truth.",
    "Add or improve tests per specs/002 and 004. Ensure tests define the contract; do not modify tests to make implementation pass.",
    "Implement spec 004-ci-pipeline.md if any items remain. Only modify files listed in the spec.",
    "Implement spec 003-agent-telegram-decision-loop.md next items. Follow spec exactly.",
    "Implement spec 002-agent-orchestration-api.md any remaining checkboxes. Keep implementation minimal.",
    "Review docs/PLAN.md roadmap. Implement the next smallest deliverable for Month 1 graph foundation.",
]


def _setup_logging(verbose: bool = False) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    log = logging.getLogger("overnight_orchestrator")
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


def run(interval: int, hours: float, log: logging.Logger, verbose: bool = False) -> None:
    deadline = time.time() + hours * 3600 if hours else None
    idx = 0
    created = 0

    with httpx.Client(timeout=15.0) as client:
        while True:
            if deadline and time.time() >= deadline:
                log.info("Reached time limit (%.1f h), stopping", hours)
                break

            try:
                r = client.get(f"{BASE}/api/agent/tasks", params={"status": "pending", "limit": 1})
                if r.status_code != 200:
                    log.warning("GET tasks failed status=%s", r.status_code)
                    time.sleep(interval)
                    continue

                data = r.json()
                pending = (data.get("tasks") or [])
                total = data.get("total", 0)

                if total == 0 or len(pending) == 0:
                    direction = DIRECTIONS[idx % len(DIRECTIONS)]
                    idx += 1
                    resp = client.post(
                        f"{BASE}/api/agent/tasks",
                        json={"direction": direction, "task_type": "impl"},
                    )
                    if resp.status_code == 201:
                        t = resp.json()
                        created += 1
                        log.info("created task=%s direction=%s...", t.get("id", ""), direction[:50])
                        if verbose:
                            print(f"  Created task {t.get('id')}: {direction[:60]}...")
                    else:
                        log.warning("POST task failed status=%s", resp.status_code)
                else:
                    log.debug("pending=%d, no new task needed", total)

            except Exception as e:
                log.exception("poll error: %s", e)

            time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description="Overnight orchestrator: keep impl tasks in queue")
    ap.add_argument("--interval", type=int, default=60, help="Seconds between polls")
    ap.add_argument("--hours", type=float, default=8, help="Run for N hours (0 = indefinitely)")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    log = _setup_logging(verbose=args.verbose)
    log.info("Overnight orchestrator started API=%s interval=%ds hours=%s", BASE, args.interval, args.hours)
    if args.verbose:
        print(f"Overnight orchestrator | API: {BASE} | interval: {args.interval}s | log: {LOG_FILE}\n")

    run(interval=args.interval, hours=args.hours, log=log, verbose=args.verbose)


if __name__ == "__main__":
    main()
