#!/usr/bin/env python3
"""Audit automation pipeline energy loss from evidence + GitHub Actions runs."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ACTIONS_COST_PER_MINUTE = 0.008
DEFAULT_RUN_LIMIT = 120


@dataclass(frozen=True)
class RunRow:
    workflow: str
    event: str
    status: str
    conclusion: str
    created_at: dt.datetime | None
    updated_at: dt.datetime | None
    head_sha: str
    url: str
    duration_minutes: float


def _parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    cleaned = str(value).strip()
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


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and any(isinstance(x, str) and x.strip() for x in value)


def _collect_commit_evidence(root: Path) -> dict[str, Any]:
    evidence_files = sorted(glob.glob(str(root / "docs" / "system_audit" / "commit_evidence_*.json")))
    rows: list[dict[str, Any]] = []
    parse_errors = 0
    for name in evidence_files:
        path = Path(name)
        try:
            data = _load_json(path)
        except Exception:
            parse_errors += 1
            continue
        data["_path"] = str(path.relative_to(root))
        rows.append(data)

    status_counter: dict[str, Counter[str]] = {
        "local_validation": Counter(),
        "ci_validation": Counter(),
        "deploy_validation": Counter(),
        "phase_gate": Counter(),
    }
    missing = Counter()
    missing_files: dict[str, list[str]] = {
        "idea_ids": [],
        "spec_ids": [],
        "change_files": [],
    }
    idea_count = 0
    spec_count = 0
    impl_count = 0
    runtime_intent_count = 0
    runtime_with_e2e = 0

    for row in rows:
        if _non_empty_string_list(row.get("idea_ids")):
            idea_count += 1
        else:
            missing["idea_ids"] += 1
            missing_files["idea_ids"].append(str(row.get("_path") or ""))
        if _non_empty_string_list(row.get("spec_ids")):
            spec_count += 1
        else:
            missing["spec_ids"] += 1
            missing_files["spec_ids"].append(str(row.get("_path") or ""))
        if _non_empty_string_list(row.get("change_files")):
            impl_count += 1
        else:
            missing["change_files"] += 1
            missing_files["change_files"].append(str(row.get("_path") or ""))

        local_status = str((row.get("local_validation") or {}).get("status") or "missing").strip().lower()
        ci_status = str((row.get("ci_validation") or {}).get("status") or "missing").strip().lower()
        deploy_status = str((row.get("deploy_validation") or {}).get("status") or "missing").strip().lower()
        phase_gate = bool((row.get("phase_gate") or {}).get("can_move_next_phase"))

        status_counter["local_validation"][local_status] += 1
        status_counter["ci_validation"][ci_status] += 1
        status_counter["deploy_validation"][deploy_status] += 1
        status_counter["phase_gate"]["true" if phase_gate else "false"] += 1

        change_intent = str(row.get("change_intent") or "").strip().lower()
        if change_intent in {"runtime_feature", "runtime_fix"}:
            runtime_intent_count += 1
            if isinstance(row.get("e2e_validation"), dict):
                runtime_with_e2e += 1

    return {
        "evidence_file_count": len(rows),
        "parse_errors": parse_errors,
        "stage_coverage": {
            "idea_linked": idea_count,
            "spec_linked": spec_count,
            "implementation_linked": impl_count,
        },
        "validation_status": {k: dict(v) for k, v in status_counter.items()},
        "runtime_intent": {
            "runtime_intent_count": runtime_intent_count,
            "with_e2e_validation": runtime_with_e2e,
            "missing_e2e_validation": max(0, runtime_intent_count - runtime_with_e2e),
        },
        "missing_field_counts": dict(missing),
        "missing_field_files": {k: [x for x in v if x] for k, v in missing_files.items()},
    }


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _gh_run_list(limit: int) -> list[dict[str, Any]]:
    raw = subprocess.check_output(
        [
            "gh",
            "run",
            "list",
            "--limit",
            str(limit),
            "--json",
            "databaseId,workflowName,status,conclusion,event,headSha,url,createdAt,updatedAt",
        ],
        text=True,
    )
    payload = json.loads(raw or "[]")
    return payload if isinstance(payload, list) else []


def _collect_runs(limit: int) -> tuple[list[RunRow], str | None]:
    if not _gh_available():
        return [], "gh_cli_unavailable"
    try:
        payload = _gh_run_list(limit)
    except Exception as exc:  # pragma: no cover - depends on local gh auth/network
        return [], f"gh_query_failed:{exc}"

    rows: list[RunRow] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        workflow = str(item.get("workflowName") or "").strip() or "(unknown)"
        event = str(item.get("event") or "").strip() or "unknown"
        status = str(item.get("status") or "").strip().lower() or "unknown"
        conclusion = str(item.get("conclusion") or "").strip().lower()
        created = _parse_dt(item.get("createdAt"))
        updated = _parse_dt(item.get("updatedAt"))
        duration = 0.0
        if created and updated and updated >= created:
            duration = round((updated - created).total_seconds() / 60.0, 4)
        rows.append(
            RunRow(
                workflow=workflow,
                event=event,
                status=status,
                conclusion=conclusion,
                created_at=created,
                updated_at=updated,
                head_sha=str(item.get("headSha") or "").strip(),
                url=str(item.get("url") or "").strip(),
                duration_minutes=duration,
            )
        )
    return rows, None


def _run_summary(runs: list[RunRow], cost_per_minute: float) -> dict[str, Any]:
    total_minutes = round(sum(x.duration_minutes for x in runs), 4)
    by_workflow: dict[str, dict[str, Any]] = {}
    failed_states = {"failure", "failed", "cancelled", "timed_out", "action_required", "startup_failure"}
    failure_rows: list[dict[str, Any]] = []

    for row in runs:
        item = by_workflow.setdefault(
            row.workflow,
            {
                "run_count": 0,
                "total_minutes": 0.0,
                "failed_minutes": 0.0,
                "failure_count": 0,
                "success_count": 0,
                "in_progress_count": 0,
            },
        )
        item["run_count"] += 1
        item["total_minutes"] = round(item["total_minutes"] + row.duration_minutes, 4)
        if row.status == "in_progress":
            item["in_progress_count"] += 1
        if row.conclusion == "success":
            item["success_count"] += 1
        if row.conclusion in failed_states:
            item["failure_count"] += 1
            item["failed_minutes"] = round(item["failed_minutes"] + row.duration_minutes, 4)
            failure_rows.append(
                {
                    "workflow": row.workflow,
                    "event": row.event,
                    "conclusion": row.conclusion,
                    "duration_minutes": row.duration_minutes,
                    "url": row.url,
                }
            )

    for item in by_workflow.values():
        item["estimated_cost_usd"] = round(item["total_minutes"] * cost_per_minute, 4)
        item["estimated_failed_cost_usd"] = round(item["failed_minutes"] * cost_per_minute, 4)
        total = max(1, int(item["run_count"]))
        item["failure_rate"] = round(float(item["failure_count"]) / total, 4)

    top_loss = sorted(
        by_workflow.items(),
        key=lambda kv: (float(kv[1]["failed_minutes"]), float(kv[1]["failure_rate"])),
        reverse=True,
    )

    return {
        "run_count": len(runs),
        "total_duration_minutes": total_minutes,
        "estimated_total_cost_usd": round(total_minutes * cost_per_minute, 4),
        "by_workflow": by_workflow,
        "top_energy_loss_workflows": [
            {
                "workflow": name,
                "failed_minutes": values["failed_minutes"],
                "failure_rate": values["failure_rate"],
                "estimated_failed_cost_usd": values["estimated_failed_cost_usd"],
            }
            for name, values in top_loss[:10]
        ],
        "sample_failure_runs": failure_rows[:20],
    }


def _build_report(root: Path, run_limit: int, cost_per_minute: float) -> dict[str, Any]:
    evidence = _collect_commit_evidence(root)
    runs, run_error = _collect_runs(run_limit)
    run_summary = _run_summary(runs, cost_per_minute) if runs else {}

    gaps: list[str] = []
    if evidence["evidence_file_count"] == 0:
        gaps.append("missing_commit_evidence_files")
    if evidence["runtime_intent"]["missing_e2e_validation"] > 0:
        gaps.append("runtime_intents_missing_e2e_validation")
    if not runs:
        gaps.append("missing_github_actions_run_data")
    if run_error:
        gaps.append(run_error)
    for field_name, count in (evidence.get("missing_field_counts") or {}).items():
        if int(count or 0) > 0:
            gaps.append(f"commit_evidence_missing_{field_name}")
    if not evidence.get("missing_field_files"):
        gaps.append("missing_commit_evidence_field_file_map")

    # Current commit evidence format does not carry stage timestamps for idea/spec/implementation.
    # Without these, full stage-by-stage elapsed-time energy is only available for CI/CD runs.
    gaps.append("missing_stage_timestamps_for_idea_spec_implementation")

    highest_loss = (run_summary.get("top_energy_loss_workflows") or [])[:3]
    return {
        "generated_at": _now_utc().isoformat(),
        "sources": {
            "commit_evidence_glob": "docs/system_audit/commit_evidence_*.json",
            "github_actions_run_limit": run_limit,
            "actions_cost_per_minute_usd": cost_per_minute,
        },
        "pipeline_stage_audit": {
            "idea_to_spec_to_implementation": evidence["stage_coverage"],
            "verification_and_gate_states": evidence["validation_status"],
        },
        "automation_energy": {
            "evidence_summary": evidence,
            "actions_summary": run_summary,
            "highest_energy_loss_hotspots": highest_loss,
        },
        "data_gaps": gaps,
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    stages = report.get("pipeline_stage_audit", {})
    energy = report.get("automation_energy", {})
    evidence = energy.get("evidence_summary", {})
    actions = energy.get("actions_summary", {})
    hotspots = energy.get("highest_energy_loss_hotspots") or []
    gaps = report.get("data_gaps") or []

    lines = [
        "# Automation Energy Loss Audit",
        "",
        f"Generated: `{report.get('generated_at')}`",
        "",
        "## Stage Coverage",
        "",
        f"- idea_linked: `{stages.get('idea_to_spec_to_implementation', {}).get('idea_linked', 0)}`",
        f"- spec_linked: `{stages.get('idea_to_spec_to_implementation', {}).get('spec_linked', 0)}`",
        f"- implementation_linked: `{stages.get('idea_to_spec_to_implementation', {}).get('implementation_linked', 0)}`",
        "",
        "## Actions Energy",
        "",
        f"- run_count: `{actions.get('run_count', 0)}`",
        f"- total_duration_minutes: `{actions.get('total_duration_minutes', 0)}`",
        f"- estimated_total_cost_usd: `{actions.get('estimated_total_cost_usd', 0)}`",
        "",
        "## Highest Energy Loss",
        "",
    ]
    if hotspots:
        for item in hotspots:
            lines.append(
                "- "
                f"{item.get('workflow')}: failed_minutes={item.get('failed_minutes')} "
                f"failure_rate={item.get('failure_rate')} "
                f"estimated_failed_cost_usd={item.get('estimated_failed_cost_usd')}"
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
        "## Data Gaps",
        "",
    ]
    )
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")

    missing_field_files = evidence.get("missing_field_files") or {}
    if missing_field_files:
        lines.extend(
            [
                "",
                "## Missing Field Files",
                "",
            ]
        )
        for field_name in ("idea_ids", "spec_ids", "change_files"):
            files = [x for x in (missing_field_files.get(field_name) or []) if isinstance(x, str) and x.strip()]
            if not files:
                continue
            lines.append(f"- {field_name}:")
            for file_path in files[:20]:
                lines.append(f"  - {file_path}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-limit", type=int, default=DEFAULT_RUN_LIMIT)
    parser.add_argument("--actions-cost-per-minute", type=float, default=DEFAULT_ACTIONS_COST_PER_MINUTE)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    today = _now_utc().date().isoformat()
    out_json = Path(args.out_json) if args.out_json else root / "docs" / "system_audit" / f"automation_energy_loss_report_{today}.json"
    out_md = Path(args.out_md) if args.out_md else root / "docs" / "system_audit" / f"automation_energy_loss_report_{today}.md"

    report = _build_report(root=root, run_limit=max(20, args.run_limit), cost_per_minute=max(0.0, args.actions_cost_per_minute))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_markdown(out_md, report)
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
