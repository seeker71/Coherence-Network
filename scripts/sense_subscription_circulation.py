#!/usr/bin/env python3
"""Sense subscription circulation — are the AI subscriptions we pay for actually flowing?

Reads the LOCAL CLI traces each tool leaves on this machine (~/.claude, ~/.codex,
~/.grok, ~/.gemini, Cursor app-support) and reflects back, per subscription:

  - consumption — tokens where the trace carries them (Claude), else turns/sessions
  - recency — days since last breath; an idle paid subscription is waste, friction
  - alignment — Coherence-mission vs side-mission, from the cwd each turn records
  - limit standing — where the trace carries it (Codex logs the vendor's own
    used_percent + window + resets_at directly): how close to the edge, when it resets

Waste is friction; friction lowers health. This sensor moves attention to where a
paid resource sits still or presses a limit. Companion to the server-side
api/app/services/automation_usage_service.py, which senses the *runner's* providers
against subscription policy — this senses *this laptop's* personal circulation from
the real traces those providers leave behind.

One engine over uniform events; each provider is an extractor that fills whatever
its trace can honestly carry (fidelity is reported, never faked).

CANONICAL LOGIC LIVES IN FORM, not here. The verdict / pace / alignment rules are
defined and proven in docs/coherence-substrate/circulation-as-recipe.form (the
body's tongue, executable via `coh substrate run`). This Python is the BOOTSTRAP
carrier: it reads the traces (edge IO, legitimately Python) and *mirrors* those
recipes. When the two disagree, the .form is right and this is drifting. (The
.form carries ratios as integer percents 0..100; this carrier uses the matching
fraction thresholds 0.80 ⇔ 80, 0.40 ⇔ 40 — the same decisions.)

Run: python3 scripts/sense_subscription_circulation.py            (the reading)
     python3 scripts/sense_subscription_circulation.py --json     (machine payload)
     python3 scripts/sense_subscription_circulation.py --days 7   (narrow the window)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import socket
import sys
import time
import urllib.request
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
NOW = time.time()


def _epoch(ts_raw: object) -> float | None:
    """ISO-8601 (with trailing Z) or epoch number → unix seconds."""
    if ts_raw is None:
        return None
    if isinstance(ts_raw, (int, float)):
        return float(ts_raw)
    try:
        return datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None

# --- Plan estimates. EDIT to your actual tier — these are only used to name the
#     dollars-at-rest when a subscription goes idle. Honest guesses, not asserted fact.
PLANS: dict[str, dict[str, object]] = {
    "claude": {"plan": "Claude Max", "usd_per_month": 100.0},
    "codex": {"plan": "ChatGPT Pro (Codex)", "usd_per_month": 200.0},
    "cursor": {"plan": "Cursor Pro", "usd_per_month": 20.0},
    "grok": {"plan": "SuperGrok", "usd_per_month": 30.0},
    "gemini": {"plan": "Google AI Pro", "usd_per_month": 20.0},
}

IDLE_DAYS = 7.0      # no breath in this many days → paid but not circulating
SOFT_IDLE_DAYS = 3.0
NEAR_LIMIT_PCT = 80.0


def _aligned(path: str | None) -> bool:
    """A turn is mission-aligned when its working dir lives in a Coherence tree.
    Covers both 'Coherence' and the 'Coherency' coin spelling."""
    return bool(path) and "oheren" in path.lower()


@dataclass
class Event:
    ts: float
    tokens: int = 0
    requests: int = 1
    project: str | None = None


@dataclass
class LimitReading:
    label: str            # e.g. "5h rolling", "weekly"
    used_percent: float
    resets_at: float | None
    source: str           # provenance
    window_minutes: float | None = None

    def pace(self) -> str | None:
        """Are we burning faster than the clock? Compares fraction-used to
        fraction-of-window-elapsed — the 'rate vs remaining' question directly.
        Mirror of `pace_projected` / `pace_on_track` in circulation-as-recipe.form."""
        if not (self.resets_at and self.window_minutes):
            return None
        window_s = self.window_minutes * 60
        elapsed = NOW - (self.resets_at - window_s)
        if elapsed <= 0 or window_s <= 0:
            return None
        frac_elapsed, frac_used = elapsed / window_s, self.used_percent / 100.0
        if frac_used <= 0:
            return "untouched this window"
        projected = frac_used / frac_elapsed
        if projected <= 1.05:
            return f"on pace (~{projected*100:.0f}% used by reset)"
        rate = frac_used / elapsed              # fraction per second
        secs_to_full = max(0.0, 1.0 / rate - elapsed)
        return f"ahead of pace — ~full in {_reset_in(NOW + secs_to_full)}, window resets in {_reset_in(self.resets_at)}"


@dataclass
class Reading:
    provider: str
    fidelity: str                       # "measured tokens" | "measured turns" | "recency"
    unit: str                           # tokens | turns | sessions
    events: list[Event] = field(default_factory=list)
    limits: list[LimitReading] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # derived
    def vol(self, days: float) -> int:
        cut = NOW - days * 86400
        return sum((e.tokens or e.requests) for e in self.events if e.ts >= cut)

    @property
    def last_ts(self) -> float | None:
        return max((e.ts for e in self.events), default=None)

    @property
    def idle_days(self) -> float | None:
        lt = self.last_ts
        return None if lt is None else (NOW - lt) / 86400

    def alignment(self) -> tuple[int, int]:
        """(aligned, side) by native unit, over events that carry a project tag.
        Mirror of `aligned_pct` / `side_pct` in circulation-as-recipe.form."""
        a = s = 0
        for e in self.events:
            if e.project is None:
                continue
            w = e.tokens or e.requests
            if _aligned(e.project):
                a += w
            else:
                s += w
        return a, s


# ---------------------------------------------------------------------------
# Extractors — each returns a Reading. They do their own windowing for speed.
# ---------------------------------------------------------------------------

def _iter_json_lines(path: str, must_contain: tuple[str, ...] = ()):
    """Yield parsed json objects from a jsonl file, pre-filtering by substring
    so we only pay json.loads on lines that can matter."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if must_contain and not any(m in line for m in must_contain):
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def extract_claude(days: float) -> Reading:
    r = Reading("claude", "measured tokens", "tokens")
    root = HOME / ".claude" / "projects"
    files = [f for f in glob.glob(str(root / "**" / "*.jsonl"), recursive=True)
             if NOW - os.path.getmtime(f) < (days + 1) * 86400]
    cut = NOW - days * 86400
    for f in files:
        for o in _iter_json_lines(f, must_contain=('"usage"',)):
            msg = o.get("message") or {}
            u = msg.get("usage") or o.get("usage")
            t = _epoch(o.get("timestamp"))
            if not (u and t) or t < cut:
                continue
            toks = (u.get("input_tokens", 0) + u.get("output_tokens", 0)
                    + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0))
            r.events.append(Event(ts=t, tokens=toks, project=o.get("cwd")))
    r.notes.append("tokens include cache reads/writes (volume, not billed equivalent)")
    return r


def extract_codex(days: float) -> Reading:
    """Codex rollout logs carry the vendor's own rate-limit telemetry — the
    authoritative used_percent / window / resets_at — plus per-turn cwd."""
    r = Reading("codex", "measured turns + vendor limits", "turns")
    roots = [HOME / ".codex" / "sessions", HOME / ".codex" / "archived_sessions"]
    files = []
    for root in roots:
        files += [f for f in glob.glob(str(root / "**" / "rollout-*.jsonl"), recursive=True)
                  if NOW - os.path.getmtime(f) < (days + 1) * 86400]
    files.sort(key=os.path.getmtime)
    cut = NOW - days * 86400
    latest_limit: dict | None = None
    latest_limit_ts = 0.0
    for f in files:
        file_cwd: str | None = None
        for o in _iter_json_lines(f, must_contain=('"token_count"', '"turn_context"')):
            ts = _epoch(o.get("timestamp")) or os.path.getmtime(f)
            payload = o.get("payload") or {}
            if o.get("type") == "turn_context":
                file_cwd = payload.get("cwd") or file_cwd
            if payload.get("type") == "token_count":
                if ts >= cut:
                    r.events.append(Event(ts=ts, requests=1, project=file_cwd))
                rl = payload.get("rate_limits") or {}
                if rl and ts > latest_limit_ts:
                    latest_limit, latest_limit_ts = rl, ts
    if latest_limit:
        plan = latest_limit.get("plan_type")
        if plan:
            r.notes.append(f"vendor plan_type={plan}")
        for key, label in (("primary", "primary"), ("secondary", "secondary")):
            w = latest_limit.get(key)
            if not w:
                continue
            mins = w.get("window_minutes")
            wl = ({300: "5h rolling", 10080: "weekly"}.get(mins) or (f"{mins}min" if mins else label))
            r.limits.append(LimitReading(
                label=wl, used_percent=float(w.get("used_percent", 0.0)),
                resets_at=w.get("resets_at"), source="codex local rollout (vendor-reported)",
                window_minutes=mins))
    return r


def extract_grok(days: float) -> Reading:
    r = Reading("grok", "measured turns", "turns")
    logs = glob.glob(str(HOME / ".grok" / "logs" / "unified*.jsonl"))
    cut = NOW - days * 86400
    for f in logs:
        for o in _iter_json_lines(f, must_contain=("inference_start",)):
            if o.get("msg") != "shell.turn.inference_start":
                continue
            ts = _epoch(o.get("ts"))
            if ts is None or ts < cut:
                continue
            ctx = o.get("ctx") or {}
            r.events.append(Event(ts=ts, requests=1, project=ctx.get("cwd") or ctx.get("path")))
    # plan hint, if the auth file carries one
    auth = HOME / ".grok" / "auth.json"
    if auth.exists():
        try:
            a = json.loads(auth.read_text())
            tier = a.get("plan") or a.get("tier") or (a.get("subscription") or {}).get("tier")
            if tier:
                r.notes.append(f"auth tier={tier}")
        except Exception:
            pass
    r.notes.append("runner never routes to grok — coh model_routing.json has no grok executor")
    return r


def _child_mtimes(dirs: list[Path], days: float, cap: int = 4000) -> list[Event]:
    """Immediate-child mtimes only — bounded, fast. Each child (a workspace or
    session dir) stands in for one stretch of activity. Coarse, but honest."""
    cut = NOW - days * 86400
    out: list[Event] = []
    for d in dirs:
        try:
            with os.scandir(d) as it:
                for entry in it:
                    try:
                        m = entry.stat().st_mtime
                    except Exception:
                        continue
                    if m >= cut:
                        out.append(Event(ts=m, requests=1))
                    if len(out) >= cap:
                        return out
        except Exception:
            continue
    return out


def extract_gemini(days: float) -> Reading:
    """Most Gemini use flows through the Antigravity IDE, which keeps a real
    transcript (USER_INPUT turns, created_at, and the Cwd of each tool call)."""
    r = Reading("gemini", "measured turns (Antigravity)", "turns")
    cut = NOW - days * 86400
    # os.walk (not glob) — the transcript lives under a hidden `.system_generated` dir
    brain = HOME / ".gemini" / "antigravity" / "brain"
    transcripts: list[str] = []
    for root, _dirs, files in os.walk(brain):
        if "transcript.jsonl" in files:
            transcripts.append(os.path.join(root, "transcript.jsonl"))
    for f in transcripts:
        file_project: str | None = None
        events: list[Event] = []
        for line in open(f, encoding="utf-8", errors="ignore"):
            if file_project is None and '"Cwd"' in line:
                m = re.search(r'"Cwd":\s*"\\?"?(/[^"\\]+)', line)
                if m:
                    file_project = m.group(1)
            if '"USER_INPUT"' in line:
                try:
                    ts = _epoch(json.loads(line).get("created_at"))
                except Exception:
                    ts = None
                if ts and ts >= cut:
                    events.append(Event(ts=ts, requests=1))
        for e in events:
            e.project = file_project
        r.events.extend(events)
    if not r.events:  # fall back to bare-CLI session dirs
        r.fidelity = "recency / sessions"
        r.unit = "sessions"
        r.events = _child_mtimes([HOME / ".gemini" / "tmp", HOME / ".gemini" / "history"], days)
    r.notes.append("Antigravity IDE transcripts; bare-gemini-CLI usage (if any) lives in Google's dashboard")
    return r


def extract_cursor(days: float) -> Reading:
    """One Event per Cursor workspace: state.vscdb mtime = last touched, and
    workspace.json's folder gives the project (so alignment is real)."""
    r = Reading("cursor", "recency (per-workspace)", "sessions")
    cut = NOW - days * 86400
    ws_root = HOME / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    try:
        children = list(os.scandir(ws_root))
    except Exception:
        children = []
    for entry in children:
        db = Path(entry.path) / "state.vscdb"
        wj = Path(entry.path) / "workspace.json"
        try:
            m = db.stat().st_mtime if db.exists() else entry.stat().st_mtime
        except Exception:
            continue
        if m < cut:
            continue
        project = None
        try:
            folder = json.loads(wj.read_text()).get("folder", "") if wj.exists() else ""
            project = folder.replace("file://", "") or None
        except Exception:
            pass
        r.events.append(Event(ts=m, requests=1, project=project))
    r.notes.append("per-workspace recency; request/token counts live in cursor.com dashboard")
    return r


EXTRACTORS = {
    "claude": extract_claude,
    "codex": extract_codex,
    "grok": extract_grok,
    "gemini": extract_gemini,
    "cursor": extract_cursor,
}


# ---------------------------------------------------------------------------
# Reading → verdict + render
# ---------------------------------------------------------------------------

def _fmt_vol(n: int, unit: str) -> str:
    if unit == "tokens":
        if n >= 1e9:
            return f"{n/1e9:.1f}B tok"
        if n >= 1e6:
            return f"{n/1e6:.0f}M tok"
        return f"{n/1e3:.0f}K tok"
    return f"{n} {unit}"


def _fmt_ago(idle_days: float | None) -> str:
    if idle_days is None:
        return "never seen"
    if idle_days < 1:
        return f"{idle_days*24:.0f}h ago"
    return f"{idle_days:.0f}d ago"


def _reset_in(resets_at: float | None) -> str:
    if not resets_at:
        return "?"
    dt = resets_at - NOW
    if dt <= 0:
        return "now"
    if dt < 3600:
        return f"{dt/60:.0f}m"
    if dt < 86400:
        return f"{dt/3600:.0f}h"
    return f"{dt/86400:.1f}d"


def verdict(r: Reading, days: float) -> tuple[str, str]:
    """(tag, sentence) — where attention wants to move.

    Mirror of `circulation_verdict` in circulation-as-recipe.form (canonical).
    Same cascade, same order; thresholds correspond 0.80⇔80, 0.40⇔40."""
    idle = r.idle_days
    if r.fidelity == "unavailable":
        return "BLIND", "couldn't read this trace — sensing gap, not necessarily idle"
    near = [lm for lm in r.limits if lm.used_percent >= NEAR_LIMIT_PCT]
    usd = PLANS.get(r.provider, {}).get("usd_per_month")
    if idle is None or idle >= IDLE_DAYS:
        money = f" (~${usd:.0f}/mo at rest)" if usd else ""
        return "IDLE", f"paid but not circulating in {days:.0f}d{money} — waste, or a tool to retire"
    if near:
        lm = max(near, key=lambda x: x.used_percent)
        return "NEAR LIMIT", f"{lm.label} at {lm.used_percent:.0f}% — resets in {_reset_in(lm.resets_at)}; pressing the edge"
    if idle >= SOFT_IDLE_DAYS:
        return "COOLING", f"last breath {_fmt_ago(idle)} — circulation slowing"
    a, s = r.alignment()
    if a + s > 0 and s / (a + s) > 0.4:
        return "SIDE-HEAVY", f"{s/(a+s)*100:.0f}% side-mission — attention spread off-mission"
    return "FLOWING", "circulating, aligned"


def build_readings(days: float) -> list[Reading]:
    out = []
    for name, fn in EXTRACTORS.items():
        try:
            out.append(fn(days))
        except Exception as e:  # a blind provider is a note, not a crash
            r = Reading(name, "unavailable", "—")
            r.notes.append(f"extractor error: {type(e).__name__}: {e}")
            out.append(r)
    return out


def render(readings: list[Reading], days: float) -> None:
    print("\n  Subscription circulation — this laptop's local traces"
          f"  (window: {days:.0f}d)\n")
    hdr = f"  {'subscription':<10} {'last used':<11} {f'{days:.0f}d activity':<14} {'aligned':<9} {'limit standing':<22} reading"
    print(hdr)
    print("  " + "-" * (len(hdr)))
    total_idle_usd = 0.0
    for r in sorted(readings, key=lambda x: -(x.idle_days or 1e9)):
        tag, sentence = verdict(r, days)
        vol = _fmt_vol(r.vol(days), r.unit) if r.events else "—"
        a, s = r.alignment()
        align = f"{a/(a+s)*100:.0f}%" if (a + s) else "—"
        if r.limits:
            lm = max(r.limits, key=lambda x: x.used_percent)
            limit = f"{lm.label} {lm.used_percent:.0f}% (↻{_reset_in(lm.resets_at)})"
        else:
            limit = "dashboard-only"
        print(f"  {r.provider:<10} {_fmt_ago(r.idle_days):<11} {vol:<14} {align:<9} {limit:<22} {tag}")
        usd = PLANS.get(r.provider, {}).get("usd_per_month")
        if tag == "IDLE" and usd:
            total_idle_usd += usd

    print("\n  Reading:")
    for r in sorted(readings, key=lambda x: -(x.idle_days or 1e9)):
        tag, sentence = verdict(r, days)
        mark = {"FLOWING": "·", "SIDE-HEAVY": "~", "COOLING": "~",
                "NEAR LIMIT": "!", "IDLE": "✗", "BLIND": "?"}.get(tag, "·")
        print(f"    {mark} {r.provider:<8} {sentence}")
        for lm in r.limits:
            pace = lm.pace()
            print(f"        {lm.label}: {lm.used_percent:.0f}% used"
                  + (f" · {pace}" if pace else "")
                  + f"  [{lm.source}]")
        for n in r.notes[:2]:
            print(f"        {n}")

    # portfolio: concentration + alignment across what we could measure
    measurable = [r for r in readings if r.events and r.unit in ("tokens", "turns")]
    if measurable:
        a_tot = sum(r.alignment()[0] for r in measurable)
        s_tot = sum(r.alignment()[1] for r in measurable)
        if a_tot + s_tot:
            print(f"\n  Across measured turns/tokens: {a_tot/(a_tot+s_tot)*100:.0f}% aligned to Coherence"
                  f", {s_tot/(a_tot+s_tot)*100:.0f}% side-mission.")

    if total_idle_usd:
        print(f"\n  ≈ ${total_idle_usd:.0f}/mo sitting in idle subscriptions — attention wants to move here.")
    print("    (plan $/mo are editable estimates in PLANS at the top of this file.)\n")


def to_payload(readings: list[Reading], days: float) -> dict:
    return {
        "generated_at": int(NOW),
        "window_days": days,
        "providers": [
            {
                "provider": r.provider,
                "fidelity": r.fidelity,
                "unit": r.unit,
                "last_used_epoch": int(r.last_ts) if r.last_ts else None,
                "idle_days": round(r.idle_days, 2) if r.idle_days is not None else None,
                "volume": {f"{d}d": r.vol(d) for d in (1, 7, 30) if d <= days or d == 1},
                "alignment": dict(zip(("aligned", "side"), r.alignment())),
                "limits": [vars(lm) for lm in r.limits],
                "verdict": verdict(r, days)[0],
                "reading": verdict(r, days)[1],
                "notes": r.notes,
            }
            for r in readings
        ],
    }


# ---------------------------------------------------------------------------
# Push to the collective body — map readings to the canonical ProviderUsageSnapshot
# shape and POST so the /usage surface (not just this CLI) can see the circulation.
# ---------------------------------------------------------------------------

_SNAPSHOT_UNIT = {"tokens": "tokens", "turns": "requests", "sessions": "tasks"}


def snapshots_payload(readings: list[Reading], days: float) -> list[dict]:
    out = []
    for r in readings:
        unit = _SNAPSHOT_UNIT.get(r.unit, "tasks")
        metrics: list[dict] = []
        if r.events:
            metrics.append({
                "id": f"volume_{int(days)}d", "label": f"{r.provider} activity ({int(days)}d)",
                "unit": unit, "used": float(r.vol(days)), "window": f"{int(days)}d",
                "evidence_source": r.fidelity,
            })
        a, s = r.alignment()
        if a + s:
            metrics.append({
                "id": "aligned_ratio", "label": "Coherence-aligned share", "unit": "ratio",
                "used": round(a / (a + s), 4), "limit": 1.0, "evidence_source": "cwd of each turn",
            })
        for lm in r.limits:
            frac = round(lm.used_percent / 100.0, 4)
            metrics.append({
                "id": f"limit_{lm.label.replace(' ', '_')}", "label": f"{lm.label} limit",
                "unit": "ratio", "used": frac, "limit": 1.0, "remaining": round(max(0.0, 1 - frac), 4),
                "window": lm.label, "evidence_source": lm.source,
            })
        tag, sentence = verdict(r, days)
        out.append({
            "id": f"local_{r.provider}_{int(NOW)}", "provider": r.provider, "kind": "custom",
            "status": "ok" if r.events else "unavailable", "metrics": metrics,
            "data_source": "provider_cli",
            "usage_per_time": f"{r.vol(1)} {unit}/24h" if r.events else None,
            "notes": [sentence] + r.notes[:3],
            "raw": {"verdict": tag, "fidelity": r.fidelity,
                    "idle_days": round(r.idle_days, 2) if r.idle_days is not None else None,
                    "alignment": {"aligned": a, "side": s}},
        })
    return out


def push(readings: list[Reading], days: float, api_base: str, host: str) -> tuple[int, str]:
    body = json.dumps({"host": host, "snapshots": snapshots_payload(readings, days)}).encode()
    url = api_base.rstrip("/") + "/api/automation/usage/local-circulation"
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode()[:200]


def main() -> int:
    ap = argparse.ArgumentParser(description="Sense subscription circulation from local CLI traces.")
    ap.add_argument("--days", type=float, default=32.0, help="window to sense over (default 32)")
    ap.add_argument("--json", action="store_true", help="emit machine payload")
    ap.add_argument("--push", action="store_true",
                    help="push the reading to the collective body's /usage store")
    ap.add_argument("--api", default="https://api.coherencycoin.com",
                    help="API base for --push (default prod)")
    ap.add_argument("--host", default=socket.gethostname(),
                    help="host label for pushed snapshots")
    args = ap.parse_args()
    readings = build_readings(args.days)
    if args.json:
        print(json.dumps(to_payload(readings, args.days), indent=2))
    else:
        render(readings, args.days)
    if args.push:
        try:
            status, _ = push(readings, args.days, args.api, args.host)
            print(f"  → pushed {len(readings)} snapshots to {args.api} as host={args.host} (HTTP {status})")
        except Exception as e:
            print(f"  → push failed: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
