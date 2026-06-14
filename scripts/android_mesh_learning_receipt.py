#!/usr/bin/env python3
"""Record a Mac + Android mesh-learning receipt from a real adb device.

This is a capability and liveness receipt, not a raw sensor recorder. It keeps
privacy-sensitive data out of durable artifacts while proving which physical
lanes can feed Form-native learning and oracle-retirement recipes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "com.coherence.sense"
ACTIVITY = f"{PACKAGE}/.MainActivity"


def run(cmd: list[str], *, timeout: int = 20, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=check,
    )


def sh(cmd: str, *, timeout: int = 20) -> str:
    proc = run(["bash", "-lc", cmd], timeout=timeout)
    return proc.stdout.strip()


def adb(serial: str, args: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", serial, *args], timeout=timeout)


def masked(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def parse_devices(raw: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for line in raw.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        row: dict[str, str] = {"serial": fields[0], "state": fields[1]}
        for field in fields[2:]:
            if ":" in field:
                key, value = field.split(":", 1)
                row[key] = value
        devices.append(row)
    return devices


def choose_device(serial: str | None) -> dict[str, str]:
    if shutil.which("adb") is None:
        raise SystemExit("FAIL: adb not found on PATH")
    raw = run(["adb", "devices", "-l"], check=True).stdout
    devices = parse_devices(raw)
    authorized = [d for d in devices if d.get("state") == "device"]
    if serial:
        matches = [d for d in authorized if d["serial"] == serial]
        if not matches:
            raise SystemExit(f"FAIL: requested adb serial is not authorized: {serial}")
        return matches[0]
    if len(authorized) != 1:
        raise SystemExit(f"FAIL: expected exactly one authorized adb device, found {len(authorized)}")
    return authorized[0]


def parse_battery(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    wanted = {
        "AC powered": "ac_powered",
        "USB powered": "usb_powered",
        "Wireless powered": "wireless_powered",
        "status": "status",
        "health": "health",
        "level": "level",
        "scale": "scale",
        "voltage": "voltage_mv",
        "temperature": "temperature_tenths_c",
        "technology": "technology",
    }
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key not in wanted:
            continue
        target = wanted[key]
        if value.lower() in {"true", "false"}:
            out[target] = value.lower() == "true"
        else:
            try:
                out[target] = int(value)
            except ValueError:
                out[target] = value
    if isinstance(out.get("level"), int) and isinstance(out.get("scale"), int) and out["scale"]:
        out["percent"] = round(100 * out["level"] / out["scale"], 2)
    if isinstance(out.get("temperature_tenths_c"), int):
        out["temperature_c"] = round(out["temperature_tenths_c"] / 10, 1)
    return out


def summarize_features(raw: str) -> dict[str, Any]:
    features = sorted(line.split(":", 1)[1].strip() for line in raw.splitlines() if ":" in line)
    probes = {
        "camera": "android.hardware.camera.any",
        "microphone": "android.hardware.microphone",
        "gps": "android.hardware.location.gps",
        "wifi": "android.hardware.wifi",
        "wifi_aware": "android.hardware.wifi.aware",
        "wifi_direct": "android.hardware.wifi.direct",
        "bluetooth_le": "android.hardware.bluetooth_le",
        "nfc": "android.hardware.nfc",
        "vulkan_compute": "android.hardware.vulkan.compute",
        "accelerometer": "android.hardware.sensor.accelerometer",
        "gyroscope": "android.hardware.sensor.gyroscope",
        "compass": "android.hardware.sensor.compass",
        "barometer": "android.hardware.sensor.barometer",
        "step_counter": "android.hardware.sensor.stepcounter",
    }
    return {
        "count": len(features),
        "present": {name: feature in features for name, feature in probes.items()},
        "vulkan_version": next((f.split("=", 1)[1] for f in features if f.startswith("android.hardware.vulkan.version=")), "unknown"),
        "vulkan_level": next((f.split("=", 1)[1] for f in features if f.startswith("android.hardware.vulkan.level=")), "unknown"),
    }


def summarize_sensors(raw: str) -> dict[str, Any]:
    names: list[str] = []
    total = 0
    match_total = re.search(r"Total\s+(\d+)\s+h/w sensors", raw)
    if match_total:
        total = int(match_total.group(1))
    for line in raw.splitlines():
        if "Sensor List" in line:
            continue
        if line.strip().startswith("Fusion States"):
            break
        match = re.match(r"0x[0-9a-fA-F]+\)\s+([^|]+?)\s+\|", line.strip())
        if match:
            names.append(match.group(1).strip())
    text = raw.lower()
    categories = {
        "accelerometer": "accelerometer" in text,
        "gyroscope": "gyroscope" in text,
        "magnetometer": "magnet" in text or "ak099" in text,
        "light": "light" in text,
        "pressure": "pressure" in text or "barometer" in text,
        "proximity": "proximity" in text,
        "rotation_vector": "rotation" in text,
        "step": "step" in text,
        "gravity": "gravity" in text,
    }
    return {"count": total or len(names), "categories": categories, "sample_names": names[:12]}


def mac_summary() -> dict[str, Any]:
    tools = ["clang", "adb", "git", "rg", "curl", "jq", "ffmpeg", "ollama", "whisper-cli"]
    witness = run(["bash", "experiments/coherence-sense-android/macos-witness-service.sh", "status"], timeout=10)
    return {
        "kind": "macos-binary",
        "arch": platform.machine(),
        "os": sh("sw_vers -productVersion 2>/dev/null || uname -r"),
        "model": sh("sysctl -n hw.model 2>/dev/null || uname -m"),
        "cpu_count": int(sh("sysctl -n hw.ncpu 2>/dev/null || getconf _NPROCESSORS_ONLN") or "0"),
        "memory_bytes": int(sh("sysctl -n hw.memsize 2>/dev/null || echo 0") or "0"),
        "tools": {tool: shutil.which(tool) is not None for tool in tools},
        "witness_service": {
            "status_checked": True,
            "running": witness.returncode == 0 and "not running" not in witness.stdout.lower(),
            "summary": (witness.stdout.strip() or witness.stderr.strip()).splitlines()[:3],
        },
    }


def android_summary(serial: str, start_app: bool) -> dict[str, Any]:
    props = {
        "model": adb(serial, ["shell", "getprop", "ro.product.model"]).stdout.strip(),
        "device": adb(serial, ["shell", "getprop", "ro.product.device"]).stdout.strip(),
        "abi": adb(serial, ["shell", "getprop", "ro.product.cpu.abi"]).stdout.strip(),
        "android_release": adb(serial, ["shell", "getprop", "ro.build.version.release"]).stdout.strip(),
        "sdk": adb(serial, ["shell", "getprop", "ro.build.version.sdk"]).stdout.strip(),
    }
    package_present = PACKAGE in adb(serial, ["shell", "pm", "list", "packages", PACKAGE]).stdout
    app_start = {"requested": start_app, "attempted": False, "ok": False, "stderr": ""}
    if start_app and package_present:
        proc = adb(serial, ["shell", "am", "start", "-n", ACTIVITY], timeout=15)
        app_start = {
            "requested": True,
            "attempted": True,
            "ok": proc.returncode == 0 and "Error" not in proc.stderr,
            "stderr": proc.stderr.strip()[:240],
        }
        time.sleep(1.0)
    pid = adb(serial, ["shell", "pidof", PACKAGE]).stdout.strip()
    return {
        "kind": "android-phone",
        "serial": masked(serial),
        "props": props,
        "battery": parse_battery(adb(serial, ["shell", "dumpsys", "battery"]).stdout),
        "features": summarize_features(adb(serial, ["shell", "pm", "list", "features"]).stdout),
        "sensors": summarize_sensors(adb(serial, ["shell", "dumpsys", "sensorservice"], timeout=30).stdout),
        "coherence_sense": {
            "package": PACKAGE,
            "installed": package_present,
            "start": app_start,
            "running": bool(pid),
            "pid_present": bool(pid),
        },
    }


def learning_routes(android: dict[str, Any], mac: dict[str, Any]) -> list[dict[str, Any]]:
    present = android["features"]["present"]
    sensors = android["sensors"]["categories"]
    app_running = android["coherence_sense"]["running"]
    native_quality = {
        "summarize": 82 if mac["tools"].get("ollama") else 65,
        "code-lower": 88 if mac["tools"].get("clang") else 55,
        "tool-select": 80,
        "speech-transcribe": 72 if present.get("microphone") and app_running else 45,
        "vision-describe": 72 if present.get("camera") and app_running else 45,
        "multimodal-align": 76 if app_running and sensors.get("accelerometer") else 50,
        "distill-retire": 85,
    }
    oracle_cost = {
        "summarize": "high-token",
        "code-lower": "high-debug-loop",
        "tool-select": "medium-token",
        "speech-transcribe": "medium-model",
        "vision-describe": "high-model",
        "multimodal-align": "high-model",
        "distill-retire": "teacher-sampling",
    }
    routes = []
    for feature, quality in native_quality.items():
        if quality >= 80:
            decision = "native-first"
        elif quality >= 70:
            decision = "native-first-sample-oracle"
        else:
            decision = "oracle-teacher-until-physical-samples"
        routes.append(
            {
                "feature": feature,
                "native_quality_floor": quality,
                "oracle_pressure": oracle_cost[feature],
                "decision": decision,
            }
        )
    return routes


def build_receipt(serial: str, start_app: bool) -> dict[str, Any]:
    android = android_summary(serial, start_app)
    mac = mac_summary()
    channels = [
        {"from": "android-phone", "to": "macos-binary", "protocol": "sensor:signal", "status": "ready-inventory"},
        {"from": "android-phone", "to": "macos-binary", "protocol": "audio:pcm16", "status": "offered-permissioned"},
        {"from": "android-phone", "to": "macos-binary", "protocol": "video:rgba-time", "status": "offered-permissioned"},
        {"from": "android-phone", "to": "macos-binary", "protocol": "gpu:compute", "status": "cataloged-vulkan"},
        {"from": "macos-binary", "to": "android-phone", "protocol": "hati.mesh:presence", "status": "ready"},
    ]
    return {
        "receipt_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "mac-android mesh learning capability receipt for native-first oracle-retirement routing",
        "privacy": "raw sensor values, location coordinates, package inventory, and adb serial are not stored",
        "android": android,
        "mac": mac,
        "channels": channels,
        "learning_routes": learning_routes(android, mac),
        "floor": {
            "physical_device_seen": True,
            "coherence_sense_installed": android["coherence_sense"]["installed"],
            "coherence_sense_running": android["coherence_sense"]["running"],
            "mac_witness_service_running": mac["witness_service"]["running"],
            "sensor_categories_ready": [
                name for name, ok in android["sensors"]["categories"].items() if ok
            ],
            "oracle_retirement_spine": [
                "llm-feature-channel-floor",
                "co-learning-stream",
                "champion-challenger",
                "colearning-retire",
                "android-mesh-learning",
            ],
        },
        "north_star": "run this receipt loop 24/7 while app and Mac witness emit samples into Form-native learners; sample third-party oracles as teachers until native candidates win per feature and category",
        "next_physical_samples": [
            "permissioned mic RMS/frame receipts",
            "permissioned camera frame receipts",
            "Vulkan/NNAPI compute sample receipts",
            "Mac witness event stream joined with Android app flow counters",
        ],
    }


def write_receipt(receipt: dict[str, Any], out_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "android-mesh-learning-summary.json"
    events = out_dir / "events.jsonl"
    summary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    events.write_text(json.dumps({"event": "receipt", **receipt}, sort_keys=True) + "\n", encoding="utf-8")
    latest = out_root / "latest.json"
    latest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="adb serial to use when several devices are authorized")
    parser.add_argument("--start-app", action="store_true", help="launch Coherence Sense before sampling")
    parser.add_argument("--loop", action="store_true", help="keep writing receipts")
    parser.add_argument("--interval", type=float, default=60.0, help="seconds between loop receipts")
    parser.add_argument("--out-dir", default=".cache/android-mesh-learning", help="receipt output root")
    args = parser.parse_args()

    out_root = (ROOT / args.out_dir).resolve()
    while True:
        device = choose_device(args.serial)
        receipt = build_receipt(device["serial"], args.start_app)
        path = write_receipt(receipt, out_root)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "summary": str(path),
                    "android_model": receipt["android"]["props"]["model"],
                    "android_abi": receipt["android"]["props"]["abi"],
                    "sense_running": receipt["android"]["coherence_sense"]["running"],
                    "routes": [row["decision"] for row in receipt["learning_routes"]],
                },
                sort_keys=True,
            )
        )
        if not args.loop:
            return 0
        time.sleep(max(args.interval, 5.0))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stdout, end="")
        print(exc.stderr, end="", file=sys.stderr)
        raise
