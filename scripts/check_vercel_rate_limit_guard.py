#!/usr/bin/env python3
"""Fail fast when PR checks show active Vercel deployment rate limiting."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _run_gh(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _as_utc(value: str) -> dt.datetime | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _retry_minutes(desc: str) -> int | None:
    text = str(desc or "").strip().lower()
    if not text:
        return None
    m_hours = re.search(r"retry in\s+(\d+)\s+hours?", text)
    if m_hours:
        return int(m_hours.group(1)) * 60
    m_mins = re.search(r"retry in\s+(\d+)\s+minutes?", text)
    if m_mins:
        return int(m_mins.group(1))
    return None


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _resolve_repo(explicit_repo: str) -> str:
    if explicit_repo.strip():
        return explicit_repo.strip()
    code, out, err = _run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if code != 0:
        raise RuntimeError(f"failed to resolve repo: {err.strip() or out.strip()}")
    return out.strip()


def _resolve_pr(repo: str, explicit_pr: str, branch: str) -> dict[str, Any] | None:
    if explicit_pr.strip():
        code, out, err = _run_gh(
            ["pr", "view", explicit_pr.strip(), "--repo", repo, "--json", "number,url,headRefName,state"]
        )
        if code != 0:
            raise RuntimeError(f"failed to resolve PR {explicit_pr.strip()}: {err.strip() or out.strip()}")
        payload = json.loads(out or "{}")
        return payload if isinstance(payload, dict) else None

    code, out, err = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--head",
            branch,
            "--limit",
            "1",
            "--json",
            "number,url,headRefName,state",
        ]
    )
    if code != 0:
        raise RuntimeError(f"failed to resolve branch PR: {err.strip() or out.strip()}")
    payload = json.loads(out or "[]")
    if isinstance(payload, list) and payload:
        row = payload[0]
        return row if isinstance(row, dict) else None
    return None


def _checks_for_pr(repo: str, pr_number: int) -> list[dict[str, Any]]:
    code, out, err = _run_gh(
        [
            "pr",
            "checks",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "name,state,bucket,description,link,startedAt,completedAt",
        ]
    )
    if code != 0:
        # gh uses exit code 8 for pending checks; still emits JSON. Only fail on no output.
        if not out.strip():
            raise RuntimeError(f"failed to fetch PR checks: {err.strip()}")
    payload = json.loads(out or "[]")
    return payload if isinstance(payload, list) else []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="")
    parser.add_argument("--pr", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--allow-rate-limited", action="store_true")
    parser.add_argument("--default-retry-hours", type=int, default=12)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    audit_dir = root / "docs" / "system_audit"
    latest_path = audit_dir / "vercel_rate_limit_guard_latest.json"
    history_path = audit_dir / "vercel_rate_limit_guard_history.jsonl"

    started = _utcnow()
    status = "pass"
    reason = "no_vercel_rate_limit_detected"
    blocked_until: str | None = None
    vercel_hits: list[dict[str, Any]] = []
    repo = ""
    pr_number: int | None = None

    try:
        repo = _resolve_repo(str(args.repo))
        branch = str(args.branch).strip()
        if not branch:
            code, out, err = _run_gh(["repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"])
            if code != 0:
                # Fallback to git local branch.
                proc = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                branch = (proc.stdout or "").strip()
            else:
                # Use local branch over default branch when available.
                proc = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                branch = (proc.stdout or "").strip() or out.strip()

        pr_row = _resolve_pr(repo, str(args.pr), branch)
        if not pr_row:
            reason = "no_open_pr_for_branch"
        else:
            pr_number = int(pr_row.get("number") or 0)
            checks = _checks_for_pr(repo, pr_number)
            for row in checks:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "")
                bucket = str(row.get("bucket") or "").lower()
                desc = str(row.get("description") or "")
                if "vercel" not in name.lower():
                    continue
                if bucket != "fail":
                    continue
                if "rate limit" not in desc.lower():
                    continue
                retry_minutes = _retry_minutes(desc)
                completed = _as_utc(str(row.get("completedAt") or ""))
                if retry_minutes is None:
                    retry_minutes = int(args.default_retry_hours) * 60
                reference = completed or started
                until = reference + dt.timedelta(minutes=retry_minutes)
                vercel_hits.append(
                    {
                        "name": name,
                        "bucket": bucket,
                        "description": desc,
                        "link": str(row.get("link") or ""),
                        "retry_minutes": retry_minutes,
                        "completed_at": completed.isoformat() if completed else None,
                        "blocked_until": until.isoformat(),
                    }
                )
            if vercel_hits:
                latest_until = max(_as_utc(hit.get("blocked_until") or "") for hit in vercel_hits)
                if latest_until and latest_until > started:
                    blocked_until = latest_until.isoformat()
                    status = "blocked"
                    reason = "vercel_rate_limit_active"
                else:
                    reason = "vercel_rate_limit_elapsed"
    except Exception as exc:
        status = "warning"
        reason = f"guard_query_error:{exc}"

    payload = {
        "generated_at": started.isoformat(),
        "repo": repo,
        "pr_number": pr_number,
        "status": status,
        "reason": reason,
        "blocked_until": blocked_until,
        "vercel_rate_limit_hits": vercel_hits,
        "allow_rate_limited": bool(args.allow_rate_limited),
    }
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _append_jsonl(history_path, payload)
    print(f"Wrote {latest_path}")
    print(f"Appended {history_path}")
    print(f"status={status} reason={reason}")
    if blocked_until:
        print(f"blocked_until={blocked_until}")

    if status == "blocked" and not args.allow_rate_limited:
        print("ERROR: Vercel deployment rate limit is active. Avoid new PR iteration until cooldown elapses.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
