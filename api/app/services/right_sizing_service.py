"""Right-sizing service: automatic idea granularity management (spec 158).

Detects too_large, too_small, and overlap signals across the portfolio and
generates split/merge suggestions with confidence and rationale.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models.idea import (
    GranularitySignal,
    PortfolioHealthCounts,
    RightSizingApplyResponse,
    RightSizingHistoryEntry,
    RightSizingHistoryResponse,
    RightSizingReport,
    RightSizingSuggestion,
    SuggestionType,
    TrendInfo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "right_sizing.json"
_CONFIG_CACHE: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    try:
        _CONFIG_CACHE = json.loads(_CONFIG_PATH.read_text())
    except Exception:
        _CONFIG_CACHE = {
            "thresholds": {
                "too_large_questions": 10,
                "too_large_tasks": 8,
                "too_small_age_days": 14,
                "overlap_score_min": 0.80,
            },
            "sweep_interval_hours": 6,
            "snapshot_retention_days": 90,
        }
    return _CONFIG_CACHE


def _thresholds() -> dict[str, Any]:
    return _load_config().get("thresholds", {})


# ---------------------------------------------------------------------------
# Text overlap (simple word-level Jaccard / TF-IDF-lite)
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "the a an and or but is in it of to for with on at by from as this that "
    "be are was were has have had do does did not no will can may should would "
    "could shall might must been being am its our we they them their he she "
    "his her you your all any each so if".split()
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase tokenize, remove stop words."""
    tokens = _WORD_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _tf_vector(tokens: list[str]) -> dict[str, float]:
    """Term-frequency vector normalized to unit length."""
    counts = Counter(tokens)
    total = len(tokens) or 1
    vec = {t: c / total for t, c in counts.items()}
    return vec


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF vectors."""
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def compute_text_overlap(text_a: str, text_b: str) -> float:
    """Return 0.0-1.0 similarity score between two idea texts."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    return _cosine_similarity(_tf_vector(tokens_a), _tf_vector(tokens_b))


# ---------------------------------------------------------------------------
# Signal computation
# ---------------------------------------------------------------------------


def _idea_text(idea: Any) -> str:
    """Combine name + description for overlap analysis."""
    name = getattr(idea, "name", "") or ""
    desc = getattr(idea, "description", "") or ""
    return f"{name} {desc}"


def compute_granularity_signal(
    idea: Any,
    spec_count: int = 0,
    task_count: int = 0,
) -> tuple[GranularitySignal, dict[str, Any]]:
    """Compute the granularity signal for a single idea.

    Returns (signal, metadata) where metadata contains diagnostic info.
    """
    thresholds = _thresholds()
    oq_count = len(getattr(idea, "open_questions", []) or [])
    too_large_q = thresholds.get("too_large_questions", 10)
    too_large_t = thresholds.get("too_large_tasks", 8)

    # too_large: too many open questions OR too many specs/tasks
    if oq_count >= too_large_q or spec_count > 5 or task_count >= too_large_t:
        return GranularitySignal.TOO_LARGE, {
            "open_questions": oq_count,
            "spec_count": spec_count,
            "task_count": task_count,
        }

    # too_small: no specs at all (and idea has been around — lifecycle is active)
    if spec_count == 0:
        lifecycle = getattr(idea, "lifecycle", None)
        lv = lifecycle.value if hasattr(lifecycle, "value") else str(lifecycle or "active")
        if lv == "active":
            return GranularitySignal.TOO_SMALL, {"spec_count": 0}

    return GranularitySignal.HEALTHY, {}


def generate_suggestions(ideas: list[Any], spec_counts: dict[str, int]) -> list[RightSizingSuggestion]:
    """Generate split/merge suggestions for the portfolio."""
    suggestions: list[RightSizingSuggestion] = []
    thresholds = _thresholds()
    overlap_min = thresholds.get("overlap_score_min", 0.80)

    # Check for too_large -> suggest split
    for idea in ideas:
        iid = getattr(idea, "id", "")
        sc = spec_counts.get(iid, 0)
        oq_count = len(getattr(idea, "open_questions", []) or [])
        name = getattr(idea, "name", iid)

        signal, _meta = compute_granularity_signal(idea, spec_count=sc)

        if signal == GranularitySignal.TOO_LARGE:
            confidence = min(1.0, 0.5 + 0.05 * max(oq_count - 5, sc - 3, 0))
            suggestions.append(RightSizingSuggestion(
                suggestion_type=SuggestionType.SPLIT,
                idea_id=iid,
                rationale=f"Idea '{name}' has {oq_count} open questions and {sc} specs — consider splitting into focused sub-ideas.",
                confidence=round(confidence, 2),
                proposed_children=[
                    {"name": f"{name} (core)", "description": f"Core delivery tasks for {name}"},
                    {"name": f"{name} (research)", "description": f"Open questions and research for {name}"},
                ],
                proposed_action="split_into_children",
            ))

    # Check for overlap -> suggest merge
    seen_pairs: set[tuple[str, str]] = set()
    for i, idea_a in enumerate(ideas):
        text_a = _idea_text(idea_a)
        id_a = getattr(idea_a, "id", "")
        for j, idea_b in enumerate(ideas):
            if j <= i:
                continue
            id_b = getattr(idea_b, "id", "")
            pair_key = (min(id_a, id_b), max(id_a, id_b))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            text_b = _idea_text(idea_b)
            score = compute_text_overlap(text_a, text_b)

            if score >= overlap_min:
                name_a = getattr(idea_a, "name", id_a)
                name_b = getattr(idea_b, "name", id_b)
                suggestions.append(RightSizingSuggestion(
                    suggestion_type=SuggestionType.MERGE,
                    idea_id=id_a,
                    rationale=f"Ideas '{name_a}' and '{name_b}' have {score:.0%} text overlap — consider merging.",
                    confidence=round(min(score, 1.0), 2),
                    overlap_with_id=id_b,
                    overlap_score=round(score, 4),
                    proposed_action="merge_and_archive",
                ))

    return suggestions


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def build_report() -> RightSizingReport:
    """Build the full right-sizing report for the portfolio."""
    from app.services import idea_service, spec_registry_service

    portfolio = idea_service.list_ideas(read_only_guard=True)
    ideas = portfolio.ideas

    # Count specs per idea
    all_specs = spec_registry_service.list_specs(limit=1000)
    spec_counts: dict[str, int] = {}
    for spec in all_specs:
        idea_id = getattr(spec, "idea_id", None)
        if idea_id:
            spec_counts[idea_id] = spec_counts.get(idea_id, 0) + 1

    # Compute signals
    healthy = 0
    too_large = 0
    too_small = 0
    overlap_count = 0

    for idea in ideas:
        iid = getattr(idea, "id", "")
        sc = spec_counts.get(iid, 0)
        signal, _ = compute_granularity_signal(idea, spec_count=sc)
        if signal == GranularitySignal.HEALTHY:
            healthy += 1
        elif signal == GranularitySignal.TOO_LARGE:
            too_large += 1
        elif signal == GranularitySignal.TOO_SMALL:
            too_small += 1

    # Check overlaps
    thresholds = _thresholds()
    overlap_min = thresholds.get("overlap_score_min", 0.80)
    overlap_ids: set[str] = set()
    for i, idea_a in enumerate(ideas):
        text_a = _idea_text(idea_a)
        for j, idea_b in enumerate(ideas):
            if j <= i:
                continue
            text_b = _idea_text(idea_b)
            score = compute_text_overlap(text_a, text_b)
            if score >= overlap_min:
                overlap_ids.add(getattr(idea_a, "id", ""))
                overlap_ids.add(getattr(idea_b, "id", ""))
    overlap_count = len(overlap_ids)

    total = len(ideas)
    health = PortfolioHealthCounts(
        total=total,
        healthy=healthy,
        too_large=too_large,
        too_small=too_small,
        overlap=overlap_count,
    )

    suggestions = generate_suggestions(ideas, spec_counts)

    # Trend
    healthy_pct_now = healthy / total if total > 0 else 1.0
    history = get_history(days=7)
    healthy_pct_7d: float | None = None
    if history.series:
        healthy_pct_7d = history.series[0].healthy_pct

    if healthy_pct_7d is None:
        direction = "stable"
    elif healthy_pct_now > healthy_pct_7d + 0.02:
        direction = "improving"
    elif healthy_pct_now < healthy_pct_7d - 0.02:
        direction = "degrading"
    else:
        direction = "stable"

    trend = TrendInfo(
        healthy_pct_now=round(healthy_pct_now, 4),
        healthy_pct_7d_ago=round(healthy_pct_7d, 4) if healthy_pct_7d is not None else None,
        direction=direction,
    )

    return RightSizingReport(
        generated_at=datetime.now(timezone.utc),
        portfolio_health=health,
        suggestions=suggestions,
        trend=trend,
    )


# ---------------------------------------------------------------------------
# Apply suggestion
# ---------------------------------------------------------------------------


def apply_suggestion(
    suggestion_type: str,
    idea_id: str,
    action: str,
    proposed_children: list[dict] | None = None,
    overlap_with_id: str | None = None,
    dry_run: bool = True,
) -> RightSizingApplyResponse:
    """Execute a split or merge. When dry_run=True, preview only."""
    from app.services import idea_service

    valid_actions = {"split_into_children", "merge_and_archive"}
    if action not in valid_actions:
        raise ValueError(f"Invalid action: {action}. Must be one of {valid_actions}")

    # Validate that the idea exists
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        raise LookupError(f"Idea '{idea_id}' not found")

    changes: list[dict] = []

    if suggestion_type == "split" and action == "split_into_children":
        children = proposed_children or []
        for child in children:
            child_name = child.get("name", "")
            child_slug = re.sub(r"[^a-z0-9-]", "-", child_name.lower().strip())
            child_slug = re.sub(r"-+", "-", child_slug).strip("-")
            changes.append({
                "op": "create_idea",
                "idea_id": child_slug,
                "name": child_name,
                "description": child.get("description", ""),
            })
        changes.append({
            "op": "update_idea",
            "idea_id": idea_id,
            "set": {"idea_type": "super"},
        })

        if not dry_run:
            for change in changes:
                if change["op"] == "create_idea":
                    idea_service.create_idea(
                        idea_id=change["idea_id"],
                        name=change["name"],
                        description=change["description"],
                        potential_value=idea.potential_value / max(len(children), 1),
                        estimated_cost=idea.estimated_cost / max(len(children), 1),
                        confidence=idea.confidence,
                        parent_idea_id=idea_id,
                    )
                elif change["op"] == "update_idea":
                    idea_service.update_idea(idea_id=change["idea_id"], name=idea.name)
                    # Set idea_type via direct internal update
                    _set_idea_type(change["idea_id"], "super")

    elif suggestion_type == "merge" and action == "merge_and_archive":
        if not overlap_with_id:
            raise ValueError("overlap_with_id required for merge action")
        merge_idea = idea_service.get_idea(overlap_with_id)
        if merge_idea is None:
            raise LookupError(f"Overlap idea '{overlap_with_id}' not found")

        changes.append({
            "op": "update_idea",
            "idea_id": overlap_with_id,
            "set": {"lifecycle": "archived", "duplicate_of": idea_id},
        })
        changes.append({
            "op": "update_idea",
            "idea_id": idea_id,
            "set": {"note": f"Merged from {overlap_with_id}"},
        })

        if not dry_run:
            from app.models.idea import IdeaLifecycle
            idea_service.update_idea(
                idea_id=overlap_with_id,
                lifecycle=IdeaLifecycle.ARCHIVED,
                duplicate_of=idea_id,
            )

    return RightSizingApplyResponse(
        applied=not dry_run,
        dry_run=dry_run,
        changes=changes,
    )


def _set_idea_type(idea_id: str, idea_type: str) -> None:
    """Internal helper to set the idea_type field."""
    from app.services import idea_service
    ideas = idea_service._read_ideas(persist_ensures=True)
    for idea in ideas:
        if idea.id == idea_id:
            from app.models.idea import IdeaType
            idea.idea_type = IdeaType(idea_type)
            break
    idea_service._write_ideas(ideas)


# ---------------------------------------------------------------------------
# Snapshot / history (in-memory for MVP; PostgreSQL table in follow-up)
# ---------------------------------------------------------------------------

_SNAPSHOTS: list[dict] = []


def snapshot_health() -> dict:
    """Take a health snapshot of the current portfolio and store it."""
    from app.services import idea_service, spec_registry_service

    portfolio = idea_service.list_ideas(read_only_guard=True)
    ideas = portfolio.ideas
    total = len(ideas)

    all_specs = spec_registry_service.list_specs(limit=1000)
    spec_counts: dict[str, int] = {}
    for spec in all_specs:
        idea_id_val = getattr(spec, "idea_id", None)
        if idea_id_val:
            spec_counts[idea_id_val] = spec_counts.get(idea_id_val, 0) + 1

    healthy = too_large = too_small = 0
    for idea in ideas:
        iid = getattr(idea, "id", "")
        sc = spec_counts.get(iid, 0)
        signal, _ = compute_granularity_signal(idea, spec_count=sc)
        if signal == GranularitySignal.HEALTHY:
            healthy += 1
        elif signal == GranularitySignal.TOO_LARGE:
            too_large += 1
        elif signal == GranularitySignal.TOO_SMALL:
            too_small += 1

    healthy_pct = healthy / total if total > 0 else 1.0
    snap = {
        "date": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "healthy": healthy,
        "too_large": too_large,
        "too_small": too_small,
        "overlap": 0,  # Overlap is expensive to compute; skip in sweep
        "healthy_pct": round(healthy_pct, 4),
    }
    _SNAPSHOTS.append(snap)

    # Retain only 90 days of snapshots
    retention = _load_config().get("snapshot_retention_days", 90)
    cutoff = datetime.now(timezone.utc).timestamp() - retention * 86400
    _SNAPSHOTS[:] = [
        s for s in _SNAPSHOTS
        if datetime.fromisoformat(s["date"]).timestamp() > cutoff
    ]

    return snap


def get_history(days: int = 7) -> RightSizingHistoryResponse:
    """Return time-series health snapshots for the given window."""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    series = []
    for s in _SNAPSHOTS:
        try:
            ts = datetime.fromisoformat(s["date"]).timestamp()
        except (ValueError, KeyError):
            continue
        if ts >= cutoff:
            series.append(RightSizingHistoryEntry(
                date=s["date"],
                total=s.get("total", 0),
                healthy=s.get("healthy", 0),
                too_large=s.get("too_large", 0),
                too_small=s.get("too_small", 0),
                overlap=s.get("overlap", 0),
                healthy_pct=s.get("healthy_pct", 0.0),
            ))
    return RightSizingHistoryResponse(series=series)


def clear_snapshots() -> None:
    """Test helper: clear all in-memory snapshots."""
    _SNAPSHOTS.clear()
