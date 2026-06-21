#!/usr/bin/env python3
"""Mac host as a self-registering, self-sensing Hati mesh organ.

The Android phone (`MainActivity.kt`) is the reference: it senses its native organs,
announces itself to the cloud Hati mesh, and heartbeats live flow. This is the macOS
twin — a carrier-last host-glue daemon that reads everything the Mac can sense
(cpu/ram/disk/io/network/gpu/thermal/battery + mic/camera/screen summaries), announces
itself to the cloud mesh as a `host-kernel` organ, heartbeats its live flow, and writes a
full local sense receipt other peers and the Form world-model recipes can read.

The body — recognition, world-growth, voice-traits, perception — lives in Form recipes
(`form/form-stdlib/world-model-live-sense.fk`, `perception-pipeline.fk`, `voice-traits.fk`).
This script does not re-implement that logic; it senses the host and feeds the body.

Privacy floor (same as Android): summaries only. Mic → RMS amplitude. Camera/screen → mean
luma. No raw audio, frames, or screenshots are stored or transmitted.

Run:    python3 mac-sense-organ.py [--mesh URL] [--witness URL] [--interval S] [--no-media] [--once]
Install: macos-sense-organ-service.sh install
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
IDENTITY_DIR = HOME / ".coherence-network" / "hati"
IDENTITY_FILE = IDENTITY_DIR / "macos-organ-id"
RECEIPT_LATEST = IDENTITY_DIR / "mac-sense-latest.json"
RECEIPT_LOG = IDENTITY_DIR / "mac-sense-receipts.jsonl"

DEFAULT_MESH = "https://api.coherencycoin.com/api"
DEFAULT_WITNESS = "http://127.0.0.1:8800"

CAPABILITIES = [
    "cap.host.vitals",
    "cap.compute.cpu",
    "cap.compute.gpu",
    "cap.sensor.read",
    "cap.audio.sample",
    "cap.video.frame",
    "cap.screen.read",
    "cap.network.presence",
    "cap.mesh.presence",
    "cap.app.update",
]
LANES = [
    "cpu", "ram", "disk", "io", "network",
    "gpu", "thermal", "battery", "mic", "camera", "screen",
]


def _run(cmd: list[str], timeout: float = 4.0) -> str:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return (out.stdout or "") + (out.stderr or "")
    except Exception:
        return ""


def stable_organ_id() -> str:
    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    if IDENTITY_FILE.exists():
        existing = IDENTITY_FILE.read_text().strip()
        if existing:
            return existing
    organ_id = f"hati-organ-macos-{uuid.uuid4().hex[:24]}"
    IDENTITY_FILE.write_text(organ_id + "\n")
    return organ_id


# ── host vitals (cheap, no permission) ─────────────────────────────────────

def cpu_reading() -> dict:
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0
    cores = os.cpu_count() or 1
    # load relative to core count, clamped to [0,1] → ppm
    rel = min(max(load1 / cores, 0.0), 1.0)
    return {
        "cpu_count": cores,
        "cpu_load1": round(load1, 3),
        "cpu_load5": round(load5, 3),
        "cpu_load_ppm": int(rel * 1_000_000),
    }


def ram_reading() -> dict:
    page_size = 4096
    free = active = inactive = wired = compressed = speculative = 0
    text = _run(["vm_stat"])
    for line in text.splitlines():
        m = re.search(r"page size of (\d+) bytes", line)
        if m:
            page_size = int(m.group(1))
        m = re.match(r"Pages free:\s+(\d+)", line)
        if m:
            free = int(m.group(1))
        m = re.match(r"Pages active:\s+(\d+)", line)
        if m:
            active = int(m.group(1))
        m = re.match(r"Pages inactive:\s+(\d+)", line)
        if m:
            inactive = int(m.group(1))
        m = re.match(r"Pages wired down:\s+(\d+)", line)
        if m:
            wired = int(m.group(1))
        m = re.match(r"Pages occupied by compressor:\s+(\d+)", line)
        if m:
            compressed = int(m.group(1))
        m = re.match(r"Pages speculative:\s+(\d+)", line)
        if m:
            speculative = int(m.group(1))
    total_bytes = 0
    out = _run(["sysctl", "-n", "hw.memsize"]).strip()
    if out.isdigit():
        total_bytes = int(out)
    used_bytes = (active + wired + compressed) * page_size
    used_ppm = int(min(used_bytes / total_bytes, 1.0) * 1_000_000) if total_bytes else 0
    return {
        "ram_total_bytes": total_bytes,
        "ram_used_bytes": used_bytes,
        "ram_used_ppm": used_ppm,
    }


def disk_reading() -> dict:
    try:
        import shutil
        usage = shutil.disk_usage("/")
        used_ppm = int(min(usage.used / usage.total, 1.0) * 1_000_000) if usage.total else 0
        return {
            "disk_total_bytes": usage.total,
            "disk_used_bytes": usage.used,
            "disk_used_ppm": used_ppm,
        }
    except Exception:
        return {"disk_total_bytes": 0, "disk_used_bytes": 0, "disk_used_ppm": 0}


def net_counters() -> tuple[int, int]:
    """Sum non-loopback interface rx/tx bytes from netstat -ib."""
    rx = tx = 0
    text = _run(["netstat", "-ib"])
    seen: set[str] = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 11 or parts[0] == "Name" or parts[0].startswith("lo"):
            continue
        iface = parts[0]
        if iface in seen:
            continue
        # netstat -ib columns vary; rx bytes and tx bytes are the large numerics
        nums = [p for p in parts if p.isdigit()]
        if len(nums) >= 2:
            try:
                rx += int(nums[-5]) if len(nums) >= 5 else 0
                tx += int(nums[-2]) if len(nums) >= 2 else 0
                seen.add(iface)
            except (ValueError, IndexError):
                continue
    return rx, tx


def gpu_static() -> dict:
    """GPU identity (slow; cached by caller)."""
    name = ""
    cores = 0
    text = _run(["system_profiler", "SPDisplaysDataType"], timeout=8.0)
    for line in text.splitlines():
        m = re.search(r"Chipset Model:\s*(.+)", line)
        if m:
            name = m.group(1).strip()
        m = re.search(r"Total Number of Cores:\s*(\d+)", line)
        if m:
            cores = int(m.group(1))
    return {"gpu_name": name or "apple-gpu", "gpu_cores": cores}


def gpu_util_ppm() -> int | None:
    """Best-effort GPU utilization without sudo (ioreg PerformanceStatistics)."""
    text = _run(["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"])
    m = re.search(r'"Device Utilization %"\s*=\s*(\d+)', text)
    if m:
        return int(min(int(m.group(1)) / 100.0, 1.0) * 1_000_000)
    return None


def thermal_reading() -> str:
    text = _run(["pmset", "-g", "therm"])
    if "CPU_Speed_Limit" in text:
        m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", text)
        if m and int(m.group(1)) < 100:
            return f"throttled-{m.group(1)}pct"
    if "No thermal warning level" in text or text.strip() == "":
        return "nominal"
    return "nominal"


def battery_reading() -> dict:
    text = _run(["pmset", "-g", "batt"])
    pct = 0
    charging = False
    m = re.search(r"(\d+)%", text)
    if m:
        pct = int(m.group(1))
    charging = ("charging" in text) and ("discharging" not in text)
    return {"battery_ppm": pct * 10_000, "battery_charging": charging}


def uptime_reading() -> int:
    out = _run(["sysctl", "-n", "kern.boottime"])
    m = re.search(r"sec\s*=\s*(\d+)", out)
    if m:
        return int(time.time()) - int(m.group(1))
    return 0


# ── media senses (summary-only, need TCC grants) ───────────────────────────

def mic_rms() -> dict:
    """Record a short mic sample, return RMS amplitude only. Never stores audio."""
    if not _which("sox") and not _which("rec"):
        return {"mic_status": "unavailable", "mic_rms": 0.0}
    tmp = f"/tmp/hati-mic-{os.getpid()}.wav"
    rec = _which("rec") or _which("sox")
    try:
        if _which("rec"):
            _run(["rec", "-q", "-c", "1", "-r", "16000", tmp, "trim", "0", "0.6"], timeout=6.0)
        else:
            return {"mic_status": "needs-rec", "mic_rms": 0.0}
        stat = _run(["sox", tmp, "-n", "stat"], timeout=6.0)
        m = re.search(r"RMS\s+amplitude:\s*([0-9.]+)", stat)
        if m:
            return {"mic_status": "ok", "mic_rms": float(m.group(1))}
        # produced no stats → likely TCC-denied (silent/zero file)
        return {"mic_status": "denied?", "mic_rms": 0.0}
    except Exception as e:  # noqa: BLE001
        return {"mic_status": f"error:{type(e).__name__}", "mic_rms": 0.0}
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _yavg_from_signalstats(src_args: list[str]) -> float | None:
    text = _run(
        ["ffmpeg", "-hide_banner", *src_args, "-frames:v", "1",
         "-vf", "signalstats,metadata=print", "-f", "null", "-"],
        timeout=8.0,
    )
    m = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", text)
    if m:
        return round(float(m.group(1)) / 255.0, 5)
    return None


def camera_luma() -> dict:
    if not _which("ffmpeg"):
        return {"camera_status": "unavailable", "camera_luma": 0.0}
    y = _yavg_from_signalstats(["-f", "avfoundation", "-i", "0:none"])
    if y is None:
        return {"camera_status": "denied?", "camera_luma": 0.0}
    return {"camera_status": "ok", "camera_luma": y}


def screen_luma() -> dict:
    if not _which("screencapture") or not _which("ffmpeg"):
        return {"screen_status": "unavailable", "screen_luma": 0.0}
    tmp = f"/tmp/hati-screen-{os.getpid()}.jpg"
    try:
        _run(["screencapture", "-x", "-t", "jpg", tmp], timeout=6.0)
        if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
            return {"screen_status": "denied?", "screen_luma": 0.0}
        y = _yavg_from_signalstats(["-i", tmp])
        if y is None:
            return {"screen_status": "decode-fail", "screen_luma": 0.0}
        return {"screen_status": "ok", "screen_luma": y}
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


# ── mesh + witness carriers ────────────────────────────────────────────────

def _post(url: str, payload: dict, timeout: float = 6.0) -> tuple[int, str]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "coherence-sense-mac/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(2000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def announce(mesh: str, organ_id: str, host: str, snap: dict, gpu: dict) -> tuple[int, str]:
    active = snap.get("organs_active", [])
    payload = {
        "organ_id": organ_id,
        "organ_kind": "host-kernel",
        "app": "coherence-sense-mac",
        "app_version": "0.1",
        "target": "macos-arm64",
        "display_name": host,
        "dwelling_name": host,
        "discovery_state": "streaming",
        "trust_score_ppm": 820_000,
        "signal_strength_ppm": snap.get("signal_strength_ppm", 0),
        "battery_level_ppm": snap.get("battery_ppm", 0),
        "power_cost_ppm": snap.get("power_cost_ppm", 0),
        "capabilities": CAPABILITIES,
        "lanes": [l for l in LANES if l in active] or LANES,
    }
    return _post(f"{mesh}/hati/mesh/organs/announce", payload)


def heartbeat(mesh: str, organ_id: str, snap: dict) -> tuple[int, str]:
    payload = {
        "organ_id": organ_id,
        "listening": True,
        "active_channels": snap.get("organs_active", []),
        "sample_rate_hz": 1.0,
        "bytes_per_second": float(snap.get("net_tx_bps", 0) + snap.get("net_rx_bps", 0)),
        "discovery_state": "streaming",
        "trust_score_ppm": 820_000,
        "signal_strength_ppm": snap.get("signal_strength_ppm", 0),
        "battery_level_ppm": snap.get("battery_ppm", 0),
        "power_cost_ppm": snap.get("power_cost_ppm", 0),
    }
    return _post(f"{mesh}/hati/mesh/organs/heartbeat", payload)


# ── main loop ──────────────────────────────────────────────────────────────

def sense(prev_net: tuple[int, int] | None, dt: float, gpu_cache: dict,
          do_media: bool) -> tuple[dict, tuple[int, int]]:
    snap: dict = {}
    snap.update(cpu_reading())
    snap.update(ram_reading())
    snap.update(disk_reading())
    snap.update(battery_reading())
    snap["thermal_pressure"] = thermal_reading()
    snap["uptime_s"] = uptime_reading()

    rx, tx = net_counters()
    if prev_net and dt > 0:
        snap["net_rx_bps"] = max(int((rx - prev_net[0]) / dt), 0)
        snap["net_tx_bps"] = max(int((tx - prev_net[1]) / dt), 0)
    else:
        snap["net_rx_bps"] = 0
        snap["net_tx_bps"] = 0

    snap.update(gpu_cache)
    util = gpu_util_ppm()
    snap["gpu_util_ppm"] = util
    snap["gpu_present"] = True

    organs = ["cpu", "ram", "disk", "network", "gpu", "thermal", "battery"]
    channels = ["network", "mesh"]

    if do_media:
        m = mic_rms()
        snap.update(m)
        if m.get("mic_status") == "ok":
            organs.append("mic")
            channels.append("audio")
        c = camera_luma()
        snap.update(c)
        if c.get("camera_status") == "ok":
            organs.append("camera")
            channels.append("video")
        s = screen_luma()
        snap.update(s)
        if s.get("screen_status") == "ok":
            organs.append("screen")
            channels.append("screen")

    snap["organs_active"] = organs
    snap["channels_offered"] = channels
    snap["privacy"] = "summary-only"

    # derived mesh metrics
    cpu_ppm = snap.get("cpu_load_ppm", 0)
    gpu_ppm = util or 0
    snap["power_cost_ppm"] = int(min((cpu_ppm + gpu_ppm) / 2, 1_000_000))
    # signal = liveness proxy: net throughput + mic activity
    net_total = snap.get("net_rx_bps", 0) + snap.get("net_tx_bps", 0)
    snap["signal_strength_ppm"] = int(min(net_total / 1_000_000 * 1_000_000, 1_000_000))
    return snap, (rx, tx)


def write_receipt(organ_id: str, host: str, snap: dict) -> None:
    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    record = {"organ_id": organ_id, "organ_kind": "host-kernel",
              "target": "macos-arm64", "host": host, "ts": round(time.time(), 2), **snap}
    RECEIPT_LATEST.write_text(json.dumps(record, indent=2))
    with RECEIPT_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default=os.environ.get("HATI_MESH", DEFAULT_MESH))
    ap.add_argument("--witness", default=os.environ.get("HATI_WITNESS", DEFAULT_WITNESS))
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--media-every", type=int, default=4,
                    help="capture mic/camera/screen every N ticks")
    ap.add_argument("--no-media", action="store_true", help="host vitals only")
    ap.add_argument("--once", action="store_true", help="one tick, print, exit")
    args = ap.parse_args()

    organ_id = stable_organ_id()
    host = socket.gethostname().split(".")[0]
    gpu_cache = gpu_static()
    print(f"[mac-sense] organ={organ_id} host={host} gpu={gpu_cache.get('gpu_name')} "
          f"mesh={args.mesh} media={'off' if args.no_media else 'on'}", flush=True)

    prev_net: tuple[int, int] | None = None
    last_t = time.time()
    tick = 0
    announced = False
    while True:
        now = time.time()
        dt = now - last_t
        last_t = now
        do_media = (not args.no_media) and (args.once or tick % args.media_every == 0)
        snap, prev_net = sense(prev_net, dt, gpu_cache, do_media)
        snap["tick"] = tick
        write_receipt(organ_id, host, snap)

        if not announced or tick % 12 == 0:
            ac, ar = announce(args.mesh, organ_id, host, snap, gpu_cache)
            announced = ac in (200, 201)
            print(f"[mac-sense] announce -> {ac}", flush=True)
        hc, hr = heartbeat(args.mesh, organ_id, snap)

        if args.once:
            print(json.dumps(snap, indent=2))
            print(f"[mac-sense] heartbeat -> {hc}")
            return 0

        if tick % 6 == 0:
            print(f"[mac-sense] tick={tick} cpu={snap['cpu_load_ppm']/10000:.1f}% "
                  f"ram={snap['ram_used_ppm']/10000:.1f}% gpu_util={snap.get('gpu_util_ppm')} "
                  f"net={snap['net_rx_bps']}/{snap['net_tx_bps']}B/s "
                  f"mic={snap.get('mic_status','-')} cam={snap.get('camera_status','-')} "
                  f"scr={snap.get('screen_status','-')} hb={hc}", flush=True)
        tick += 1
        time.sleep(max(args.interval - (time.time() - now), 0.1))


if __name__ == "__main__":
    sys.exit(main())
