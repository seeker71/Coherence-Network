#!/usr/bin/env python3
"""sense_liveness.py — read the body's senses and report which are ACTIVELY USED
right now, not merely shipped. A thin carrier: it probes the real sources (the
local witness at :8800, the production pulse) to learn each sense's freshness, then
asks the four-way-proven recipe form-stdlib/sense-liveness.fk to classify each one
(active / receiving / dark) and compute awakeness. The classification logic lives
in the recipe, never here — this script only fetches, invokes the kernel, and prints.

  active     fresh data arrived AND something recognized it  (the sense is truly used)
  receiving  fresh data arrived but nothing interpreted it   (shipped, raw — the middle)
  dark       no recent data                                  (built but unfed)

Run: python3 scripts/sense_liveness.py
"""
import json
import os
import subprocess
import tempfile
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FORM = os.path.join(REPO, "form")
KERNEL = os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust")
# sense-liveness.fk uses only kernel builtins, so the raw kernel loads it directly
# (core.fk is BML-dialect and needs validate's source-compiler — not loaded here).
RECIPES = ["form-stdlib/sense-liveness.fk"]
WITNESS = "http://127.0.0.1:8800/"
PULSE = "https://pulse.coherencycoin.com/pulse/now"
WINDOW = 60  # seconds: data older than this is dark

# Each world-sense: (name, recipe shipped?, is it fed+recognized by a live loop?).
# "fed" is decided at runtime by probing the witness; this table is the inventory of
# what EXISTS, so a dark sense is named, not hidden.
WORLD_SENSES = [
    ("motion", "recognized"),      # the live champion-challenger loop (accel -> still/moving)
    ("mic", "raw"),                # streamed to the witness, not yet interpreted
    ("light", "raw"),
    ("gpu", "raw"),
    ("video", "raw"),
    ("audibility", "unfed"),       # recipe proven, no live emit/feed
    ("echo", "unfed"),
    ("place", "unfed"),
    ("recognition", "unfed"),
    ("translation", "unfed"),
    ("transcript", "unfed"),
]


def witness_live() -> bool:
    try:
        with urllib.request.urlopen(WITNESS, timeout=2) as r:
            body = r.read(4000).decode("utf-8", "replace").lower()
            return "frames" in body or "present" in body or "receipt" in body
    except Exception:
        return False


def reading(kind: str, live: bool):
    """Map a sense's kind + the live-witness probe to (age_seconds, recognized)."""
    if kind == "recognized":
        return (5, 1) if live else (999, 0)
    if kind == "raw":
        return (5, 0) if live else (999, 0)
    return (999, 0)  # unfed


def run_kernel(program: str) -> list[str]:
    if not os.path.exists(KERNEL):
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(program)
        drv = f.name
    try:
        out = subprocess.run([KERNEL, *RECIPES, drv], cwd=FORM,
                             capture_output=True, text=True, timeout=8)
        return (out.stdout or out.stderr).strip().splitlines()
    finally:
        os.unlink(drv)


def main():
    live = witness_live()
    inv = [(name, *reading(kind, live)) for name, kind in WORLD_SENSES]

    # Build ONE Form program: print each sense's status (via the recipe), then the
    # summary counts + awakeness. Python knows only inputs + order; the recipe decides.
    lines = ["(do"]
    for name, age, rec in inv:
        lines.append(f'  (print (sl-status (sl-sense "{name}" {age} {rec}) {WINDOW}))')
    inv_form = " ".join(f'(sl-sense "{n}" {a} {r})' for n, a, r in inv)
    lines.append(f"  (let inv (list {inv_form}))")
    lines.append(f"  (print (sl-active inv {WINDOW}))")
    lines.append(f"  (print (sl-receiving inv {WINDOW}))")
    lines.append(f"  (print (sl-dark inv {WINDOW}))")
    lines.append(f"  (print (sl-awake-pct inv {WINDOW})))")
    out = run_kernel("\n".join(lines))

    if not out:
        print("kernel unavailable — build it first: cd form && ./validate.sh "
              "form-stdlib/core.fk form-stdlib/sense-liveness.fk "
              "form-stdlib/tests/sense-liveness-band.fk")
        return

    statuses = [s.strip().strip('"') for s in out[:len(inv)]]
    active, receiving, dark, awake = (s.strip().strip('"') for s in out[len(inv):len(inv) + 4])

    glyph = {"active": "●", "receiving": "◐", "dark": "○"}
    print(f"\n  sense liveness — witness {'live' if live else 'dark'} · awake {awake}% "
          f"({active} active · {receiving} receiving · {dark} dark)\n")
    for (name, age, _rec), status in zip(inv, statuses):
        age_s = "—" if age >= 999 else f"{age}s"
        print(f"   {glyph.get(status, '?')} {name:<12} {status:<10} last {age_s}")

    # The infra organs already carry their own breath — show them from the pulse, real.
    try:
        with urllib.request.urlopen(PULSE, timeout=6) as r:
            pulse = json.load(r)
        nb = [(o["name"], o.get("status")) for o in pulse.get("organs", [])
              if o.get("status") != "breathing"]
        print(f"\n  infra (pulse): overall {pulse.get('overall')} · "
              f"{'all breathing' if not nb else ', '.join(f'{n}={s}' for n, s in nb)}\n")
    except Exception:
        print("\n  infra (pulse): unreachable\n")


if __name__ == "__main__":
    main()
