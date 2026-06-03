#!/usr/bin/env python3
"""compare_summary.py — aggregate the kernel-router's COMPARE-mode [compare] logs.

COMPARE mode (COH_ROUTER_COMPARE=1) emits one structured `[compare]` line per
native request to stdout (captured by `docker logs`). This reader folds those
lines — fed on stdin — into a PER-ROUTE summary so a rollout can read divergence
and latency at a glance without eyeballing thousands of lines:

    docker logs coherence-network-kernel-router 2>&1 | \\
        python3 deploy/kernel-router/compare_summary.py

What it reports per route:
  - count            requests compared
  - mismatch         responses where native != CPython (status or body)
  - cpython_error    shadow fan-outs that failed (the user still got native)
  - p50 native_ms    median native serve time
  - p50 cpython_ms   median CPython serve time (what the user actually waited for)

A CLEAN rollout shows mismatch=0 and cpython_error≈0 across every route — the
green light to cut over (unset COH_ROUTER_COMPARE). Any mismatch row names a route
whose native handler diverges from CPython; grep that route's [compare] lines for
the mismatch_native_snippet / mismatch_cpython_snippet to see the divergence.

Network-independent and unit-testable: the parsing + folding is pure (parse_line,
summarize); only main() touches stdin.

The line format this parses (key=value, space-separated; values may be quoted by
the Rust {:?} debug for the status fields, which this strips):

    [compare] route=/api/utils/coherence_weight matched=true status_native="200 OK" \\
        status_cpython="200 OK" status_match=true body_match=true native_ms=0.31 \\
        cpython_ms=12.74 nbytes=91 cbytes=91
    [compare] route=/api/utils/foo compare_fanout_failed error="..." native_ms=0.2 returning=native
"""
from __future__ import annotations

import re
import sys
from statistics import median


# One [compare] record, parsed from a log line. A `matched` line carries the full
# comparison; a `compare_fanout_failed` line carries only route + the failure flag
# (the user got native, the shadow upstream hiccuped).
def parse_line(line: str) -> dict | None:
    """Parse ONE [compare] log line into a dict, or None if it is not one.

    The mismatch diff-snippet lines (`mismatch_native_snippet=...`) are NOT
    records — they carry no `matched=`/`compare_fanout_failed` and are skipped so
    they do not inflate counts.
    """
    line = line.strip()
    if not line.startswith("[compare]"):
        return None
    rest = line[len("[compare]"):].strip()

    # The shadow-error record: the upstream fan-out failed, native was returned.
    if "compare_fanout_failed" in rest:
        m = re.search(r"route=(\S+)", rest)
        if not m:
            return None
        rec = {"route": m.group(1), "kind": "cpython_error"}
        nm = re.search(r"native_ms=([0-9.]+)", rest)
        if nm:
            rec["native_ms"] = float(nm.group(1))
        return rec

    # A full comparison record requires matched= AND both latencies. The
    # diff-snippet follow-up lines lack matched=, so they fall through to None.
    if "matched=" not in rest:
        return None
    m = re.search(r"route=(\S+)", rest)
    if not m:
        return None
    rec: dict = {"route": m.group(1), "kind": "compare"}
    matched = re.search(r"\bmatched=(true|false)\b", rest)
    if not matched:
        return None
    rec["matched"] = matched.group(1) == "true"
    nm = re.search(r"native_ms=([0-9.]+)", rest)
    cm = re.search(r"cpython_ms=([0-9.]+)", rest)
    if not nm or not cm:
        return None
    rec["native_ms"] = float(nm.group(1))
    rec["cpython_ms"] = float(cm.group(1))
    return rec


def summarize(lines) -> dict[str, dict]:
    """Fold an iterable of log lines into {route: summary}. Pure — no I/O."""
    agg: dict[str, dict] = {}

    def slot(route: str) -> dict:
        return agg.setdefault(route, {
            "count": 0, "mismatch": 0, "cpython_error": 0,
            "native_ms": [], "cpython_ms": [],
        })

    for line in lines:
        rec = parse_line(line)
        if rec is None:
            continue
        s = slot(rec["route"])
        if rec["kind"] == "cpython_error":
            s["cpython_error"] += 1
            if "native_ms" in rec:
                s["native_ms"].append(rec["native_ms"])
            continue
        s["count"] += 1
        if not rec["matched"]:
            s["mismatch"] += 1
        s["native_ms"].append(rec["native_ms"])
        s["cpython_ms"].append(rec["cpython_ms"])
    return agg


def _p50(xs: list[float]) -> float:
    return median(xs) if xs else 0.0


def render(agg: dict[str, dict]) -> str:
    """Render the per-route summary table as text."""
    if not agg:
        return "no [compare] lines found on stdin (is COMPARE mode on, and are native routes being hit?)"
    rows = []
    header = (f"{'route':<44} {'count':>7} {'mismatch':>9} {'cpy_err':>8} "
              f"{'p50_native_ms':>14} {'p50_cpython_ms':>15}")
    rows.append(header)
    rows.append("-" * len(header))
    total = mismatches = errors = 0
    for route in sorted(agg):
        s = agg[route]
        total += s["count"]
        mismatches += s["mismatch"]
        errors += s["cpython_error"]
        rows.append(
            f"{route:<44} {s['count']:>7} {s['mismatch']:>9} {s['cpython_error']:>8} "
            f"{_p50(s['native_ms']):>14.3f} {_p50(s['cpython_ms']):>15.3f}"
        )
    rows.append("-" * len(header))
    verdict = ("CLEAN — no divergence; safe to cut over (unset COH_ROUTER_COMPARE)"
               if mismatches == 0 else
               f"{mismatches} MISMATCH(es) — investigate before cutover")
    rows.append(f"totals: compared={total} mismatch={mismatches} cpython_error={errors}  =>  {verdict}")
    return "\n".join(rows)


def main() -> int:
    print(render(summarize(sys.stdin)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
