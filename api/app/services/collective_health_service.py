"""Collective health: coherence, resonance, flow, and friction from live task/metrics/friction data."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.services import friction_service, metrics_service
from app.services.friction_service import FrictionEvent, _severity_rank

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 7


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _balance_spread(by_task_type: dict[str, Any]) -> float:
    """How evenly work completes across spec/impl/test/review (0–1). Degrades gracefully when sparse."""
    pillars = ("spec", "impl", "test", "review")
    comps = [int((by_task_type.get(p) or {}).get("completed") or 0) for p in pillars]
    if sum(comps) == 0:
        return 0.5
    mn = min(comps)
    mx = max(comps)
    if mx <= 0:
        return 0.5
    return _clamp01((mn + 1) / (mx + 1))


def _coherence_score(rate: float, balance: float) -> float:
    return round(0.5 * rate + 0.5 * math.sqrt(balance), 4)


def _resonance_score(rate: float, issues_open: int) -> float:
    issue_damp = 1.0 - min(1.0, issues_open * 0.12)
    return round(0.5 * rate + 0.5 * issue_damp, 4)


def _flow_score(completed_7d: int, window_days: int, p95_seconds: float) -> float:
    tpd = completed_7d / max(1, window_days)
    throughput_factor = min(1.0, tpd / 5.0)
    latency_factor = 1.0 / (1.0 + max(0.0, float(p95_seconds)) / 1800.0)
    return round(0.6 * throughput_factor + 0.4 * latency_factor, 4)


def _friction_score(open_events: int, total_energy_loss: float) -> float:
    if open_events <= 0 and total_energy_loss <= 0:
        return 0.12
    open_norm = min(1.0, open_events / 8.0)
    energy_norm = min(1.0, max(0.0, total_energy_loss) / 20.0)
    return round(0.45 * open_norm + 0.55 * energy_norm, 4)


def _open_friction_events(events: list[FrictionEvent], window_days: int) -> list[FrictionEvent]:
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=max(1, window_days))
    return [e for e in events if e.timestamp >= since and e.status == "open"]


def _friction_queue(open_events: list[FrictionEvent], *, limit: int = 12) -> list[dict[str, Any]]:
    def sort_key(e: FrictionEvent) -> float:
        return float(e.energy_loss_estimate) * (1.0 + 0.25 * float(_severity_rank(e.severity)))

    rows: list[dict[str, Any]] = []
    for e in sorted(open_events, key=sort_key, reverse=True)[:limit]:
        sig = _clamp01((e.energy_loss_estimate / 10.0) * (1.0 + 0.2 * float(_severity_rank(e.severity))))
        title = (e.unblock_condition or e.block_type or "friction").strip()
        rows.append(
            {
                "key": f"{e.block_type}:{e.id}",
                "title": title[:240],
                "severity": e.severity,
                "signal": round(sig, 4),
            }
        )
    return rows


def _opportunities(
    *,
    coherence: float,
    resonance: float,
    flow: float,
    friction: float,
    balance: float,
    issues_open: int,
    p95_seconds: float,
    open_friction: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if balance < 0.55:
        out.append(
            {
                "pillar": "coherence",
                "signal": "balance_spec_impl_test_review",
                "impact_estimate": round(max(0.0, 0.65 - coherence), 4),
            }
        )
    if issues_open >= 2 or resonance < 0.55:
        out.append(
            {
                "pillar": "resonance",
                "signal": "reduce_open_monitor_issues",
                "impact_estimate": round(min(1.0, 0.08 * issues_open), 4),
            }
        )
    if p95_seconds > 900:
        out.append(
            {
                "pillar": "flow",
                "signal": "reduce_p95_execution_latency",
                "impact_estimate": round(min(1.0, min(1.0, p95_seconds / 7200.0)), 4),
            }
        )
    if open_friction >= 1 or friction > 0.35:
        out.append(
            {
                "pillar": "friction",
                "signal": "clear_open_friction_events",
                "impact_estimate": round(friction, 4),
            }
        )
    if not out:
        out.append(
            {
                "pillar": "collective",
                "signal": "maintain_current_operating_posture",
                "impact_estimate": 0.05,
            }
        )
    return out[:12]


def build_collective_health(*, window_days: int | None = None) -> dict[str, Any]:
    """Aggregate coherence, resonance, flow, friction, and collective_value from operational telemetry."""
    days = window_days if window_days is not None and 1 <= int(window_days) <= 90 else DEFAULT_WINDOW_DAYS
    try:
        aggregates = metrics_service.get_aggregates(days)
    except Exception:
        logger.warning("collective_health: metrics aggregates failed", exc_info=True)
        aggregates = {
            "success_rate": {"completed": 0, "failed": 0, "total": 0, "rate": 0.0},
            "execution_time": {"p50_seconds": 0, "p95_seconds": 0},
            "by_task_type": {},
        }

    sr = aggregates.get("success_rate") or {}
    completed = int(sr.get("completed") or 0)
    failed = int(sr.get("failed") or 0)
    total_m = completed + failed
    rate = float(sr.get("rate") or (completed / total_m if total_m > 0 else 0.0))

    by_tt = aggregates.get("by_task_type") or {}
    balance = _balance_spread(by_tt)

    exec_t = aggregates.get("execution_time") or {}
    p95 = int(exec_t.get("p95_seconds") or 0)

    coh = _coherence_score(rate, balance)
    monitor = friction_service._load_monitor_issues()
    issues = monitor.get("issues") if isinstance(monitor, dict) else []
    issues_open = len(issues) if isinstance(issues, list) else 0
    res = _resonance_score(rate, issues_open)
    fl = _flow_score(completed, days, float(p95))

    try:
        events, _ignored = friction_service.load_events()
    except Exception:
        logger.warning("collective_health: friction load_events failed", exc_info=True)
        events = []

    summ = friction_service.summarize(events, days)
    open_ct = int(summ.get("open_events") or 0)
    energy = float(summ.get("total_energy_loss") or 0.0)
    fric = _friction_score(open_ct, energy)

    coh = _clamp01(coh)
    res = _clamp01(res)
    fl = _clamp01(fl)
    fric = _clamp01(fric)

    collective_value = round(coh * res * fl * (1.0 - fric), 4)

    open_evts = _open_friction_events(events, days)
    top_q = _friction_queue(open_evts)
    tops = _opportunities(
        coherence=coh,
        resonance=res,
        flow=fl,
        friction=fric,
        balance=balance,
        issues_open=issues_open,
        p95_seconds=float(p95),
        open_friction=open_ct,
    )

    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "generated_at": generated,
        "window_days": days,
        "scores": {
            "coherence": coh,
            "resonance": res,
            "flow": fl,
            "friction": fric,
            "collective_value": collective_value,
        },
        "coherence": {
            "task_count": total_m,
            "success_rate": rate,
            "balance_spread": round(balance, 4),
            "by_task_type_completed": {
                k: int((by_tt.get(k) or {}).get("completed") or 0) for k in ("spec", "impl", "test", "review", "heal")
            },
        },
        "resonance": {
            "issues_open": issues_open,
            "success_rate_component": rate,
            "monitor_issues_path": str(friction_service.monitor_issues_file_path()),
        },
        "flow": {
            "completed_7d": completed,
            "tasks_per_day": round(completed / max(1, days), 4),
            "p95_seconds": p95,
            "p50_seconds": int((exec_t.get("p50_seconds") or 0)),
        },
        "friction": {
            "open_events": open_ct,
            "total_energy_loss": energy,
            "window_total_events": int(summ.get("total_events") or 0),
            "top_block_types": (summ.get("top_block_types") or [])[:8],
        },
        "top_friction_queue": top_q,
        "top_opportunities": tops,
    }
