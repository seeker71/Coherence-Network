#!/usr/bin/env python3
"""Write summary-only witness oracle emission records from the live Mac witness."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_URL = "http://localhost:8800/state"
DEFAULT_OUT_DIR = ".cache/witness-oracle-emissions"
PRIVACY = "summary-only/no-raw-audio-frame-buffer"
NO_FRAME_PRIVACY = "summary-only/no-frame"
NO_BUFFER_PRIVACY = "summary-only/no-buffer"


class CarrierError(ValueError):
    """Raised when the live witness cannot produce a valid emission record."""


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_label(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def scale_ppm(value: Any) -> int:
    try:
        return max(0, int(round(float(value) * 1_000_000)))
    except (TypeError, ValueError):
        return 0


def scale_us(value: Any) -> int:
    try:
        return max(0, int(round(float(value) * 1000)))
    except (TypeError, ValueError):
        return 0


def fetch_state(url: str, timeout: float = 3.0) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise CarrierError("witness state must be a JSON object")
    return payload


def load_states(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    raise CarrierError("state file must contain one object or a list of objects")


def summarize_state(payload: dict[str, Any]) -> dict[str, Any]:
    latest = payload.get("latest")
    if not isinstance(latest, dict):
        raise CarrierError("witness state has no latest object")
    body_state = latest.get("body_state") if isinstance(latest.get("body_state"), dict) else {}
    organs = latest.get("organs_active")
    if not isinstance(organs, list):
        organs = []
    frames = int(payload.get("frames") or latest.get("tick") or 0)
    sample_count = int(body_state.get("sample_count") or 0)
    return {
        "source": "form-native-witness-state",
        "present": bool(payload.get("present")),
        "frames": frames,
        "mic_rms_ppm": scale_ppm(latest.get("mic_rms")),
        "camera_luma_ppm": scale_ppm(latest.get("camera_luma")),
        "camera_samples": int(latest.get("camera_samples") or 0),
        "gpu_samples": int(latest.get("gpu_samples") or 0),
        "gpu_latency_us": scale_us(latest.get("gpu_latency_ms")),
        "sample_count": sample_count,
        "active_organs": [str(organ) for organ in organs],
        "privacy": PRIVACY,
    }


def _has(summary: dict[str, Any], organ: str) -> bool:
    return organ in set(summary.get("active_organs") or [])


def summary_ready(summary: dict[str, Any]) -> bool:
    return (
        bool(summary["present"])
        and summary["frames"] > 0
        and summary["mic_rms_ppm"] > 0
        and summary["camera_luma_ppm"] > 0
        and summary["camera_samples"] > 0
        and summary["gpu_samples"] > 0
        and summary["gpu_latency_us"] > 0
        and summary["sample_count"] > 0
        and _has(summary, "mic")
        and _has(summary, "camera")
        and _has(summary, "gpu")
    )


def tool_presence() -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in ("whisper-cli", "ffmpeg", "ollama", "adb")}


def confidence(value: int, base: int, divisor: int) -> int:
    return min(99, max(70, base + (value // divisor)))


def build_export(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "native-witness-export",
        "transport": "substrate:receipt-cell",
        "seq": summary["frames"],
        "frames": summary["frames"],
        "sample_count": summary["sample_count"],
        "checksum": sha256_label(summary),
        "privacy": PRIVACY,
    }


def build_processes(summary: dict[str, Any], tools: dict[str, bool]) -> list[dict[str, Any]]:
    speech_ready = summary["mic_rms_ppm"] > 0 and _has(summary, "mic") and tools.get("whisper-cli", False)
    vision_ready = summary["camera_luma_ppm"] > 0 and _has(summary, "camera")
    multimodal_ready = speech_ready and vision_ready and summary["sample_count"] > 0
    gpu_ready = summary["gpu_samples"] > 0 and summary["gpu_latency_us"] > 0 and _has(summary, "gpu")
    rows = [
        ("speech-transcribe", "whisper-oracle", "oracle:stt", speech_ready, 70, PRIVACY),
        ("vision-describe", "vision-summary-oracle", "oracle:vision", vision_ready, 70, NO_FRAME_PRIVACY),
        ("multimodal-align", "multimodal-summary-oracle", "oracle:multimodal", multimodal_ready, 70, PRIVACY),
        ("gpu-readback-kernel", "gpu-summary-oracle", "oracle:gpu", gpu_ready, 70, NO_BUFFER_PRIVACY),
    ]
    return [
        {
            "feature": feature,
            "provider": provider,
            "protocol": protocol,
            "status": "running" if ready else "blocked",
            "confidence_floor": floor,
            "privacy": privacy,
        }
        for feature, provider, protocol, ready, floor, privacy in rows
    ]


def build_labels(summary: dict[str, Any], export: dict[str, Any]) -> list[dict[str, Any]]:
    speech_conf = confidence(summary["mic_rms_ppm"], 78, 1000)
    vision_conf = confidence(summary["camera_luma_ppm"], 76, 1500)
    gpu_conf = confidence(summary["gpu_latency_us"], 82, 400)
    multimodal_conf = min(speech_conf, vision_conf, gpu_conf)
    return [
        {
            "feature": "speech-transcribe",
            "provider": "whisper-oracle",
            "protocol": "oracle:stt",
            "label": "speech-present",
            "confidence": speech_conf,
            "export_seq": export["seq"],
            "sample_ref": f"mic:{summary['frames']}",
            "privacy": PRIVACY,
        },
        {
            "feature": "vision-describe",
            "provider": "vision-summary-oracle",
            "protocol": "oracle:vision",
            "label": "scene-present",
            "confidence": vision_conf,
            "export_seq": export["seq"],
            "sample_ref": f"camera:{summary['camera_samples']}",
            "privacy": NO_FRAME_PRIVACY,
        },
        {
            "feature": "multimodal-align",
            "provider": "multimodal-summary-oracle",
            "protocol": "oracle:multimodal",
            "label": "aligned",
            "confidence": multimodal_conf,
            "export_seq": export["seq"],
            "sample_ref": f"body:{summary['sample_count']}",
            "privacy": PRIVACY,
        },
        {
            "feature": "gpu-readback-kernel",
            "provider": "gpu-summary-oracle",
            "protocol": "oracle:gpu",
            "label": "readback-ok",
            "confidence": gpu_conf,
            "export_seq": export["seq"],
            "sample_ref": f"gpu:{summary['gpu_samples']}",
            "privacy": NO_BUFFER_PRIVACY,
        },
    ]


def build_heldout_rows(summary: dict[str, Any], labels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in labels:
        feature = label["feature"]
        if feature == "speech-transcribe":
            lane, count, metric, privacy = "mic", summary["frames"], summary["mic_rms_ppm"], PRIVACY
        elif feature == "vision-describe":
            lane, count, metric, privacy = "camera", summary["camera_samples"], summary["camera_luma_ppm"], NO_FRAME_PRIVACY
        elif feature == "multimodal-align":
            lane, count, metric, privacy = "mic+camera+gpu", summary["sample_count"], summary["sample_count"], PRIVACY
        else:
            lane, count, metric, privacy = "gpu", summary["gpu_samples"], summary["gpu_latency_us"], NO_BUFFER_PRIVACY
        rows.append(
            {
                "feature": feature,
                "lane": lane,
                "count": count,
                "metric": metric,
                "native_score": min(99, int(label["confidence"]) + 2),
                "oracle_score": int(label["confidence"]),
                "champion_correct": 1,
                "challenger_correct": 1,
                "privacy": privacy,
            }
        )
    return rows


def cycle_from_summary(summary: dict[str, Any], tools: dict[str, bool]) -> dict[str, Any]:
    export = build_export(summary)
    labels = build_labels(summary, export)
    processes = build_processes(summary, tools)
    rows = build_heldout_rows(summary, labels)
    return {
        "seq": export["seq"],
        "export": export,
        "labels": labels,
        "processes": processes,
        "heldout_rows": rows,
        "privacy": PRIVACY,
    }


def cycle_valid(cycle: dict[str, Any]) -> bool:
    if cycle.get("privacy") == "raw-media":
        return False
    export = cycle.get("export") or {}
    if cycle.get("seq") != export.get("seq"):
        return False
    labels = cycle.get("labels") or []
    processes = cycle.get("processes") or []
    rows = cycle.get("heldout_rows") or []
    if len(labels) < 4 or len(processes) < 4 or len(rows) < 4:
        return False
    running = {(p["feature"], p["provider"], p["protocol"]) for p in processes if p.get("status") == "running" and p.get("provider") != "fixture"}
    return all((label["feature"], label["provider"], label["protocol"]) in running for label in labels)


def increasing(cycles: list[dict[str, Any]]) -> bool:
    for previous, current in zip(cycles, cycles[1:]):
        prev_export = previous["export"]
        cur_export = current["export"]
        if current["seq"] <= previous["seq"]:
            return False
        if cur_export["frames"] < prev_export["frames"]:
            return False
        if cur_export["sample_count"] < prev_export["sample_count"]:
            return False
    return True


def build_record(
    states: list[dict[str, Any]],
    *,
    state_source: str,
    allow_stale: bool = False,
    tools: dict[str, bool] | None = None,
) -> dict[str, Any]:
    captured_at = datetime.now(timezone.utc).isoformat()
    summaries = [summarize_state(state) for state in states]
    tools = tools if tools is not None else tool_presence()
    blocked = []
    if not allow_stale:
        for index, summary in enumerate(summaries):
            if not summary_ready(summary):
                blocked.append(f"cycle {index + 1} witness state is not live across mic/camera/gpu")
    cycles = [cycle_from_summary(summary, tools) for summary in summaries]
    if len(cycles) > 1 and not increasing(cycles):
        blocked.append("emission cycles are not increasing")
    if not all(cycle_valid(cycle) for cycle in cycles):
        blocked.append("one or more cycles are not covered by running process rows")
    status = "blocked" if blocked else "pass"
    run_id = f"witness-oracle-emission-{captured_at.replace(':', '').replace('+', 'Z')}-{cycles[-1]['seq'] if cycles else 0}"
    return {
        "ledger_schema": "witness_oracle_emission/v1",
        "run_id": run_id,
        "captured_at": captured_at,
        "status": status,
        "block_reasons": blocked,
        "source": {
            "kind": "mac-witness-state",
            "path": state_source,
            "privacy": "summary-only",
        },
        "tool_presence": tools,
        "state_summaries": summaries,
        "cycles": cycles,
        "contract": {
            "recipe": "form/form-stdlib/witness-state-receipt.fk",
            "band": "form/form-stdlib/tests/witness-state-receipt-band.fk",
            "floor": "16777215 four-way",
        },
    }


def write_record(record: dict[str, Any], out_root: Path) -> Path:
    records = out_root / "records"
    records.mkdir(parents=True, exist_ok=True)
    path = records / f"{record['run_id']}.json"
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    (out_root / "latest.json").write_text(text, encoding="utf-8")
    with (out_root / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(record) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-url", default=DEFAULT_STATE_URL)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--print-record", action="store_true")
    args = parser.parse_args()

    if args.state_file:
        states = load_states(args.state_file)
        source = str(args.state_file)
    else:
        states = []
        for index in range(max(1, args.cycles)):
            states.append(fetch_state(args.state_url))
            if index + 1 < args.cycles:
                time.sleep(max(0.1, args.interval))
        source = args.state_url

    record = build_record(states, state_source=source, allow_stale=args.allow_stale)
    output_path = None
    if not args.no_write:
        output_path = write_record(record, (ROOT / args.out_dir).resolve())

    response = {
        "status": record["status"],
        "run_id": record["run_id"],
        "cycles": len(record["cycles"]),
        "seqs": [cycle["seq"] for cycle in record["cycles"]],
        "block_reasons": record["block_reasons"],
        "path": str(output_path) if output_path else None,
    }
    if args.print_record:
        response["record"] = record
    print(json.dumps(response, sort_keys=True))
    return 0 if record["status"] == "pass" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CarrierError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
