#!/usr/bin/env python3
"""Sync local runtime events JSON files into a remote API runtime store.

Usage examples:
  python scripts/sync_runtime_events_to_remote.py --api-url https://api.coherencycoin.com
  python scripts/sync_runtime_events_to_remote.py --api-url https://... --all-worktrees
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_events_path() -> Path:
    return _repo_root() / "api" / "logs" / "runtime_events.json"


def _default_state_path() -> Path:
    return _repo_root() / "api" / "logs" / "runtime_events_remote_sync_state.json"


def _all_worktree_glob() -> str:
    repo_name = _repo_root().name
    return str(Path.home() / f".claude-worktrees/{repo_name}/*/api/logs/runtime_events.json")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _safe_scalar(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    return _canonical_json(value)


def _sanitize_metadata(value: Any) -> dict[str, str | int | float | bool]:
    if not isinstance(value, dict):
        return {}
    sanitized: dict[str, str | int | float | bool] = {}
    for key, raw in value.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        try:
            sanitized[key_text] = _safe_scalar(raw)
        except Exception:
            sanitized[key_text] = str(raw)
    return sanitized


def _coerce_source(raw: Any) -> str:
    source = str(raw or "").strip().lower()
    if source in {"api", "web", "web_api", "worker"}:
        return source
    return "worker"


def _coerce_method(raw: Any) -> str:
    method = str(raw or "").strip().upper()
    return method if method else "GET"


def _coerce_status_code(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 200
    return max(100, min(value, 599))


def _coerce_runtime_ms(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, value)


def _normalize_endpoint(raw: Any) -> str:
    endpoint = str(raw or "").strip()
    if not endpoint:
        return ""
    return endpoint if endpoint.startswith("/") else f"/{endpoint}"


@dataclass(frozen=True)
class LocalEventRecord:
    sync_id: str
    source_file: str
    local_event_id: str
    payload: dict[str, Any]


def _build_sync_id(raw_event: dict[str, Any], source_file: str) -> str:
    basis = {
        "source_file": source_file,
        "id": raw_event.get("id"),
        "recorded_at": raw_event.get("recorded_at"),
        "source": raw_event.get("source"),
        "endpoint": raw_event.get("endpoint"),
        "raw_endpoint": raw_event.get("raw_endpoint"),
        "method": raw_event.get("method"),
        "status_code": raw_event.get("status_code"),
        "runtime_ms": raw_event.get("runtime_ms"),
        "idea_id": raw_event.get("idea_id"),
        "metadata": raw_event.get("metadata"),
    }
    digest = hashlib.sha1(_canonical_json(basis).encode("utf-8")).hexdigest()
    return f"loc_{digest}"


def _load_events_from_file(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, dict):
        events = raw.get("events")
        if isinstance(events, list):
            return [row for row in events if isinstance(row, dict)]
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    return []


def _event_to_record(raw_event: dict[str, Any], source_file: str) -> LocalEventRecord | None:
    endpoint = _normalize_endpoint(raw_event.get("raw_endpoint") or raw_event.get("endpoint"))
    runtime_ms = _coerce_runtime_ms(raw_event.get("runtime_ms"))
    if not endpoint or runtime_ms <= 0.0:
        return None
    local_event_id = str(raw_event.get("id") or "").strip() or "unknown"
    sync_id = _build_sync_id(raw_event, source_file)
    metadata = _sanitize_metadata(raw_event.get("metadata"))
    metadata["local_sync_id"] = sync_id
    metadata["local_event_id"] = local_event_id
    metadata["local_source_file"] = source_file
    if raw_event.get("recorded_at"):
        metadata["local_recorded_at"] = str(raw_event.get("recorded_at"))
    if raw_event.get("runtime_cost_estimate") is not None:
        metadata["local_runtime_cost_estimate"] = _safe_scalar(raw_event.get("runtime_cost_estimate"))

    payload: dict[str, Any] = {
        "source": _coerce_source(raw_event.get("source")),
        "endpoint": endpoint,
        "raw_endpoint": _normalize_endpoint(raw_event.get("raw_endpoint")),
        "method": _coerce_method(raw_event.get("method")),
        "status_code": _coerce_status_code(raw_event.get("status_code")),
        "runtime_ms": runtime_ms,
        "idea_id": str(raw_event.get("idea_id") or "").strip() or None,
        "metadata": metadata,
    }
    return LocalEventRecord(
        sync_id=sync_id,
        source_file=source_file,
        local_event_id=local_event_id,
        payload=payload,
    )


def _load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    ids = raw.get("synced_sync_ids")
    if not isinstance(ids, list):
        return set()
    return {str(item).strip() for item in ids if str(item).strip()}


def _save_state(
    path: Path,
    synced_ids: set[str],
    *,
    api_url: str,
    posted: int,
    skipped: int,
    failed: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "api_url": api_url,
        "last_sync_at": datetime.now(timezone.utc).isoformat(),
        "posted": posted,
        "skipped": skipped,
        "failed": failed,
        "synced_sync_ids": sorted(synced_ids),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _expand_event_paths(args: argparse.Namespace) -> list[Path]:
    candidates: list[str] = []
    if args.events_path:
        candidates.extend(args.events_path)
    if args.events_glob:
        for pattern in args.events_glob:
            candidates.extend(glob.glob(pattern))
    if args.all_worktrees:
        candidates.extend(glob.glob(_all_worktree_glob()))
    if not candidates:
        candidates.append(str(_default_events_path()))

    paths: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        path = Path(item).expanduser().resolve()
        key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        paths.append(path)
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local runtime events to remote API runtime store.")
    parser.add_argument("--api-url", required=True, help="Remote API base URL, e.g. https://api.coherencycoin.com")
    parser.add_argument(
        "--events-path",
        action="append",
        default=[],
        help="Path to runtime events JSON file (repeatable).",
    )
    parser.add_argument(
        "--events-glob",
        action="append",
        default=[],
        help="Glob for runtime events JSON files (repeatable).",
    )
    parser.add_argument(
        "--all-worktrees",
        action="store_true",
        help="Also include ~/.claude-worktrees/<repo>/*/api/logs/runtime_events.json",
    )
    parser.add_argument(
        "--state-path",
        default=str(_default_state_path()),
        help="State file used to avoid re-syncing the same local events.",
    )
    parser.add_argument("--max-events", type=int, default=0, help="Optional cap on number of events to post.")
    parser.add_argument("--timeout-seconds", type=float, default=8.0, help="HTTP timeout per event POST.")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without posting.")
    parser.add_argument("--force-resync", action="store_true", help="Ignore synced state and repost events.")
    args = parser.parse_args()

    api_url = str(args.api_url or "").strip().rstrip("/")
    if not api_url:
        print("error: --api-url is required", file=sys.stderr)
        return 2

    state_path = Path(args.state_path).expanduser().resolve()
    synced_ids = set() if args.force_resync else _load_state(state_path)
    event_paths = _expand_event_paths(args)
    if not event_paths:
        print("No runtime event files found.")
        return 0

    records: list[LocalEventRecord] = []
    for path in event_paths:
        rows = _load_events_from_file(path)
        for raw in rows:
            record = _event_to_record(raw, source_file=str(path))
            if record is not None:
                records.append(record)
    records.sort(key=lambda row: str(row.payload.get("metadata", {}).get("local_recorded_at") or ""))

    total_records = len(records)
    pending = [row for row in records if row.sync_id not in synced_ids]
    if args.max_events and args.max_events > 0:
        pending = pending[: args.max_events]

    print(f"runtime_event_files={len(event_paths)} total_records={total_records} already_synced={total_records - len(pending)} pending={len(pending)}")
    for path in event_paths:
        print(f" - {path}")
    if args.dry_run:
        return 0
    if not pending:
        _save_state(state_path, synced_ids, api_url=api_url, posted=0, skipped=total_records, failed=0)
        print("Nothing to sync.")
        return 0

    post_url = f"{api_url}/api/runtime/events"
    posted = 0
    failed = 0
    with httpx.Client(timeout=args.timeout_seconds) as client:
        for idx, record in enumerate(pending, start=1):
            try:
                response = client.post(post_url, json=record.payload)
            except Exception as exc:
                failed += 1
                print(f"[{idx}/{len(pending)}] failed sync_id={record.sync_id} error={exc}")
                continue
            if int(response.status_code) in {200, 201}:
                posted += 1
                synced_ids.add(record.sync_id)
                continue
            failed += 1
            body = response.text.strip().replace("\n", " ")
            print(
                f"[{idx}/{len(pending)}] failed sync_id={record.sync_id} "
                f"status={response.status_code} body={body[:220]}"
            )

    skipped = total_records - posted - failed
    _save_state(state_path, synced_ids, api_url=api_url, posted=posted, skipped=skipped, failed=failed)
    print(f"sync_complete posted={posted} failed={failed} skipped={skipped} state={state_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
