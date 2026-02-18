# Coherence Network — common targets

.PHONY: test run setup lint web-worktree-validate spec-quality pr-preflight start-gate install-pre-push-hook

test:
	cd api && .venv/bin/pytest -v

run:
	cd api && uvicorn app.main:app --reload --port 8000

setup:
	cd api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

lint:
	cd api && .venv/bin/ruff check . 2>/dev/null || true

web-worktree-validate:
	./scripts/verify_worktree_local_web.sh

spec-quality:
	python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

pr-preflight:
	python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main

install-pre-push-hook:
	./scripts/setup_pre_push_hook.sh

start-gate:
	@if [ ! -f .git ]; then \
	  echo "start-gate: missing .git marker" && exit 1; \
	fi
	@if [ "$$(cat .git | awk '{print $$1}')" != "gitdir:" ]; then \
	  echo "start-gate: expected linked worktree (.git file). Refuse to run in primary workspace." && exit 1; \
	fi
	@if [ -n "$$(git status --short)" ]; then \
	  echo "start-gate: current worktree has local changes. Clean it before starting a task." && exit 1; \
	fi
	@python3 - <<'PY'
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

gitdir_line = Path(".git").read_text(encoding="utf-8").strip()
if not gitdir_line.startswith("gitdir:"):
    raise SystemExit("start-gate: expected .git to be a gitdir pointer file")
gitdir = gitdir_line.split(":", 1)[1].strip()
primary = Path(gitdir).resolve().parent.parent.parent
def run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"start-gate: command failed: {' '.join(cmd)}")
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

if shutil.which("gh") is None:
    raise SystemExit("start-gate: required command not found: gh")

run_command(["gh", "auth", "status"])

proc = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True, check=False)
remote = (proc.stdout or "").strip()
match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
if not match:
    raise SystemExit("start-gate: could not detect github repo owner/name from git remote.origin.url")
repo_slug = f"{match.group('owner')}/{match.group('repo')}"

runs_payload = run_json(["gh", "api", f"repos/{repo_slug}/actions/runs", "-f", "branch=main", "-f", "per_page=20"])
runs = runs_payload.get("workflow_runs", []) if isinstance(runs_payload, dict) else []
completed = [
    run for run in runs if isinstance(run, dict) and str(run.get("status") or "") == "completed"
]
if not completed:
    raise SystemExit("start-gate: no completed main workflow runs found")
failed_conclusions = {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}
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
if failures:
    failures_text = ", ".join(
        f'{item["name"]}={item["conclusion"]} ({item["html_url"]})' for item in failures
    )
    raise SystemExit(f"start-gate: latest main workflow failures detected: {failures_text}")

pulls_payload = run_json(["gh", "api", f"repos/{repo_slug}/pulls", "-f", "state=open", "-f", "per_page=50"])
pulls = pulls_payload if isinstance(pulls_payload, list) else []
failed_prs: list[dict] = []
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
        ["gh", "api", f"repos/{repo_slug}/commits/{sha}/check-runs", "-f", "per_page=100"]
    )
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
    raise SystemExit(
        "start-gate: open PR check failures detected. "
        f"Example: PR #{first['number']} {first['title']} ({first['url']})"
    )

proc = subprocess.run(
    ["git", "-C", str(primary), "status", "--short"],
    capture_output=True,
    text=True,
)
if proc.returncode != 0:
    raise SystemExit("start-gate: failed to check primary workspace state")
if proc.stdout.strip():
    raise SystemExit(
        "start-gate: primary workspace has local changes. Clean it before starting a task."
    )
print("start-gate: passed")
PY
