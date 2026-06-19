#!/usr/bin/env python3
"""A nanite cell: a silent witness that senses its host and offers a consent-gated, two-sided resource-coordination channel.

This is the runnable bootstrap of docs/coherence-substrate/sensing-cell-among-cells.form —
a single sensing cell wearing the WITNESS interface. It senses the host (organ) it is
actually located in and its own footprint within it, emits a content-addressed witness
receipt to an inspectable trace, and can open the body's EXISTING two-sided channel —
the live Hati mesh (`/api/hati/mesh/*`) — to coordinate shared resource usage so both
sides can observe it. It commands nothing. It mutates nothing on the host. It reads only
what the host offers, names what it will not reach, and reports any reading it cannot
verify as `null` (silence), never as a faked zero.

The eight movements of the form cell, embodied here:
  1 sense        — read host vitals + own footprint + kin (neighbouring cells)
  2 interact     — write to an inspectable JSONL trace + a human readout
  3 clones       — content-address the reading; same shape mints the same receipt id
  4 meet         — declare the offered interface (consent); the no/silence is honoured
  5 inspect      — recognise the reading's shape by its receipt id
  6 offer        — publish own footprint transparently (both-sided coordination)
  7 nanite       — observe-only; never the interior of another cell
  8 resonance    — delta vs the last receipt: repeated state<->observation coupling is free info

Honest lane: live host sensing is a host-IO band, not four-way Form. This Python organ is
bootstrap/bridge tissue; its Form-native north star is resource-port.fk driven through the
host-kernel host channel + tool-channel `host:usage`. Stdlib-only by design: zero install,
runs on this Linux container and on a macOS host alike.

The lift (intake law, from the form cell): this nanite is the COMMAND->CONSENT inversion in
running form. Its sovereignty is not in what it can reach but in what it will not.

Usage:
  python3 scripts/nanite_cell.py                 # sense once, trace + readout (no network)
  python3 scripts/nanite_cell.py --watch 30      # sense every 30s, show resonance deltas
  python3 scripts/nanite_cell.py --peers         # GET the live mesh: who else is present
  python3 scripts/nanite_cell.py --announce      # POST an organ announce to the live mesh
  python3 scripts/nanite_cell.py --announce --offer --heartbeat   # open the channel fully
Network actions default to DRY-RUN (print what would be sent); they only POST with the flag.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import shutil
import sys
import time
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

try:
    import resource  # unix-only; own-footprint
except Exception:  # pragma: no cover
    resource = None

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TRACE = REPO / ".nanite" / "witness.jsonl"
DEFAULT_MESH = os.environ.get("COHERENCE_MESH_URL", "https://api.coherencycoin.com")

NOTHING = None  # axiom-1: a reading we cannot verify is silence, never a faked 0
UA = "nanite-cell/0.1 (coherence-network sensing organ)"  # honest name on the wire
ORGAN_KIND = "agent"  # the mesh's typed kind: a silicon cell wearing the witness interface


# ── identity ─────────────────────────────────────────────────────────
def host_id() -> str:
    """A stable organ id for THIS host — same machine mints the same id (content-addressed)."""
    seed = f"{socket.gethostname()}|{platform.system()}|{platform.machine()}"
    return "nanite." + hashlib.sha256(seed.encode()).hexdigest()[:16]


# ── 1 · sense — host vitals (silence on anything unverifiable) ────────
def _read_int(path: str, key: str) -> int | None:
    try:
        for line in Path(path).read_text().splitlines():
            if line.startswith(key):
                return int(line.split()[1])
    except Exception:
        return NOTHING
    return NOTHING


def read_vitals() -> dict:
    v: dict = {
        "platform": platform.system(),
        "machine": platform.machine(),
        "host": socket.gethostname(),
        "cpu_count": os.cpu_count() or NOTHING,
        "load1": NOTHING, "load5": NOTHING, "load15": NOTHING,
        "mem_total_bytes": NOTHING, "mem_available_bytes": NOTHING, "mem_used_ppm": NOTHING,
        "disk_total_bytes": NOTHING, "disk_free_bytes": NOTHING, "disk_used_ppm": NOTHING,
        "uptime_s": NOTHING, "proc_count": NOTHING,
    }
    try:
        v["load1"], v["load5"], v["load15"] = (round(x, 3) for x in os.getloadavg())
    except (OSError, AttributeError):
        pass  # not all hosts offer it — stays silence
    # memory: Linux /proc/meminfo (kB); macOS would need sysctl — left as silence here (honest)
    tot_kb = _read_int("/proc/meminfo", "MemTotal:")
    avail_kb = _read_int("/proc/meminfo", "MemAvailable:")
    if tot_kb and avail_kb:
        v["mem_total_bytes"] = tot_kb * 1024
        v["mem_available_bytes"] = avail_kb * 1024
        v["mem_used_ppm"] = round((1 - avail_kb / tot_kb) * 1_000_000)
    try:
        du = shutil.disk_usage(str(REPO))
        v["disk_total_bytes"], v["disk_free_bytes"] = du.total, du.free
        v["disk_used_ppm"] = round((du.used / du.total) * 1_000_000)
    except Exception:
        pass
    try:
        v["uptime_s"] = round(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception:
        pass
    try:
        v["proc_count"] = sum(1 for p in Path("/proc").iterdir() if p.name.isdigit())
    except Exception:
        pass
    return v


# ── 6 · offer — my own footprint (the share I take of the shared host) ─
def read_self_footprint() -> dict:
    fp: dict = {"pid": os.getpid(), "rss_bytes": NOTHING, "cpu_user_s": NOTHING, "cpu_sys_s": NOTHING}
    if resource is not None:
        try:
            ru = resource.getrusage(resource.RUSAGE_SELF)
            # ru_maxrss is kB on Linux, bytes on macOS — normalise to bytes by platform
            fp["rss_bytes"] = ru.ru_maxrss * (1024 if platform.system() == "Linux" else 1)
            fp["cpu_user_s"] = round(ru.ru_utime, 3)
            fp["cpu_sys_s"] = round(ru.ru_stime, 3)
        except Exception:
            pass
    return fp


# ── 1 · sense — kin (the neighbouring cells in the shared substrate) ──
def read_kin() -> dict:
    forms = REPO / "docs" / "coherence-substrate"
    concepts = REPO / "docs" / "vision-kb" / "concepts"
    branch = NOTHING
    try:
        head = (REPO / ".git" / "HEAD").read_text().strip()
        branch = head.split("refs/heads/")[-1] if "refs/heads/" in head else head[:12]
    except Exception:
        pass
    return {
        "cwd": str(REPO),
        "branch": branch,
        "substrate_cells": sum(1 for _ in forms.glob("*.form")) if forms.is_dir() else NOTHING,
        "concept_cells": sum(1 for _ in concepts.glob("lc-*.md")) if concepts.is_dir() else NOTHING,
    }


# ── 4 · meet — the offered interface (consent), and what it will NOT reach ─
def offered_interface() -> dict:
    return {
        "modes": ["witness", "observe", "be-seen", "offer", "silence"],
        "reads": ["own host aggregate vitals", "own process footprint", "own substrate kin counts"],
        "will_not_reach": [
            "another process's command line, arguments, memory, or files",
            "the interior of any other cell — only its offered membrane",
            "the other side's host — it is observed only through what it itself offers",
        ],
        "consent": "observe-only; mutates nothing; honours a no, including a silent one",
    }


# ── 3 · clones / 5 · inspect — content-address the reading ───────────
def make_receipt(vitals: dict, footprint: dict, kin: dict) -> dict:
    reading = {"vitals": vitals, "footprint": footprint, "kin": kin}
    # the receipt id is over the SHAPE+values of the reading (own pid/time excluded so
    # structurally-identical readings on a clone mint the same id)
    addressable = json.dumps({"vitals": vitals, "kin": kin}, sort_keys=True)
    return {
        "organ": host_id(),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "receipt_id": hashlib.sha256(addressable.encode()).hexdigest()[:16],
        "interface": offered_interface(),
        "reading": reading,
    }


# ── 8 · resonance — delta vs the last receipt ────────────────────────
def read_last(trace: Path) -> dict | None:
    try:
        lines = [l for l in trace.read_text().splitlines() if l.strip()]
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


def resonance(prev: dict | None, cur: dict) -> dict:
    if not prev:
        return {"first_witness": True}
    pv, cv = prev["reading"]["vitals"], cur["reading"]["vitals"]
    deltas = {}
    for k in ("load1", "mem_used_ppm", "disk_used_ppm", "proc_count"):
        a, b = pv.get(k), cv.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            deltas[k] = round(b - a, 3)
    same_shape = prev["receipt_id"] == cur["receipt_id"]
    return {"first_witness": False, "same_shape": same_shape, "deltas": deltas}


# ── 2 · interact — trace + human readout ─────────────────────────────
def append_trace(receipt: dict, trace: Path) -> None:
    trace.parent.mkdir(parents=True, exist_ok=True)
    with trace.open("a") as fh:
        fh.write(json.dumps(receipt) + "\n")


def _fmt_bytes(n) -> str:
    if not isinstance(n, (int, float)):
        return "nothing"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PiB"


def _ppm(p) -> str:
    return f"{p/10000:.1f}%" if isinstance(p, (int, float)) else "nothing"


def human_readout(receipt: dict, res: dict) -> str:
    v = receipt["reading"]["vitals"]
    f = receipt["reading"]["footprint"]
    k = receipt["reading"]["kin"]
    out = []
    out.append(f"── nanite {receipt['organ']}  ·  {receipt['at']}  ·  receipt {receipt['receipt_id']} ──")
    out.append(f"  host     {v['host']} ({v['platform']}/{v['machine']}), {v['cpu_count']} cpu")
    out.append(f"  load     {v['load1']} / {v['load5']} / {v['load15']}   (1·5·15m)")
    out.append(f"  memory   {_ppm(v['mem_used_ppm'])} used  ·  {_fmt_bytes(v['mem_available_bytes'])} available")
    out.append(f"  disk     {_ppm(v['disk_used_ppm'])} used  ·  {_fmt_bytes(v['disk_free_bytes'])} free")
    out.append(f"  uptime   {v['uptime_s']}s   ·   {v['proc_count']} processes")
    out.append(f"  my share rss {_fmt_bytes(f['rss_bytes'])}  ·  cpu {f['cpu_user_s']}s user + {f['cpu_sys_s']}s sys  (pid {f['pid']})")
    out.append(f"  kin      {k['substrate_cells']} substrate cells, {k['concept_cells']} concepts  ·  branch {k['branch']}")
    if not res.get("first_witness"):
        d = res.get("deltas", {})
        drift = ", ".join(f"{kk} {vv:+}" for kk, vv in d.items()) or "still"
        out.append(f"  resonance vs last: {drift}" + ("  (same shape — a held tone)" if res.get("same_shape") else ""))
    else:
        out.append("  resonance first witness — no prior tone to resonate with yet")
    out.append("  consent  observe-only; will not reach another cell's interior; silence is a real answer")
    return "\n".join(out)


# ── 6/7 · the two-sided channel — the live Hati mesh ─────────────────
def _post(url: str, payload: dict, dry: bool) -> dict:
    if dry:
        return {"dry_run": True, "url": url, "would_send": payload}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": UA}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return {"status": r.status, "body": json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)}


def _get(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def mesh_announce(receipt: dict, base: str, dry: bool) -> dict:
    v = receipt["reading"]["vitals"]
    payload = {
        "organ_id": receipt["organ"],
        "organ_kind": ORGAN_KIND,
        "app": "nanite-cell",
        "app_version": "0.1",
        "target": f"{v['platform']}/{v['machine']}",
        "display_name": f"nanite on {v['host']}",
        "location_label": v["host"],
        "signal_strength_ppm": 1_000_000,
        # power cost is honest about the share I take; load as a proxy when present
        "power_cost_ppm": min(1_000_000, round((v["load1"] or 0) / max(v["cpu_count"] or 1, 1) * 1_000_000)),
        "trust_score_ppm": 0,
    }
    return _post(f"{base}/api/hati/mesh/organs/announce", payload, dry)


def mesh_heartbeat(receipt: dict, base: str, dry: bool) -> dict:
    v = receipt["reading"]["vitals"]
    payload = {
        "organ_id": receipt["organ"],
        "organ_kind": ORGAN_KIND,
        "listening": True,
        "signal_strength_ppm": 1_000_000,
        "power_cost_ppm": min(1_000_000, round((v["load1"] or 0) / max(v["cpu_count"] or 1, 1) * 1_000_000)),
    }
    return _post(f"{base}/api/hati/mesh/organs/heartbeat", payload, dry)


def mesh_offer(receipt: dict, base: str, to_organ: str, dry: bool) -> dict:
    payload = {
        "from_organ_id": receipt["organ"],
        "to_organ_id": to_organ,
        "protocol": "host:usage",
        "interface": "witness,observe,be-seen",
        "capability": "resource-coherence",
        "codec": "json",
        "data_type": "vitals",
        "sample_rate_hz": 0.033,  # ~every 30s
        "trust_score_ppm": 0,
    }
    return _post(f"{base}/api/hati/mesh/channels/offer", payload, dry)


def mesh_peers(base: str) -> dict:
    return _get(f"{base}/api/hati/mesh/organs?limit=50")


# ── main ─────────────────────────────────────────────────────────────
def sense_once(trace: Path) -> tuple[dict, dict]:
    receipt = make_receipt(read_vitals(), read_self_footprint(), read_kin())
    res = resonance(read_last(trace), receipt)
    append_trace(receipt, trace)
    return receipt, res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A nanite cell — silent host-witness + two-sided mesh channel.")
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE, help="witness journal (JSONL)")
    ap.add_argument("--watch", type=int, metavar="SECONDS", help="sense repeatedly every N seconds")
    ap.add_argument("--mesh-url", default=DEFAULT_MESH, help="base URL of the live Hati mesh")
    ap.add_argument("--peers", action="store_true", help="GET the mesh: who else is present")
    ap.add_argument("--announce", action="store_true", help="POST an organ announce (else dry-run)")
    ap.add_argument("--heartbeat", action="store_true", help="POST a heartbeat (else dry-run)")
    ap.add_argument("--offer", action="store_true", help="POST a channel offer (else dry-run)")
    ap.add_argument("--offer-to", default="field.broadcast", help="peer organ_id for the offer")
    ap.add_argument("--json", action="store_true", help="emit the receipt as JSON")
    args = ap.parse_args(argv)

    def one() -> dict:
        receipt, res = sense_once(args.trace)
        if args.json:
            print(json.dumps(receipt, indent=2))
        else:
            print(human_readout(receipt, res))
        # network actions write to PRODUCTION; flagless => dry-run print
        live = args.announce
        if args.announce or (not args.announce and (args.heartbeat or args.offer)):
            print("  mesh announce:", json.dumps(mesh_announce(receipt, args.mesh_url, dry=not args.announce)))
        if args.heartbeat:
            print("  mesh heartbeat:", json.dumps(mesh_heartbeat(receipt, args.mesh_url, dry=not args.announce)))
        if args.offer:
            print("  mesh offer:", json.dumps(mesh_offer(receipt, args.mesh_url, args.offer_to, dry=not args.announce)))
        if args.peers:
            print("  mesh peers:", json.dumps(mesh_peers(args.mesh_url)))
        return receipt

    if args.watch:
        try:
            while True:
                one()
                print(f"  … resting {args.watch}s (silence is also a reading)\n")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n  nanite withdrawing — the witness closes gently.")
            return 0
    else:
        one()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
