#!/usr/bin/env python3
"""Local process gate to avoid abandoning open Codex PRs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
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


def _pr_details(repo: str, number: int) -> dict[str, Any]:
    raw = _run_gh(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,state,isDraft,mergeStateStatus,reviewDecision,statusCheckRollup,url,headRefName,baseRefName",
        ]
    )
    payload = json.loads(raw or "{}")
    return payload if isinstance(payload, dict) else {}


def _status_rollup_all_green(rollup: Any) -> tuple[bool, list[str]]:
    if not isinstance(rollup, list) or not rollup:
        return True, []
    errors: list[str] = []
    for row in rollup:
        if not isinstance(row, dict):
            continue
        row_type = str(row.get("__typename") or "").strip()
        name = str(row.get("name") or row.get("context") or "unknown").strip()
        if row_type == "CheckRun":
            status = str(row.get("status") or "").strip().upper()
            conclusion = str(row.get("conclusion") or "").strip().upper()
            if status != "COMPLETED":
                errors.append(f"{name}:status={status or 'UNKNOWN'}")
                continue
            if conclusion not in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
                errors.append(f"{name}:conclusion={conclusion or 'UNKNOWN'}")
                continue
            continue
        if row_type == "StatusContext":
            state = str(row.get("state") or "").strip().upper()
            if state != "SUCCESS":
                errors.append(f"{name}:state={state or 'UNKNOWN'}")
            continue
    return len(errors) == 0, errors


def _is_merge_ready(detail: dict[str, Any]) -> tuple[bool, str]:
    state = str(detail.get("state") or "").strip().upper()
    if state != "OPEN":
        return False, f"state={state or 'UNKNOWN'}"
    if bool(detail.get("isDraft")):
        return False, "is_draft=true"
    merge_state = str(detail.get("mergeStateStatus") or "").strip().upper()
    if merge_state != "CLEAN":
        return False, f"merge_state={merge_state or 'UNKNOWN'}"
    review_decision = str(detail.get("reviewDecision") or "").strip().upper()
    if review_decision == "CHANGES_REQUESTED":
        return False, "review_decision=CHANGES_REQUESTED"
    rollup_ok, rollup_errors = _status_rollup_all_green(detail.get("statusCheckRollup"))
    if not rollup_ok:
        return False, f"checks_not_green:{','.join(rollup_errors)}"
    return True, "ready"


def _merge_pr(repo: str, number: int, method: str) -> None:
    _run_gh(
        [
            "pr",
            "merge",
            str(number),
            "--repo",
            repo,
            f"--{method}",
            "--delete-branch=false",
            "--auto=false",
        ]
    )


def _auto_merge_ready_stale_prs(
    *,
    repo: str,
    stale: list[dict[str, Any]],
    method: str,
    limit: int,
    dry_run: bool,
) -> tuple[list[int], list[dict[str, Any]]]:
    merged: list[int] = []
    skipped: list[dict[str, Any]] = []
    for item in stale[: max(0, int(limit))]:
        number = int(item.get("number") or 0)
        if number <= 0:
            skipped.append({"number": number, "reason": "missing_number"})
            continue
        try:
            detail = _pr_details(repo, number)
        except subprocess.CalledProcessError as exc:
            skipped.append({"number": number, "reason": f"detail_query_failed:{exc.returncode}"})
            continue
        ready, reason = _is_merge_ready(detail)
        if not ready:
            skipped.append({"number": number, "reason": reason})
            continue
        if dry_run:
            merged.append(number)
            continue
        try:
            _merge_pr(repo, number, method)
            merged.append(number)
        except subprocess.CalledProcessError as exc:
            skipped.append({"number": number, "reason": f"merge_failed:{exc.returncode}"})
    return merged, skipped


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
    parser.add_argument(
        "--auto-merge-ready-stale",
        action="store_true",
        help="Attempt to merge stale non-draft codex PRs when merge state and checks are green.",
    )
    parser.add_argument(
        "--auto-merge-method",
        choices=("merge", "squash", "rebase"),
        default="merge",
        help="Merge strategy used with --auto-merge-ready-stale.",
    )
    parser.add_argument(
        "--auto-merge-limit",
        type=int,
        default=3,
        help="Maximum stale PRs to attempt auto-merge for in one run.",
    )
    parser.add_argument(
        "--auto-merge-dry-run",
        action="store_true",
        help="Report merge-ready stale PRs without merging them.",
    )
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

    if args.auto_merge_ready_stale and stale:
        merged, skipped = _auto_merge_ready_stale_prs(
            repo=repo,
            stale=stale,
            method=args.auto_merge_method,
            limit=args.auto_merge_limit,
            dry_run=bool(args.auto_merge_dry_run),
        )
        if merged:
            mode = "dry_run_ready" if args.auto_merge_dry_run else "merged"
            print(f"auto_merge_stale_{mode}={len(merged)}")
            for number in merged[:20]:
                print(f"- PR #{number} auto-merge candidate")
        if skipped:
            print(f"auto_merge_stale_skipped={len(skipped)}")
            for row in skipped[:20]:
                print(f"- PR #{row.get('number', 0)} skipped reason={row.get('reason', 'unknown')}")
        merged_set = {int(number) for number in merged}
        codex_open = [row for row in codex_open if int(row.get("number") or 0) not in merged_set]
        stale = [row for row in stale if int(row.get("number") or 0) not in merged_set]
        print(f"codex_open_prs_after_auto_merge={len(codex_open)}")
        print(f"stale_codex_prs_after_auto_merge={len(stale)}")

    if args.fail_on_open and codex_open:
        print("ERROR: open codex PRs detected; resolve follow-through before starting new work.")
        return 1
    if args.fail_on_stale and stale:
        print("ERROR: stale codex PRs detected; resolve follow-through before continuing.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
