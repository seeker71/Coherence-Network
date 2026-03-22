"""Coherence signal depth — real-time computed coherence score.

Replaces placeholder coherence scores with scores derived from actual data:
  - Task completion rate (idea portfolio: validated / total)
  - Spec coverage (specs with implementation / total specs)
  - Contribution activity (recent commit evidence density)
  - Runtime health (API success rate from runtime events)
  - Value realization (actual value captured / potential value)

Each signal is normalized to 0.0-1.0 and weighted to produce an aggregate score.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("coherence.signal_depth")

# Signal weights — sum to 1.0
SIGNAL_WEIGHTS: dict[str, float] = {
    "task_completion": 0.25,
    "spec_coverage": 0.20,
    "contribution_activity": 0.20,
    "runtime_health": 0.15,
    "value_realization": 0.20,
}

# Cache to avoid recomputing on every request
_CACHE: dict[str, Any] = {"expires_at": 0.0, "result": None}
_CACHE_TTL_SECONDS = 30.0


def _task_completion_score() -> tuple[float, dict[str, Any]]:
    """Compute score from idea portfolio task completion rates.

    Score = validated_ideas / total_ideas (with partial credit for PARTIAL).
    """
    from app.services import idea_service
    from app.models.idea import ManifestationStatus

    try:
        portfolio = idea_service.list_ideas(read_only_guard=True)
        ideas = portfolio.ideas
    except Exception:
        logger.debug("task_completion: failed to read ideas", exc_info=True)
        return 0.5, {"error": "failed to read ideas", "total": 0}

    if not ideas:
        return 0.5, {"total": 0, "note": "no ideas registered"}

    total = len(ideas)
    validated = sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED)
    partial = sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.PARTIAL)

    # Validated = 1.0 credit, partial = 0.5 credit
    completion = (validated + partial * 0.5) / total
    score = min(1.0, completion)

    return round(score, 4), {
        "total_ideas": total,
        "validated": validated,
        "partial": partial,
        "none": total - validated - partial,
    }


def _spec_coverage_score() -> tuple[float, dict[str, Any]]:
    """Compute score from spec registry coverage.

    Score based on fraction of specs that have implementation summaries.
    """
    from app.services import spec_registry_service

    try:
        specs = spec_registry_service.list_specs(limit=500)
    except Exception:
        logger.debug("spec_coverage: failed to read specs", exc_info=True)
        return 0.5, {"error": "failed to read specs", "total": 0}

    if not specs:
        return 0.5, {"total": 0, "note": "no specs registered"}

    total = len(specs)
    with_impl = sum(
        1 for s in specs
        if s.implementation_summary and s.implementation_summary.strip()
    )
    with_process = sum(
        1 for s in specs
        if s.process_summary and s.process_summary.strip()
    )

    # Coverage = weighted: implementation (70%) + process documentation (30%)
    if total > 0:
        impl_ratio = with_impl / total
        process_ratio = with_process / total
        score = impl_ratio * 0.7 + process_ratio * 0.3
    else:
        score = 0.5

    return round(min(1.0, score), 4), {
        "total_specs": total,
        "with_implementation": with_impl,
        "with_process": with_process,
    }


def _contribution_activity_score() -> tuple[float, dict[str, Any]]:
    """Compute score from recent commit evidence activity.

    Score based on commit density in recent windows vs baseline.
    """
    from app.services import commit_evidence_service

    try:
        records = commit_evidence_service.list_records(limit=500)
    except Exception:
        logger.debug("contribution_activity: failed to read records", exc_info=True)
        return 0.5, {"error": "failed to read records", "total": 0}

    if not records:
        return 0.5, {"total": 0, "note": "no commit evidence"}

    total = len(records)
    now = datetime.now(timezone.utc)
    recent_7d = 0
    recent_30d = 0

    for record in records:
        date_str = record.get("date") or record.get("committed_date") or ""
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            age = now - dt
            if age <= timedelta(days=7):
                recent_7d += 1
            if age <= timedelta(days=30):
                recent_30d += 1
        except (ValueError, TypeError):
            continue

    # Score: blend of 7-day intensity and 30-day breadth
    # 7-day: normalize against a baseline of ~5 commits/week being healthy
    score_7d = min(1.0, recent_7d / 5.0)
    # 30-day: normalize against ~20 commits/month being healthy
    score_30d = min(1.0, recent_30d / 20.0)
    score = score_7d * 0.6 + score_30d * 0.4

    return round(score, 4), {
        "total_records": total,
        "recent_7d": recent_7d,
        "recent_30d": recent_30d,
    }


def _runtime_health_score() -> tuple[float, dict[str, Any]]:
    """Compute score from runtime event success rates.

    Score = fraction of API calls returning 2xx/3xx in last 24h.
    """
    from app.services import runtime_service

    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        events = runtime_service.list_events(limit=2000, since=since)
    except Exception:
        logger.debug("runtime_health: failed to read events", exc_info=True)
        return 0.5, {"error": "failed to read events", "total": 0}

    if not events:
        return 0.5, {"total": 0, "note": "no runtime events in last 24h"}

    total = len(events)
    success = sum(1 for e in events if e.status_code and e.status_code < 400)
    error_5xx = sum(1 for e in events if e.status_code and e.status_code >= 500)

    if total > 0:
        success_rate = success / total
        # Penalize 5xx errors more heavily
        error_penalty = min(0.3, (error_5xx / total) * 0.5)
        score = max(0.0, success_rate - error_penalty)
    else:
        score = 0.5

    return round(score, 4), {
        "total_events_24h": total,
        "success_2xx_3xx": success,
        "error_5xx": error_5xx,
    }


def _value_realization_score() -> tuple[float, dict[str, Any]]:
    """Compute score from value gap analysis.

    Score = actual_value / potential_value across idea portfolio.
    """
    from app.services import idea_service

    try:
        portfolio = idea_service.list_ideas(read_only_guard=True)
    except Exception:
        logger.debug("value_realization: failed to read ideas", exc_info=True)
        return 0.5, {"error": "failed to read ideas"}

    ideas = portfolio.ideas
    if not ideas:
        return 0.5, {"note": "no ideas registered"}

    total_potential = sum(i.potential_value for i in ideas)
    total_actual = sum(i.actual_value for i in ideas)

    if total_potential <= 0:
        return 0.5, {
            "total_potential": 0.0,
            "total_actual": 0.0,
            "note": "no potential value registered",
        }

    realization = total_actual / total_potential
    score = min(1.0, realization)

    return round(score, 4), {
        "total_potential": round(total_potential, 2),
        "total_actual": round(total_actual, 2),
        "realization_ratio": round(realization, 4),
    }


def compute_coherence_score() -> dict[str, Any]:
    """Compute real-time coherence score from all available signals.

    Returns dict with:
      - score: float 0.0-1.0 (weighted aggregate)
      - signals: per-signal scores and details
      - signals_with_data: count of signals backed by real data
      - computed_at: ISO timestamp
    """
    now = time.time()
    cached = _CACHE.get("result")
    if cached and _CACHE.get("expires_at", 0.0) > now:
        return cached

    signal_fns = {
        "task_completion": _task_completion_score,
        "spec_coverage": _spec_coverage_score,
        "contribution_activity": _contribution_activity_score,
        "runtime_health": _runtime_health_score,
        "value_realization": _value_realization_score,
    }

    signals: dict[str, dict[str, Any]] = {}
    weighted_sum = 0.0
    signals_with_data = 0

    for name, fn in signal_fns.items():
        try:
            score, details = fn()
        except Exception:
            logger.debug("signal %s failed", name, exc_info=True)
            score = 0.5
            details = {"error": "computation failed"}

        weight = SIGNAL_WEIGHTS[name]
        weighted_sum += score * weight
        signals[name] = {
            "score": score,
            "weight": weight,
            "details": details,
        }
        # Signal has real data if it didn't fall back to 0.5 default
        has_data = "error" not in details and details.get("note") is None
        if has_data:
            signals_with_data += 1

    aggregate = round(min(1.0, max(0.0, weighted_sum)), 4)

    result = {
        "score": aggregate,
        "signals": signals,
        "signals_with_data": signals_with_data,
        "total_signals": len(signal_fns),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    _CACHE["result"] = result
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS

    return result


def invalidate_cache() -> None:
    """Clear cached score — useful for testing."""
    _CACHE["expires_at"] = 0.0
    _CACHE["result"] = None
