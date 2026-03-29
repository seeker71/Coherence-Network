"""Concept Translation Service — cross-view-synthesis from Living Codex.

Translates an idea or concept through a conceptual lens (worldview):
  scientific | economic | spiritual | artistic | philosophical

This is NOT machine translation of language. It is translation of conceptual
framework: finding analogous concepts in the target worldview by traversing
ontology resonance edges and axis similarity.

Algorithm:
1. Extract semantic tokens from the idea/concept (description keywords, tags, axes)
2. Find ontology concepts that resonate with those tokens
3. Filter to concepts whose axes align with the target lens
4. Score and rank bridging concepts by keyword overlap
5. Generate a natural-language summary framing the idea in that lens
"""

from __future__ import annotations

import re
from typing import Any

from app.services import concept_service

# ---------------------------------------------------------------------------
# Lens definitions
# ---------------------------------------------------------------------------

VALID_LENSES = frozenset({"scientific", "economic", "spiritual", "artistic", "philosophical"})

_LENS_META: dict[str, dict[str, Any]] = {
    "scientific": {
        "description": "Views the idea through empirical measurement, causal systems, and quantifiable phenomena.",
        "axis_keywords": ["physics", "causal", "temporal", "empirical", "system", "ucore", "speculative"],
        "concept_keywords": ["measure", "system", "energy", "flow", "structure", "network", "causal",
                             "process", "transform", "pattern", "feedback", "entropy", "order",
                             "force", "field", "wave", "quantum", "thermodynamic"],
    },
    "economic": {
        "description": "Views the idea through value exchange, resource allocation, and incentive structures.",
        "axis_keywords": ["exchange", "value", "resource", "production", "allocation", "incentive"],
        "concept_keywords": ["value", "exchange", "resource", "cost", "benefit", "trade", "market",
                             "capital", "invest", "return", "allocate", "optimize", "scarcity",
                             "utility", "incentive", "produce", "consume", "wealth"],
    },
    "spiritual": {
        "description": "Views the idea through meaning, sacred order, consciousness, and transcendent purpose.",
        "axis_keywords": ["tradition", "spiritual", "consciousness", "sacred", "divine", "archetypal"],
        "concept_keywords": ["spirit", "soul", "sacred", "divine", "consciousness", "meaning", "purpose",
                             "wisdom", "truth", "essence", "presence", "transcend", "unity",
                             "harmony", "love", "light", "source", "awareness", "being"],
    },
    "artistic": {
        "description": "Views the idea through form, beauty, expression, rhythm, and aesthetic perception.",
        "axis_keywords": ["aesthetic", "form", "expression", "rhythm", "visual", "creative", "artistic"],
        "concept_keywords": ["beauty", "form", "rhythm", "balance", "harmony", "express", "create",
                             "aesthetic", "visual", "design", "compose", "perceive", "feel",
                             "imagine", "metaphor", "symbol", "color", "texture", "pattern", "art"],
    },
    "philosophical": {
        "description": "Views the idea through questions of being, truth, ethics, knowledge, and existence.",
        "axis_keywords": ["epistemic", "ethical", "ontological", "logic", "reason", "philosophy"],
        "concept_keywords": ["truth", "being", "exist", "meaning", "ethics", "good", "reason",
                             "logic", "knowledge", "wisdom", "justice", "freedom", "mind",
                             "consciousness", "reality", "cause", "essence", "virtue", "principle"],
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Extract lowercase word tokens from text."""
    return re.findall(r"[a-z]+", text.lower())


def _score_concept_for_lens(concept: dict[str, Any], lens: str) -> float:
    """Score how well a concept fits a given lens (0.0–1.0)."""
    meta = _LENS_META[lens]
    lens_kws = set(meta["concept_keywords"])
    axis_kws = set(meta["axis_keywords"])

    tokens: set[str] = set()
    tokens.update(_tokenize(concept.get("name", "")))
    tokens.update(_tokenize(concept.get("description", "")))
    for kw in concept.get("keywords", []):
        tokens.update(_tokenize(kw))

    concept_axes = set(concept.get("axes", []))

    kw_overlap = len(tokens & lens_kws)
    axis_overlap = len(concept_axes & axis_kws)

    raw = kw_overlap * 0.15 + axis_overlap * 0.4
    return min(raw, 1.0)


def _find_bridging_concepts(
    source_tokens: set[str],
    lens: str,
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Find ontology concepts that bridge source tokens to the target lens."""
    all_concepts = concept_service._concepts  # type: ignore[attr-defined]
    meta = _LENS_META[lens]
    lens_kws = set(meta["concept_keywords"])

    scored = []
    for c in all_concepts:
        c_tokens: set[str] = set()
        c_tokens.update(_tokenize(c.get("name", "")))
        c_tokens.update(_tokenize(c.get("description", "")))
        for kw in c.get("keywords", []):
            c_tokens.update(_tokenize(kw))

        # Source resonance: how much does this concept overlap with source idea?
        source_overlap = len(source_tokens & c_tokens)
        # Lens affinity: how much does this concept map to the target lens?
        lens_score = _score_concept_for_lens(c, lens)

        if source_overlap == 0 and lens_score < 0.1:
            continue

        combined = (source_overlap * 0.4 + lens_score * 0.6) / max(source_overlap + 1, 1) * (source_overlap + lens_score)
        if combined > 0:
            scored.append((combined, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, c in scored[:max_results]:
        results.append({
            "id": c["id"],
            "name": c.get("name", c["id"]),
            "score": round(min(score / max(scored[0][0], 1e-9), 1.0), 3) if scored else 0.0,
            "axes": c.get("axes", []),
        })
    return results


def _generate_summary(
    name: str,
    description: str,
    lens: str,
    bridging: list[dict[str, Any]],
) -> str:
    """Generate a summary framing the idea in the given lens."""
    meta = _LENS_META[lens]
    bridge_names = [b["name"] for b in bridging[:3]]

    if lens == "scientific":
        core = (
            f"From a scientific perspective, '{name}' manifests as a measurable system. "
            f"Key structural elements—{', '.join(bridge_names) or 'process, flow, and feedback'}—"
            f"provide the empirical anchors: observable states, causal dependencies, and "
            f"quantifiable dynamics that can be modeled and tested."
        )
    elif lens == "economic":
        core = (
            f"Through an economic lens, '{name}' is a value-exchange system. "
            f"Resources and constraints—{', '.join(bridge_names) or 'value, cost, and exchange'}—"
            f"define the incentive landscape: who bears cost, who captures benefit, "
            f"and how marginal returns guide allocation decisions."
        )
    elif lens == "spiritual":
        core = (
            f"In a spiritual framing, '{name}' resonates with deeper meaning and sacred order. "
            f"Through {', '.join(bridge_names) or 'consciousness, wisdom, and unity'}, "
            f"the idea becomes a reflection of transcendent principles—"
            f"a pattern that connects individual expression to universal purpose."
        )
    elif lens == "artistic":
        core = (
            f"As an artistic expression, '{name}' takes form through rhythm, balance, and beauty. "
            f"Concepts like {', '.join(bridge_names) or 'form, rhythm, and expression'} "
            f"reveal the aesthetic texture: how the idea moves, what it evokes, "
            f"and how its composition communicates beyond analytical description."
        )
    else:  # philosophical
        core = (
            f"Philosophically, '{name}' opens questions of being and knowledge. "
            f"Drawing on {', '.join(bridge_names) or 'truth, reason, and existence'}, "
            f"the idea invites inquiry: What is its essence? Under what conditions does it hold? "
            f"What values and assumptions underpin its claims?"
        )

    return core


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
    """Translate an idea through a conceptual lens.

    Returns a ConceptTranslationResponse-shaped dict.
    """
    source_tokens: set[str] = set()
    source_tokens.update(_tokenize(idea_name))
    source_tokens.update(_tokenize(idea_description))
    for tag in idea_tags:
        source_tokens.update(_tokenize(tag))

    bridging = _find_bridging_concepts(source_tokens, view)
    summary = _generate_summary(idea_name, idea_description, view, bridging)
    meta = _LENS_META[view]

    return {
        "idea_id": idea_id,
        "view": view,
        "translation_kind": "concept_framing",
        "lens_description": meta["description"],
        "summary": summary,
        "bridging_concepts": bridging,
        "analogous_ideas": [],  # future: query graph for ideas with similar concept tags
    }


def translate_concept(
    concept_id: str,
    concept: dict[str, Any],
    from_lens: str,
    to_lens: str,
) -> dict[str, Any]:
    """Translate a concept from one lens to another.

    Returns a ConceptLensTranslationResponse-shaped dict.
    """
    source_tokens: set[str] = set()
    source_tokens.update(_tokenize(concept.get("name", "")))
    source_tokens.update(_tokenize(concept.get("description", "")))
    for kw in concept.get("keywords", []):
        source_tokens.update(_tokenize(kw))

    target_bridging = _find_bridging_concepts(source_tokens, to_lens)
    source_axes = concept.get("axes", [])

    # Also score source concept in from_lens to show context
    source_lens_score = _score_concept_for_lens(concept, from_lens)

    summary = _generate_summary(
        concept.get("name", concept_id),
        concept.get("description", ""),
        to_lens,
        target_bridging,
    )

    return {
        "concept_id": concept_id,
        "concept_name": concept.get("name", concept_id),
        "from_lens": from_lens,
        "to_lens": to_lens,
        "translation_kind": "concept_framing",
        "summary": summary,
        "source_axes": source_axes,
        "source_lens_score": round(source_lens_score, 3),
        "target_bridging_concepts": target_bridging,
    }
