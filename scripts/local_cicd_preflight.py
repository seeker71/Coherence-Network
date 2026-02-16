#!/usr/bin/env python3
"""Run local CI/CD preflight checks and track recurring failure hotspots."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _safe_git_rev_parse(ref: str, cwd: Path) -> str:
    code, out, _ = _run(["git", "rev-parse", ref], cwd)
    if code == 0:
        return out.strip()
    return ""


def _resolve_base_sha(cwd: Path, base_ref: str) -> str:
    code, _, _ = _run(["git", "fetch", "origin", "main"], cwd)
    if code != 0:
        # Continue with local refs if fetch is unavailable.
        pass
    base_sha = _safe_git_rev_parse(base_ref, cwd)
    if base_sha:
        return base_sha
    merge_base_cmd = ["git", "merge-base", "HEAD", "origin/main"]
    code, out, _ = _run(merge_base_cmd, cwd)
    if code == 0 and out.strip():
        return out.strip()
    return _safe_git_rev_parse("HEAD~1", cwd)


def _changed_files(cwd: Path, base_sha: str, head_sha: str) -> list[str]:
    if not base_sha or not head_sha:
        return []
    code, out, _ = _run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base_sha, head_sha],
        cwd,
    )
    if code != 0:
        return []
    return sorted({row.strip() for row in out.splitlines() if row.strip()})


def _npm_build_command(web_dir: Path) -> list[str]:
    if (web_dir / "node_modules").exists():
        return ["npm", "run", "build"]
    return ["bash", "-lc", "npm ci && npm run build"]


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _load_recent_history(path: Path, max_rows: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows[-max(1, max_rows) :]


def _history_hotspots(history_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    acc: dict[str, dict[str, float]] = {}
    for run in history_rows:
        steps = run.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            name = str(step.get("name") or "").strip()
            if not name:
                continue
            slot = acc.setdefault(
                name,
                {"runs": 0.0, "failures": 0.0, "total_seconds": 0.0, "failed_seconds": 0.0},
            )
            ok = bool(step.get("ok"))
            duration = float(step.get("duration_seconds") or 0.0)
            slot["runs"] += 1.0
            slot["total_seconds"] += max(0.0, duration)
            if not ok:
                slot["failures"] += 1.0
                slot["failed_seconds"] += max(0.0, duration)

    ranked: list[dict[str, Any]] = []
    for name, slot in acc.items():
        runs = max(1.0, slot["runs"])
        failures = slot["failures"]
        failure_rate = failures / runs
        ranked.append(
            {
                "step": name,
                "runs": int(slot["runs"]),
                "failures": int(failures),
                "failure_rate": round(failure_rate, 4),
                "total_seconds": round(slot["total_seconds"], 3),
                "failed_seconds": round(slot["failed_seconds"], 3),
            }
        )
    ranked.sort(key=lambda x: (float(x["failed_seconds"]), float(x["failure_rate"])), reverse=True)
    return ranked[:10]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--history-limit", type=int, default=100)
    parser.add_argument("--skip-api-tests", action="store_true")
    parser.add_argument("--skip-web-build", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    api_dir = root / "api"
    web_dir = root / "web"
    audit_dir = root / "docs" / "system_audit"
    latest_path = audit_dir / "local_cicd_preflight_latest.json"
    history_path = audit_dir / "local_cicd_preflight_history.jsonl"

    base_sha = _resolve_base_sha(root, str(args.base_ref))
    head_sha = _safe_git_rev_parse(str(args.head_ref), root) or "HEAD"
    changed = _changed_files(root, base_sha, head_sha)
    has_api_changes = any(path.startswith("api/") for path in changed)
    has_web_changes = any(path.startswith("web/") for path in changed)

    steps: list[dict[str, Any]] = []
    pipeline: list[tuple[str, list[str], Path, bool]] = [
        (
            "validate_commit_evidence",
            [
                "python3",
                "scripts/validate_commit_evidence.py",
                "--base",
                base_sha,
                "--head",
                head_sha,
                "--require-changed-evidence",
            ],
            root,
            True,
        ),
        (
            "validate_spec_quality",
            [
                "python3",
                "scripts/validate_spec_quality.py",
                "--base",
                base_sha,
                "--head",
                head_sha,
            ],
            root,
            True,
        ),
        ("validate_workflow_references", ["python3", "scripts/validate_workflow_references.py"], root, True),
        ("check_runtime_drift", ["python3", "scripts/check_runtime_drift.py"], root, True),
        (
            "maintainability_audit_regression",
            [
                "python3",
                "api/scripts/run_maintainability_audit.py",
                "--output",
                "maintainability_audit_report.json",
                "--fail-on-regression",
            ],
            root,
            True,
        ),
    ]
    if has_api_changes and not args.skip_api_tests:
        pipeline.append(("api_pytest_quick", ["python3", "-m", "pytest", "-q"], api_dir, True))
    if has_web_changes and not args.skip_web_build:
        pipeline.append(("web_build", _npm_build_command(web_dir), web_dir, True))

    overall_ok = True
    started = _utcnow()
    for name, cmd, cwd, blocking in pipeline:
        t0 = time.perf_counter()
        code, out, err = _run(cmd, cwd)
        duration = round(time.perf_counter() - t0, 3)
        ok = code == 0
        if blocking and not ok:
            overall_ok = False
        step = {
            "name": name,
            "ok": ok,
            "return_code": code,
            "duration_seconds": duration,
            "cwd": str(cwd.relative_to(root)) if cwd != root else ".",
            "command": " ".join(cmd),
            "stdout_tail": out[-2000:],
            "stderr_tail": err[-2000:],
        }
        steps.append(step)
        print(f"[{'PASS' if ok else 'FAIL'}] {name} ({duration}s)")
        if not ok:
            print(step["stderr_tail"] or step["stdout_tail"])

    ended = _utcnow()
    total_seconds = round((ended - started).total_seconds(), 3)
    run_row = {
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_file_count": len(changed),
        "has_api_changes": has_api_changes,
        "has_web_changes": has_web_changes,
        "overall_ok": overall_ok,
        "total_seconds": total_seconds,
        "steps": steps,
    }
    _append_jsonl(history_path, run_row)

    recent = _load_recent_history(history_path, int(args.history_limit))
    hotspots = _history_hotspots(recent)
    latest_payload = {
        "generated_at": ended.isoformat(),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_files": changed,
        "run": run_row,
        "history_window_runs": len(recent),
        "highest_energy_loss_steps": hotspots,
        "recommendation": (
            "Prioritize fixing the top failed_seconds step before opening new PRs; "
            "this minimizes repeat CI iteration cost."
        ),
    }
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(latest_payload, indent=2) + "\n", encoding="utf-8")

    if hotspots:
        print("Top recurring local preflight energy loss steps:")
        for row in hotspots[:5]:
            print(
                f"- {row['step']}: failed_seconds={row['failed_seconds']} "
                f"failure_rate={row['failure_rate']} runs={row['runs']}"
            )
    print(f"Wrote {latest_path}")
    print(f"Appended {history_path}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
