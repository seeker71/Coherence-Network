#!/usr/bin/env python3
"""Worktree PR guard: prevent common CI failures and track PR check failures."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "api"

# Allow importing api.app services from repo root script.
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services import release_gate_service as gates  # noqa: E402
try:  # noqa: SIM105
    from app.services import telemetry_persistence_service  # type: ignore[attr-defined]  # noqa: E402
except Exception:  # pragma: no cover - best effort import only
    telemetry_persistence_service = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record_external_tool_usage(
    *,
    tool_name: str,
    provider: str,
    operation: str,
    resource: str,
    status: str,
    http_status: int | None = None,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if telemetry_persistence_service is None:
        return
    try:
        telemetry_persistence_service.append_external_tool_usage_event(
            {
                "event_id": f"tool_{uuid.uuid4().hex}",
                "occurred_at": _utc_now(),
                "tool_name": tool_name,
                "provider": provider,
                "operation": operation,
                "resource": resource,
                "status": status,
                "http_status": http_status,
                "duration_ms": duration_ms,
                "payload": payload or {},
            }
        )
    except Exception:
        return


def _safe_branch_name(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-") or "unknown-branch"


def _default_branch() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "unknown-branch"
    value = (proc.stdout or "").strip()
    return value or "unknown-branch"


@dataclass
class StepResult:
    name: str
    command: str
    ok: bool
    exit_code: int
    duration_seconds: float
    output_tail: str
    hint: str


def _hint_for_step(name: str, command: str, output: str) -> str:
    lower = f"{name} {command} {output}".lower()
    if "validate_commit_evidence" in lower:
        return "Add/update docs/system_audit/commit_evidence_*.json and include changed files under change_files."
    if "validate_spec_quality" in lower:
        return "Update changed specs to satisfy quality contract sections (acceptance, gaps, references)."
    if "validate_workflow_references" in lower:
        return "Fix missing/broken workflow file references in docs/specs before push."
    if "run_maintainability_audit" in lower or "maintainability" in lower:
        return "Address maintainability regressions or update baseline with explicit review evidence."
    if "pytest" in lower:
        return "Reproduce locally with failing test subset, fix implementation, re-run full api pytest."
    if "npm run build" in lower:
        return "Fix web build/type/runtime issues and re-run npm ci && npm run build in web/."
    if "verify_worktree_local_web" in lower:
        return "Inspect API/web runtime logs emitted by verify_worktree_local_web.sh and fix failing route/runtime errors."
    return "Review command output tail, fix root cause, and re-run this guard before push."


def _existing_script_command(*relative_candidates: str) -> str | None:
    for rel in relative_candidates:
        if (REPO_ROOT / rel).exists():
            return f"python3 {rel}"
    return None


def _run_step(name: str, command: str, cwd: Path, env: dict[str, str] | None = None) -> StepResult:
    start = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
        env=env,
    )
    duration = time.monotonic() - start
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    lines = output.splitlines()
    tail = "\n".join(lines[-60:]) if lines else ""
    hint = _hint_for_step(name, command, output)
    return StepResult(
        name=name,
        command=command,
        ok=proc.returncode == 0,
        exit_code=proc.returncode,
        duration_seconds=round(duration, 2),
        output_tail=tail,
        hint=hint,
    )


def _changed_paths_worktree() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    paths: list[str] = []
    for line in (proc.stdout or "").splitlines():
        if not line.strip():
            continue
        payload = line[3:] if len(line) >= 4 else ""
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        if payload:
            paths.append(payload.strip())
    return paths


def _changed_paths_range(base_ref: str, head_ref: str = "HEAD") -> tuple[list[str], str | None]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base_ref, head_ref],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or "failed to compute changed files in diff range"
        return [], err
    paths = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return paths, None


def _is_runtime_change(path: str) -> bool:
    checks = (
        "api/app/",
        "api/scripts/",
        "web/app/",
        "web/components/",
        "web/lib/",
    )
    return path.startswith(checks)


def _worktree_has_runtime_changes(base_ref: str) -> bool:
    changed, err = _changed_paths_range(base_ref)
    worktree_changed = _changed_paths_worktree()
    if err:
        # Fail-open to avoid incorrectly skipping a blocking guard on diff lookup issues.
        return True
    all_changed = set(changed)
    all_changed.update(worktree_changed)
    return any(_is_runtime_change(path) for path in all_changed)


def _run_commit_evidence_guard(base_ref: str) -> StepResult:
    start = time.monotonic()
    changed, diff_error = _changed_paths_range(base_ref)
    worktree_changed = _changed_paths_worktree()
    if diff_error:
        return StepResult(
            name="commit-evidence-guard",
            command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
            ok=False,
            exit_code=1,
            duration_seconds=round(time.monotonic() - start, 2),
            output_tail=f"ERROR: unable to compute changed files for range {base_ref}..HEAD: {diff_error}",
            hint=f"Verify git refs are available locally (for example: git fetch origin main) and rerun with --base-ref {base_ref}.",
        )

    if not changed and not worktree_changed:
        return StepResult(
            name="commit-evidence-guard",
            command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
            ok=True,
            exit_code=0,
            duration_seconds=round(time.monotonic() - start, 2),
            output_tail=f"No changed files detected in range {base_ref}..HEAD or current worktree; evidence guard skipped.",
            hint="No action required.",
        )

    tails: list[str] = []
    if changed:
        cmd = [
            "python3",
            "scripts/validate_commit_evidence.py",
            "--base",
            base_ref,
            "--head",
            "HEAD",
            "--require-changed-evidence",
        ]
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        out = f"$ {' '.join(cmd)}\n{(proc.stdout or '').strip()}\n{(proc.stderr or '').strip()}".strip()
        tails.append(out)
        if proc.returncode != 0:
            return StepResult(
                name="commit-evidence-guard",
                command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
                ok=False,
                exit_code=proc.returncode,
                duration_seconds=round(time.monotonic() - start, 2),
                output_tail="\n\n".join(tails)[-5000:],
                hint="Fix commit evidence fields to satisfy CI diff-range validation.",
            )

    if worktree_changed:
        evidence_files = sorted(
            p for p in worktree_changed if re.match(r"^docs/system_audit/commit_evidence_.*\.json$", p)
        )
        if not evidence_files:
            return StepResult(
                name="commit-evidence-guard",
                command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
                ok=False,
                exit_code=1,
                duration_seconds=round(time.monotonic() - start, 2),
                output_tail="ERROR: changed files present in working tree but no changed docs/system_audit/commit_evidence_*.json file found.",
                hint="Add/update a commit_evidence JSON file before committing.",
            )

        declared: set[str] = set()
        for evidence_file in evidence_files:
            cmd = ["python3", "scripts/validate_commit_evidence.py", "--file", evidence_file]
            proc = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            out = f"$ {' '.join(cmd)}\n{(proc.stdout or '').strip()}\n{(proc.stderr or '').strip()}".strip()
            tails.append(out)
            if proc.returncode != 0:
                return StepResult(
                    name="commit-evidence-guard",
                    command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
                    ok=False,
                    exit_code=proc.returncode,
                    duration_seconds=round(time.monotonic() - start, 2),
                    output_tail="\n\n".join(tails)[-5000:],
                    hint="Fix commit evidence schema/required fields before commit.",
                )
            try:
                payload = json.loads((REPO_ROOT / evidence_file).read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive guard
                return StepResult(
                    name="commit-evidence-guard",
                    command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
                    ok=False,
                    exit_code=1,
                    duration_seconds=round(time.monotonic() - start, 2),
                    output_tail=f"ERROR: unable to parse evidence file {evidence_file}: {exc}",
                    hint="Fix commit evidence JSON syntax.",
                )
            listed = payload.get("change_files")
            if isinstance(listed, list):
                declared.update(str(item).strip() for item in listed if isinstance(item, str) and str(item).strip())

        expected = sorted(
            path
            for path in worktree_changed
            if not re.match(r"^docs/system_audit/commit_evidence_.*\.json$", path)
        )
        missing = [path for path in expected if path not in declared]
        if missing:
            tails.append(f"ERROR: worktree evidence coverage missing changed paths: {missing}")
            return StepResult(
                name="commit-evidence-guard",
                command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
                ok=False,
                exit_code=1,
                duration_seconds=round(time.monotonic() - start, 2),
                output_tail="\n\n".join(tails)[-5000:],
                hint="Update change_files to include all changed worktree paths before commit.",
            )

    return StepResult(
        name="commit-evidence-guard",
        command=f"python3 scripts/validate_commit_evidence.py --base {base_ref} --head HEAD --require-changed-evidence",
        ok=True,
        exit_code=0,
        duration_seconds=round(time.monotonic() - start, 2),
        output_tail="\n\n".join(tails)[-5000:],
        hint="Commit evidence contract passed for CI-parity and worktree coverage validation.",
    )


def _local_steps(
    base_ref: str,
    skip_api_tests: bool,
    skip_web_build: bool,
    require_gh_auth: bool,
) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    workflow_check = _existing_script_command("scripts/validate_workflow_references.py")
    if workflow_check:
        steps.append(("workflow-reference-guard", workflow_check))
    no_v1_check = _existing_script_command(
        "scripts/validate_no_v1_api_usage.py",
        "api/scripts/validate_no_v1_api_usage.py",
    )
    if no_v1_check:
        steps.append(("no-internal-v1-guard", no_v1_check))
    steps.extend(
        [
            (
                "spec-quality-guard",
                f"python3 scripts/validate_spec_quality.py --base {base_ref} --head HEAD",
            ),
            (
                "runtime-drift-guard",
                "python3 scripts/check_runtime_drift.py",
            ),
            (
                "maintainability-regression-guard",
                "python3 api/scripts/run_maintainability_audit.py --output maintainability_audit_report.json --fail-on-regression",
            ),
        ]
    )
    if not _worktree_has_runtime_changes(base_ref):
        steps = [s for s in steps if s[0] != "maintainability-regression-guard"]
    if require_gh_auth:
        steps.insert(0, ("dev-auth-preflight", "python3 scripts/check_dev_auth.py --json"))
    if not skip_api_tests:
        steps.append(("api-tests", "cd api && pytest -q"))
    if not skip_web_build:
        steps.append(("web-build", "cd web && npm ci && npm run build"))
    steps.append(("worktree-runtime-web-guard", "./scripts/verify_worktree_local_web.sh"))
    return steps


def _check_run_hint(name: str) -> str:
    value = name.lower()
    mapping: list[tuple[str, str]] = [
        ("validate commit evidence", "python3 scripts/validate_commit_evidence.py --base origin/main --head HEAD --require-changed-evidence"),
        ("spec quality", "python3 scripts/validate_spec_quality.py --base origin/main --head HEAD"),
        ("workflow file references", "python3 scripts/validate_workflow_references.py"),
        ("maintainability", "python3 api/scripts/run_maintainability_audit.py --output maintainability_audit_report.json --fail-on-regression"),
        ("run api tests", "cd api && pytest -q"),
        ("test", "cd api && pytest -q"),
        ("build web", "cd web && npm ci && npm run build"),
        ("thread gates", "python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main"),
    ]
    for key, cmd in mapping:
        if key in value:
            return cmd
    return "python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main"


def _collect_remote_pr_failures(repo: str, branch: str, base: str, token: str | None) -> dict[str, Any]:
    prs = gates.get_open_prs(repo, head_branch=branch, github_token=token)
    if not prs:
        return {
            "status": "no_open_pr",
            "repo": repo,
            "branch": branch,
            "base": base,
            "message": "No open PR found for branch; remote check tracking skipped.",
        }

    pr = prs[0]
    head_sha = pr.get("head", {}).get("sha")
    if not isinstance(head_sha, str) or not head_sha:
        return {
            "status": "error",
            "repo": repo,
            "branch": branch,
            "base": base,
            "message": "Open PR found but head SHA missing.",
        }

    required_contexts = gates.get_required_contexts(repo, base, github_token=token) or []
    commit_status = gates.get_commit_status(repo, head_sha, github_token=token)
    check_runs = gates.get_check_runs(repo, head_sha, github_token=token)
    gate_eval = gates.evaluate_pr_gates(pr, commit_status, check_runs, required_contexts)

    failing_states = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
    failures: list[dict[str, Any]] = []
    for run in check_runs:
        conclusion = str(run.get("conclusion") or "").lower()
        status = str(run.get("status") or "").lower()
        if conclusion and conclusion in failing_states:
            name = str(run.get("name") or "unknown")
            failures.append(
                {
                    "name": name,
                    "status": status,
                    "conclusion": conclusion,
                    "html_url": run.get("html_url"),
                    "details_url": run.get("details_url"),
                    "started_at": run.get("started_at"),
                    "completed_at": run.get("completed_at"),
                    "suggested_local_preflight": _check_run_hint(name),
                }
            )

    status_context_failures: list[dict[str, Any]] = []
    statuses = commit_status.get("statuses")
    if isinstance(statuses, list):
        for item in statuses:
            if not isinstance(item, dict):
                continue
            state = str(item.get("state") or "").lower()
            if state in ("success", "expected"):
                continue
            context = str(item.get("context") or "unknown")
            status_context_failures.append(
                {
                    "context": context,
                    "state": state or "unknown",
                    "description": item.get("description"),
                    "target_url": item.get("target_url"),
                    "suggested_local_preflight": _check_run_hint(context),
                }
            )

    return {
        "status": "ok",
        "repo": repo,
        "branch": branch,
        "base": base,
        "pr_number": pr.get("number"),
        "pr_url": pr.get("html_url"),
        "head_sha": head_sha,
        "combined_status_state": commit_status.get("state"),
        "ready_to_merge": gate_eval.get("ready_to_merge"),
        "missing_required_contexts": gate_eval.get("missing_required_contexts"),
        "failing_required_contexts": gate_eval.get("failing_required_contexts"),
        "failing_check_runs": failures,
        "failing_status_contexts": status_context_failures,
    }


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _collect_deployment_health(repo: str, token: str, max_age_hours: float) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}/actions/workflows/public-deploy-contract.yml/runs"
    started = time.monotonic()
    with httpx.Client(timeout=12.0, headers=gates._headers(token)) as client:
        response = client.get(url, params={"branch": "main", "per_page": 10})
        _record_external_tool_usage(
            tool_name="github-api",
            provider="github-actions",
            operation="deployment_health_workflow_runs",
            resource=f"{repo}/actions/workflows/public-deploy-contract.yml/runs",
            status="success" if response.status_code < 400 else "error",
            http_status=response.status_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            payload={"branch": "main"},
        )
        response.raise_for_status()
        payload = response.json()

    runs = payload.get("workflow_runs") if isinstance(payload, dict) else []
    if not isinstance(runs, list) or not runs:
        return {
            "status": "unknown",
            "healthy": False,
            "message": "No Public Deploy Contract runs found on main.",
        }

    latest = None
    for run in runs:
        if isinstance(run, dict) and str(run.get("status")) == "completed":
            latest = run
            break
    if latest is None:
        latest = runs[0] if isinstance(runs[0], dict) else None
    if not isinstance(latest, dict):
        return {
            "status": "unknown",
            "healthy": False,
            "message": "Could not parse latest Public Deploy Contract run.",
        }

    conclusion = str(latest.get("conclusion") or "unknown")
    updated_at = _parse_iso8601(latest.get("updated_at"))
    age_hours = None
    if updated_at is not None:
        age_hours = round((datetime.now(UTC) - updated_at.astimezone(UTC)).total_seconds() / 3600, 2)
    healthy = conclusion == "success" and (age_hours is not None and age_hours <= max_age_hours)
    return {
        "status": "ok",
        "healthy": healthy,
        "conclusion": conclusion,
        "max_age_hours": max_age_hours,
        "age_hours": age_hours,
        "run_id": latest.get("id"),
        "run_url": latest.get("html_url"),
        "created_at": latest.get("created_at"),
        "updated_at": latest.get("updated_at"),
        "message": (
            "Latest deploy contract is healthy."
            if healthy
            else "Latest deploy contract is failed/stale; fix deployment before new feature work."
        ),
    }


def _write_report(output_dir: Path, payload: dict[str, Any], branch: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"pr_check_guard_{stamp}_{_safe_branch_name(branch)}.json"
    path = output_dir / filename
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local CI-parity preflight checks and track remote PR check failures."
    )
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--branch", default=_default_branch())
    parser.add_argument("--base", default="main")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file guards.")
    parser.add_argument("--mode", choices=("local", "remote", "all"), default="all")
    parser.add_argument("--skip-api-tests", action="store_true")
    parser.add_argument("--skip-web-build", action="store_true")
    parser.add_argument(
        "--require-gh-auth",
        action="store_true",
        help="Include check_dev_auth.py in local preflight (off by default).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "docs" / "system_audit" / "pr_check_failures"),
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout.")
    parser.add_argument(
        "--deploy-success-max-age-hours",
        type=float,
        default=6.0,
        help="Maximum age (hours) for latest successful Public Deploy Contract run on main.",
    )
    args = parser.parse_args()

    report: dict[str, Any] = {
        "generated_at": _utc_now(),
        "tool": "scripts/worktree_pr_guard.py",
        "repo_root": str(REPO_ROOT),
        "repo": args.repo,
        "branch": args.branch,
        "base": args.base,
        "mode": args.mode,
        "local_preflight": {"status": "skipped", "steps": []},
        "remote_pr_checks": {"status": "skipped"},
        "deployment_health": {"status": "skipped"},
    }

    if args.mode in ("local", "all"):
        steps: list[StepResult] = []
        for name, command in _local_steps(
            args.base_ref,
            args.skip_api_tests,
            args.skip_web_build,
            args.require_gh_auth,
        ):
            step = _run_step(name, command, cwd=REPO_ROOT)
            steps.append(step)
            if not step.ok:
                break
            if step.name == "spec-quality-guard":
                evidence_step = _run_commit_evidence_guard(args.base_ref)
                steps.append(evidence_step)
                if not evidence_step.ok:
                    break
        local_ok = all(s.ok for s in steps)
        report["local_preflight"] = {
            "status": "pass" if local_ok else "fail",
            "steps": [
                {
                    "name": s.name,
                    "command": s.command,
                    "ok": s.ok,
                    "exit_code": s.exit_code,
                    "duration_seconds": s.duration_seconds,
                    "hint": s.hint,
                    "output_tail": s.output_tail,
                }
                for s in steps
            ],
        }

    if args.mode in ("remote", "all"):
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if not token:
            report["remote_pr_checks"] = {
                "status": "skipped_no_token",
                "message": "Set GITHUB_TOKEN or GH_TOKEN to track remote PR check failures.",
            }
        else:
            report["remote_pr_checks"] = _collect_remote_pr_failures(
                repo=args.repo,
                branch=args.branch,
                base=args.base,
                token=token,
            )
            report["deployment_health"] = _collect_deployment_health(
                repo=args.repo,
                token=token,
                max_age_hours=args.deploy_success_max_age_hours,
            )

    blocking = False
    local_status = report["local_preflight"].get("status")
    if local_status == "fail":
        blocking = True

    remote = report.get("remote_pr_checks", {})
    if isinstance(remote, dict):
        if remote.get("status") == "ok":
            if (
                remote.get("failing_check_runs")
                or remote.get("failing_status_contexts")
                or remote.get("missing_required_contexts")
                or remote.get("failing_required_contexts")
            ):
                blocking = True
        elif remote.get("status") == "error":
            blocking = True
    deploy_health = report.get("deployment_health", {})
    if isinstance(deploy_health, dict) and deploy_health.get("status") == "ok":
        if not bool(deploy_health.get("healthy")):
            blocking = True

    report["ready_for_push"] = not blocking
    report["summary"] = (
        "All selected checks passed."
        if not blocking
        else "Blocking failures detected; see local_preflight/remote_pr_checks details."
    )
    _record_external_tool_usage(
        tool_name="worktree-pr-guard",
        provider="coherence-internal",
        operation="run",
        resource=f"mode={args.mode}",
        status="success" if report["ready_for_push"] else "error",
        payload={
            "branch": args.branch,
            "base": args.base,
            "local_preflight_status": report["local_preflight"].get("status"),
            "remote_pr_checks_status": report["remote_pr_checks"].get("status"),
            "deployment_health_status": report["deployment_health"].get("status"),
            "summary": report["summary"],
        },
    )

    output_path = _write_report(Path(args.output_dir), report, args.branch)
    report["report_path"] = str(output_path)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"PR guard report: {output_path}")
        print(f"ready_for_push={report['ready_for_push']}")
        print(report["summary"])
        local = report["local_preflight"]
        print(f"local_preflight={local.get('status')}")
        remote_status = report["remote_pr_checks"].get("status")
        print(f"remote_pr_checks={remote_status}")

    return 0 if not blocking else 2


if __name__ == "__main__":
    raise SystemExit(main())
