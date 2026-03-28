"""Concept framing translation — view ideas/concepts through scientific, economic, spiritual, etc.

Uses the Living Codex ontology (axes, keywords) plus idea↔idea concept resonance.
This is not machine translation of natural language; it reframes conceptual overlap.
"""

from __future__ import annotations

import re
from typing import Final

from app.services import concept_service, idea_service
from app.models.translation import (
    AnalogousIdeaRef,
    ConceptTranslationResponse,
    IdeaTranslationResponse,
    OntologyConceptRef,
)
from app.services.idea_service import _idea_concept_tokens

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")

VALID_LENSES: Final[frozenset[str]] = frozenset({
    "scientific",
    "economic",
    "spiritual",
    "artistic",
    "philosophical",
})

# Ontology axis ids (core-axes / concept.axes) preferred per lens.
LENS_PREFERRED_AXES: Final[dict[str, frozenset[str]]] = {
    "scientific": frozenset({
        "causal", "empirical", "informational", "systemic", "energetic",
        "spatial", "temporal", "rational",
    }),
    "economic": frozenset({
        "axiological", "relational", "pragmatic", "social", "network",
    }),
    "spiritual": frozenset({
        "spiritual", "consciousness", "contemplative", "mystical", "transcendent",
    }),
    "artistic": frozenset({"aesthetic"}),
    "philosophical": frozenset({
        "epistemological", "ontological", "rational", "metaphysical", "phenomenological",
    }),
}

LENS_DESCRIPTIONS: Final[dict[str, str]] = {
    "scientific": "Emphasizes measurement, mechanism, causality, and empirical structure.",
    "economic": "Emphasizes value, incentives, resources, trade-offs, and allocation.",
    "spiritual": "Emphasizes meaning, inner experience, sacred pattern, and contemplative depth.",
    "artistic": "Emphasizes form, beauty, composition, and aesthetic resonance.",
    "philosophical": "Emphasizes reasons, categories, being, and justification.",
}


def _blob_tokens(concept: dict) -> set[str]:
    parts: list[str] = [
        concept.get("name") or "",
        concept.get("description") or "",
    ]
    parts.extend(concept.get("keywords") or [])
    text = " ".join(parts).lower().replace("_", " ")
    return {t for t in _TOKEN_RE.findall(text) if len(t) >= 3}


def _axis_bonus(concept: dict, lens: str) -> float:
    axes = set(concept.get("axes") or [])
    preferred = LENS_PREFERRED_AXES.get(lens, frozenset())
    if axes & preferred:
        return 0.55
    return 0.15


def _score_ontology_concept(concept: dict, idea_tokens: set[str], lens: str) -> float:
    if not idea_tokens:
        return 0.0
    blob = _blob_tokens(concept)
    hits = len(idea_tokens & blob)
    overlap = hits / max(len(idea_tokens), 1)
    bonus = _axis_bonus(concept, lens)
    raw = min(1.0, overlap * 0.65 + bonus * 0.35)
    return round(raw, 4)


def _list_all_concepts() -> list[dict]:
    total = concept_service.get_stats().get("concepts", 0)
    batch = max(50, min(total + 10, 20000))
    return concept_service.list_concepts(limit=batch, offset=0).get("items", [])


def translate_idea(idea_id: str, view: str, *, limit_concepts: int = 8) -> IdeaTranslationResponse | None:
    """Reframe an idea through a lens using ontology bridges + cross-domain resonance."""
    if view not in VALID_LENSES:
        raise ValueError(f"Unsupported view {view!r}")
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return None
    tokens = _idea_concept_tokens(idea)
    scored: list[tuple[float, dict]] = []
    for c in _list_all_concepts():
        s = _score_ontology_concept(c, tokens, view)
        if s <= 0.0:
            continue
        scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    bridging: list[OntologyConceptRef] = []
    for s, c in scored[: max(1, limit_concepts)]:
        bridging.append(
            OntologyConceptRef(
                id=c["id"],
                name=c.get("name") or c["id"],
                score=s,
                axes=list(c.get("axes") or []),
            )
        )

    resonance = idea_service.get_concept_resonance_matches(idea_id, limit=5, min_score=0.04)
    analogous: list[AnalogousIdeaRef] = []
    if resonance:
        for m in resonance.matches:
            analogous.append(
                AnalogousIdeaRef(
                    idea_id=m.idea_id,
                    name=m.name,
                    resonance_score=m.resonance_score,
                    cross_domain=m.cross_domain,
                )
            )

    names = ", ".join(b.name for b in bridging[:4]) if bridging else "general patterns in the ontology"
    analogy = f" Cross-domain analogies include «{analogous[0].name}»." if analogous else ""
    summary = (
        f"Through the {view} lens: «{idea.name}» maps onto anchors such as {names}. "
        f"This is conceptual framing (not word-for-word translation).{analogy}"
    ).strip()

    return IdeaTranslationResponse(
        idea_id=idea.id,
        view=view,
        summary=summary,
        lens_description=LENS_DESCRIPTIONS[view],
        bridging_concepts=bridging,
        analogous_ideas=analogous,
    )


def _score_concept_for_lens(concept: dict, lens: str) -> float:
    axes = set(concept.get("axes") or [])
    preferred = LENS_PREFERRED_AXES.get(lens, frozenset())
    hit = len(axes & preferred)
    return min(1.0, 0.2 + 0.2 * hit)


def translate_concept(
    concept_id: str,
    from_lens: str,
    to_lens: str,
    *,
    limit: int = 8,
) -> ConceptTranslationResponse | None:
    """Find ontology neighbours that express the same cluster in the target lens."""
    if from_lens not in VALID_LENSES or to_lens not in VALID_LENSES:
        raise ValueError("Invalid lens")
    if from_lens == to_lens:
        raise ValueError("from_lens and to_lens must differ")
    src = concept_service.get_concept(concept_id)
    if src is None:
        return None

    src_tokens = _blob_tokens(src)
    parents = set(src.get("parentConcepts") or [])
    scored: list[tuple[float, dict]] = []
    for c in _list_all_concepts():
        if c["id"] == concept_id:
            continue
        shared_parents = parents & set(c.get("parentConcepts") or [])
        token_hits = len(src_tokens & _blob_tokens(c))
        if not shared_parents and token_hits < 1:
            continue
        structure = 0.35 * (1.0 if shared_parents else 0.0) + 0.35 * min(1.0, token_hits / max(len(src_tokens), 1))
        lens_score = _score_concept_for_lens(c, to_lens)
        s = round(min(1.0, structure * 0.5 + lens_score * 0.5), 4)
        if s <= 0.0:
            continue
        scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    targets: list[OntologyConceptRef] = []
    for s, c in scored[: max(1, limit)]:
        targets.append(
            OntologyConceptRef(
                id=c["id"],
                name=c.get("name") or c["id"],
                score=s,
                axes=list(c.get("axes") or []),
            )
        )

    summary = (
        f"From {from_lens} toward {to_lens}: «{src.get('name', concept_id)}» — "
        f"bridging nodes include {targets[0].name if targets else 'nearby ontology entries'} "
        f"(same parent cluster or keyword overlap, re-weighted for the target lens)."
    )

    return ConceptTranslationResponse(
        concept_id=concept_id,
        from_lens=from_lens,
        to_lens=to_lens,
        summary=summary,
        source_axes=list(src.get("axes") or []),
        target_bridging_concepts=targets,
    )
