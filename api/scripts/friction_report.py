#!/usr/bin/env python3
"""Summarize friction events and rank top energy-loss sources."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class FrictionEvent:
    event_id: str
    timestamp: datetime
    stage: str
    block_type: str
    severity: str
    owner: str
    unblock_condition: str
    energy_loss_estimate: float
    cost_of_delay: float
    status: str
    resolved_at: datetime | None
    time_open_hours: float | None
    resolution_action: str | None
    notes: str | None


def _parse_iso_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_event(raw: dict[str, Any]) -> FrictionEvent | None:
    required = [
        "id",
        "timestamp",
        "stage",
        "block_type",
        "severity",
        "owner",
        "unblock_condition",
        "energy_loss_estimate",
        "cost_of_delay",
        "status",
    ]
    if any(k not in raw for k in required):
        return None
    try:
        resolved_at = _parse_iso_utc(raw["resolved_at"]) if raw.get("resolved_at") else None
        return FrictionEvent(
            event_id=str(raw["id"]),
            timestamp=_parse_iso_utc(str(raw["timestamp"])),
            stage=str(raw["stage"]),
            block_type=str(raw["block_type"]),
            severity=str(raw["severity"]),
            owner=str(raw["owner"]),
            unblock_condition=str(raw["unblock_condition"]),
            energy_loss_estimate=float(raw["energy_loss_estimate"]),
            cost_of_delay=float(raw["cost_of_delay"]),
            status=str(raw["status"]),
            resolved_at=resolved_at,
            time_open_hours=(
                float(raw["time_open_hours"]) if raw.get("time_open_hours") is not None else None
            ),
            resolution_action=(
                str(raw["resolution_action"]) if raw.get("resolution_action") is not None else None
            ),
            notes=str(raw["notes"]) if raw.get("notes") is not None else None,
        )
    except (TypeError, ValueError):
        return None


def load_events(path: Path) -> tuple[list[FrictionEvent], int]:
    if not path.exists():
        return [], 0
    events: list[FrictionEvent] = []
    ignored = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            ignored += 1
            continue
        if not isinstance(payload, dict):
            ignored += 1
            continue
        event = _to_event(payload)
        if event is None:
            ignored += 1
            continue
        events.append(event)
    return events, ignored


def summarize(events: list[FrictionEvent], window_days: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    in_window = [e for e in events if e.timestamp >= since]
    open_events = [e for e in in_window if e.status == "open"]

    by_block_type: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy_loss": 0.0, "cost_of_delay": 0.0}
    )
    by_stage: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy_loss": 0.0}
    )

    for event in in_window:
        bt = by_block_type[event.block_type]
        bt["count"] += 1
        bt["energy_loss"] += event.energy_loss_estimate
        bt["cost_of_delay"] += event.cost_of_delay

        st = by_stage[event.stage]
        st["count"] += 1
        st["energy_loss"] += event.energy_loss_estimate

    top_block_types = sorted(
        (
            {
                "block_type": block_type,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
                "cost_of_delay": round(float(vals["cost_of_delay"]), 4),
            }
            for block_type, vals in by_block_type.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    top_stages = sorted(
        (
            {
                "stage": stage,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
            }
            for stage, vals in by_stage.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    return {
        "window_days": window_days,
        "from": since.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
        "total_events": len(in_window),
        "open_events": len(open_events),
        "total_energy_loss": round(sum(e.energy_loss_estimate for e in in_window), 4),
        "total_cost_of_delay": round(sum(e.cost_of_delay for e in in_window), 4),
        "top_block_types": top_block_types,
        "top_stages": top_stages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank friction points by energy loss.")
    parser.add_argument(
        "--file",
        default="logs/friction_events.jsonl",
        help="Path to friction events JSONL file (default: logs/friction_events.jsonl)",
    )
    parser.add_argument("--window-days", type=int, default=7, help="Rolling window in days.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    path = Path(args.file)
    events, ignored = load_events(path)
    report = summarize(events, window_days=max(1, args.window_days))
    report["source_file"] = str(path)
    report["ignored_lines"] = ignored

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"Friction report: {path}")
    print(f"Window: last {report['window_days']} day(s)")
    print(f"Events: {report['total_events']} (open: {report['open_events']}, ignored lines: {ignored})")
    print(
        "Totals: "
        f"energy_loss={report['total_energy_loss']:.2f}, "
        f"cost_of_delay={report['total_cost_of_delay']:.2f}"
    )
    print("")
    print("Top block types by energy loss:")
    if report["top_block_types"]:
        for idx, item in enumerate(report["top_block_types"], start=1):
            print(
                f"{idx}. {item['block_type']} | count={item['count']} "
                f"| energy_loss={item['energy_loss']:.2f} | cost_of_delay={item['cost_of_delay']:.2f}"
            )
    else:
        print("No events in window.")


if __name__ == "__main__":
    main()
