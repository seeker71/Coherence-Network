"""Run: python3 organ_demo.py

Trains the organ-cell on a small set of felt-moments (each labeled with
spectrum + dispositions + needs), then walks a generic day-sequence
moment by moment. Watch:

  • the spectrum shape change with each moment
  • dispositions (surprise / attend / want / change-perception) light up
  • need predictions per channel
  • desire accumulator build through the day and release at evening
  • strategy choice shift (tend → withdraw → rest, etc.)
  • articulation: the strategy speaks back about now
"""

from organ import (
    Cell, BAND_NAMES, DISPO_NAMES, NEED_NAMES, N_BANDS, N_NEEDS,
)


# ─── training felt-data ──────────────────────────────────────────────────
# Each entry: (text, sense, spectrum[8], dispositions{4}, needs{3})

TRAINING = [
    ("morning sun and slow tea", "felt-outside",
     [+.5, +.4, +.6, +.4, +.3, +.5, +.7, +.7],
     {"surprise": 0.1, "attend": 0.7, "want": 0.1, "change-perception": 0.0},
     {"presence": 0.1, "rest": 0.2, "expression": 0.2}),

    ("sitting by the fire with people I love", "felt-outside",
     [+.6, +.4, +.9, +.3, +.5, +.9, +.6, +.8],
     {"surprise": 0.1, "attend": 0.7, "want": 0.2, "change-perception": 0.1},
     {"presence": 0.1, "rest": 0.2, "expression": 0.2}),

    ("walking in the woods at dawn", "felt-outside",
     [+.7, +.6, +.5, +.4, +.4, +.4, +.8, +.8],
     {"surprise": 0.2, "attend": 0.7, "want": 0.1, "change-perception": 0.1},
     {"presence": 0.1, "rest": 0.2, "expression": 0.2}),

    ("listening to Mose at sunrise", "heard",
     [+.7, +.6, +.6, +.4, +.5, +.6, +.8, +.9],
     {"surprise": 0.3, "attend": 0.9, "want": 0.1, "change-perception": 0.0},
     {"presence": 0.1, "rest": 0.2, "expression": 0.3}),

    ("deep work on something alive", "thought",
     [+.5, +.6, +.3, +.9, +.8, +.4, +.5, +.7],
     {"surprise": 0.2, "attend": 0.9, "want": 0.4, "change-perception": 0.1},
     {"presence": 0.2, "rest": 0.3, "expression": 0.1}),

    ("a true thing landing — oh that's it", "felt-inside",
     [+.4, +.5, +.4, +.8, +.7, +.6, +.7, +.8],
     {"surprise": 0.9, "attend": 0.9, "want": 0.1, "change-perception": 0.3},
     {"presence": 0.1, "rest": 0.1, "expression": 0.1}),

    ("body asking for water", "felt-inside",
     [+.2, +.3, +.1, +.2, +.0, +.1, +.2, +.4],
     {"surprise": 0.1, "attend": 0.8, "want": 0.7, "change-perception": 0.4},
     {"presence": 0.2, "rest": 0.4, "expression": 0.1}),

    ("aimless scrolling at 2am", "saw",
     [-.5, -.6, -.3, -.7, -.4, -.5, -.6, -.7],
     {"surprise": 0.0, "attend": 0.1, "want": 0.5, "change-perception": 0.8},
     {"presence": 0.6, "rest": 0.9, "expression": 0.4}),

    ("rushed performance meeting with no breath", "thought",
     [-.4, -.7, -.2, +.1, -.2, -.3, -.6, -.5],
     {"surprise": 0.0, "attend": 0.6, "want": 0.1, "change-perception": 0.7},
     {"presence": 0.4, "rest": 0.5, "expression": 0.3}),

    ("forced productivity theater", "thought",
     [-.6, -.5, -.4, -.2, -.7, -.3, -.4, -.6],
     {"surprise": 0.1, "attend": 0.2, "want": 0.2, "change-perception": 0.9},
     {"presence": 0.3, "rest": 0.6, "expression": 0.8}),

    ("notifications stacking up unread", "saw",
     [-.3, -.4, -.2, -.5, -.3, -.2, -.4, -.4],
     {"surprise": 0.1, "attend": 0.4, "want": 0.2, "change-perception": 0.7},
     {"presence": 0.4, "rest": 0.5, "expression": 0.3}),

    ("calendar packed wall to wall", "saw",
     [-.4, -.5, -.3, -.4, -.5, -.3, -.6, -.5],
     {"surprise": 0.0, "attend": 0.3, "want": 0.1, "change-perception": 0.8},
     {"presence": 0.5, "rest": 0.6, "expression": 0.5}),

    ("evening tea in quiet company", "felt-outside",
     [+.5, +.4, +.8, +.3, +.4, +.8, +.6, +.7],
     {"surprise": 0.1, "attend": 0.6, "want": 0.2, "change-perception": 0.0},
     {"presence": 0.1, "rest": 0.2, "expression": 0.2}),

    ("deep sleep by the open window", "felt-inside",
     [+.6, +.3, +.4, +.0, +.0, +.2, +.7, +.5],
     {"surprise": 0.0, "attend": 0.2, "want": 0.0, "change-perception": 0.0},
     {"presence": 0.0, "rest": 0.0, "expression": 0.1}),
]


# ─── day sequence — moments arriving in time ─────────────────────────────
# Watch desire build through the middle of the day, release at evening.

DAY = [
    ("morning sun and slow tea by the window",            "felt-outside"),
    ("first calendar invite arriving",                    "saw"),
    ("back-to-back meetings begin",                       "thought"),
    ("rushed performance meeting",                        "thought"),
    ("another meeting compressed in",                     "thought"),
    ("notifications stacking up",                         "saw"),
    ("forced productivity theater all afternoon",         "thought"),
    ("a quiet walk in the woods",                         "felt-outside"),
    ("evening tea in quiet company by the fire",          "felt-outside"),
    ("deep sleep with the window open",                   "felt-inside"),
]


# ─── visualization ───────────────────────────────────────────────────────

def bar(v: float, half: int = 6) -> str:
    """Render -1..+1 as a centered bar of width 2*half+1."""
    cells = [" "] * (2 * half + 1)
    cells[half] = "│"
    if v >= 0:
        n = min(half, int(round(v * half)))
        for i in range(n):
            cells[half + 1 + i] = "█"
    else:
        n = min(half, int(round(-v * half)))
        for i in range(n):
            cells[half - 1 - i] = "█"
    return "".join(cells)


def show_moment(i: int, m: dict) -> None:
    print(f"\n─── moment {i} — {m['text']!r} (sense: {m['sense']}) ───")
    print("  spectrum:")
    for name, v in zip(BAND_NAMES, m["spectrum"]):
        print(f"    {name:>11}  {bar(v)}  {v:+.2f}")
    dispos = "  ".join(f"{k}={v:.2f}" for k, v in m["dispositions"].items())
    print(f"  dispositions: {dispos}")
    needs = "  ".join(f"{k}={v:.2f}" for k, v in m["needs"].items())
    print(f"  needs:        {needs}")
    desire = "  ".join(f"{k}={v:.2f}" for k, v in m["desire"].items())
    print(f"  desire:       {desire}")
    print(f"  strategy:     {m['strategy']}  (cosine={m['strategy_score']:+.2f})")
    print(f"  → {m['articulation']}")


def desire_trajectory(timeline: list[dict]) -> None:
    print("\n═══ desire trajectory across the day (how pressure built and released) ═══")
    print(f"  {'moment':<48}  " + "  ".join(f"{n:>10}" for n in NEED_NAMES))
    for i, m in enumerate(timeline):
        label = f"{i:>2}. {m['text'][:44]}"
        vals = "  ".join(f"{m['desire'][n]:>10.2f}" for n in NEED_NAMES)
        print(f"  {label:<48}  {vals}")


def strategy_trajectory(timeline: list[dict]) -> None:
    print("\n═══ strategy choice across the day ═══")
    for i, m in enumerate(timeline):
        print(f"  {i:>2}. {m['strategy']:<10}  ({m['strategy_score']:+.2f})  {m['text']}")


# ─── main ────────────────────────────────────────────────────────────────

def main():
    cell = Cell(name="A", seed=42)

    for text, sense, spec, dispos, needs in TRAINING:
        cell.ingest(text, sense, spec, dispos, needs)
    final_loss = cell.tend(steps=600, lr=0.15)
    print(f"Tended on {len(TRAINING)} felt-moments. Final loss = {final_loss:.4f}")

    # Walk the day. Each call to perceive() advances desire state.
    for text, sense in DAY:
        m = cell.perceive(text, sense)
        show_moment(len(cell.timeline), m)

    desire_trajectory(cell.timeline)
    strategy_trajectory(cell.timeline)


if __name__ == "__main__":
    main()
