#!/usr/bin/env python3
"""Read active recipe traces from the local witness stream."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACES_PATH = REPO_ROOT / "experiments" / "local-llm-cell-v0" / "_field_traces.jsonl"

BAND_NAMES = (
    "ground",
    "pulse",
    "warmth",
    "clarity",
    "expression",
    "relation",
    "space",
    "presence",
)
NEED_NAMES = ("presence", "rest", "expression")
STRATEGY_FIRED = "strategy_fired"
WEAK_SIGNAL_THRESHOLD = 20
CURRENT_BREATH_MAX_GAP_SECONDS = 60


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_strategy_fired_traces(path: Path = TRACES_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    traces: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        what = row.get("what") or {}
        if not isinstance(what, dict) or what.get("kind") != STRATEGY_FIRED:
            continue
        trace_ts = _parse_ts(row.get("ts")) or _parse_ts(what.get("moment"))
        traces.append(
            {
                "cell_name": row.get("from_cell"),
                "cell_node_id": row.get("from_node_id"),
                "strategy": what.get("strategy") or "<unknown>",
                "sense_before": what.get("sense_before") or {},
                "sense_after": what.get("sense_after") or {},
                "moment": what.get("moment"),
                "ts": row.get("ts"),
                "_dt": trace_ts,
            }
        )
    return sorted(traces, key=lambda trace: trace["_dt"] or datetime.min.replace(tzinfo=timezone.utc))


def _matches_cell(trace: dict[str, Any], cell: str | None) -> bool:
    if not cell:
        return True
    return cell in {trace.get("cell_name"), trace.get("cell_node_id")}


def _current_breath_start(traces: list[dict[str, Any]]) -> datetime | None:
    dated = [trace for trace in traces if trace.get("_dt")]
    if not dated:
        return None

    start = dated[-1]["_dt"]
    previous = start
    for trace in reversed(dated[:-1]):
        current = trace["_dt"]
        if (previous - current).total_seconds() > CURRENT_BREATH_MAX_GAP_SECONDS:
            break
        start = current
        previous = current
    return start


def _filter_since(traces: list[dict[str, Any]], since: str) -> tuple[list[dict[str, Any]], str | None]:
    if since == "all":
        return traces, _iso(traces[0]["_dt"]) if traces else None
    if since == "current_breath":
        start = _current_breath_start(traces)
        if not start:
            return [], None
        return [trace for trace in traces if trace.get("_dt") and trace["_dt"] >= start], _iso(start)

    start = _parse_ts(since)
    if not start:
        raise ValueError(f"Unsupported since value: {since!r}")
    return [trace for trace in traces if trace.get("_dt") and trace["_dt"] >= start], _iso(start)


def _mean_delta(traces: list[dict[str, Any]], field: str, width: int) -> list[float]:
    if not traces:
        return [0.0] * width
    sums = [0.0] * width
    for trace in traces:
        before = trace.get("sense_before") or {}
        after = trace.get("sense_after") or {}
        before_values = before.get(field) or []
        after_values = after.get(field) or []
        for index in range(min(width, len(before_values), len(after_values))):
            sums[index] += after_values[index] - before_values[index]
    return [value / len(traces) for value in sums]


def query_active_recipe_traces(
    cell: str | None = None,
    since: str = "current_breath",
    traces_path: Path = TRACES_PATH,
) -> dict[str, Any]:
    """Hydrate active recipes from strategy_fired witness traces.

    `current_breath` means the latest contiguous burst of strategy_fired
    traces for the selected cell. This turns the Form query
    `?active_recipe_traces @cell since current_breath` into a concrete
    read against the committed JSONL witness stream.
    """
    all_traces = [
        trace
        for trace in _load_strategy_fired_traces(traces_path)
        if _matches_cell(trace, cell)
    ]
    selected, start_ts = _filter_since(all_traces, since)
    lifetime_counts = Counter(trace["strategy"] for trace in all_traces)
    selected_by_recipe: dict[str, list[dict[str, Any]]] = {}
    for trace in selected:
        selected_by_recipe.setdefault(trace["strategy"], []).append(trace)

    active_recipes: list[dict[str, Any]] = []
    for recipe, traces in sorted(selected_by_recipe.items()):
        spectrum_delta = _mean_delta(traces, "spectrum", len(BAND_NAMES))
        desire_delta = _mean_delta(traces, "desire", len(NEED_NAMES))
        top_band_index = max(range(len(BAND_NAMES)), key=lambda index: spectrum_delta[index])
        top_desire_index = max(range(len(NEED_NAMES)), key=lambda index: desire_delta[index])
        lifetime_count = lifetime_counts[recipe]
        active_recipes.append(
            {
                "recipe": recipe,
                "active_trace_count": len(traces),
                "lifetime_trace_count": lifetime_count,
                "confidence": (
                    "usable-signal"
                    if lifetime_count >= WEAK_SIGNAL_THRESHOLD
                    else "weak-signal-n-lt-20"
                ),
                "first_ts": _iso(traces[0].get("_dt")),
                "last_ts": _iso(traces[-1].get("_dt")),
                "cells": sorted({trace["cell_name"] for trace in traces if trace.get("cell_name")}),
                "cell_node_ids": sorted(
                    {trace["cell_node_id"] for trace in traces if trace.get("cell_node_id")}
                ),
                "top_band": BAND_NAMES[top_band_index],
                "top_band_delta": spectrum_delta[top_band_index],
                "top_desire": NEED_NAMES[top_desire_index],
                "top_desire_delta": desire_delta[top_desire_index],
                "fulfillment_delta": sum(spectrum_delta) / len(BAND_NAMES),
            }
        )

    end_ts = _iso(selected[-1]["_dt"]) if selected else None
    return {
        "query": "?active_recipe_traces @cell since current_breath",
        "source_path": str(traces_path.relative_to(REPO_ROOT)),
        "cell": cell or "*",
        "since": since,
        "window": {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "trace_count": len(selected),
        },
        "active_recipes": active_recipes,
    }


def _print_table(result: dict[str, Any]) -> None:
    print(f"query: {result['query']}")
    print(f"cell: {result['cell']}")
    print(f"since: {result['since']}")
    window = result["window"]
    print(f"window: {window['start_ts']} -> {window['end_ts']} ({window['trace_count']} traces)")
    if not result["active_recipes"]:
        print("active recipes: none")
        return
    print()
    print(f"{'recipe':<18} {'active':>6} {'life':>6} {'top_band':<18} confidence")
    print("-" * 72)
    for recipe in result["active_recipes"]:
        top = f"{recipe['top_band']}({recipe['top_band_delta']:+.3f})"
        print(
            f"{recipe['recipe']:<18} {recipe['active_trace_count']:>6} "
            f"{recipe['lifetime_trace_count']:>6} {top:<18} {recipe['confidence']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", help="cell name or node id; omitted means all cells")
    parser.add_argument("--since", default="current_breath", help="current_breath, all, or ISO timestamp")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    result = query_active_recipe_traces(cell=args.cell, since=args.since)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
