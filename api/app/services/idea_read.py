"""Idea read operations — list + single-idea lookup with scoring.

Extracted from idea_service.py (#163). Both functions wrap _read_ideas
(in idea_service) and decorate results with scoring + selection weights.

Public surface (re-exported from idea_service):
  list_ideas, get_idea
"""

from __future__ import annotations

import logging

from app.models.idea import (
    IdeaPortfolioResponse,
    IdeaSummary,
    IdeaWithScore,
    ManifestationStatus,
    PaginationInfo,
)
from app.services.idea_derivation import _derived_idea_for_id
from app.services.idea_internal_filter import _KNOWN_INTERNAL_IDEA_IDS, is_internal_idea_id
from app.services.idea_scoring import _softmax_weights, _with_score

logger = logging.getLogger(__name__)


def list_ideas(
    only_unvalidated: bool = False,
    limit: int | None = None,
    offset: int = 0,
    include_internal: bool = True,
    read_only_guard: bool = False,
    sort_method: str = "free_energy",
    tags_filter: list[str] | None = None,
    curated_only: bool = False,
    pillar: str | None = None,
    workspace_id: str | None = None,
) -> IdeaPortfolioResponse:
    """When read_only_guard=True, ensure logic is applied in memory but not persisted (for invariant/guard runs).

    sort_method: "free_energy" (default, Method A) or "marginal_cc" (Method B).
    tags_filter: when provided, only return ideas that carry ALL of the given normalized tags.
    curated_only: when True, only return ideas where is_curated=True (the 16 super-ideas from ideas/*.md).
    pillar: when provided, only return ideas with this pillar value.
    workspace_id: when provided, only return ideas that belong to that workspace.
    """
    from app.services.idea_service import _read_ideas

    ideas = _read_ideas(persist_ensures=not read_only_guard)
    if not include_internal:
        ideas = [i for i in ideas if not is_internal_idea_id(i.id, i.interfaces)]
    if only_unvalidated:
        ideas = [i for i in ideas if i.manifestation_status != ManifestationStatus.VALIDATED]
    if tags_filter:
        required = set(tags_filter)
        ideas = [i for i in ideas if required.issubset(set(i.tags))]
    if curated_only:
        ideas = [i for i in ideas if getattr(i, "is_curated", False)]
    if pillar:
        ideas = [i for i in ideas if getattr(i, "pillar", None) == pillar]
    if workspace_id:
        ideas = [i for i in ideas if getattr(i, "workspace_id", "coherence-network") == workspace_id]

    scored = [_with_score(i) for i in ideas]
    if sort_method == "marginal_cc":
        sort_key = lambda i: i.marginal_cc_score
        raw_scores = [s.marginal_cc_score for s in scored]
    else:
        sort_key = lambda i: i.free_energy_score
        raw_scores = [s.free_energy_score for s in scored]

    weights = _softmax_weights(raw_scores, temperature=1.0)
    for s, w in zip(scored, weights):
        s.selection_weight = round(w, 6)

    ranked = sorted(scored, key=sort_key, reverse=True)
    total_ranked = len(ranked)
    safe_offset = max(0, int(offset))
    safe_limit = None if limit is None else max(1, min(int(limit), 500))
    if safe_limit is None:
        page_items = ranked[safe_offset:]
    else:
        page_items = ranked[safe_offset:safe_offset + safe_limit]
    total_potential = sum(i.potential_value for i in ideas)
    total_actual = sum(i.actual_value for i in ideas)
    summary = IdeaSummary(
        total_ideas=len(ideas),
        unvalidated_ideas=sum(1 for i in ideas if i.manifestation_status != ManifestationStatus.VALIDATED),
        validated_ideas=sum(1 for i in ideas if i.manifestation_status == ManifestationStatus.VALIDATED),
        total_potential_value=round(total_potential, 4),
        total_actual_value=round(total_actual, 4),
        total_value_gap=round(max(total_potential - total_actual, 0.0), 4),
    )
    pagination = PaginationInfo(
        total=total_ranked,
        limit=safe_limit or max(total_ranked, 1),
        offset=safe_offset,
        returned=len(page_items),
        has_more=(safe_offset + len(page_items)) < total_ranked,
    )
    return IdeaPortfolioResponse(ideas=page_items, summary=summary, pagination=pagination)


def get_idea(idea_id: str) -> IdeaWithScore | None:
    from app.services.idea_service import _read_ideas, _resolve_idea_raw

    ideas = _read_ideas()
    idea = _resolve_idea_raw(idea_id, ideas)
    if idea is not None:
        return _with_score(idea)
    # Some runtime/inventory idea ids are derived and may not be persisted in the
    # portfolio store yet. Expose them so UI links remain walkable.
    if idea_id in _KNOWN_INTERNAL_IDEA_IDS:
        return _with_score(_derived_idea_for_id(idea_id))
    logger.info("Idea not found: %s", idea_id)
    return None
