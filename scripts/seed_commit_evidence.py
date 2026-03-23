#!/usr/bin/env python3
"""Seed the commit evidence API from local git history.

Reads recent git commits and POSTs them in batches to the
commit-evidence endpoint.

Usage:
    python scripts/seed_commit_evidence.py
    python scripts/seed_commit_evidence.py --api https://api.coherencycoin.com
    python scripts/seed_commit_evidence.py --days 60 --batch-size 50
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


def _git_log(days: int) -> list[dict]:
    """Return recent commits as a list of dicts."""
    sep = "---COMMIT-SEP---"
    fmt = f"%H%n%aI%n%an%n%s%n{sep}"
    result = subprocess.run(
        ["git", "log", f"--since={days} days ago", f"--pretty=format:{fmt}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"git log failed: {result.stderr.strip()}", file=sys.stderr)
        return []

    commits: list[dict] = []
    blocks = result.stdout.strip().split(sep)
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 4:
            continue
        sha, date, author, message = lines[0], lines[1], lines[2], lines[3]
        commits.append({
            "sha": sha.strip(),
            "date": date.strip(),
            "author": author.strip(),
            "message": message.strip(),
        })
    return commits


def _post_batch(api_base: str, commits: list[dict]) -> dict:
    """POST a batch of commits to the API and return the response body."""
    url = f"{api_base.rstrip('/')}/api/inventory/commit-evidence"
    body = json.dumps({"commits": commits}).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {"error": f"HTTP {exc.code}: {detail}"}
    except URLError as exc:
        return {"error": str(exc.reason)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed commit evidence from git log")
    parser.add_argument(
        "--api",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of history to include (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of commits per POST request (default: 100)",
    )
    args = parser.parse_args()

    commits = _git_log(args.days)
    if not commits:
        print("No commits found.")
        return

    print(f"Found {len(commits)} commits from the last {args.days} days.")

    total_stored = 0
    total_dupes = 0
    for i in range(0, len(commits), args.batch_size):
        batch = commits[i : i + args.batch_size]
        print(f"  POSTing batch {i // args.batch_size + 1} ({len(batch)} commits) -> {args.api}")
        result = _post_batch(args.api, batch)
        if "error" in result:
            print(f"  Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        stored = result.get("stored", 0)
        dupes = result.get("duplicates_skipped", 0)
        total_stored += stored
        total_dupes += dupes
        print(f"  stored={stored}, duplicates_skipped={dupes}")

    print(f"Done. Total stored={total_stored}, duplicates_skipped={total_dupes}")


if __name__ == "__main__":
    main()
