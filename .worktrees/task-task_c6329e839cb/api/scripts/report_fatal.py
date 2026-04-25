#!/usr/bin/env python3
"""Report fatal issues from api/logs/fatal_issues.json. No user interaction.
Used by agents/scripts to surface unrecoverable failures."""

import json
import os
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FATAL_FILE = os.path.join(_api_dir, "logs", "fatal_issues.json")


def main() -> None:
    if not os.path.isfile(FATAL_FILE):
        print("No fatal issues.")
        sys.exit(0)
    with open(FATAL_FILE, encoding="utf-8") as f:
        data = json.load(f)
    print("FATAL:", data.get("reason", "unknown"))
    print("Detail:", data.get("detail", ""))
    print("At:", data.get("at", ""))
    sys.exit(1)


if __name__ == "__main__":
    main()
