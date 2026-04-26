"""Resonance + concept token helpers for ideas.

Extracted from idea_service.py to reduce that module under the modularity
threshold (#163). Public surface: _humanize_idea_id (used by lifecycle
flows), _extract_resonance_tokens, _idea_concept_tokens,
_idea_domain_tokens, _find_closest_graph_idea — all re-exported from
idea_service for backward compat.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.idea import Idea


def _humanize_idea_id(idea_id: str) -> str:
    words = [part for part in idea_id.replace("_", "-").split("-") if part]
    if not words:
        return "Derived tracked idea"
    return " ".join(words).strip().capitalize()


_FUZZY_STOP_WORDS = frozenset({
    "spec", "origin", "endpoint", "lineage", "the", "a", "for", "and", "of",
    "with", "from", "to", "in", "on", "by", "is", "at", "or", "an",
})
_RESONANCE_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")
_CONCEPT_RESONANCE_STOP_WORDS = _FUZZY_STOP_WORDS.union({
    "idea",
    "ideas",
    "concept",
    "concepts",
    "network",
    "system",
    "platform",
    "service",
    "services",
    "tool",
    "tools",
    "domain",
    "domains",
    "cross",
    "related",
    "across",
    "core",
})


def _extract_resonance_tokens(*parts: Any) -> set[str]:
    tokens: set[str] = set()
    pending = list(parts)
    while pending:
        part = pending.pop()
        if part is None:
            continue
        if isinstance(part, (list, tuple, set)):
            pending.extend(part)
            continue
        text = str(part).strip().lower()
        if not text:
            continue
        text = text.replace("_", " ").replace("-", " ")
        for token in _RESONANCE_TOKEN_PATTERN.findall(text):
            if token in _CONCEPT_RESONANCE_STOP_WORDS:
                continue
            tokens.add(token)
    return tokens


def _idea_concept_tokens(idea: Idea) -> set[str]:
    return _extract_resonance_tokens(
        idea.id,
        idea.name,
        idea.description,
        idea.tags,
        [item.question for item in idea.open_questions],
    )


def _idea_domain_tokens(idea: Idea) -> set[str]:
    return _extract_resonance_tokens(idea.tags, idea.interfaces)


def _find_closest_graph_idea(idea_id: str, graph_ideas: list) -> Any | None:
    """Find the graph idea with the highest Jaccard word overlap to the given ID."""
    target_words = set(idea_id.replace("-", " ").replace("_", " ").lower().split()) - _FUZZY_STOP_WORDS
    if len(target_words) < 2:
        return None

    best_match = None
    best_score = 0.0
    for idea in graph_ideas:
        idea_words = set(idea.id.replace("-", " ").replace("_", " ").lower().split()) - _FUZZY_STOP_WORDS
        if not idea_words:
            continue
        overlap = len(target_words & idea_words)
        union = len(target_words | idea_words)
        score = overlap / union if union > 0 else 0
        if score > best_score and score >= 0.5:
            best_score = score
            best_match = idea
    return best_match
