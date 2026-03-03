from __future__ import annotations

import json
import re
import shutil
import subprocess
import os
import time
from collections.abc import Callable
from pathlib import Path


def env_flag(name: str, *, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _workflow_name_set(value: str) -> set[str]:
    names = set()
    for raw in value.split(","):
        normalized = raw.strip().lower()
        if normalized:
            names.add(normalized)
    return names


def run_json(cmd: list[str], *, required: bool = True) -> dict | None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        if required:
            raise SystemExit(f"start-gate: command failed: {' '.join(cmd)}")
        return None

    output = proc.stdout.strip()
    if not output:
        raise SystemExit(f"start-gate: empty JSON output from {' '.join(cmd)}")

    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"start-gate: invalid JSON from {' '.join(cmd)}: {exc}")

    return payload


def run_command(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        raise SystemExit(
            "start-gate: command failed: "
            f"{' '.join(cmd)} ({stderr or stdout or 'unknown failure'})"
        )

    return proc


def _list_stash_refs(repo_dir: str) -> list[str]:
    proc = run_command(["git", "-C", repo_dir, "stash", "list"], check=False)
    if proc.returncode != 0:
        return []
    refs: list[str] = []
    for line in (proc.stdout or "").splitlines():
        ref = line.split(":", 1)[0].strip()
        if ref:
            refs.append(ref)
    return refs


def _auto_heal_dirty_repo(repo_dir: str, *, label: str) -> str | None:
    before = _list_stash_refs(repo_dir)
    stash_message = f"start-gate-auto-heal:{label}:{int(time.time())}:{os.getpid()}"
    proc = subprocess.run(
        [
            "git",
            "-C",
            repo_dir,
            "stash",
            "push",
            "--include-untracked",
            "-m",
            stash_message,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        raise SystemExit(
            "start-gate: auto-heal failed while creating stash: "
            f"{' '.join(proc.args)} ({stderr or stdout or 'unknown failure'})"
        )

    output = (proc.stdout or "") + (proc.stderr or "")
    if "No local changes to save" in output:
        return None

    after = _list_stash_refs(repo_dir)
    new_refs = [ref for ref in after if ref not in before]
    if new_refs:
        return new_refs[0]

    # Fallback for older git versions / unusual output; newest stash entry should be ours.
    return "stash@{0}"


def _restore_stash(repo_dir: str, stash_ref: str) -> None:
    apply = run_command(["git", "-C", repo_dir, "stash", "apply", stash_ref], check=False)
    if apply.returncode != 0:
        raise SystemExit(
            "start-gate: auto-heal failed to restore local changes; "
            f"please run `git stash show {stash_ref}` and `git stash pop {stash_ref}` manually."
        )
    drop = run_command(["git", "-C", repo_dir, "stash", "drop", stash_ref], check=False)
    if drop.returncode != 0:
        print(
            "start-gate: warning: local changes restored but stash entry could not be dropped automatically "
            f"({drop.stderr or drop.stdout})"
        )


def _ensure_repo_clean(
    repo_dir: str,
    *,
    label: str,
    auto_heal: bool,
) -> Callable[[], None] | None:
    proc = subprocess.run(
        ["git", "-C", repo_dir, "status", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("start-gate: failed to check repository state")

    if not proc.stdout.strip():
        return None

    if not auto_heal:
        raise SystemExit(
            f"start-gate: {label} has local changes. Clean it before starting a task."
        )

    stash_ref = _auto_heal_dirty_repo(repo_dir, label=label)
    if not stash_ref:
        raise SystemExit(
            f"start-gate: {label} appears dirty but stash capture reported no changes."
        )

    rerun = subprocess.run(
        ["git", "-C", repo_dir, "status", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )
    if rerun.returncode != 0:
        _restore_stash(repo_dir, stash_ref)
        raise SystemExit("start-gate: failed to re-check repository state after auto-heal")

    if rerun.stdout.strip():
        _restore_stash(repo_dir, stash_ref)
        raise SystemExit(
            "start-gate: auto-heal did not produce a clean tree. "
            "Please resolve blockers and rerun."
        )

    print(
        f"start-gate: warning: {label} had local changes; auto-healed via stash and will restore after checks."
    )
    return lambda: _restore_stash(repo_dir, stash_ref)


def main() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("start-gate: required command not found: gh")

    require_gh_checks = env_flag("START_GATE_REQUIRE_GH", default=True)
    enforce_remote_failures = env_flag("START_GATE_ENFORCE_REMOTE_FAILURES", default=True)
    auto_heal_current = env_flag("START_GATE_AUTO_HEAL_CURRENT", default=True)
    auto_heal_primary = env_flag("START_GATE_AUTO_HEAL_PRIMARY", default=False)
    advisory_main_workflows = _workflow_name_set(
        os.environ.get(
            "START_GATE_ADVISORY_MAIN_WORKFLOWS",
            "Maintainability Architecture Audit",
        )
    )

    if require_gh_checks:
        run_command(["gh", "auth", "status"])
    else:
        print("start-gate: warning: skipping gh auth check because START_GATE_REQUIRE_GH=0")

    git_marker = Path(".git")
    if not git_marker.exists():
        raise SystemExit("start-gate: missing .git marker")

    in_worktree = False
    if git_marker.is_file():
        gitdir_line = git_marker.read_text(encoding="utf-8").strip()
        if not gitdir_line.startswith("gitdir:"):
            raise SystemExit("start-gate: expected .git to be a gitdir pointer file")

        gitdir = gitdir_line.split(":", 1)[1].strip()
        gitdir_path = Path(gitdir).resolve()
        in_worktree = ".git/worktrees/" in gitdir_path.as_posix()
        primary = gitdir_path.parent.parent.parent
    elif git_marker.is_dir():
        primary = Path.cwd().resolve()
    else:
        raise SystemExit("start-gate: unrecognized .git marker type")

    restore_hooks: list[Callable[[], None]] = []

    try:
        restore_current = _ensure_repo_clean(
            os.getcwd(),
            label="current worktree",
            auto_heal=auto_heal_current,
        )
        if restore_current is not None:
            restore_hooks.append(restore_current)

        proc = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=False,
        )
        remote = (proc.stdout or "").strip()
        match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
        if not match:
            raise SystemExit(
                "start-gate: could not detect github repo owner/name from git remote.origin.url"
            )
        repo_slug = f"{match.group('owner')}/{match.group('repo')}"
        failed_conclusions = {
            "failure",
            "timed_out",
            "cancelled",
            "startup_failure",
            "action_required",
            "stale",
        }

        failed_prs: list[dict] = []

        runs_payload = run_json(
            ["gh", "api", f"repos/{repo_slug}/actions/runs?branch=main&per_page=20"],
            required=require_gh_checks,
        )
        if runs_payload is None:
            print(
                "start-gate: warning: skipping workflow checks because gh is unavailable in current environment"
            )
        else:
            runs = runs_payload.get("workflow_runs", []) if isinstance(runs_payload, dict) else []
            completed = [
                run for run in runs if isinstance(run, dict) and str(run.get("status") or "") == "completed"
            ]
            if not completed:
                if enforce_remote_failures:
                    raise SystemExit("start-gate: no completed main workflow runs found")
                print("start-gate: warning: no completed main workflow runs found")

            latest_by_workflow: dict[str, dict] = {}
            for run in completed:
                if not isinstance(run, dict):
                    continue
                name = str(run.get("name") or "")
                if name not in latest_by_workflow:
                    latest_by_workflow[name] = run

            failures = [
                {
                    "name": row.get("name"),
                    "conclusion": row.get("conclusion"),
                    "html_url": row.get("html_url"),
                }
                for row in latest_by_workflow.values()
                if str(row.get("conclusion") or "").strip().lower() in failed_conclusions
            ]
            advisory_failures = [
                item
                for item in failures
                if str(item.get("name") or "").strip().lower() in advisory_main_workflows
            ]
            blocking_failures = [item for item in failures if item not in advisory_failures]

            if advisory_failures:
                advisory_text = ", ".join(
                    f'{item["name"]}={item["conclusion"]} ({item["html_url"]})'
                    for item in advisory_failures
                )
                print(
                    "start-gate: warning: advisory main workflow failures detected: "
                    f"{advisory_text}"
                )

            if blocking_failures:
                failures_text = ", ".join(
                    f'{item["name"]}={item["conclusion"]} ({item["html_url"]})'
                    for item in blocking_failures
                )
                if enforce_remote_failures:
                    raise SystemExit(
                        f"start-gate: latest main workflow failures detected: {failures_text}"
                    )
                print(
                    "start-gate: warning: ignoring remote main workflow failures (non-blocking mode): "
                    f"{failures_text}"
                )

        pulls_payload = run_json(
            ["gh", "api", f"repos/{repo_slug}/pulls?state=open&per_page=50"],
            required=require_gh_checks,
        )
        if pulls_payload is not None:
            pulls = pulls_payload if isinstance(pulls_payload, list) else []
            for pr in (pulls if isinstance(pulls, list) else []):
                if not isinstance(pr, dict):
                    continue

                head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
                branch = str((head or {}).get("ref") or "")
                if not branch.startswith("codex/"):
                    continue

                number = pr.get("number")
                sha = str((head or {}).get("sha") or "")
                if not number or not sha:
                    continue

                checks_payload = run_json(
                    [
                        "gh",
                        "api",
                        f"repos/{repo_slug}/commits/{sha}/check-runs?per_page=100",
                    ],
                    required=require_gh_checks,
                )
                if checks_payload is None:
                    continue
                checks = (
                    checks_payload.get("check_runs", [])
                    if isinstance(checks_payload, dict)
                    else []
                )
                failed_checks = []
                for check in checks:
                    if not isinstance(check, dict):
                        continue
                    status = str(check.get("status") or "").strip().lower()
                    conclusion = str(check.get("conclusion") or "").strip().lower()
                    if status == "completed" and conclusion in failed_conclusions:
                        failed_checks.append(
                            {
                                "name": check.get("name"),
                                "conclusion": conclusion,
                            }
                        )
                if failed_checks:
                    failed_prs.append(
                        {
                            "number": number,
                            "title": pr.get("title"),
                            "url": pr.get("html_url"),
                            "failed_checks": failed_checks,
                        }
                    )

        if failed_prs:
            first = failed_prs[0]
            failure_text = (
                "start-gate: open PR check failures detected. "
                f"Example: PR #{first['number']} {first['title']} ({first['url']})"
            )
            if enforce_remote_failures:
                raise SystemExit(failure_text)
            print(f"start-gate: warning: {failure_text}")

        require_primary_default = False if in_worktree else True
        require_primary_clean = env_flag(
            "START_GATE_REQUIRE_PRIMARY_CLEAN", default=require_primary_default
        )
        if require_primary_clean:
            proc = subprocess.run(
                ["git", "-C", str(primary), "status", "--short"],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                raise SystemExit("start-gate: failed to check primary workspace state")

            if proc.stdout.strip():
                if not auto_heal_primary:
                    raise SystemExit(
                        "start-gate: primary workspace has local changes. Clean it before starting a task."
                    )
                restore_primary = _ensure_repo_clean(
                    str(primary),
                    label="primary workspace",
                    auto_heal=auto_heal_primary,
                )
                if restore_primary is not None:
                    restore_hooks.append(restore_primary)
        elif in_worktree:
            print(
                "start-gate: skipping primary workspace cleanliness check in worktree mode "
                "(START_GATE_REQUIRE_PRIMARY_CLEAN=0)."
            )
        else:
            print("start-gate: skipping primary workspace cleanliness check (START_GATE_REQUIRE_PRIMARY_CLEAN=0)")

        print("start-gate: passed")
    finally:
        for restore in reversed(restore_hooks):
            try:
                restore()
            except Exception as exc:
                print(f"start-gate: warning: failed to restore auto-healed state ({exc})")


if __name__ == "__main__":
    main()
