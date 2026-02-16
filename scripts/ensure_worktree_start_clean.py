#!/usr/bin/env python3
"""Start-task gate: enforce worktree-only execution and clean git state."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)


def _repo_root() -> Path:
    proc = _run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if proc.returncode != 0:
        raise RuntimeError("not a git repository")
    return Path((proc.stdout or "").strip())


def _status_lines(repo: Path) -> list[str]:
    proc = _run(["git", "status", "--porcelain"], cwd=repo)
    if proc.returncode != 0:
        return [f"git status failed in {repo}"]
    return [line for line in (proc.stdout or "").splitlines() if line.strip()]


def _gh_api_json(args: list[str], cwd: Path) -> Any:
    proc = _run(["gh", "api", "--method", "GET", *args], cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh api failed").strip())
    raw = (proc.stdout or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh api returned non-json output: {exc}") from exc


def _repo_slug_from_git(repo: Path) -> str:
    env_repo = str(os.getenv("GITHUB_REPOSITORY", "")).strip()
    if env_repo and "/" in env_repo:
        return env_repo
    proc = _run(["git", "config", "--get", "remote.origin.url"], cwd=repo)
    if proc.returncode != 0:
        return ""
    remote = (proc.stdout or "").strip()
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/.]+)(?:\.git)?$", remote)
    if not match:
        return ""
    return f"{match.group('owner')}/{match.group('name')}"


def _latest_main_ci_state(repo: Path, repo_slug: str) -> tuple[bool, str, dict[str, Any]]:
    data = _gh_api_json(
        [f"repos/{repo_slug}/actions/runs", "-f", "branch=main", "-f", "per_page=20"],
        cwd=repo,
    )
    rows = data.get("workflow_runs") if isinstance(data, dict) else []
    runs = rows if isinstance(rows, list) else []
    completed = [row for row in runs if isinstance(row, dict) and str(row.get("status") or "") == "completed"]
    if not completed:
        return (
            False,
            "no completed workflow runs found on main",
            {"repo": repo_slug, "latest": None, "failed_recent": []},
        )
    non_signal_conclusions = {"skipped", "neutral"}
    relevant = [
        row
        for row in completed
        if str((row or {}).get("conclusion") or "").strip().lower() not in non_signal_conclusions
    ]
    latest = relevant[0] if relevant else completed[0]
    latest_conclusion = str(latest.get("conclusion") or "").strip().lower()
    failed_conclusions = {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}
    failed_recent: list[dict[str, Any]] = []
    for row in completed[:10]:
        conclusion = str(row.get("conclusion") or "").strip().lower()
        if conclusion in failed_conclusions:
            failed_recent.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "conclusion": conclusion,
                    "html_url": row.get("html_url"),
                    "created_at": row.get("created_at"),
                }
            )
    latest_by_workflow: dict[str, dict[str, Any]] = {}
    for row in completed:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "unknown")
        if name not in latest_by_workflow:
            latest_by_workflow[name] = row
    unresolved_failures: list[dict[str, Any]] = []
    for row in latest_by_workflow.values():
        conclusion = str(row.get("conclusion") or "").strip().lower()
        if conclusion in failed_conclusions:
            unresolved_failures.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "conclusion": conclusion,
                    "html_url": row.get("html_url"),
                    "created_at": row.get("created_at"),
                }
            )
    ok = len(unresolved_failures) == 0
    if ok:
        detail = (
            f"latest main signal workflow run conclusion={latest_conclusion or 'unknown'}"
            if latest_conclusion
            else "latest main signal workflow run has no conclusion"
        )
    else:
        detail = f"main has unresolved failing workflows: {len(unresolved_failures)}"
    return (
        ok,
        detail,
        {
            "repo": repo_slug,
            "latest": {
                "id": latest.get("id"),
                "name": latest.get("name"),
                "status": latest.get("status"),
                "conclusion": latest_conclusion,
                "html_url": latest.get("html_url"),
                "created_at": latest.get("created_at"),
            },
            "failed_recent": failed_recent,
            "unresolved_failing_workflows": unresolved_failures,
        },
    )


def _open_pr_check_failures(repo: Path, repo_slug: str) -> tuple[bool, str, list[dict[str, Any]]]:
    pulls = _gh_api_json([f"repos/{repo_slug}/pulls", "-f", "state=open", "-f", "per_page=50"], cwd=repo)
    rows = pulls if isinstance(pulls, list) else []
    failures: list[dict[str, Any]] = []
    failed_conclusions = {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}
    for pr in rows:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        sha = str(head.get("sha") or "").strip()
        if not number or not sha:
            continue
        checks = _gh_api_json([f"repos/{repo_slug}/commits/{sha}/check-runs", "-f", "per_page=100"], cwd=repo)
        check_rows = checks.get("check_runs") if isinstance(checks, dict) else []
        if not isinstance(check_rows, list):
            continue
        failed_checks: list[dict[str, Any]] = []
        for check in check_rows:
            if not isinstance(check, dict):
                continue
            status = str(check.get("status") or "").strip().lower()
            conclusion = str(check.get("conclusion") or "").strip().lower()
            if status == "completed" and conclusion in failed_conclusions:
                failed_checks.append(
                    {
                        "name": check.get("name"),
                        "conclusion": conclusion,
                        "details_url": check.get("details_url"),
                    }
                )
        if failed_checks:
            failures.append(
                {
                    "number": int(number),
                    "title": pr.get("title"),
                    "html_url": pr.get("html_url"),
                    "head_ref": head.get("ref"),
                    "failed_checks": failed_checks,
                }
            )
    ok = len(failures) == 0
    detail = "no open PR check failures" if ok else f"open PRs with failing checks: {len(failures)}"
    return ok, detail, failures


def _worktree_rows(repo: Path) -> list[tuple[Path, str | None]]:
    proc = _run(["git", "worktree", "list", "--porcelain"], cwd=repo)
    if proc.returncode != 0:
        return []
    rows: list[tuple[Path, str | None]] = []
    current_path: Path | None = None
    current_branch: str | None = None
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if line.startswith("worktree "):
            if current_path is not None:
                rows.append((current_path, current_branch))
            current_path = Path(line.removeprefix("worktree ").strip())
            current_branch = None
        elif line.startswith("branch "):
            current_branch = line.removeprefix("branch ").strip()
    if current_path is not None:
        rows.append((current_path, current_branch))
    return rows


def _primary_workspace(rows: list[tuple[Path, str | None]]) -> Path | None:
    for path, _branch in rows:
        if (path / ".git").is_dir():
            return path
    return rows[0][0] if rows else None


@dataclass
class GateResult:
    name: str
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Block new task starts unless running from a clean worktree."
    )
    parser.add_argument(
        "--allow-dirty-primary",
        action="store_true",
        help="Do not fail when primary workspace has local changes.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--skip-remote-ci",
        action="store_true",
        help="Skip GitHub remote CI/PR failure checks (not recommended).",
    )
    args = parser.parse_args()

    repo = _repo_root()
    rows = _worktree_rows(repo)
    primary = _primary_workspace(rows)
    in_linked_worktree = (repo / ".git").is_file()
    current_dirty = _status_lines(repo)
    primary_dirty = _status_lines(primary) if primary else []

    checks = [
        GateResult(
            name="running_in_worktree",
            ok=in_linked_worktree,
            detail=f"repo={repo}",
        ),
        GateResult(
            name="current_worktree_clean",
            ok=len(current_dirty) == 0,
            detail="clean" if not current_dirty else f"dirty: {len(current_dirty)} file(s)",
        ),
    ]

    if primary is not None:
        checks.append(
            GateResult(
                name="primary_workspace_clean",
                ok=args.allow_dirty_primary or len(primary_dirty) == 0,
                detail=(
                    "clean"
                    if not primary_dirty
                    else f"dirty: {len(primary_dirty)} file(s) at {primary}"
                ),
            )
        )

    remote_details: dict[str, Any] = {"repo_slug": None, "main_ci": None, "open_pr_failures": None}
    if not args.skip_remote_ci:
        repo_slug = _repo_slug_from_git(repo)
        remote_details["repo_slug"] = repo_slug
        if not repo_slug:
            checks.append(
                GateResult(
                    name="repo_slug_detected",
                    ok=False,
                    detail="could not detect GitHub repository slug from env or git remote",
                )
            )
        else:
            gh_auth = _run(["gh", "auth", "status"], cwd=repo)
            checks.append(
                GateResult(
                    name="gh_auth_ready",
                    ok=gh_auth.returncode == 0,
                    detail="authenticated" if gh_auth.returncode == 0 else "gh auth not ready",
                )
            )
            if gh_auth.returncode == 0:
                try:
                    main_ok, main_detail, main_payload = _latest_main_ci_state(repo, repo_slug)
                    remote_details["main_ci"] = main_payload
                    checks.append(
                        GateResult(
                            name="main_ci_green",
                            ok=main_ok,
                            detail=main_detail,
                        )
                    )
                except Exception as exc:
                    checks.append(
                        GateResult(
                            name="main_ci_green",
                            ok=False,
                            detail=f"failed to query main CI state: {exc}",
                        )
                    )
                try:
                    pr_ok, pr_detail, pr_payload = _open_pr_check_failures(repo, repo_slug)
                    remote_details["open_pr_failures"] = pr_payload
                    checks.append(
                        GateResult(
                            name="open_pr_checks_green",
                            ok=pr_ok,
                            detail=pr_detail,
                        )
                    )
                except Exception as exc:
                    checks.append(
                        GateResult(
                            name="open_pr_checks_green",
                            ok=False,
                            detail=f"failed to query open PR checks: {exc}",
                        )
                    )

    ok = all(c.ok for c in checks)
    payload = {
        "ok": ok,
        "repo_root": str(repo),
        "primary_workspace": str(primary) if primary else None,
        "checks": [asdict(c) for c in checks],
        "current_worktree_dirty_files": current_dirty,
        "primary_workspace_dirty_files": primary_dirty[:50],
        "remote_ci": remote_details,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for c in checks:
            status = "OK" if c.ok else "FAIL"
            print(f"{status}: {c.name} ({c.detail})")
        if current_dirty:
            print("Current worktree dirty files:")
            for line in current_dirty:
                print(f"  {line}")
        if primary_dirty:
            print("Primary workspace dirty files:")
            for line in primary_dirty[:20]:
                print(f"  {line}")
        if not args.skip_remote_ci:
            main_ci = remote_details.get("main_ci")
            open_pr_failures = remote_details.get("open_pr_failures")
            if isinstance(main_ci, dict):
                latest = main_ci.get("latest") if isinstance(main_ci.get("latest"), dict) else {}
                if latest:
                    print(
                        "Latest main CI:"
                        f" {latest.get('name')} conclusion={latest.get('conclusion')} link={latest.get('html_url')}"
                    )
            if isinstance(open_pr_failures, list) and open_pr_failures:
                print("Open PR failures (top 5):")
                for row in open_pr_failures[:5]:
                    failed_checks = row.get("failed_checks") if isinstance(row, dict) else []
                    first_check = failed_checks[0] if isinstance(failed_checks, list) and failed_checks else {}
                    print(
                        f"  PR #{row.get('number')} {row.get('title')} -> {first_check.get('name')} "
                        f"({first_check.get('conclusion')}) {row.get('html_url')}"
                    )
        print(f"overall_ok={ok}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
