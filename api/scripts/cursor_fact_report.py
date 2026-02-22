#!/usr/bin/env python3
"""Generate hard-data report for Cursor subscription/routing state.

Outputs a JSON report with:
- local Cursor CLI auth/model availability
- local runtime usage summary and cursor provider snapshot
- deterministic executor-policy routing proofs (cursor vs openclaw/codex)
- optional public API usage/readiness snapshots
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request


API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.models.agent import TaskType  # noqa: E402
from app.services import agent_routing_service, agent_service, automation_usage_service  # noqa: E402


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_command(command: list[str], timeout_sec: int = 12) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def _http_json(url: str, timeout_sec: int = 45) -> dict[str, Any]:
    req = request.Request(url=url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status": int(resp.status),
                "url": url,
                "json": json.loads(payload),
                "error": "",
            }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": int(exc.code),
            "url": url,
            "json": None,
            "error": body[:800],
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "ok": False,
            "status": None,
            "url": url,
            "json": None,
            "error": str(exc),
        }


def _routing_policy_proof() -> list[dict[str, Any]]:
    cases = [
        (TaskType.IMPL, "Change api/app/services/agent_service.py in this repo", {}),
        (TaskType.SPEC, "What is the long-term market outlook for coding agents?", {}),
        (TaskType.HEAL, "Investigate provider readiness degradation in automation usage", {}),
    ]
    rows: list[dict[str, Any]] = []
    for task_type, direction, context in cases:
        selected_executor, policy_meta = agent_service._select_executor(task_type, direction, dict(context))
        rows.append(
            {
                "task_type": task_type.value,
                "direction": direction,
                "selected_executor": selected_executor,
                "policy_meta": policy_meta,
            }
        )
    return rows


def _route_decision_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for executor in ("cursor", "openclaw", "auto"):
        for task_type in (TaskType.SPEC, TaskType.IMPL, TaskType.HEAL):
            route = agent_routing_service.route_for_executor(
                task_type=task_type,
                executor=executor,
                default_command_template='placeholder "{{direction}}"',
            )
            rows.append(
                {
                    "executor": executor,
                    "task_type": task_type.value,
                    "model": route.get("model"),
                    "provider": route.get("provider"),
                    "billing_provider": route.get("billing_provider"),
                    "is_paid_provider": route.get("is_paid_provider"),
                }
            )
    return rows


def generate_report(public_api_base: str) -> dict[str, Any]:
    cursor_status = _run_command(["agent", "status"])
    cursor_about = _run_command(["agent", "about"])
    cursor_models = _run_command(["agent", "models"])

    usage_summary = agent_service.get_usage_summary()
    execution = usage_summary.get("execution") if isinstance(usage_summary.get("execution"), dict) else {}
    cursor_snapshot = next(
        (row for row in automation_usage_service.collect_usage_overview(force_refresh=True).providers if row.provider == "cursor"),
        None,
    )
    cursor_guard = automation_usage_service.provider_limit_guard_decision("cursor", force_refresh=True)

    readiness_url = f"{public_api_base.rstrip('/')}/api/automation/usage/readiness"
    usage_url = f"{public_api_base.rstrip('/')}/api/automation/usage"

    report = {
        "generated_at": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "official_sources": [
            "https://www.cursor.com/pricing",
            "https://docs.cursor.com/account/pricing",
            "https://www.cursor.com/changelog/our-shift-to-usage-based-pricing",
            "https://www.cursor.com/pricing/business",
        ],
        "cursor_cli": {
            "status": cursor_status,
            "about": cursor_about,
            "models": cursor_models,
        },
        "local_runtime_usage": {
            "execution": execution,
            "by_model": usage_summary.get("by_model", {}),
        },
        "local_cursor_provider_snapshot": (
            cursor_snapshot.model_dump(mode="json") if cursor_snapshot is not None else {}
        ),
        "local_cursor_guard_decision": cursor_guard,
        "routing_policy_proof": _routing_policy_proof(),
        "route_decision_matrix": _route_decision_matrix(),
        "public_api_snapshots": {
            "usage_readiness": _http_json(readiness_url),
            "usage_overview": _http_json(usage_url),
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate hard-data cursor fact report")
    parser.add_argument(
        "--public-api-base",
        default=os.getenv("PUBLIC_API_BASE", "https://coherence-network-production.up.railway.app"),
        help="Public API base URL for usage/readiness snapshots",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output path. Defaults to docs/system_audit/cursor_fact_report_<YYYY-MM-DD>.json",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = (REPO_ROOT / output_path).resolve()
    else:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        output_path = (REPO_ROOT / "docs" / "system_audit" / f"cursor_fact_report_{stamp}.json").resolve()

    report = generate_report(args.public_api_base)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
