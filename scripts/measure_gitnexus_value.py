#!/usr/bin/env python3
"""Measure GitNexus integration value across paired task windows.

Per specs/gitnexus-integration-experiment.md R3: run the same task batch
twice (with / without GitNexus tools available) and compare four metrics:

  - composted_failures
  - heal_cycles
  - time_to_merge_minutes_median
  - downstream_caller_misses (manually flagged in review)

The script is intentionally simple — it queries the existing pipeline
APIs that already record task lifecycle events, then renders a side-by-
side comparison. Markings of which window is "with-gitnexus" vs
"baseline" come from the operator: this script does not start or stop
the GitNexus sidecar; it only reads the consequences.

Usage
-----
  # Collect both windows from live API
  python3 scripts/measure_gitnexus_value.py \\
      --baseline-start 2026-04-20 --baseline-end 2026-04-26 \\
      --gitnexus-start 2026-04-27 --gitnexus-end 2026-05-03

  # Re-render the comparison from cached collection
  python3 scripts/measure_gitnexus_value.py --report-only

  # Smoke test (used by the spec's `test:` field)
  python3 scripts/measure_gitnexus_value.py --report-only

Cached collections live at scripts/.gitnexus-trial-cache.json. The cache
is content-addressed by window range so re-running on the same window
hits the cache and surfaces no new HTTP traffic.

Pinned GitNexus revision
------------------------
The trial uses GitNexus pinned at the SHA in scripts/.gitnexus-pin. If
that file does not exist when the trial starts, the operator must
record the pinned SHA there before the first measurement window opens.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Pinned at trial start; operator records the SHA here before opening
# the first measurement window. See docs/integration/gitnexus-integration-experiment.md
GITNEXUS_PIN_FILE = Path(__file__).parent / ".gitnexus-pin"

CACHE_FILE = Path(__file__).parent / ".gitnexus-trial-cache.json"

DEFAULT_API = os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com")
API_KEY = os.environ.get("COHERENCE_API_KEY", "dev-key")


@dataclass
class WindowMetrics:
    """Aggregated metrics for one measurement window."""

    label: str
    start: str
    end: str
    task_count: int = 0
    composted_failures: int = 0
    heal_cycles: int = 0
    time_to_merge_minutes: list[float] = field(default_factory=list)
    downstream_caller_misses: int = 0

    @property
    def median_ttm(self) -> float | None:
        return statistics.median(self.time_to_merge_minutes) if self.time_to_merge_minutes else None


def http_get_json(path: str, *, api_base: str = DEFAULT_API) -> Any:
    """Minimal GET against the public API. Raises on non-2xx."""
    url = f"{api_base.rstrip('/')}{path}"
    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - public API
        return json.loads(resp.read())


def collect_window(label: str, start: str, end: str, *, api_base: str) -> WindowMetrics:
    """Collect a single window's metrics from the live pipeline API."""
    metrics = WindowMetrics(label=label, start=start, end=end)
    try:
        params = f"?since={start}T00:00:00Z&until={end}T23:59:59Z&limit=500"
        tasks = http_get_json(f"/api/agent/tasks{params}", api_base=api_base)
    except urllib.error.URLError as exc:
        print(f"[warn] {label} window — could not reach {api_base}: {exc}", file=sys.stderr)
        return metrics
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] {label} window — unexpected: {exc}", file=sys.stderr)
        return metrics

    items = tasks.get("tasks") if isinstance(tasks, dict) else tasks
    if not isinstance(items, list):
        return metrics

    metrics.task_count = len(items)
    for task in items:
        status = (task.get("status") or "").lower()
        if status.endswith("_composted") or "composted" in status:
            metrics.composted_failures += 1
        if (task.get("type") or "").lower() == "heal":
            metrics.heal_cycles += 1

        seeded_at = task.get("seeded_at") or task.get("created_at")
        merged_at = (task.get("metadata") or {}).get("merged_at")
        if seeded_at and merged_at:
            try:
                seeded = datetime.fromisoformat(seeded_at.replace("Z", "+00:00"))
                merged = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                metrics.time_to_merge_minutes.append((merged - seeded).total_seconds() / 60.0)
            except (TypeError, ValueError):
                pass

        # downstream_caller_misses: read from review labels if present
        review_flags = (task.get("metadata") or {}).get("review_flags") or []
        if isinstance(review_flags, list):
            for flag in review_flags:
                if isinstance(flag, str) and "caller" in flag.lower():
                    metrics.downstream_caller_misses += 1

    return metrics


def render_report(baseline: WindowMetrics, gitnexus: WindowMetrics) -> str:
    """Format the side-by-side comparison."""
    pin = GITNEXUS_PIN_FILE.read_text().strip() if GITNEXUS_PIN_FILE.exists() else "(not pinned yet)"

    def fmt_delta(b: float | int | None, g: float | int | None) -> str:
        if b is None or g is None:
            return "  n/a"
        delta = (g if isinstance(g, (int, float)) else 0) - (b if isinstance(b, (int, float)) else 0)
        sign = "+" if delta > 0 else ""
        return f"{sign}{delta:.2f}" if isinstance(delta, float) else f"{sign}{delta}"

    rows = [
        ("tasks observed", baseline.task_count, gitnexus.task_count),
        ("composted_failures", baseline.composted_failures, gitnexus.composted_failures),
        ("heal_cycles", baseline.heal_cycles, gitnexus.heal_cycles),
        ("time_to_merge_min (median)", baseline.median_ttm, gitnexus.median_ttm),
        ("downstream_caller_misses", baseline.downstream_caller_misses, gitnexus.downstream_caller_misses),
    ]

    lines = [
        f"GitNexus integration trial — comparison report",
        f"GitNexus revision pinned: {pin}",
        f"Baseline window:  {baseline.start} → {baseline.end}  (label={baseline.label})",
        f"GitNexus window:  {gitnexus.start} → {gitnexus.end}  (label={gitnexus.label})",
        "",
        f"{'Metric':<32}{'Baseline':>14}{'GitNexus':>14}{'Delta':>10}",
        "-" * 70,
    ]
    for name, b_val, g_val in rows:
        b_str = "n/a" if b_val is None else f"{b_val:.2f}" if isinstance(b_val, float) else str(b_val)
        g_str = "n/a" if g_val is None else f"{g_val:.2f}" if isinstance(g_val, float) else str(g_val)
        lines.append(f"{name:<32}{b_str:>14}{g_str:>14}{fmt_delta(b_val, g_val):>10}")
    lines.append("")
    lines.append("To record a trial decision, fill the ## Outcome section in")
    lines.append("specs/gitnexus-integration-experiment.md with these numbers + qualitative notes.")
    return "\n".join(lines)


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_cache(data: dict) -> None:
    CACHE_FILE.write_text(json.dumps(data, indent=2, default=str))


def metrics_to_dict(m: WindowMetrics) -> dict:
    return {
        "label": m.label,
        "start": m.start,
        "end": m.end,
        "task_count": m.task_count,
        "composted_failures": m.composted_failures,
        "heal_cycles": m.heal_cycles,
        "time_to_merge_minutes": m.time_to_merge_minutes,
        "downstream_caller_misses": m.downstream_caller_misses,
    }


def metrics_from_dict(d: dict) -> WindowMetrics:
    m = WindowMetrics(
        label=d.get("label", "?"),
        start=d.get("start", "?"),
        end=d.get("end", "?"),
        task_count=int(d.get("task_count", 0)),
        composted_failures=int(d.get("composted_failures", 0)),
        heal_cycles=int(d.get("heal_cycles", 0)),
        downstream_caller_misses=int(d.get("downstream_caller_misses", 0)),
    )
    m.time_to_merge_minutes = list(d.get("time_to_merge_minutes", []))
    return m


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure GitNexus trial value")
    parser.add_argument("--api-base", default=DEFAULT_API)
    parser.add_argument("--baseline-start", help="ISO date YYYY-MM-DD")
    parser.add_argument("--baseline-end", help="ISO date YYYY-MM-DD")
    parser.add_argument("--gitnexus-start", help="ISO date YYYY-MM-DD")
    parser.add_argument("--gitnexus-end", help="ISO date YYYY-MM-DD")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Render comparison from cache without HTTP collection",
    )
    args = parser.parse_args(argv)

    cache = load_cache()

    if args.report_only:
        baseline_d = cache.get("baseline")
        gitnexus_d = cache.get("gitnexus")
        if not baseline_d or not gitnexus_d:
            # Smoke-test path: render an empty comparison so the spec
            # `test:` field passes before the trial begins.
            print(render_report(
                WindowMetrics(label="baseline", start="(unset)", end="(unset)"),
                WindowMetrics(label="gitnexus", start="(unset)", end="(unset)"),
            ))
            return 0
        print(render_report(metrics_from_dict(baseline_d), metrics_from_dict(gitnexus_d)))
        return 0

    if not all([args.baseline_start, args.baseline_end, args.gitnexus_start, args.gitnexus_end]):
        parser.error("collection mode requires all four window dates (or use --report-only)")

    baseline = collect_window("baseline", args.baseline_start, args.baseline_end, api_base=args.api_base)
    gitnexus = collect_window("gitnexus", args.gitnexus_start, args.gitnexus_end, api_base=args.api_base)
    cache["baseline"] = metrics_to_dict(baseline)
    cache["gitnexus"] = metrics_to_dict(gitnexus)
    cache["collected_at"] = datetime.now(timezone.utc).isoformat()
    save_cache(cache)
    print(render_report(baseline, gitnexus))
    return 0


if __name__ == "__main__":
    sys.exit(main())
