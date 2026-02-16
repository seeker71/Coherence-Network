#!/usr/bin/env python3
"""Local process gate to avoid abandoning open Codex PRs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from typing import Any


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_time(value: str) -> dt.datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _run_gh(args: list[str]) -> str:
    out = subprocess.check_output(["gh", *args], text=True)
    return out.strip()


def _resolve_repo(explicit_repo: str) -> str:
    if explicit_repo.strip():
        return explicit_repo.strip()
    return _run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])


def _list_open_prs(repo: str) -> list[dict[str, Any]]:
    raw = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,headRefName,updatedAt,url,isDraft",
        ]
    )
    payload = json.loads(raw or "[]")
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _minutes_since(updated_at: str, now: dt.datetime) -> float:
    try:
        then = _parse_time(updated_at)
    except Exception:
        return 0.0
    delta = now - then
    return max(0.0, delta.total_seconds() / 60.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="", help="owner/repo; defaults to current gh repo")
    parser.add_argument("--stale-minutes", type=float, default=90.0)
    parser.add_argument("--fail-on-stale", action="store_true")
    parser.add_argument("--fail-on-open", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail when gh is unavailable")
    args = parser.parse_args()

    if shutil.which("gh") is None:
        msg = "WARNING: gh CLI not found; cannot evaluate PR follow-through."
        print(msg)
        return 2 if args.strict else 0

    try:
        repo = _resolve_repo(args.repo)
        prs = _list_open_prs(repo)
    except subprocess.CalledProcessError as exc:
        print(f"WARNING: failed to query GitHub PRs: {exc}")
        return 2 if args.strict else 0

    now = _utcnow()
    codex_open = []
    stale = []
    for row in prs:
        head = str(row.get("headRefName") or "").strip()
        if not head.startswith("codex/"):
            continue
        if bool(row.get("isDraft")):
            continue
        updated_at = str(row.get("updatedAt") or "")
        age_min = _minutes_since(updated_at, now)
        item = {
            "number": int(row.get("number") or 0),
            "title": str(row.get("title") or "").strip(),
            "head": head,
            "url": str(row.get("url") or "").strip(),
            "updated_at": updated_at,
            "age_minutes": round(age_min, 1),
        }
        codex_open.append(item)
        if age_min >= float(args.stale_minutes):
            stale.append(item)

    print(f"repo={repo}")
    print(f"codex_open_prs={len(codex_open)}")
    print(f"stale_threshold_minutes={args.stale_minutes}")
    print(f"stale_codex_prs={len(stale)}")
    for item in stale[:20]:
        print(
            f"- PR #{item['number']} head={item['head']} age_min={item['age_minutes']} url={item['url']}"
        )

    if args.fail_on_open and codex_open:
        print("ERROR: open codex PRs detected; resolve follow-through before starting new work.")
        return 1
    if args.fail_on_stale and stale:
        print("ERROR: stale codex PRs detected; resolve follow-through before continuing.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
