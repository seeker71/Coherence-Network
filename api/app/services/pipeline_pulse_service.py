"""Pipeline pulse — self-awareness digest for the idea→spec→impl→verify pipeline.

Answers three questions:
1. Where is the pipeline generating value? (ideas that advanced this period)
2. Where is it wasting effort? (recurring failures, stuck phases)
3. What should change? (concrete next action)
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import agent_service, idea_service

log = logging.getLogger(__name__)

_PHASE_ORDER = ["spec", "impl", "test", "review"]


def compute_pulse(window_days: int = 7, task_limit: int = 500) -> dict[str, Any]:
    """Compute a pipeline self-awareness pulse."""

    # Load tasks — list_tasks returns (items, total, backfill_count)
    all_tasks, _total, _backfill = agent_service.list_tasks(limit=task_limit, offset=0)

    # Load portfolio for idea context
    portfolio = idea_service.list_ideas(include_internal=False, read_only_guard=True)
    idea_names = {idea.id: idea.name for idea in portfolio.ideas}

    # ── Phase success rates ──────────────────────────────────────────
    phase_stats: dict[str, dict[str, int]] = {}
    for phase in _PHASE_ORDER:
        typed = [t for t in all_tasks if t.get("task_type") == phase]
        completed = sum(1 for t in typed if t.get("status") == "completed")
        failed = sum(1 for t in typed if t.get("status") in ("failed", "timed_out"))
        pending = sum(1 for t in typed if t.get("status") == "pending")
        running = sum(1 for t in typed if t.get("status") == "running")
        total_resolved = completed + failed
        phase_stats[phase] = {
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "total": len(typed),
            "success_rate": round(completed / total_resolved, 2) if total_resolved > 0 else None,
        }

    # ── Idea progression ─────────────────────────────────────────────
    idea_completed = defaultdict(set)
    idea_failed = defaultdict(set)
    for t in all_tasks:
        idea_id = (t.get("context") or {}).get("idea_id", "")
        if not idea_id:
            continue
        if t.get("status") == "completed":
            idea_completed[idea_id].add(t.get("task_type", ""))
        elif t.get("status") in ("failed", "timed_out"):
            idea_failed[idea_id].add(t.get("task_type", ""))

    # Ideas that completed ALL phases
    full_cycle = [
        iid for iid, phases in idea_completed.items()
        if phases >= {"spec", "impl", "test", "review"}
    ]

    # Ideas advancing (have at least 1 completed phase)
    advancing = [
        {
            "idea_id": iid,
            "idea_name": idea_names.get(iid, iid),
            "completed_phases": sorted(phases),
            "failed_phases": sorted(idea_failed.get(iid, set())),
            "depth": len(phases),
        }
        for iid, phases in idea_completed.items()
    ]
    advancing.sort(key=lambda x: x["depth"], reverse=True)

    # Ideas stuck (have failures but no completions)
    stuck = [
        {
            "idea_id": iid,
            "idea_name": idea_names.get(iid, iid),
            "failed_phases": sorted(phases),
        }
        for iid, phases in idea_failed.items()
        if iid not in idea_completed
    ]

    # ── Pipeline balance ─────────────────────────────────────────────
    # Is the pipeline balanced or top-heavy?
    total_by_type = Counter(t.get("task_type", "?") for t in all_tasks)
    type_total = sum(total_by_type.values()) or 1
    balance = {
        phase: round(total_by_type.get(phase, 0) / type_total, 2)
        for phase in _PHASE_ORDER
    }

    # ── Bottleneck detection ─────────────────────────────────────────
    bottleneck = None
    bottleneck_reason = None

    # Check: are we spec-starved?
    ideas_without_spec = sum(
        1 for idea in portfolio.ideas
        if idea.id not in idea_completed or "spec" not in idea_completed[idea.id]
    )
    ideas_total = len(portfolio.ideas)

    if ideas_without_spec > ideas_total * 0.7:
        bottleneck = "spec_starvation"
        bottleneck_reason = (
            f"{ideas_without_spec} of {ideas_total} ideas ({ideas_without_spec*100//ideas_total}%) "
            f"have no spec. The pipeline can't move ideas forward without plans."
        )
    elif phase_stats.get("impl", {}).get("success_rate") is not None and phase_stats["impl"]["success_rate"] < 0.5:
        bottleneck = "impl_failure"
        bottleneck_reason = (
            f"Implementation success rate is {phase_stats['impl']['success_rate']:.0%}. "
            f"Specs may not be precise enough for implementation."
        )
    elif phase_stats.get("review", {}).get("success_rate") is not None and phase_stats["review"]["success_rate"] < 0.5:
        bottleneck = "review_failure"
        bottleneck_reason = (
            f"Review success rate is {phase_stats['review']['success_rate']:.0%}. "
            f"Code quality or review criteria may need adjustment."
        )
    elif balance.get("review", 0) > 0.6:
        bottleneck = "review_heavy"
        bottleneck_reason = (
            f"Reviews are {balance['review']:.0%} of all tasks. "
            f"The pipeline is reviewing more than building."
        )

    # ── Recommended action ───────────────────────────────────────────
    if bottleneck == "spec_starvation":
        recommendation = (
            f"Run POST /api/inventory/gaps/bootstrap-specs?max_tasks=20 to create spec tasks "
            f"for the top 20 highest-ROI ideas. This will feed the pipeline with work."
        )
    elif bottleneck == "impl_failure":
        recommendation = (
            "Review recent failed implementation tasks. Check if spec verification criteria "
            "are concrete enough for providers to implement against."
        )
    elif bottleneck == "review_failure":
        recommendation = (
            "Check if review criteria match what implementations actually produce. "
            "Consider adjusting DIF thresholds or review prompt specificity."
        )
    elif bottleneck == "review_heavy":
        recommendation = (
            "The pipeline has too many reviews relative to implementations. "
            "Bootstrap more specs to feed the impl→test→review chain."
        )
    else:
        recommendation = "Pipeline appears balanced. Keep monitoring phase success rates."

    # Normalise: bottleneck fields must always be strings (never None) so the
    # dashboard can safely call .replace() without a null-check.
    if bottleneck is None:
        bottleneck = "balanced"
    if bottleneck_reason is None:
        bottleneck_reason = "No significant bottleneck detected."

    # ── Tasks needing human attention ───────────────────────────────
    needs_decision = []
    for t in all_tasks:
        status_val = t.get("status", "")
        if hasattr(status_val, "value"):
            status_val = status_val.value
        if status_val == "needs_decision":
            ctx = t.get("context") or {}
            analysis = ctx.get("failure_analysis", {})
            needs_decision.append({
                "task_id": t.get("id", ""),
                "task_type": t.get("task_type", ""),
                "idea_id": ctx.get("idea_id", ""),
                "idea_name": idea_names.get(ctx.get("idea_id", ""), ctx.get("idea_id", "")),
                "failure_type": analysis.get("failure_type", "unknown"),
                "reason": analysis.get("reason", t.get("decision_prompt", "")[:100]),
                "decision_prompt": t.get("decision_prompt", ""),
            })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "task_count": len(all_tasks),
        "phase_stats": phase_stats,
        "bottleneck": {
            "type": bottleneck,
            "reason": bottleneck_reason,
            "recommendation": recommendation,
        },
        "balance": balance,
        "ideas": {
            "total_in_portfolio": ideas_total,
            "without_spec": ideas_without_spec,
            "with_activity": len(idea_completed) + len(stuck),
            "advancing": advancing[:20],
            "stuck": stuck[:20],
            "full_cycle": [
                {"idea_id": iid, "idea_name": idea_names.get(iid, iid)}
                for iid in full_cycle
            ],
        },
        "needs_decision": needs_decision,
        "needs_decision_count": len(needs_decision),
    }
