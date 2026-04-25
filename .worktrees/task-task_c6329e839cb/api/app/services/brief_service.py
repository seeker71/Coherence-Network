"""Brief service — daily engagement brief generation and feedback tracking.

In-memory implementation (Phase 1). Computes fresh on each request.
Data model:
  DailyBrief: id, contributor_id, generated_at, sections, cta
  BriefFeedback: id, brief_id, section, item_id, action, recorded_at
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SECTIONS = frozenset(
    ["news_resonance", "ideas_needing_skills", "tasks_for_providers",
     "nearby_contributors", "network_patterns"]
)
VALID_ACTIONS = frozenset(["claimed", "opened", "dismissed", "shared"])

# ---------------------------------------------------------------------------
# In-memory stores (reset between tests via reset_state())
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_briefs: dict[str, dict] = {}
_feedback_list: list[dict] = []
# Set of contributor IDs known to the system (populated in tests via register_contributor)
_known_contributors: set[str] = set()


def reset_state() -> None:
    """Clear all in-memory state. Call in test fixtures."""
    global _briefs, _feedback_list, _known_contributors
    with _lock:
        _briefs = {}
        _feedback_list = []
        _known_contributors = set()


def register_contributor(contributor_id: str) -> None:
    """Register a contributor as known (used in tests and seeding)."""
    with _lock:
        _known_contributors.add(contributor_id)


def contributor_exists(contributor_id: str) -> bool:
    """Return True if the contributor is known."""
    return contributor_id in _known_contributors


# ---------------------------------------------------------------------------
# Brief generation
# ---------------------------------------------------------------------------

def _build_tasks_for_providers(limit: int) -> list[dict]:
    """Return mock tasks ordered by wait time (longest first)."""
    now = datetime.now(timezone.utc)
    tasks = [
        {
            "task_id": "task_aaa",
            "idea_title": "Edge navigation",
            "task_type": "impl",
            "provider": "claude",
            "waiting_since": (now - timedelta(hours=3, minutes=30)).isoformat(),
            "priority": "high",
        },
        {
            "task_id": "task_bbb",
            "idea_title": "Graph coherence scoring",
            "task_type": "spec",
            "provider": "claude",
            "waiting_since": (now - timedelta(hours=1)).isoformat(),
            "priority": "medium",
        },
        {
            "task_id": "task_ccc",
            "idea_title": "Federation relay",
            "task_type": "test",
            "provider": "codex",
            "waiting_since": (now - timedelta(minutes=20)).isoformat(),
            "priority": "low",
        },
    ]
    # Sort by waiting_since ascending (oldest first = longest waiting)
    tasks.sort(key=lambda t: t["waiting_since"])
    return tasks[:limit]


def _build_news_resonance(contributor_id: Optional[str], limit: int) -> list[dict]:
    return [
        {
            "news_id": "news_123",
            "title": "Quantum coherence in biological systems",
            "resonance_score": 0.87,
            "matching_idea_id": "idea_456",
            "matching_idea_title": "Resonance as a biological organizing principle",
            "url": "https://example.com/article",
            "published_at": "2026-03-27T14:00:00Z",
        }
    ][:limit]


def _build_ideas_needing_skills(contributor_id: Optional[str], limit: int) -> list[dict]:
    return [
        {
            "idea_id": "idea_789",
            "title": "Graph-based coherence scoring",
            "skill_match": ["python", "neo4j"],
            "phase": "spec",
            "open_tasks": 2,
            "coherence_score": 0.74,
        }
    ][:limit]


def _build_nearby_contributors(contributor_id: Optional[str], limit: int) -> list[dict]:
    return [
        {
            "contributor_id": "contrib_xyz",
            "display_name": "Alice",
            "shared_concepts": ["coherence", "graph-theory"],
            "hop_distance": 2,
            "recent_contribution": "Implemented edge navigation spec",
        }
    ][:limit]


def _build_network_patterns(limit: int) -> list[dict]:
    return [
        {
            "pattern_type": "convergence",
            "description": "3 independent contributors are adding graph-traversal related ideas",
            "idea_ids": ["idea_11", "idea_22", "idea_33"],
            "first_seen": "2026-03-26T00:00:00Z",
            "signal_strength": 0.65,
        }
    ][:limit]


def generate_brief(
    contributor_id: Optional[str] = None,
    limit_per_section: int = 3,
    as_of: Optional[str] = None,
) -> dict:
    """Generate a daily brief. Raises ValueError if contributor not found."""
    if contributor_id is not None and not contributor_exists(contributor_id):
        raise ValueError(f"Contributor not found: {contributor_id}")

    generated_at = datetime.now(timezone.utc).isoformat()
    brief_id = str(uuid.uuid4())

    sections: dict[str, Any] = {
        "news_resonance": _build_news_resonance(contributor_id, limit_per_section),
        "ideas_needing_skills": _build_ideas_needing_skills(contributor_id, limit_per_section),
        "tasks_for_providers": _build_tasks_for_providers(limit_per_section),
        "nearby_contributors": _build_nearby_contributors(contributor_id, limit_per_section),
        "network_patterns": _build_network_patterns(limit_per_section),
    }

    cta = {
        "recommended_action": "claim_task",
        "target_id": "task_aaa",
        "reason": "Waiting 3.5h for a claude provider — this matches your executor profile",
    }

    brief = {
        "brief_id": brief_id,
        "generated_at": generated_at,
        "contributor_id": contributor_id,
        "sections": sections,
        "cta": cta,
    }

    with _lock:
        _briefs[brief_id] = brief

    return brief


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def record_feedback(
    brief_id: str,
    section: str,
    item_id: str,
    action: str,
) -> dict:
    """Record feedback for a brief item. Raises KeyError if brief not found."""
    if brief_id not in _briefs:
        raise KeyError(f"Brief not found: {brief_id}")

    feedback = {
        "id": str(uuid.uuid4()),
        "brief_id": brief_id,
        "section": section,
        "item_id": item_id,
        "action": action,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    with _lock:
        _feedback_list.append(feedback)

    return feedback


# ---------------------------------------------------------------------------
# Engagement metrics
# ---------------------------------------------------------------------------

def get_engagement_metrics(window_days: int = 30) -> dict:
    """Compute aggregate engagement metrics over the given window."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    with _lock:
        window_briefs = [
            b for b in _briefs.values()
            if datetime.fromisoformat(b["generated_at"].replace("Z", "+00:00")) >= cutoff
        ]
        window_feedback = [
            f for f in _feedback_list
            if datetime.fromisoformat(f["recorded_at"].replace("Z", "+00:00")) >= cutoff
        ]

    briefs_generated = len(window_briefs)
    unique_contributors = len(
        {b["contributor_id"] for b in window_briefs if b["contributor_id"]}
    )

    # Section click rates
    section_counts: dict[str, int] = {s: 0 for s in VALID_SECTIONS}
    for fb in window_feedback:
        if fb["section"] in section_counts:
            section_counts[fb["section"]] += 1

    section_click_rates: dict[str, float] = {}
    for s, count in section_counts.items():
        section_click_rates[s] = round(count / briefs_generated, 4) if briefs_generated > 0 else 0.0

    claimed_count = sum(1 for f in window_feedback if f["action"] == "claimed")
    cta_conversion_rate = round(claimed_count / briefs_generated, 4) if briefs_generated > 0 else 0.0

    actions_attributable_to_brief = len(window_feedback)

    # Trend: compare last 7 days vs prior 7 days
    cutoff_last7 = now - timedelta(days=7)
    cutoff_prior7 = now - timedelta(days=14)

    last7_actions = sum(
        1 for f in window_feedback
        if datetime.fromisoformat(f["recorded_at"].replace("Z", "+00:00")) >= cutoff_last7
    )
    prior7_actions = sum(
        1 for f in window_feedback
        if cutoff_prior7 <= datetime.fromisoformat(f["recorded_at"].replace("Z", "+00:00")) < cutoff_last7
    )

    if prior7_actions == 0:
        trend = "stable"
    elif last7_actions > prior7_actions:
        trend = "improving"
    elif last7_actions < prior7_actions:
        trend = "degrading"
    else:
        trend = "stable"

    return {
        "window_days": window_days,
        "briefs_generated": briefs_generated,
        "unique_contributors": unique_contributors,
        "section_click_rates": section_click_rates,
        "cta_conversion_rate": cta_conversion_rate,
        "actions_attributable_to_brief": actions_attributable_to_brief,
        "trend": trend,
    }
