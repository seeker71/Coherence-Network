#!/usr/bin/env python3
"""Backward-compatible start gate entrypoint used by Codex worktree docs and scripts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit JSON status")
    args = parser.parse_args()

    script_path = Path(__file__).with_name("start_gate.py")
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=bool(args.json),
        text=True,
        check=False,
    )

    if args.json:
        payload = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "script": "scripts/start_gate.py",
        }
        if proc.returncode != 0:
            payload["error"] = (proc.stderr or proc.stdout or "start-gate failed").strip()
            print(json.dumps(payload))
            return proc.returncode

        print(json.dumps(payload))
        return 0

    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
