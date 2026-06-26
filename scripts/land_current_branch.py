#!/usr/bin/env python3
"""Land the current Codex worktree branch through proof, PR, and API merge.

This script is the regular-path wrapper for a finished branch. It keeps the
whole flow on the current named worktree branch and never checks out local
`main`, so linked worktrees cannot collide during merge cleanup.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class CommandFailure(RuntimeError):
    def __init__(self, cmd: list[str], result: subprocess.CompletedProcess[str]) -> None:
        self.cmd = cmd
        self.result = result
        super().__init__(f"command failed ({result.returncode}): {_fmt(cmd)}")


def _fmt(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _run(
    cmd: list[str],
    *,
    capture: bool = False,
    check: bool = True,
    cwd: Path | None = None,
) -> str:
    print(f"$ {_fmt(cmd)}", flush=True)
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture,
    )
    if check and result.returncode != 0:
        if capture:
            if result.stdout.strip():
                print(result.stdout.rstrip(), file=sys.stdout)
            if result.stderr.strip():
                print(result.stderr.rstrip(), file=sys.stderr)
        raise CommandFailure(cmd, result)
    return (result.stdout or "").strip()


def _git(args: list[str], *, capture: bool = False, check: bool = True) -> str:
    return _run(["git", *args], capture=capture, check=check)


def _repo_from_git_remote() -> str:
    remote = _git(["config", "--get", "remote.origin.url"], capture=True)
    if remote.startswith("git@github.com:"):
        path = remote.split(":", 1)[1]
    elif "github.com/" in remote:
        path = remote.split("github.com/", 1)[1]
    else:
        raise RuntimeError(f"unsupported GitHub remote URL: {remote}")
    path = re.sub(r"\.git$", "", path.strip("/"))
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise RuntimeError(f"unable to resolve owner/repo from remote URL: {remote}")
    return f"{parts[0]}/{parts[1]}"


def _resolve_repo(explicit_repo: str) -> str:
    if explicit_repo.strip():
        return explicit_repo.strip()
    try:
        return _run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture=True,
        )
    except CommandFailure:
        return _repo_from_git_remote()


def _current_branch() -> str:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], capture=True)
    if not branch or branch == "HEAD":
        raise RuntimeError("current worktree is detached; attach a codex/<topic> branch first")
    if branch in {"main", "master"}:
        raise RuntimeError("refusing to land directly from main/master")
    return branch


def _require_clean_worktree() -> None:
    status = _git(["status", "--porcelain"], capture=True)
    if status:
        raise RuntimeError(f"worktree must be clean before landing:\n{status}")


def _latest_commit_subject() -> str:
    return _git(["log", "-1", "--pretty=%s"], capture=True)


def _read_body(body_file: str) -> str:
    if not body_file:
        return (
            "Automated current-branch landing.\n\n"
            "Proof path: rebase, changed commit evidence validation, local PR guard, "
            "follow-through guard, check wait, API merge."
        )
    return Path(body_file).read_text(encoding="utf-8")


def _run_local_gates(base_ref: str, *, skip_followthrough: bool) -> None:
    _run(
        [
            "python3",
            "scripts/validate_commit_evidence.py",
            "--base",
            base_ref,
            "--head",
            "HEAD",
            "--require-changed-evidence",
        ]
    )
    _run(["python3", "scripts/worktree_pr_guard.py", "--mode", "local", "--base-ref", base_ref])
    if not skip_followthrough:
        _run(
            [
                "python3",
                "scripts/check_pr_followthrough.py",
                "--stale-minutes",
                "90",
                "--fail-on-stale",
                "--strict",
            ]
        )


def _sync_with_base(base_branch: str, *, skip_local_gates: bool, skip_followthrough: bool) -> None:
    base_ref = f"origin/{base_branch}"
    _run(["git", "fetch", "origin", base_branch])
    _run(["git", "rebase", base_ref])
    _require_clean_worktree()
    if not skip_local_gates:
        _run_local_gates(base_ref, skip_followthrough=skip_followthrough)


def _upstream_branch() -> str:
    return _git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture=True,
        check=False,
    ).strip()


def _push_current_branch(branch: str) -> None:
    upstream = _upstream_branch()
    if upstream == f"origin/{branch}":
        _run(["git", "push", "--force-with-lease", "origin", f"HEAD:{branch}"])
    else:
        _run(["git", "push", "-u", "origin", f"HEAD:{branch}"])


def _gh_json(args: list[str]) -> dict[str, Any]:
    raw = _run(["gh", *args], capture=True)
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected gh JSON object from: gh {_fmt(args)}")
    return payload


def _find_pr(repo: str, branch: str) -> dict[str, Any] | None:
    try:
        return _gh_json(
            [
                "pr",
                "view",
                branch,
                "--repo",
                repo,
                "--json",
                "number,url,state,title",
            ]
        )
    except CommandFailure:
        return None


def _create_or_find_pr(
    *,
    repo: str,
    branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    existing = _find_pr(repo, branch)
    if existing:
        print(f"pr: existing #{existing.get('number')} {existing.get('url')}")
        return existing
    _run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--base",
            base_branch,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ]
    )
    created = _find_pr(repo, branch)
    if not created:
        raise RuntimeError("PR create returned successfully, but PR could not be read back")
    print(f"pr: created #{created.get('number')} {created.get('url')}")
    return created


def _pr_detail(repo: str, number: int) -> dict[str, Any]:
    return _gh_json(
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


def _check_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("context") or "unknown").strip()


def _rollup_state(rollup: Any, *, allow_empty: bool) -> tuple[str, list[str]]:
    if not isinstance(rollup, list) or not rollup:
        if allow_empty:
            return "green", []
        return "pending", ["checks:not_reported"]
    pending: list[str] = []
    failed: list[str] = []
    for row in rollup:
        if not isinstance(row, dict):
            continue
        row_type = str(row.get("__typename") or "").strip()
        name = _check_name(row)
        if row_type == "CheckRun":
            status = str(row.get("status") or "").strip().upper()
            conclusion = str(row.get("conclusion") or "").strip().upper()
            if status != "COMPLETED":
                pending.append(f"{name}:status={status or 'UNKNOWN'}")
            elif conclusion not in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
                failed.append(f"{name}:conclusion={conclusion or 'UNKNOWN'}")
            continue
        if row_type == "StatusContext":
            state = str(row.get("state") or "").strip().upper()
            if state == "SUCCESS":
                continue
            if state in {"PENDING", "EXPECTED"}:
                pending.append(f"{name}:state={state}")
            else:
                failed.append(f"{name}:state={state or 'UNKNOWN'}")
            continue
        pending.append(f"{name}:type={row_type or 'UNKNOWN'}")
    if failed:
        return "failed", failed
    if pending:
        return "pending", pending
    return "green", []


def _readiness(
    detail: dict[str, Any],
    *,
    allow_empty_checks: bool,
) -> tuple[str, str]:
    state = str(detail.get("state") or "").strip().upper()
    if state != "OPEN":
        return "blocked", f"state={state or 'UNKNOWN'}"
    if bool(detail.get("isDraft")):
        return "blocked", "draft=true"
    review_decision = str(detail.get("reviewDecision") or "").strip().upper()
    if review_decision == "CHANGES_REQUESTED":
        return "blocked", "review_decision=CHANGES_REQUESTED"

    rollup, rollup_notes = _rollup_state(
        detail.get("statusCheckRollup"),
        allow_empty=allow_empty_checks,
    )
    merge_state = str(detail.get("mergeStateStatus") or "").strip().upper()
    if merge_state == "CLEAN" and rollup == "green":
        return "ready", "merge_state=CLEAN checks=green"
    if merge_state in {"DIRTY", "BEHIND"}:
        return "needs_rebase", f"merge_state={merge_state}"
    if rollup == "failed":
        return "blocked", "checks_failed:" + ",".join(rollup_notes)
    return "waiting", f"merge_state={merge_state or 'UNKNOWN'} checks={rollup}:{','.join(rollup_notes[:4])}"


def _wait_until_ready(
    *,
    repo: str,
    number: int,
    branch: str,
    base_branch: str,
    timeout_seconds: int,
    poll_seconds: int,
    max_rebases: int,
    skip_local_gates: bool,
    skip_followthrough: bool,
    allow_empty_checks: bool,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    rebase_count = 0
    last_message = ""
    while True:
        detail = _pr_detail(repo, number)
        status, reason = _readiness(detail, allow_empty_checks=allow_empty_checks)
        message = f"pr #{number}: {status} ({reason})"
        if message != last_message:
            print(message, flush=True)
            last_message = message
        if status == "ready":
            return detail
        if status == "blocked":
            raise RuntimeError(f"PR #{number} is blocked: {reason}")
        if status == "needs_rebase":
            if rebase_count >= max_rebases:
                raise RuntimeError(f"PR #{number} still needs rebase after {max_rebases} attempt(s)")
            rebase_count += 1
            print(f"pr #{number}: rebasing current branch because {reason}", flush=True)
            _sync_with_base(
                base_branch,
                skip_local_gates=skip_local_gates,
                skip_followthrough=skip_followthrough,
            )
            _push_current_branch(branch)
            last_message = ""
            continue
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out waiting for PR #{number}: {reason}")
        time.sleep(max(1, poll_seconds))


def _api_merge(repo: str, number: int, method: str) -> None:
    _run(
        [
            "gh",
            "api",
            "-X",
            "PUT",
            f"repos/{repo}/pulls/{number}/merge",
            "-f",
            f"merge_method={method}",
        ]
    )


def _delete_remote_branch(repo: str, branch: str) -> None:
    try:
        _run(["gh", "api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{branch}"])
    except CommandFailure as exc:
        print(f"warning: remote branch delete failed ({exc.result.returncode}); branch={branch}")


def _post_merge_verify(repo: str, number: int, base_branch: str) -> None:
    detail = _gh_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "state,mergedAt,url",
        ]
    )
    print(f"post-merge-pr: state={detail.get('state')} mergedAt={detail.get('mergedAt')}")
    _run(["git", "fetch", "origin", base_branch])
    cmd = ["git", "diff", "--quiet", "HEAD", f"origin/{base_branch}"]
    print(f"$ {_fmt(cmd)}", flush=True)
    result = subprocess.run(cmd, text=True)
    print(f"post-merge-tree-matches-origin-{base_branch}={result.returncode == 0}")


def _plan(args: argparse.Namespace, branch: str, repo: str) -> None:
    print("land-current-branch dry run")
    print(f"branch={branch}")
    print(f"repo={repo}")
    print(f"base=origin/{args.base}")
    print("would: require clean worktree")
    if not args.skip_local_gates:
        print("would: fetch, rebase, validate changed commit evidence, run local PR guard")
    if not args.skip_followthrough:
        print("would: run stale PR follow-through guard")
    print("would: push current branch, create/read PR, wait for clean merge state and green checks")
    if args.merge:
        print(f"would: merge PR through GitHub API using method={args.merge_method}")
        if args.delete_branch:
            print("would: delete remote branch through GitHub API")
    if args.settle_deploy:
        print("would: run scripts/settle_public_deploy.sh after merge")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="", help="GitHub owner/repo; defaults to current repo")
    parser.add_argument("--base", default="main", help="base branch name, default: main")
    parser.add_argument("--title", default="", help="PR title; defaults to latest commit subject")
    parser.add_argument("--body-file", default="", help="file containing PR body")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--max-rebases", type=int, default=2)
    parser.add_argument("--skip-local-gates", action="store_true")
    parser.add_argument("--skip-followthrough", action="store_true")
    parser.add_argument("--allow-empty-checks", action="store_true")
    parser.add_argument("--merge", action="store_true", help="merge after checks are ready")
    parser.add_argument(
        "--merge-method",
        choices=("merge", "squash", "rebase"),
        default="rebase",
    )
    parser.add_argument(
        "--delete-branch",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="delete the remote branch through the GitHub API after merge",
    )
    parser.add_argument("--settle-deploy", action="store_true", help="wait for public deploy after merge")
    parser.add_argument("--api-url", default="https://api.coherencycoin.com")
    parser.add_argument("--web-url", default="https://coherencycoin.com")
    parser.add_argument("--dry-run", action="store_true", help="print the planned flow and exit")
    args = parser.parse_args()

    try:
        branch = _current_branch()
        repo = _resolve_repo(args.repo)
        if args.dry_run:
            _plan(args, branch, repo)
            return 0

        _require_clean_worktree()
        _sync_with_base(
            args.base,
            skip_local_gates=bool(args.skip_local_gates),
            skip_followthrough=bool(args.skip_followthrough),
        )
        _push_current_branch(branch)

        title = args.title.strip() or _latest_commit_subject()
        pr = _create_or_find_pr(
            repo=repo,
            branch=branch,
            base_branch=args.base,
            title=title,
            body=_read_body(args.body_file),
        )
        number = int(pr.get("number") or 0)
        if number <= 0:
            raise RuntimeError("PR number was not available after create/read")

        _wait_until_ready(
            repo=repo,
            number=number,
            branch=branch,
            base_branch=args.base,
            timeout_seconds=max(1, int(args.timeout_seconds)),
            poll_seconds=max(1, int(args.poll_seconds)),
            max_rebases=max(0, int(args.max_rebases)),
            skip_local_gates=bool(args.skip_local_gates),
            skip_followthrough=bool(args.skip_followthrough),
            allow_empty_checks=bool(args.allow_empty_checks),
        )

        if args.merge:
            _api_merge(repo, number, args.merge_method)
            if args.delete_branch:
                _delete_remote_branch(repo, branch)
            _post_merge_verify(repo, number, args.base)
            if args.settle_deploy:
                _run(["bash", "scripts/settle_public_deploy.sh", args.api_url, args.web_url])
        else:
            print(f"ready-pr: #{number} {pr.get('url')}")
            print("merge skipped; rerun with --merge to land through the GitHub API")
        return 0
    except (CommandFailure, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
