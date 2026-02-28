from __future__ import annotations

import json
import re
import shutil
import subprocess
import os
from datetime import datetime, timezone
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


def _parse_iso8601_utc(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, (dict, list)):
        return payload
    return None


def _load_workflow_owners(path: Path) -> dict[str, str]:
    payload = _load_json_file(path)
    if not isinstance(payload, dict):
        return {}
    mapping = payload.get("workflow_owners")
    if not isinstance(mapping, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in mapping.items():
        name = str(key or "").strip().lower()
        owner = str(value or "").strip()
        if name and owner:
            out[name] = owner
    return out


def _load_active_waivers(path: Path, now: datetime) -> tuple[dict[str, list[dict]], list[str]]:
    payload = _load_json_file(path)
    if payload is None:
        return {}, []
    if not isinstance(payload, dict):
        return {}, [f"start-gate: warning: invalid waiver payload in {path} (expected object)"]

    rows = payload.get("waivers")
    if not isinstance(rows, list):
        return {}, [f"start-gate: warning: invalid waiver payload in {path} (missing waivers list)"]

    warnings: list[str] = []
    active_by_workflow: dict[str, list[dict]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            warnings.append(f"start-gate: warning: ignoring waiver[{index}] in {path} (expected object)")
            continue
        workflow = str(row.get("workflow") or "").strip().lower()
        owner = str(row.get("owner") or "").strip()
        reason = str(row.get("reason") or "").strip()
        expires_at_raw = str(row.get("expires_at") or "").strip()
        run_url_contains = str(row.get("run_url_contains") or "").strip()
        expires_at = _parse_iso8601_utc(expires_at_raw)
        if not workflow or not owner or not reason or expires_at is None:
            warnings.append(
                f"start-gate: warning: ignoring waiver[{index}] in {path} "
                "(requires workflow, owner, reason, expires_at)"
            )
            continue
        if expires_at <= now:
            continue
        waiver = {
            "workflow": workflow,
            "owner": owner,
            "reason": reason,
            "expires_at": expires_at,
            "run_url_contains": run_url_contains,
        }
        active_by_workflow.setdefault(workflow, []).append(waiver)
    return active_by_workflow, warnings


def _match_waiver_for_failure(failure: dict, waivers: list[dict]) -> dict | None:
    failure_url = str(failure.get("html_url") or "").strip()
    for waiver in waivers:
        run_url_contains = str(waiver.get("run_url_contains") or "").strip()
        if run_url_contains and run_url_contains not in failure_url:
            continue
        return waiver
    return None


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


def main() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("start-gate: required command not found: gh")

    require_gh_checks = env_flag("START_GATE_REQUIRE_GH", default=True)
    enforce_remote_failures = env_flag("START_GATE_ENFORCE_REMOTE_FAILURES", default=True)
    advisory_main_workflows = _workflow_name_set(
        os.environ.get(
            "START_GATE_ADVISORY_MAIN_WORKFLOWS",
            "Maintainability Architecture Audit",
        )
    )
    owners_file = Path(
        os.environ.get(
            "START_GATE_WORKFLOW_OWNERS_FILE",
            "config/start_gate_workflow_owners.json",
        )
    )
    waivers_file = Path(
        os.environ.get(
            "START_GATE_MAIN_FAILURE_WAIVERS_FILE",
            "config/start_gate_main_workflow_waivers.json",
        )
    )
    require_workflow_owner = env_flag("START_GATE_REQUIRE_WORKFLOW_OWNER", default=True)
    now = datetime.now(timezone.utc)
    workflow_owners = _load_workflow_owners(owners_file)
    active_waivers, waiver_warnings = _load_active_waivers(waivers_file, now)
    for warning in waiver_warnings:
        print(warning)

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

    proc = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit("start-gate: failed to check current worktree state")
    if proc.stdout.strip():
        raise SystemExit(
            "start-gate: current worktree has local changes. Do not abandon in-flight work: "
            "finish merge/deploy (or record an explicit blocker), then rerun start-gate from a clean worktree."
        )

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
        print("start-gate: warning: skipping workflow checks because gh is unavailable in current environment")
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
        waived_failures: list[tuple[dict, dict]] = []
        remaining_blocking: list[dict] = []
        for failure in blocking_failures:
            name_key = str(failure.get("name") or "").strip().lower()
            waiver = _match_waiver_for_failure(failure, active_waivers.get(name_key, []))
            if waiver is None:
                remaining_blocking.append(failure)
                continue
            waived_failures.append((failure, waiver))
        blocking_failures = remaining_blocking

        if advisory_failures:
            advisory_text = ", ".join(
                f'{item["name"]}={item["conclusion"]} ({item["html_url"]})'
                for item in advisory_failures
            )
            print(
                "start-gate: warning: advisory main workflow failures detected: "
                f"{advisory_text}"
            )
        if waived_failures:
            waiver_text = ", ".join(
                (
                    f'{failure["name"]}={failure["conclusion"]} ({failure["html_url"]}) '
                    f'waived_by={waiver["owner"]} until={waiver["expires_at"].isoformat()} '
                    f'reason="{waiver["reason"]}"'
                )
                for failure, waiver in waived_failures
            )
            print(f"start-gate: warning: temporary workflow waivers applied: {waiver_text}")

        if blocking_failures:
            if require_workflow_owner:
                missing_owner = [
                    item for item in blocking_failures if str(item.get("name") or "").strip().lower() not in workflow_owners
                ]
                if missing_owner:
                    missing_text = ", ".join(str(item.get("name") or "unknown") for item in missing_owner)
                    raise SystemExit(
                        "start-gate: blocking main workflow failures missing owner mapping: "
                        f"{missing_text}. Update {owners_file}."
                    )
            failures_text = ", ".join(
                (
                    f'{item["name"]}={item["conclusion"]} ({item["html_url"]}) '
                    f'owner={workflow_owners.get(str(item.get("name") or "").strip().lower(), "unassigned")}'
                )
                for item in blocking_failures
            )
            if enforce_remote_failures:
                raise SystemExit(
                    f"start-gate: latest main workflow failures detected: {failures_text}"
                )
            print(f"start-gate: warning: ignoring remote main workflow failures (non-blocking mode): {failures_text}")

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
                ["gh", "api", f"repos/{repo_slug}/commits/{sha}/check-runs?per_page=100"],
                required=require_gh_checks,
            )
            if checks_payload is None:
                continue
            checks = checks_payload.get("check_runs", []) if isinstance(checks_payload, dict) else []
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
            raise SystemExit(
                "start-gate: primary workspace has local changes. Do not abandon in-flight work: "
                "finish merge/deploy (or record an explicit blocker), then rerun start-gate from a clean workspace."
            )
    elif in_worktree:
        print(
            "start-gate: skipping primary workspace cleanliness check in worktree mode "
            "(START_GATE_REQUIRE_PRIMARY_CLEAN=0)."
        )
    else:
        print("start-gate: skipping primary workspace cleanliness check (START_GATE_REQUIRE_PRIMARY_CLEAN=0)")

    print("start-gate: passed")


if __name__ == "__main__":
    main()
