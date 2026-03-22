"""Client-side push logic for federation measurement summaries (Spec 131).

Reads SlotSelector JSON measurement files, computes aggregated summaries
per (decision_point, slot_id), and POSTs them to the federation hub.
Local execution is never blocked by hub availability.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_LAST_PUSH_DIR = Path.home() / ".coherence-network"
_LAST_PUSH_PATH = _LAST_PUSH_DIR / "last_push.json"
_DEFAULT_FALLBACK_HOURS = 24


def load_last_push(path: Path | None = None) -> str | None:
    """Read the last_push_utc timestamp from disk. Returns ISO string or None."""
    p = path or _LAST_PUSH_PATH
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        return data.get("last_push_utc")
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not parse %s; treating as missing", p)
        return None


def save_last_push(ts: str, path: Path | None = None) -> None:
    """Persist the last_push_utc timestamp to disk."""
    p = path or _LAST_PUSH_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"last_push_utc": ts}))


def compute_summaries(
    store_dir: Path,
    last_push_utc: str | None,
    *,
    node_id: str = "local",
) -> list[dict]:
    """Read SlotSelector JSON files and compute aggregated summaries.

    Each file is named ``{decision_point}.json`` and contains a JSON array
    of measurement dicts with keys: slot_id, value_score, timestamp, and
    optionally error_class, duration_s.

    Only measurements with timestamp > last_push_utc are included.
    If last_push_utc is None or unparseable, defaults to 24 hours ago.
    """
    if not store_dir.is_dir():
        return []

    # Determine cutoff
    cutoff_dt: datetime | None = None
    if last_push_utc:
        try:
            cutoff_dt = datetime.fromisoformat(last_push_utc.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            cutoff_dt = None
    if cutoff_dt is None:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=_DEFAULT_FALLBACK_HOURS)

    # Group measurements by (decision_point, slot_id)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for fpath in sorted(store_dir.glob("*.json")):
        decision_point = fpath.stem
        try:
            data = json.loads(fpath.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Skipping corrupt file %s: %s", fpath, exc)
            continue
        if not isinstance(data, list):
            continue
        for m in data:
            ts_str = m.get("timestamp")
            if not ts_str:
                continue
            try:
                ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if ts_dt <= cutoff_dt:
                continue
            slot_id = m.get("slot_id")
            if not slot_id:
                continue
            groups[(decision_point, slot_id)].append(m)

    # Aggregate each group
    summaries: list[dict] = []
    for (dp, sid), measurements in groups.items():
        sample_count = len(measurements)
        successes = sum(1 for m in measurements if float(m.get("value_score", 0)) > 0.0)
        failures = sample_count - successes

        # Mean value score
        mean_vs = sum(float(m.get("value_score", 0)) for m in measurements) / sample_count

        # Mean duration (only measurements that have it)
        durations = [float(m["duration_s"]) for m in measurements if m.get("duration_s") is not None]
        mean_dur = (sum(durations) / len(durations)) if durations else None

        # Error classes
        err_counts: dict[str, int] = defaultdict(int)
        for m in measurements:
            ec = m.get("error_class")
            if ec:
                err_counts[ec] += 1

        # Period
        timestamps = []
        for m in measurements:
            ts_str = m.get("timestamp", "")
            try:
                timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
            except (ValueError, TypeError):
                pass

        if not timestamps:
            continue

        period_start = min(timestamps).isoformat()
        period_end = max(timestamps).isoformat()

        summaries.append({
            "node_id": node_id,
            "decision_point": dp,
            "slot_id": sid,
            "period_start": period_start,
            "period_end": period_end,
            "sample_count": sample_count,
            "successes": successes,
            "failures": failures,
            "mean_duration_s": mean_dur,
            "mean_value_score": round(mean_vs, 6),
            "error_classes_json": dict(err_counts),
        })

    return summaries


def push_to_hub(
    hub_url: str,
    node_id: str,
    summaries: list[dict],
    *,
    timeout: float = 30.0,
) -> bool:
    """POST summaries to the hub. Returns True on success, False otherwise.

    Never raises -- logs warnings on failure so local execution continues.
    """
    if not summaries:
        logger.info("No summaries to push.")
        return True
    url = f"{hub_url.rstrip('/')}/api/federation/nodes/{node_id}/measurements"
    payload = {"summaries": summaries}
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
        if 200 <= resp.status_code < 300:
            logger.info("Pushed %d summaries to hub: %s", len(summaries), resp.json())
            return True
        else:
            logger.warning("Hub returned %d: %s", resp.status_code, resp.text)
            return False
    except httpx.ConnectError as exc:
        logger.warning("Hub unreachable at %s: %s", url, exc)
        return False
    except Exception as exc:
        logger.warning("Push failed: %s", exc)
        return False
