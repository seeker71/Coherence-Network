#!/usr/bin/env python3
"""Run a single backlog item by 1-based index.

Usage:
  python scripts/run_backlog_item.py --index 5
  python scripts/run_backlog_item.py --index 5 --backlog ../specs/006-overnight-backlog.md

Creates a state file with backlog_index = index-1, phase = spec, then runs
project_manager --once to kick off the spec task for that item.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
sys.path.insert(0, _api_dir)

DEFAULT_BACKLOG = os.path.join(PROJECT_ROOT, "specs", "006-overnight-backlog.md")


def main():
    ap = argparse.ArgumentParser(description="Run single backlog item by index")
    ap.add_argument("--index", "-n", type=int, required=True, help="1-based backlog item index")
    ap.add_argument("--backlog", default=DEFAULT_BACKLOG, help="Backlog file path")
    args = ap.parse_args()

    backlog_path = os.path.abspath(args.backlog) if not os.path.isabs(args.backlog) else args.backlog
    if not os.path.isfile(backlog_path):
        print(f"ERROR: Backlog not found: {backlog_path}")
        sys.exit(1)

    # Load backlog to validate index
    from importlib.util import spec_from_file_location, module_from_spec
    pm_spec = spec_from_file_location(
        "project_manager",
        os.path.join(_api_dir, "scripts", "project_manager.py"),
    )
    pm = module_from_spec(pm_spec)
    pm_spec.loader.exec_module(pm)

    orig_backlog = pm.BACKLOG_FILE
    pm.BACKLOG_FILE = backlog_path
    try:
        items = pm.load_backlog()
    finally:
        pm.BACKLOG_FILE = orig_backlog

    idx = args.index - 1
    if idx < 0 or idx >= len(items):
        print(f"ERROR: Index {args.index} out of range (backlog has {len(items)} items)")
        sys.exit(1)

    item = items[idx]
    print(f"Running backlog item {args.index}: {item[:70]}...")

    # Create temp state file pointing to this item
    log_dir = os.path.join(_api_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    fd, state_path = tempfile.mkstemp(suffix=".json", prefix="pm_state_", dir=log_dir)
    try:
        os.close(fd)
        state = {
            "backlog_index": idx,
            "phase": "spec",
            "current_task_id": None,
            "iteration": 1,
            "blocked": False,
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        cmd = [
            sys.executable,
            os.path.join(_api_dir, "scripts", "project_manager.py"),
            "--backlog", backlog_path,
            "--state-file", state_path,
            "--once",
            "--verbose",
        ]
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        sys.exit(result.returncode)
    finally:
        if os.path.isfile(state_path):
            os.remove(state_path)


if __name__ == "__main__":
    main()
