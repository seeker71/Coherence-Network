"""Analysis — turn raw samples into silences and uptime percentages.

All the interpretation logic lives here, separate from storage and probing,
so it is trivially unit-testable with hand-crafted sample sequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pulse_app.storage import Sample, SilenceRow, Store, iso_utc


# --- tunables -------------------------------------------------------------

# How many consecutive failures before we open a silence.
SILENCE_OPEN_FAILURES = 3
# How many consecutive successes before we close an open silence.
SILENCE_CLOSE_SUCCESSES = 3
# Duration at which a "strained" silence escalates to "silent" — 5 minutes.
SILENCE_ESCALATION_SECONDS = 300


Severity = Literal["strained", "silent"]


def severity_for_duration(seconds: int) -> Severity:
    return "silent" if seconds >= SILENCE_ESCALATION_SECONDS else "strained"


# --- silence derivation ---------------------------------------------------

def reconcile_silences(store: Store, organ: str) -> None:
    """Open, escalate, or close silences for one organ based on recent samples.

    Called from the scheduler after every probe round. Only looks at the
    tail of recent samples (enough to see a run), so it's cheap.
    """
    window = max(SILENCE_OPEN_FAILURES, SILENCE_CLOSE_SUCCESSES) + 2
    recent = store.recent_samples_for_organ(organ, limit=window)
    if not recent:
        return

    ongoing = store.ongoing_silence_for_organ(organ)

    # Count the trailing run of identical ok/not-ok.
    last = recent[-1]
    run_ok = last.ok
    run_len = 0
    for s in reversed(recent):
        if s.ok == run_ok:
            run_len += 1
        else:
            break

    now_iso = iso_utc()

    if ongoing is None:
        # No silence yet — open one if we have enough consecutive failures.
        if (not run_ok) and run_len >= SILENCE_OPEN_FAILURES:
            # Start the silence at the timestamp of the first failure in the run.
            started_at = recent[-run_len].ts
            store.open_silence(organ, started_at, "strained")
        return

    # There is an ongoing silence.
    if run_ok and run_len >= SILENCE_CLOSE_SUCCESSES:
        # Close at the timestamp of the first of the closing successes.
        ended_at = recent[-run_len].ts
        store.close_silence(ongoing.id, ended_at)
        return

    # Still failing — check if it's time to escalate.
    started_dt = _parse_iso(ongoing.started_at)
    now_dt = _parse_iso(now_iso)
    duration = int((now_dt - started_dt).total_seconds())
    target = severity_for_duration(duration)
    if target != ongoing.severity and target == "silent":
        store.escalate_silence(ongoing.id, "silent")


# --- daily rollup ---------------------------------------------------------

@dataclass(frozen=True)
class DayBucket:
    date: str            # YYYY-MM-DD
    samples: int
    failures: int
    # Latency percentiles across successful samples for the day. None when
    # there were no successful samples (so None and 0 stay visually distinct).
    latency_p50_ms: int | None = None
    latency_p95_ms: int | None = None

    @property
    def status(self) -> str:
        if self.samples == 0:
            return "unknown"
        if self.failures == 0:
            return "breathing"
        # Strictly more than half the samples failed → silent.
        if self.failures * 2 > self.samples:
            return "silent"
        return "strained"


def _percentile(sorted_values: list[int], pct: float) -> int | None:
    """Nearest-rank percentile on an already-sorted list. None for empty input."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    # Nearest-rank: rank = ceil(pct/100 * N), 1-indexed
    import math
    rank = max(1, math.ceil((pct / 100.0) * len(sorted_values)))
    return sorted_values[min(rank - 1, len(sorted_values) - 1)]


def rollup_daily(samples: list[Sample], days: int, now: datetime | None = None) -> list[DayBucket]:
    """Group samples into the last `days` day-buckets ending today UTC.

    Days with no samples become DayBuckets with samples=0 and status=unknown.
    Latency percentiles (p50/p95) are computed across the successful samples
    of each day and return None for days with no successful samples.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()

    # Pre-create every bucket so the output is always length `days`.
    @dataclass
    class _Accum:
        samples: int = 0
        failures: int = 0
        ok_latencies: list[int] = field(default_factory=list)

    buckets: dict[date, _Accum] = {}
    for i in range(days):
        d = today - timedelta(days=(days - 1 - i))
        buckets[d] = _Accum()

    for s in samples:
        d = _parse_iso(s.ts).date()
        acc = buckets.get(d)
        if acc is None:
            continue
        acc.samples += 1
        if s.ok:
            if s.latency_ms is not None:
                acc.ok_latencies.append(int(s.latency_ms))
        else:
            acc.failures += 1

    out: list[DayBucket] = []
    for d in sorted(buckets.keys()):
        acc = buckets[d]
        acc.ok_latencies.sort()
        out.append(
            DayBucket(
                date=d.isoformat(),
                samples=acc.samples,
                failures=acc.failures,
                latency_p50_ms=_percentile(acc.ok_latencies, 50),
                latency_p95_ms=_percentile(acc.ok_latencies, 95),
            )
        )
    return out


def uptime_percent(samples: list[Sample]) -> float:
    """Percentage of samples that were ok, rounded to 2 decimals."""
    if not samples:
        return 0.0
    ok = sum(1 for s in samples if s.ok)
    return round(100.0 * ok / len(samples), 2)


def latency_percentiles(samples: list[Sample]) -> tuple[int | None, int | None]:
    """Return (p50_ms, p95_ms) across the successful samples, or (None, None)."""
    ok_latencies = sorted(
        int(s.latency_ms) for s in samples if s.ok and s.latency_ms is not None
    )
    return _percentile(ok_latencies, 50), _percentile(ok_latencies, 95)


# --- current status -------------------------------------------------------

def status_from_last_sample(sample: Sample | None) -> str:
    if sample is None:
        return "unknown"
    return "breathing" if sample.ok else "silent"


def overall_status(organ_statuses: list[str]) -> str:
    """Combine per-organ statuses into an overall verdict."""
    if not organ_statuses:
        return "unknown"
    if all(s == "unknown" for s in organ_statuses):
        return "unknown"
    if any(s == "silent" for s in organ_statuses):
        return "silent"
    if any(s == "strained" for s in organ_statuses):
        return "strained"
    return "breathing"


# --- helpers --------------------------------------------------------------

def _parse_iso(ts: str) -> datetime:
    # Accepts "2026-04-15T17:19:30Z" style (what iso_utc emits).
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def duration_seconds_until_now(started_at: str, now: datetime | None = None) -> int:
    if now is None:
        now = datetime.now(timezone.utc)
    return max(0, int((now - _parse_iso(started_at)).total_seconds()))


def duration_between(started_at: str, ended_at: str) -> int:
    return max(0, int((_parse_iso(ended_at) - _parse_iso(started_at)).total_seconds()))


def since_iso(days: int, now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    return iso_utc(now - timedelta(days=days))


# Convenience re-export for main/route code.
def silence_duration(row: SilenceRow, now: datetime | None = None) -> int:
    if row.ended_at is None:
        return duration_seconds_until_now(row.started_at, now)
    return duration_between(row.started_at, row.ended_at)
