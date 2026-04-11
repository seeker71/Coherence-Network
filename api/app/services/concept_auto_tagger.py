"""Concept auto-tagger -- matches ideas against the Living Codex ontology.

Extracts keywords from idea name + description, scores them against all
184 concepts (name, description, keywords), and tags each idea with the
top-scoring concepts.  No external models -- pure keyword overlap.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services import concept_service, idea_service

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stopword set (mirrors concept_service._extract_keywords)
# ---------------------------------------------------------------------------

_STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "that", "this", "it", "its", "they", "their", "we", "our", "you",
    "your", "i", "my", "he", "she", "his", "her", "which", "who", "what",
    "when", "where", "how", "not", "no", "so", "as", "if", "then",
}

# Minimum score to count as a match (0.0-1.0)
_MIN_SCORE = 0.05

# Maximum concepts to tag per idea
_MAX_TAGS = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text (stopword-free, deduplicated)."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        if w not in _STOPWORDS and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords


def _score_concept(concept: dict[str, Any], keywords: list[str]) -> float:
    """Score how well a concept matches a bag of keywords (0.0-1.0).

    Uses bidirectional matching:
    - Forward: fraction of idea keywords found in concept text
    - Reverse: fraction of concept keywords found in idea text
    The final score is the weighted combination, biased toward forward.
    """
    if not keywords:
        return 0.0

    concept_text = " ".join([
        concept.get("name", ""),
        concept.get("description", ""),
        " ".join(concept.get("keywords", [])),
    ]).lower()

    idea_text = " ".join(keywords)

    # Forward: how many idea keywords appear in concept text
    forward_hits = sum(1 for kw in keywords if kw in concept_text)
    forward_score = forward_hits / len(keywords) if keywords else 0.0

    # Reverse: how many concept keywords appear in idea text
    concept_kws = concept.get("keywords", [])
    if concept_kws:
        reverse_hits = sum(1 for ckw in concept_kws if ckw.lower() in idea_text)
        reverse_score = reverse_hits / len(concept_kws)
    else:
        reverse_score = 0.0

    # Exact name match bonus
    name_lower = concept.get("name", "").lower()
    name_bonus = 0.3 if name_lower in idea_text else 0.0

    score = (0.5 * forward_score) + (0.3 * reverse_score) + name_bonus
    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_concepts(
    idea_name: str,
    idea_description: str,
    max_results: int = _MAX_TAGS,
) -> list[dict[str, Any]]:
    """Return top matching concepts for the given idea text.

    Each result dict: {"concept_id": str, "concept_name": str, "score": float}
    """
    text = f"{idea_name} {idea_description}"
    keywords = _extract_keywords(text)
    if not keywords:
        return []

    all_concepts = concept_service.list_concepts(limit=9999, offset=0).get("items", [])

    scored: list[tuple[float, dict[str, Any]]] = []
    for c in all_concepts:
        score = _score_concept(c, keywords)
        if score >= _MIN_SCORE:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[dict[str, Any]] = []
    for score, c in scored[:max_results]:
        results.append({
            "concept_id": c["id"],
            "concept_name": c.get("name", c["id"]),
            "score": score,
        })
    return results


def tag_idea(
    idea_id: str,
    idea_name: str,
    idea_description: str,
) -> dict[str, Any]:
    """Match concepts for an idea and create concept-idea tags.

    Returns summary with idea_id, matched concepts, and count.
    """
    matches = match_concepts(idea_name, idea_description)
    if not matches:
        return {
            "idea_id": idea_id,
            "concepts_tagged": [],
            "count": 0,
        }

    concept_ids = [m["concept_id"] for m in matches]
    concept_service.tag_entity(
        entity_type="idea",
        entity_id=idea_id,
        concept_ids=concept_ids,
    )

    log.info("Auto-tagged idea %s with %d concepts: %s", idea_id, len(concept_ids), concept_ids)
    return {
        "idea_id": idea_id,
        "concepts_tagged": matches,
        "count": len(matches),
    }


def tag_all_ideas() -> dict[str, Any]:
    """Iterate all ideas in the portfolio and auto-tag each one.

    Returns aggregate stats: total ideas processed, total tags created,
    and per-idea results.
    """
    portfolio = idea_service.list_ideas(limit=9999, include_internal=False)
    ideas = portfolio.ideas

    total_tagged = 0
    results: list[dict[str, Any]] = []

    for idea in ideas:
        result = tag_idea(
            idea_id=idea.id,
            idea_name=idea.name,
            idea_description=idea.description,
        )
        if result["count"] > 0:
            total_tagged += 1
            results.append(result)

    log.info("Auto-tag-all complete: %d/%d ideas tagged", total_tagged, len(ideas))
    return {
        "ideas_processed": len(ideas),
        "ideas_tagged": total_tagged,
        "total_concept_links": sum(r["count"] for r in results),
        "results": results,
    }
