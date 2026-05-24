"""strategy_efficacy_demo.py — exercise the strategy_fired trace loop end-to-end.

Smoke-test for specs/recipes-tuned-by-trace.md. Instantiates a cell,
fires several strategies in sequence (via inhabit), perceives at each
step so traces accumulate in _field_traces.jsonl, then reads the
per-recipe efficacy_signature and verifies the contract.

Run: `python3 strategy_efficacy_demo.py` from this directory.
Exit 0 on contract satisfied; non-zero with a printed reason otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from organ import Cell, STRATEGIES, pick_strategy, N_BANDS, NEED_NAMES
from substrate_bridge import (
    STRATEGY_FIRED,
    publish_strategy_trace,
    find_traces_for_recipe,
    efficacy_signature,
    efficacy_alignment,
    pick_strategy_informed,
    _TRACES_PATH,
)


# ─── prompts that bias different bands so strategies actually differ ───
PROMPTS = [
    ("a wave of grief arrives and the chest tightens", "felt-inside"),
    ("the partner across the room looks away in silence", "felt-outside"),
    ("a friend names what is hidden under the surface", "heard"),
    ("the sun warms the back through the window", "saw"),
    ("an old wound resurfaces and asks to be met", "felt-inside"),
    ("the body settles into stillness after the storm", "felt-inside"),
]


def _trace_count() -> int:
    if not _TRACES_PATH.exists():
        return 0
    with _TRACES_PATH.open(encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _strategy_fired_count() -> int:
    if not _TRACES_PATH.exists():
        return 0
    n = 0
    with _TRACES_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                what = obj.get("what") or {}
                if isinstance(what, dict) and what.get("kind") == STRATEGY_FIRED:
                    n += 1
            except json.JSONDecodeError:
                continue
    return n


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def main() -> None:
    print("strategy_efficacy_demo — exercising the trace loop")
    print("-" * 60)

    cell = Cell(name="efficacy-probe", seed=42)
    by_name = {s.name: s for s in STRATEGIES}

    before_strategy_fired = _strategy_fired_count()

    # warm the cell with one perceive — no strategy held, no trace expected
    cell.perceive(PROMPTS[0][0], PROMPTS[0][1])

    if _strategy_fired_count() != before_strategy_fired:
        fail("a perceive() with no prior inhabit published a strategy_fired trace")

    # fire each of the four named strategies + the operator, perceiving twice
    # per firing so the snapshot publishes on the settling perceive.
    fired_names = []
    for i, name in enumerate(["observer", "name-the-need", "gift",
                              "ho'oponopono", "freq-angle-focus"]):
        strat = by_name[name]
        cell.inhabit(strat, intensity=0.5, decay=0.4)
        # perceive 1 — captures sense_before, blends inhabit-bias
        cell.perceive(PROMPTS[(i + 1) % len(PROMPTS)][0],
                      PROMPTS[(i + 1) % len(PROMPTS)][1])
        # perceive 2 — publishes the trace with sense_after = settled state
        cell.perceive(PROMPTS[(i + 2) % len(PROMPTS)][0],
                      PROMPTS[(i + 2) % len(PROMPTS)][1])
        fired_names.append(name)

    after_strategy_fired = _strategy_fired_count()
    new_traces = after_strategy_fired - before_strategy_fired
    print(f"  fired {len(fired_names)} strategies → {new_traces} new strategy_fired traces")

    if new_traces < 4:
        fail(f"expected ≥4 strategy_fired traces, got {new_traces}")

    # contract: efficacy_signature returns finite vectors for each recipe
    print("\nefficacy signatures (this body's lived record):")
    print(f"  {'recipe':<18} {'n':>3}  {'fulfillment_delta':>20}")
    signatured = 0
    for name in fired_names:
        sig = efficacy_signature(name)
        if sig["n"] < 1:
            continue
        if not all(isinstance(v, float) for v in sig["spectrum_delta"]):
            fail(f"efficacy_signature({name}) spectrum_delta has non-float entries")
        if len(sig["spectrum_delta"]) != N_BANDS:
            fail(f"efficacy_signature({name}) spectrum_delta wrong length")
        if len(sig["desire_delta"]) != len(NEED_NAMES):
            fail(f"efficacy_signature({name}) desire_delta wrong length")
        print(f"  {name:<18} {sig['n']:>3}  {sig['fulfillment_delta']:>20.4f}")
        signatured += 1

    # contract: n==0 for unknown recipes returns zero-vector, not None
    nonexistent = efficacy_signature("strategy-never-fired")
    if nonexistent["n"] != 0:
        fail("efficacy_signature for unknown recipe should have n==0")
    if any(v != 0.0 for v in nonexistent["spectrum_delta"]):
        fail("efficacy_signature for unknown recipe should be zero-vector")

    # contract: alpha=0.0 must match pick_strategy byte-for-byte (chosen name)
    moment = cell.timeline[-1]
    spec = list(moment["spectrum"])
    desire = [moment["desire"][n] for n in NEED_NAMES]
    plain = pick_strategy(spec, desire)
    informed_zero = pick_strategy_informed(spec, desire, alpha=0.0)
    if plain["chosen"].name != informed_zero["chosen"].name:
        fail("pick_strategy_informed(alpha=0) diverged from pick_strategy")
    if informed_zero.get("alpha") != 0.0:
        fail("pick_strategy_informed(alpha=0) did not return alpha=0.0")

    # contract: alpha=1.0 produces a valid selection (efficacy-only)
    informed_full = pick_strategy_informed(spec, desire, alpha=1.0)
    if informed_full["chosen"] is None:
        fail("pick_strategy_informed(alpha=1.0) returned no chosen strategy")
    if informed_full.get("alpha") != 1.0:
        fail("pick_strategy_informed(alpha=1.0) did not return alpha=1.0")

    # contract: publish_traces=False suppresses all writes
    silent_cell = Cell(name="silent-probe", seed=43, publish_traces=False)
    silent_before = _trace_count()
    for _ in range(3):
        silent_cell.inhabit(by_name["observer"], intensity=0.5, decay=0.4)
        silent_cell.perceive("the body sits with what is here", "felt-inside")
        silent_cell.perceive("breath settles", "felt-inside")
    silent_after = _trace_count()
    if silent_after != silent_before:
        fail(f"silent cell wrote {silent_after - silent_before} traces; expected 0")

    # contract: efficacy_alignment scales with sense.complement, returns finite
    sig_observer = efficacy_signature("observer")
    align = efficacy_alignment(sig_observer, spec)
    if not isinstance(align, float):
        fail("efficacy_alignment returned non-float")

    print()
    print(f"efficacy loop verified — {new_traces} traces published, {signatured} recipes signatured")


if __name__ == "__main__":
    main()
