"""Generic multi-slot selection via Thompson Sampling.

Any decision point in the system where alternatives should be tried,
measured, and automatically ranked uses this service.

Design:
  - N slots (typically 2-3), each identified by a string key
  - Each slot has a version; when config changes, stale measurements are ignored
  - Thompson Sampling selects from the probability curve — no labels, no promotion
  - Data determines ranking; worst slot is the candidate for replacement
  - No implicit default — uniform random when no data exists

Usage:
    selector = SlotSelector("prompt_template")
    slot = selector.select(["a", "b", "c"], version_map={"a": "v1", "b": "v2", "c": "v1"})
    # ... use slot ...
    selector.record(slot, value_score=0.8, resource_cost=1.2, config_version="v1")
"""
from __future__ import annotations

import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    import msvcrt

    def _lock(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock(f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def _unlock(f):
        fcntl.flock(f, fcntl.LOCK_UN)

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path(__file__).resolve().parents[2] / "logs" / "slot_measurements"


class SlotSelector:
    """Thompson Sampling selector for a named decision point."""

    def __init__(
        self,
        decision_point: str,
        *,
        store_dir: Path | None = None,
        store_path: Path | None = None,
        task_type_filter: str | None = None,
    ):
        """
        Args:
            decision_point: Name of the decision (e.g. "prompt_template", "model", "routing_strategy")
            store_dir: Directory for measurement files. One file per decision point.
            store_path: Exact path override (used by tests and legacy callers).
            task_type_filter: Legacy compat — when multiple decision points share one store file,
                filter measurements by this task_type value.
        """
        self.decision_point = decision_point
        self._store_dir = store_dir or _DEFAULT_STORE_DIR
        self._store_path_override = store_path
        self._task_type_filter = task_type_filter

    @property
    def store_path(self) -> Path:
        if self._store_path_override:
            return self._store_path_override
        return self._store_dir / f"{self.decision_point}.json"

    # ── Measurement storage ──────────────────────────────────────────

    def _load_measurements(self, task_type_filter: str | None = None) -> list[dict]:
        """Load measurements, optionally filtering by task_type.

        task_type_filter is for backward compat when multiple decision points share a store file.
        In normal usage (each decision point has its own file), this isn't needed.
        """
        if not self.store_path.exists():
            return []
        try:
            with open(self.store_path, "r") as f:
                data = json.load(f)
            measurements = data if isinstance(data, list) else []
            if task_type_filter:
                measurements = [m for m in measurements if m.get("task_type") == task_type_filter]
            return measurements
        except (OSError, json.JSONDecodeError):
            return []

    def record(
        self,
        slot_id: str,
        value_score: float,
        resource_cost: float,
        *,
        config_version: str = "",
        task_id: str | None = None,
        raw_signals: dict | None = None,
        error_class: str | None = None,
        duration_s: float | None = None,
    ) -> dict:
        """Record an outcome measurement for a slot.

        value_score: 0.0-1.0 (higher = better outcome)
        resource_cost: >0 (tokens, time, dollars — lower = cheaper)
        config_version: must match the slot's current config version
        error_class: categorized failure reason (e.g. "cli_args", "timeout", "auth", "rate_limit")
        duration_s: wall-clock seconds for root-cause analysis
        """
        if not (0.0 <= value_score <= 1.0):
            raise ValueError(f"value_score must be in [0.0, 1.0], got {value_score}")
        if resource_cost <= 0:
            raise ValueError(f"resource_cost must be > 0, got {resource_cost}")

        self._store_dir.mkdir(parents=True, exist_ok=True)

        measurement: dict = {
            "slot_id": slot_id,
            "value_score": value_score,
            "resource_cost": resource_cost,
            "config_version": config_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error_class:
            measurement["error_class"] = error_class
        if duration_s is not None:
            measurement["duration_s"] = duration_s
        # Store task_type for backward compat (legacy callers filter on it)
        if self._task_type_filter:
            measurement["task_type"] = self._task_type_filter
        if task_id is not None:
            measurement["task_id"] = task_id
        if raw_signals is not None:
            measurement["raw_signals"] = raw_signals

        with open(self.store_path, "a+" if self.store_path.exists() else "w+") as f:
            _lock(f)
            try:
                f.seek(0)
                content = f.read().strip()
                measurements: list[dict] = json.loads(content) if content else []
                measurements.append(measurement)
                f.seek(0)
                f.truncate()
                json.dump(measurements, f, indent=2)
            finally:
                _unlock(f)

        return measurement

    # ── Version filtering ────────────────────────────────────────────

    @staticmethod
    def _filter_by_version(
        measurements: list[dict],
        version_map: dict[str, str] | None,
    ) -> list[dict]:
        """Keep only measurements whose config_version matches the current version.

        - If version_map is None: all measurements kept (no version tracking)
        - If a slot has no entry in version_map: all its measurements kept
        - If a slot has a version but the measurement doesn't match: dropped (stale)
        """
        if not version_map:
            return measurements
        result = []
        for m in measurements:
            sid = m.get("slot_id", "")
            current_version = version_map.get(sid, "")
            if not current_version:
                result.append(m)
            elif m.get("config_version", "") == current_version:
                result.append(m)
        return result

    # ── Thompson Sampling ────────────────────────────────────────────

    @staticmethod
    def _is_blocked(records: list[dict], cooldown_hours: float = 1.0) -> bool:
        """A slot is blocked if its last 3 measurements are all failures.

        But blocking is temporary — after cooldown_hours, the slot gets a
        probe attempt (small weight) to see if the issue was fixed.
        """
        n = len(records)
        if n < 3:
            return False

        # Check last 3 (not first 3) — recent failures matter more
        last_three = records[-3:]
        if not all(r["value_score"] == 0.0 for r in last_three):
            return False

        # Blocked, but check cooldown
        last_ts = records[-1].get("timestamp", "")
        if last_ts:
            try:
                last_time = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
                if elapsed >= cooldown_hours:
                    return False  # cooldown expired, allow probe
            except (ValueError, TypeError):
                pass

        return True

    @staticmethod
    def _compute_weights(
        slots: list[str],
        slot_data: dict[str, list[dict]],
        *,
        recency_window: int = 5,
        recency_weight: float = 0.6,
    ) -> dict[str, float]:
        """Compute Thompson Sampling samples using Beta distribution with recency bias.

        Every slot uses Beta(alpha, beta). Recent performance (last N runs)
        is weighted more heavily than historical, so the system reacts quickly
        to provider improvements or degradation.

        Weight formula: recency_weight * last_N_rate + (1 - recency_weight) * all_time_rate
        This blended rate feeds into the Beta distribution parameters.

        - 0 samples: uniform random (fair exploration)
        - 2/2 recent successes: high draw, quickly favored
        - Recent failures after historical success: draw drops fast
        - Blocked slots (last 3 all failures): tiny random probe weight [0.01, 0.02]
        """
        weights: dict[str, float] = {}
        for sid in slots:
            records = slot_data.get(sid, [])
            n = len(records)

            if SlotSelector._is_blocked(records):
                # Tiny random probe weight to ensure variety when multiple slots are blocked
                weights[sid] = 0.01 + random.random() * 0.01
                continue

            if n == 0:
                # No data — uniform prior
                weights[sid] = random.betavariate(1.0, 1.0)
                continue

            # All-time rate
            all_time_value = sum(r["value_score"] for r in records)
            all_time_rate = all_time_value / n

            # Recent rate (last recency_window runs)
            recent = records[-recency_window:]
            recent_value = sum(r["value_score"] for r in recent)
            recent_rate = recent_value / len(recent)

            # Blend: recent data matters more than historical
            blended_rate = recency_weight * recent_rate + (1 - recency_weight) * all_time_rate

            # Convert blended rate to Beta parameters scaled by sample count
            # Use effective_n to control distribution width (more data = tighter)
            effective_n = min(n, 20)  # cap to prevent over-concentration
            alpha = 1.0 + blended_rate * effective_n
            beta_param = 1.0 + (1 - blended_rate) * effective_n
            weights[sid] = random.betavariate(alpha, beta_param)

        return weights

    def select(
        self,
        available_slots: list[str],
        *,
        version_map: dict[str, str] | None = None,
    ) -> str | None:
        """Select a slot using Thompson Sampling.

        Returns a slot ID from available_slots. Uniform random when no
        measurements exist. Uses argmax of Beta samples for selection.
        """
        if not available_slots:
            raise ValueError("available_slots/available_variants must not be empty")

        measurements = self._load_measurements(self._task_type_filter)
        measurements = self._filter_by_version(measurements, version_map)

        # Group by slot_id
        slot_data: dict[str, list[dict]] = {}
        for m in measurements:
            sid = m.get("slot_id", "")
            slot_data.setdefault(sid, []).append(m)

        # No data for any available slot — uniform random
        if not any(s in slot_data for s in available_slots):
            return random.choice(available_slots)

        weights = self._compute_weights(available_slots, slot_data)

        # Standard Thompson Sampling: pick the slot with the highest sample
        return max(weights, key=weights.get)

    # ── Stats & slot management ──────────────────────────────────────

    def stats(
        self,
        available_slots: list[str] | None = None,
        *,
        version_map: dict[str, str] | None = None,
    ) -> dict:
        """Per-slot statistics with selection probabilities."""
        measurements = self._load_measurements(self._task_type_filter)
        measurements = self._filter_by_version(measurements, version_map)

        slot_data: dict[str, list[dict]] = {}
        for m in measurements:
            sid = m.get("slot_id", "")
            slot_data.setdefault(sid, []).append(m)

        slots_to_report = available_slots or list(slot_data.keys())
        slots: dict[str, dict] = {}
        blocked_count = 0

        for sid in slots_to_report:
            records = slot_data.get(sid, [])
            n = len(records)
            successes = sum(1 for r in records if r["value_score"] > 0)
            failures = n - successes
            total_value = sum(r["value_score"] for r in records)
            total_cost = sum(r["resource_cost"] for r in records)
            mean_value = total_value / n if n > 0 else 0.0
            mean_cost = total_cost / n if n > 0 else 0.0
            roi = total_value / total_cost if total_cost > 0 else 0.0

            blocked = self._is_blocked(records)
            if blocked:
                blocked_count += 1

            # Error class breakdown
            error_classes: dict[str, int] = {}
            for r in records:
                ec = r.get("error_class")
                if ec:
                    error_classes[ec] = error_classes.get(ec, 0) + 1

            # Duration stats
            durations = [r["duration_s"] for r in records if "duration_s" in r]
            mean_duration = sum(durations) / len(durations) if durations else 0.0
            max_duration = max(durations) if durations else 0.0
            p90_duration = sorted(durations)[int(len(durations) * 0.9)] if durations else 0.0

            # Last N stats for recency awareness
            last_5 = records[-5:]
            last_5_successes = sum(1 for r in last_5 if r["value_score"] > 0)
            last_5_rate = last_5_successes / len(last_5) if last_5 else 0.0

            # Data-driven timeout: 2.5x p90 with floor of 60s, cap at 600s
            if p90_duration > 0:
                suggested_timeout = max(60.0, min(600.0, p90_duration * 2.5))
            else:
                suggested_timeout = 300.0  # default when no data

            slots[sid] = {
                "sample_count": n,
                "successes": successes,
                "failures": failures,
                "mean_value": round(mean_value, 4),
                "mean_cost": round(mean_cost, 4),
                "mean_duration_s": round(mean_duration, 1),
                "max_duration_s": round(max_duration, 1),
                "p90_duration_s": round(p90_duration, 1),
                "suggested_timeout_s": round(suggested_timeout, 0),
                "last_5_rate": round(last_5_rate, 4),
                "last_5_count": len(last_5),
                "roi": round(roi, 4),
                "blocked": blocked,
                "error_classes": error_classes,
                "selection_probability": 0.0,
            }

        # Compute selection probabilities (all slots, including blocked with probe weight)
        weights = self._compute_weights(slots_to_report, slot_data)
        total_weight = sum(weights.values())
        if total_weight > 0:
            for sid in weights:
                if sid in slots:
                    slots[sid]["selection_probability"] = round(
                        weights[sid] / total_weight, 4
                    )

        active = [s for s in slots_to_report if not slots.get(s, {}).get("blocked")]

        # Surface blind spots — undiagnosable failures that need priority attention
        blind_spots = []
        for sid in slots_to_report:
            slot_info = slots.get(sid, {})
            errors = slot_info.get("error_classes", {})
            blind_count = errors.get("blind_timeout", 0) + errors.get("empty_output", 0)
            if blind_count > 0:
                blind_spots.append({
                    "slot": sid,
                    "blind_failures": blind_count,
                    "total_failures": slot_info.get("failures", 0),
                    "priority": "HIGH" if blind_count >= 2 else "MEDIUM",
                    "action": "Root-cause needed: these failures cost compute but produce zero diagnostic value",
                })

        return {
            "decision_point": self.decision_point,
            "slots": slots,
            "total_measurements": len(measurements),
            "active_slots": len(active),
            "blocked_slots": blocked_count,
            "blind_spots": blind_spots,
        }

    def weakest_slot(
        self,
        available_slots: list[str],
        all_possible_slots: list[str],
        *,
        version_map: dict[str, str] | None = None,
    ) -> str:
        """Return the best slot to replace with a new candidate.

        If there are empty slots (in all_possible_slots but not available), returns one.
        Otherwise returns the slot with the lowest selection probability.
        """
        empty = [s for s in all_possible_slots if s not in available_slots]
        if empty:
            return empty[0]

        st = self.stats(available_slots, version_map=version_map)
        slot_stats = st.get("slots", {})
        return min(
            available_slots,
            key=lambda s: slot_stats.get(s, {}).get("selection_probability", 0.0),
        )
