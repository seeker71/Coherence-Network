#!/usr/bin/env python3
"""Run low-level hosted-worker tasks and emit before/after proof artifacts."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

LOW_LEVEL_TASK_TYPES = ("spec", "test", "review")
TERMINAL_STATUSES = {"completed", "failed", "needs_decision"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_tasks(client: httpx.Client, api_url: str, *, limit: int = 200) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit), 100))
    response = client.get(f"{api_url.rstrip('/')}/api/agent/tasks", params={"limit": bounded_limit}, timeout=30.0)
    response.raise_for_status()
    payload = _safe_json(response)
    rows = payload.get("tasks")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _create_task(
    client: httpx.Client,
    api_url: str,
    *,
    direction: str,
    task_type: str,
    executor: str,
    retry_max: int,
) -> dict[str, Any]:
    body = {
        "direction": direction,
        "task_type": task_type,
        "context": {
            "executor": executor,
            "retry_max": int(max(retry_max, 0)),
        },
    }
    response = client.post(
        f"{api_url.rstrip('/')}/api/agent/tasks",
        json=body,
        timeout=30.0,
    )
    response.raise_for_status()
    payload = _safe_json(response)
    return payload


def _get_task(client: httpx.Client, api_url: str, task_id: str) -> dict[str, Any]:
    response = client.get(f"{api_url.rstrip('/')}/api/agent/tasks/{task_id}", timeout=30.0)
    response.raise_for_status()
    payload = _safe_json(response)
    return payload


def _is_hosted_claim(claimed_by: Any) -> bool:
    value = str(claimed_by or "").strip().lower()
    return value.startswith("openai-codex:")


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    hosted_claimed = 0
    for row in rows:
        status = str(row.get("status") or "unknown").strip().lower()
        status_counts[status] = status_counts.get(status, 0) + 1
        if _is_hosted_claim(row.get("claimed_by")):
            hosted_claimed += 1
    total = len(rows)
    return {
        "total": total,
        "status_counts": status_counts,
        "hosted_claimed_count": hosted_claimed,
        "hosted_claim_ratio": round(hosted_claimed / float(total), 4) if total else 0.0,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Proof run for hosted-worker low-level tasks.")
    parser.add_argument("--api-url", required=True, help="Base API URL")
    parser.add_argument("--run-id", default="", help="Optional run id token")
    parser.add_argument(
        "--executor",
        default="claude",
        help="Executor to request for low-level tasks (default: claude)",
    )
    parser.add_argument(
        "--task-types",
        default="spec,test,review,spec,test",
        help="Comma-separated low-level task types to create",
    )
    parser.add_argument("--retry-max", type=int, default=0, help="retry_max task context value")
    parser.add_argument("--poll-seconds", type=int, default=8, help="poll interval in seconds")
    parser.add_argument("--timeout-seconds", type=int, default=240, help="max wait for terminal statuses")
    parser.add_argument("--before-output", required=True, help="before artifact output path")
    parser.add_argument("--after-output", required=True, help="after artifact output path")
    args = parser.parse_args()

    run_id = str(args.run_id or "").strip() or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task_types = [part.strip().lower() for part in str(args.task_types).split(",") if part.strip()]
    for task_type in task_types:
        if task_type not in LOW_LEVEL_TASK_TYPES:
            raise SystemExit(f"Unsupported task_type '{task_type}'. Allowed: {', '.join(LOW_LEVEL_TASK_TYPES)}")
    tag = f"HOSTED_LOWLEVEL_PROOF {run_id}"

    before_path = Path(args.before_output).resolve()
    after_path = Path(args.after_output).resolve()

    with httpx.Client(headers={"User-Agent": "coherence-hosted-low-level-proof/1.0"}) as client:
        all_before = _list_tasks(client, args.api_url, limit=100)
        tagged_before = [row for row in all_before if tag in str(row.get("direction") or "")]
        before_payload = {
            "generated_at": _now_iso(),
            "api_url": args.api_url,
            "run_id": run_id,
            "tag": tag,
            "executor": args.executor,
            "task_types": task_types,
            "matching_tasks": tagged_before,
            "summary": _summarize(tagged_before),
        }
        _write_json(before_path, before_payload)

        created_task_ids: list[str] = []
        created_rows: list[dict[str, Any]] = []
        for index, task_type in enumerate(task_types, start=1):
            direction = (
                f"{tag} index={index} task_type={task_type}. "
                f"Return exactly HOSTED_LOWLEVEL_{task_type.upper()}_{index}_OK"
            )
            created = _create_task(
                client,
                args.api_url,
                direction=direction,
                task_type=task_type,
                executor=args.executor,
                retry_max=args.retry_max,
            )
            task_id = str(created.get("id") or "").strip()
            if task_id:
                created_task_ids.append(task_id)
            created_rows.append(created)

        start = time.time()
        final_rows: dict[str, dict[str, Any]] = {}
        while True:
            all_terminal = True
            for task_id in created_task_ids:
                row = _get_task(client, args.api_url, task_id)
                final_rows[task_id] = row
                status = str(row.get("status") or "").strip().lower()
                if status not in TERMINAL_STATUSES:
                    all_terminal = False
            if all_terminal:
                break
            if time.time() - start >= max(1, int(args.timeout_seconds)):
                break
            time.sleep(max(1, int(args.poll_seconds)))

        final_list = [final_rows.get(task_id, {}) for task_id in created_task_ids]
        after_payload = {
            "generated_at": _now_iso(),
            "api_url": args.api_url,
            "run_id": run_id,
            "tag": tag,
            "executor": args.executor,
            "task_types": task_types,
            "created_tasks": created_rows,
            "final_tasks": final_list,
            "summary": _summarize(final_list),
            "timed_out": any(
                str(row.get("status") or "").strip().lower() not in TERMINAL_STATUSES
                for row in final_list
                if isinstance(row, dict)
            ),
        }
        _write_json(after_path, after_payload)

        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "executor": args.executor,
                    "created_count": len(created_task_ids),
                    "before_summary": before_payload["summary"],
                    "after_summary": after_payload["summary"],
                    "timed_out": after_payload["timed_out"],
                    "before_output": str(before_path),
                    "after_output": str(after_path),
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
