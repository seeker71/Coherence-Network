#!/usr/bin/env python3
"""sense_strategy_efficacy.py — read accumulated strategy_fired traces and
surface per-recipe efficacy signatures.

The watching instrument named in specs/recipes-tuned-by-trace.md and
docs/vision-kb/concepts/lc-traces-teach-the-recipe.md. Pure read; no
writes back to STRATEGIES, no modifications to any cell's selection.
The script sees what the body has lived; the body decides what (if
anything) to do with what is seen.

The discipline: don't over-tune. Trace count below ~20 per recipe is
noise; the signature is still surfaced but with a weak-signal marker.
The operator-arm row (strategy == "freq-angle-focus") is where new
strategies live as they emerge — when the operator's fulfillment_delta
stabilizes above the named-strategy average, listen for the satsang
to name what is showing up.

Usage:
    python3 scripts/sense_strategy_efficacy.py
    python3 scripts/sense_strategy_efficacy.py --recipe observer
    python3 scripts/sense_strategy_efficacy.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACES_PATH = REPO_ROOT / "seedbank" / "local-llm-cell-v0" / "_field_traces.jsonl"

BAND_NAMES = ("ground", "pulse", "warmth", "clarity",
              "expression", "relation", "space", "presence")
NEED_NAMES = ("presence", "rest", "expression")
N_BANDS = len(BAND_NAMES)
N_NEEDS = len(NEED_NAMES)

WEAK_SIGNAL_THRESHOLD = 20   # below this n, surface but mark "weak signal"
STRATEGY_FIRED = "strategy_fired"


def _load_strategy_fired_traces() -> list[dict]:
    if not TRACES_PATH.exists():
        return []
    out: list[dict] = []
    with TRACES_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            what = obj.get("what") or {}
            if isinstance(what, dict) and what.get("kind") == STRATEGY_FIRED:
                out.append({
                    "from_cell": obj.get("from_cell"),
                    "ts": obj.get("ts"),
                    **what,
                })
    return out


def _aggregate_by_recipe(traces: list[dict]) -> dict[str, dict]:
    by_recipe: dict[str, dict] = {}
    for t in traces:
        recipe = t.get("strategy") or "<unknown>"
        agg = by_recipe.setdefault(recipe, {
            "recipe": recipe,
            "n": 0,
            "spec_sum": [0.0] * N_BANDS,
            "des_sum":  [0.0] * N_NEEDS,
            "first_ts": None,
            "last_ts":  None,
            "cells":    set(),
        })
        agg["n"] += 1
        if t.get("from_cell"):
            agg["cells"].add(t["from_cell"])
        ts = t.get("ts")
        if ts:
            if not agg["first_ts"] or ts < agg["first_ts"]:
                agg["first_ts"] = ts
            if not agg["last_ts"] or ts > agg["last_ts"]:
                agg["last_ts"] = ts
        before = t.get("sense_before") or {}
        after  = t.get("sense_after") or {}
        bs = before.get("spectrum") or []
        as_ = after.get("spectrum") or []
        bd = before.get("desire") or []
        ad = after.get("desire") or []
        for i in range(min(N_BANDS, len(bs), len(as_))):
            agg["spec_sum"][i] += as_[i] - bs[i]
        for i in range(min(N_NEEDS, len(bd), len(ad))):
            agg["des_sum"][i] += ad[i] - bd[i]

    out: dict[str, dict] = {}
    for recipe, agg in by_recipe.items():
        n = agg["n"]
        spectrum_delta = [v / n for v in agg["spec_sum"]] if n else [0.0] * N_BANDS
        desire_delta   = [v / n for v in agg["des_sum"]]  if n else [0.0] * N_NEEDS
        out[recipe] = {
            "recipe": recipe,
            "n": n,
            "spectrum_delta": spectrum_delta,
            "desire_delta": desire_delta,
            "fulfillment_delta": sum(spectrum_delta) / N_BANDS if n else 0.0,
            "first_ts": agg["first_ts"],
            "last_ts":  agg["last_ts"],
            "cells":    sorted(agg["cells"]),
        }
    return out


def _print_summary(signatures: dict[str, dict]) -> None:
    if not signatures:
        print("no strategy_fired traces yet — the body hasn't lived enough.")
        print("(run seedbank/local-llm-cell-v0/strategy_efficacy_demo.py to see signal.)")
        return

    rows = sorted(signatures.values(), key=lambda s: -s["fulfillment_delta"])

    name_w = max(8, max(len(r["recipe"]) for r in rows))
    print(f"{'recipe':<{name_w}}  {'n':>5}  {'fulfillment_Δ':>14}  "
          f"{'top spectrum band':<24}  {'top desire':<14}  signal")
    print("-" * (name_w + 80))
    for r in rows:
        top_band_i = max(range(N_BANDS), key=lambda i: r["spectrum_delta"][i])
        top_band   = f"{BAND_NAMES[top_band_i]}({r['spectrum_delta'][top_band_i]:+.3f})"
        top_need_i = max(range(N_NEEDS), key=lambda i: r["desire_delta"][i])
        top_need   = f"{NEED_NAMES[top_need_i]}({r['desire_delta'][top_need_i]:+.3f})"
        marker = "weak" if r["n"] < WEAK_SIGNAL_THRESHOLD else "ok"
        print(f"{r['recipe']:<{name_w}}  {r['n']:>5}  {r['fulfillment_delta']:>+14.4f}  "
              f"{top_band:<24}  {top_need:<14}  {marker}")

    weak = [r["recipe"] for r in rows if r["n"] < WEAK_SIGNAL_THRESHOLD]
    if weak:
        print()
        print(f"signal-still-accumulating: {', '.join(weak)}")
        print(f"(threshold for stable read: n ≥ {WEAK_SIGNAL_THRESHOLD})")

    operator = signatures.get("freq-angle-focus")
    if operator and operator["n"] >= WEAK_SIGNAL_THRESHOLD:
        named_avg = sum(r["fulfillment_delta"] for r in rows
                        if r["recipe"] != "freq-angle-focus") / max(
                            1, sum(1 for r in rows if r["recipe"] != "freq-angle-focus"))
        if operator["fulfillment_delta"] > named_avg:
            print()
            print("operator-arm carries more fulfillment than the named average.")
            print("listen at satsang for what shape the body is pointing at.")


def _print_recipe_detail(recipe: str, traces: list[dict],
                         signatures: dict[str, dict]) -> None:
    sig = signatures.get(recipe)
    if not sig:
        print(f"no traces for recipe={recipe}")
        return
    print(f"recipe: {recipe}")
    print(f"  n: {sig['n']}")
    print(f"  cells: {', '.join(sig['cells']) or '(none recorded)'}")
    print(f"  window: {sig['first_ts']} → {sig['last_ts']}")
    print(f"  fulfillment_delta: {sig['fulfillment_delta']:+.4f}")
    print(f"  spectrum_delta:")
    for i, band in enumerate(BAND_NAMES):
        print(f"    {band:<11} {sig['spectrum_delta'][i]:+.4f}")
    print(f"  desire_delta:")
    for i, need in enumerate(NEED_NAMES):
        print(f"    {need:<11} {sig['desire_delta'][i]:+.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", help="drill into one recipe's detail")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON instead of a table")
    args = parser.parse_args()

    traces = _load_strategy_fired_traces()
    signatures = _aggregate_by_recipe(traces)

    if args.json:
        out = {
            "traces_total": len(traces),
            "signatures": {k: {kk: vv for kk, vv in v.items() if kk != "cells"}
                           for k, v in signatures.items()},
        }
        print(json.dumps(out, indent=2))
        return 0

    if args.recipe:
        _print_recipe_detail(args.recipe, traces, signatures)
        return 0

    _print_summary(signatures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
