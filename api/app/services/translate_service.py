"""Concept translation service — reframe ideas and concepts through worldview lenses.

Implements: cross-view-synthesis from Living Codex.
Any idea can be viewed through different lenses: scientific, economic, spiritual,
artistic, philosophical. Uses ontology concept graph + keyword/tag signals to
generate conceptual framings — not machine translation of language.

API: /api/ideas/{id}/translate?view=<lens>
     /api/concepts/{id}/translate?from=<lens>&to=<lens>
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from app.services import concept_service


# ---------------------------------------------------------------------------
# Lens definitions
# ---------------------------------------------------------------------------

class TranslateLens(str, Enum):
    scientific = "scientific"
    economic = "economic"
    spiritual = "spiritual"
    artistic = "artistic"
    philosophical = "philosophical"


# ---------------------------------------------------------------------------
# Lens metadata — description and keyword vocabularies
# ---------------------------------------------------------------------------

_LENS_META: dict[str, dict[str, Any]] = {
    "scientific": {
        "description": "The scientific lens examines measurable patterns, causal mechanisms, and empirical evidence.",
        "keywords": [
            "measurement", "system", "energy", "flow", "network", "feedback", "entropy",
            "data", "model", "hypothesis", "experiment", "causal", "thermodynamic",
            "algorithm", "optimization", "signal", "structure", "pattern", "analysis",
            "physics", "chemistry", "biology", "computation", "metric", "variable",
        ],
        "axes": ["analytical", "causal", "empirical", "systematic"],
    },
    "economic": {
        "description": "The economic lens focuses on value, incentives, costs, and allocation of scarce resources.",
        "keywords": [
            "value", "cost", "incentive", "allocation", "market", "resource", "trade",
            "efficiency", "capital", "investment", "return", "utility", "scarcity",
            "exchange", "production", "consumption", "revenue", "profit", "risk",
            "strategy", "supply", "demand", "benefit", "budget", "portfolio",
        ],
        "axes": ["transactional", "incentive", "value-driven", "strategic"],
    },
    "spiritual": {
        "description": "The spiritual lens explores meaning, consciousness, resonance, and transcendent connection.",
        "keywords": [
            "meaning", "purpose", "consciousness", "resonance", "spirit", "soul",
            "harmony", "sacred", "presence", "awareness", "wholeness", "unity",
            "meditation", "prayer", "ritual", "intention", "vibration", "frequency",
            "sacred geometry", "divine", "transcendence", "being", "essence", "breath",
        ],
        "axes": ["transcendent", "resonant", "holistic", "contemplative"],
    },
    "artistic": {
        "description": "The artistic lens sees form, beauty, expression, rhythm, and aesthetic composition.",
        "keywords": [
            "form", "beauty", "expression", "composition", "rhythm", "color", "texture",
            "harmony", "contrast", "balance", "aesthetic", "design", "creativity",
            "craft", "narrative", "symbol", "metaphor", "visual", "sound", "gesture",
            "pattern", "emergence", "play", "imagination", "style", "medium",
        ],
        "axes": ["expressive", "aesthetic", "compositional", "imaginative"],
    },
    "philosophical": {
        "description": "The philosophical lens interrogates existence, truth, ethics, and foundational assumptions.",
        "keywords": [
            "existence", "truth", "ethics", "identity", "reality", "knowledge",
            "assumption", "axiom", "value", "being", "becoming", "freedom", "agency",
            "causality", "necessity", "contingency", "meaning", "justice", "logic",
            "ontology", "epistemology", "phenomenology", "dialectic", "metaphysics",
        ],
        "axes": ["reflective", "dialectic", "normative", "foundational"],
    },
}

# Concept keywords that map well to each lens (used for bridging)
_LENS_CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "scientific": ["system", "energy", "entropy", "flow", "structure", "pattern", "causal"],
    "economic": ["value", "cost", "efficiency", "resource", "capital", "exchange"],
    "spiritual": ["harmony", "unity", "consciousness", "meaning", "resonance", "sacred"],
    "artistic": ["form", "beauty", "expression", "rhythm", "composition", "aesthetic"],
    "philosophical": ["truth", "being", "identity", "ethics", "existence", "knowledge"],
}


# ---------------------------------------------------------------------------
# Core translation logic
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Extract lowercase word tokens from text."""
    return re.findall(r"[a-z]+", text.lower())


def _score_concept_for_lens(concept: dict[str, Any], lens: str) -> float:
    """Score how well a concept bridges to a given lens (0.0–1.0)."""
    target_kws = set(_LENS_CONCEPT_KEYWORDS.get(lens, []))
    if not target_kws:
        return 0.1

    tokens: set[str] = set()
    tokens.update(_tokenize(concept.get("name", "")))
    tokens.update(_tokenize(concept.get("description", "")))
    for kw in concept.get("keywords", []):
        tokens.update(_tokenize(kw))

    overlap = len(tokens & target_kws)
    max_possible = min(len(target_kws), max(1, len(tokens)))
    raw = overlap / max_possible
    return round(min(1.0, raw + 0.05), 3)  # small baseline boost


def _find_bridging_concepts(
    text: str,
    tags: list[str],
    lens: str,
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Find ontology concepts that bridge the idea text to the target lens."""
    lens_kws = set(_LENS_CONCEPT_KEYWORDS.get(lens, []))
    idea_tokens = set(_tokenize(text))
    idea_tokens.update(_tokenize(" ".join(tags)))

    scored: list[tuple[float, dict[str, Any]]] = []

    for concept in concept_service._concepts:
        concept_tokens: set[str] = set()
        concept_tokens.update(_tokenize(concept.get("name", "")))
        concept_tokens.update(_tokenize(concept.get("description", "")))
        for kw in concept.get("keywords", []):
            concept_tokens.update(_tokenize(kw))

        # Idea-to-concept affinity: shared tokens
        idea_affinity = len(idea_tokens & concept_tokens) / max(1, len(concept_tokens))

        # Concept-to-lens affinity
        lens_affinity = len(lens_kws & concept_tokens) / max(1, len(lens_kws))

        score = round(0.5 * idea_affinity + 0.5 * lens_affinity, 3)
        if score > 0.0:
            scored.append((score, concept))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = []
    for score, concept in scored[:max_results]:
        result.append({
            "id": concept.get("id"),
            "name": concept.get("name"),
            "score": score,
            "axes": concept.get("axes", []),
        })
    return result


def _find_analogous_ideas(lens: str) -> list[dict[str, Any]]:
    """Placeholder: returns empty list (future: query graph for related ideas by lens)."""
    return []


def _build_summary(idea_name: str, idea_desc: str, tags: list[str], lens: str) -> str:
    """Generate a short framing summary for the lens without calling an LLM."""
    meta = _LENS_META.get(lens, {})
    lens_desc = meta.get("description", f"The {lens} lens.")
    lens_kws = _LENS_CONCEPT_KEYWORDS.get(lens, [])

    # Find which idea tokens resonate with this lens
    idea_tokens = set(_tokenize(idea_name + " " + idea_desc + " " + " ".join(tags)))
    resonant_tokens = sorted(idea_tokens & set(lens_kws))

    if resonant_tokens:
        resonant_phrase = ", ".join(resonant_tokens[:3])
        return (
            f"{lens_desc} "
            f"Viewed through this lens, '{idea_name}' connects through concepts like {resonant_phrase}, "
            f"revealing its {lens} dimensions."
        )
    return (
        f"{lens_desc} "
        f"Viewed through this lens, '{idea_name}' can be reframed in {lens} terms "
        f"by attending to the underlying patterns that align with {lens} ways of knowing."
    )


def _build_concept_summary(concept_name: str, concept_desc: str, from_lens: str, to_lens: str) -> str:
    """Build a summary for concept-to-concept lens translation."""
    from_meta = _LENS_META.get(from_lens, {})
    to_meta = _LENS_META.get(to_lens, {})
    from_desc = from_meta.get("description", f"The {from_lens} lens.")
    to_desc = to_meta.get("description", f"The {to_lens} lens.")

    from_kws = set(_LENS_CONCEPT_KEYWORDS.get(from_lens, []))
    to_kws = set(_LENS_CONCEPT_KEYWORDS.get(to_lens, []))
    concept_tokens = set(_tokenize(concept_name + " " + concept_desc))

    from_resonant = sorted(concept_tokens & from_kws)[:2]
    to_resonant = sorted(concept_tokens & to_kws)[:2]

    from_phrase = f" (resonating with: {', '.join(from_resonant)})" if from_resonant else ""
    to_phrase = f" (bridging to: {', '.join(to_resonant)})" if to_resonant else ""

    return (
        f"'{concept_name}' in the {from_lens} frame{from_phrase} "
        f"translates to the {to_lens} frame{to_phrase}. "
        f"{to_desc}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_idea(
    idea_id: str,
    idea_name: str,
    idea_description: str,
    idea_tags: list[str],
    view: str,
) -> dict[str, Any]:
    """Translate an idea's conceptual framing to a target lens.

    Returns a dict with: idea_id, view, translation_kind, lens_description,
    summary, bridging_concepts, analogous_ideas.
    """
    text = f"{idea_name} {idea_description}"
    meta = _LENS_META.get(view, {})

    bridging = _find_bridging_concepts(text, idea_tags, view, max_results=8)
    summary = _build_summary(idea_name, idea_description, idea_tags, view)

    return {
        "idea_id": idea_id,
        "view": view,
        "translation_kind": "concept_framing",
        "lens_description": meta.get("description", f"The {view} lens."),
        "summary": summary,
        "bridging_concepts": bridging,
        "analogous_ideas": _find_analogous_ideas(view),
        "source_axes": meta.get("axes", []),
    }


def translate_concept(
    concept_id: str,
    concept_name: str,
    concept_description: str,
    from_lens: str,
    to_lens: str,
) -> dict[str, Any]:
    """Translate a concept from one lens framing to another.

    Returns a dict with: concept_id, from_lens, to_lens, translation_kind,
    summary, source_axes, target_bridging_concepts.
    """
    text = f"{concept_name} {concept_description}"
    from_meta = _LENS_META.get(from_lens, {})
    to_meta = _LENS_META.get(to_lens, {})

    # Find concepts that bridge from_lens to to_lens for this concept
    target_bridging = _find_bridging_concepts(text, [], to_lens, max_results=6)
    summary = _build_concept_summary(concept_name, concept_description, from_lens, to_lens)

    return {
        "concept_id": concept_id,
        "from_lens": from_lens,
        "to_lens": to_lens,
        "translation_kind": "concept_framing",
        "summary": summary,
        "source_axes": from_meta.get("axes", []),
        "target_axes": to_meta.get("axes", []),
        "target_bridging_concepts": target_bridging,
    }
