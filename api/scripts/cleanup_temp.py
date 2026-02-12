#!/usr/bin/env python3
"""Remove temp e2e test files and task logs.

Usage:
  python scripts/cleanup_temp.py [--keep-days N]
  --keep-days N  Keep task logs newer than N days (default: 0 = remove all)

Temp files: api/test_*e2e*.txt, test_claude_ok.txt
Task logs: api/logs/task_*.log

In-memory tasks: Cleared when API restarts. No endpoint to clear at runtime.
"""

import argparse
import glob
import os
import time

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_root = os.path.dirname(_api_dir)

TEMP_PATTERNS = [
    os.path.join(_api_dir, "test_agent_e2e.txt"),
    os.path.join(_api_dir, "test_e2e_*.txt"),
    os.path.join(_root, "test_claude_ok.txt"),
]
TASK_LOG_PATTERN = os.path.join(_api_dir, "logs", "task_*.log")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-days", type=int, default=0, help="Keep task logs newer than N days")
    args = ap.parse_args()
    cutoff = time.time() - args.keep_days * 86400 if args.keep_days else 0

    removed = []
    for p in TEMP_PATTERNS:
        for path in glob.glob(p):
            try:
                os.remove(path)
                removed.append(path)
            except OSError as e:
                print(f"Skip {path}: {e}")

    for path in glob.glob(TASK_LOG_PATTERN):
        if cutoff and os.path.getmtime(path) > cutoff:
            continue
        try:
            os.remove(path)
            removed.append(path)
        except OSError as e:
            print(f"Skip {path}: {e}")
    for p in removed:
        print(f"Removed: {p}")
    if not removed:
        print("Nothing to remove.")
    print("\nIn-memory tasks clear on API restart.")

if __name__ == "__main__":
    main()
