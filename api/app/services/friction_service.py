"""Friction ledger service for API and scripts."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.models.friction import FrictionEvent


def _default_path() -> Path:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    return logs_dir / "friction_events.jsonl"


def friction_file_path() -> Path:
    configured = os.getenv("FRICTION_EVENTS_PATH")
    return Path(configured) if configured else _default_path()


def _parse_iso_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_events(path: Path | None = None) -> tuple[list[FrictionEvent], int]:
    path = path or friction_file_path()
    if not path.exists():
        return [], 0
    events: list[FrictionEvent] = []
    ignored = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                ignored += 1
                continue
            events.append(FrictionEvent(**payload))
        except Exception:
            ignored += 1
            continue
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events, ignored


def append_event(event: FrictionEvent, path: Path | None = None) -> None:
    path = path or friction_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(event.model_dump(mode="json"))
    with path.open("a", encoding="utf-8") as f:
        f.write(serialized + "\n")


def summarize(events: list[FrictionEvent], window_days: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, window_days))
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
                "key": block_type,
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
                "key": stage,
                "count": int(vals["count"]),
                "energy_loss": round(float(vals["energy_loss"]), 4),
            }
            for stage, vals in by_stage.items()
        ),
        key=lambda item: item["energy_loss"],
        reverse=True,
    )

    return {
        "window_days": max(1, window_days),
        "from": _parse_iso_utc(since.isoformat()).isoformat().replace("+00:00", "Z"),
        "to": _parse_iso_utc(now.isoformat()).isoformat().replace("+00:00", "Z"),
        "total_events": len(in_window),
        "open_events": len(open_events),
        "total_energy_loss": round(sum(e.energy_loss_estimate for e in in_window), 4),
        "total_cost_of_delay": round(sum(e.cost_of_delay for e in in_window), 4),
        "top_block_types": top_block_types,
        "top_stages": top_stages,
    }
