#!/usr/bin/env python3
"""sense_liveness.py — read the body's senses and report which are ACTIVELY USED
right now, not merely shipped, and not merely capable. A thin carrier: it reads the
real witness state (local :8800/state) to learn each sense's freshness — whether
actual SAMPLES are flowing or only capability HEARTBEATS — then asks the four-way-
proven recipe form-stdlib/sense-liveness.fk to classify each one and compute
awakeness. The classification logic lives in the recipe, never here.

  active     fresh samples arrived AND something recognized them  (truly used)
  receiving  fresh samples flow but nothing interprets them       (the honest middle)
  capable    no samples, but the organ heartbeats "I can sense"   (present, idle)
  dark       no samples and no heartbeat                          (built but unfed)

The capable/active gap is the one a naive readout misses: a phone announcing it CAN
sense is not a phone streaming data. Run: python3 scripts/sense_liveness.py
"""
import json
import os
import subprocess
import tempfile
import time
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FORM = os.path.join(REPO, "form")
KERNEL = os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust")
# sense-liveness.fk uses only kernel builtins, so the raw kernel loads it directly
# (core.fk is BML-dialect and needs validate's source-compiler — not loaded here).
RECIPES = ["form-stdlib/sense-liveness.fk"]
STATE = "http://127.0.0.1:8800/state"
PULSE = "https://pulse.coherencycoin.com/pulse/now"
WINDOW = 60  # seconds: older than this is stale
STALE = 999  # sentinel age meaning "no recent datum"

# The inventory of what EXISTS, so a dark/capable sense is named, not hidden.
#   sensor — the phone has this organ and heartbeats it; samples may or may not flow
#   unfed  — a proven recipe with no live feed at all
SENSOR_LANES = ["motion", "mic", "light", "gpu", "video"]
UNFED_LANES = ["audibility", "echo", "place", "recognition", "translation", "transcript"]


def fetch_state():
    try:
        with urllib.request.urlopen(STATE, timeout=3) as r:
            return json.load(r)
    except Exception:
        return None


def inventory(state):
    """Build (name, sample_age, recognized, hb_age) per sense from the real witness."""
    now = time.time()
    if state:
        hb_age = int(max(0, now - state.get("last_ts", 0)))  # heartbeats are arriving
        has_samples = (state.get("sample_frames", 0) or 0) > 0
        recd = str(state.get("recognized", "")).strip()
        motion_recognized = 1 if (has_samples and recd and recd not in ("—", "-", "?", "")) else 0
    else:
        hb_age, has_samples, motion_recognized = STALE, False, 0

    inv = []
    for name in SENSOR_LANES:
        sample_age = hb_age if has_samples else STALE
        rec = motion_recognized if name == "motion" else 0
        inv.append((name, sample_age, rec, hb_age))  # heartbeat present -> capable when idle
    for name in UNFED_LANES:
        inv.append((name, STALE, 0, STALE))          # no feed at all -> dark
    return inv


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
    state = fetch_state()
    inv = inventory(state)

    # Build ONE Form program: print each sense's status (via the recipe), then the
    # summary counts + awakeness. Python knows only inputs + order; the recipe decides.
    lines = ["(do"]
    for name, sa, rec, hb in inv:
        lines.append(f'  (print (sl-status (sl-sense "{name}" {sa} {rec} {hb}) {WINDOW}))')
    inv_form = " ".join(f'(sl-sense "{n}" {sa} {rec} {hb})' for n, sa, rec, hb in inv)
    lines.append(f"  (let inv (list {inv_form}))")
    for fn in ("sl-active", "sl-receiving", "sl-capable", "sl-dark", "sl-awake-pct"):
        lines.append(f"  (print ({fn} inv {WINDOW}))")
    lines[-1] = lines[-1] + ")"
    out = run_kernel("\n".join(lines))

    if not out:
        print("kernel unavailable — build it first: cd form && ./validate.sh "
              "form-stdlib/core.fk form-stdlib/sense-liveness.fk "
              "form-stdlib/tests/sense-liveness-band.fk")
        return

    statuses = [s.strip().strip('"') for s in out[:len(inv)]]
    active, receiving, capable, dark, awake = (s.strip().strip('"') for s in out[len(inv):len(inv) + 5])

    if state:
        hb = int(max(0, time.time() - state.get("last_ts", 0)))
        src = (f"witness live · last beat {hb}s · {state.get('frames', 0)} frames "
               f"({state.get('sample_frames', 0)} samples, "
               f"{state.get('heartbeat_frames', 0)} heartbeats)")
    else:
        src = "witness dark — :8800 unreachable"

    glyph = {"active": "●", "receiving": "◐", "capable": "◌", "dark": "○"}
    print(f"\n  sense liveness — {src}")
    print(f"  awake {awake}%  ·  {active} active · {receiving} receiving · "
          f"{capable} capable · {dark} dark\n")
    for (name, sa, _rec, _hb), status in zip(inv, statuses):
        age_s = "—" if sa >= STALE else f"{sa}s"
        print(f"   {glyph.get(status, '?')} {name:<12} {status:<10} samples {age_s}")

    # The infra organs carry their own breath — show them from the pulse, real.
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
