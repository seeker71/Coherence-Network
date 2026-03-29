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
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.models.belief import BeliefAxis
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
    libertarian = "libertarian"
    engineer = "engineer"
    institutionalist = "institutionalist"
    entrepreneur = "entrepreneur"
    systemic = "systemic"


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
        "category": "discipline",
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
        "category": "discipline",
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
        "category": "worldview",
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
        "category": "discipline",
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
        "category": "discipline",
    },
    "libertarian": {
        "description": (
            "The libertarian / decentralist lens emphasizes individual sovereignty, voluntary cooperation, "
            "and resistance to coercion — freedom as a primary design constraint."
        ),
        "keywords": [
            "freedom", "sovereignty", "voluntary", "decentralization", "autonomy", "rights",
            "non-aggression", "consent", "peer", "permissionless", "censorship", "self-custody",
            "open", "neutral", "exit", "choice", "liberty", "minimal", "trustless",
        ],
        "axes": ["autonomy", "voluntary-cooperation", "anti-coercion"],
        "category": "worldview",
    },
    "engineer": {
        "description": (
            "The systems engineer lens prioritizes efficiency, scalability, reliability, and explicit trade-offs — "
            "what works under load and how to measure it."
        ),
        "keywords": [
            "efficiency", "scalability", "reliability", "latency", "throughput", "trade-off",
            "architecture", "abstraction", "interface", "testing", "observability", "sla",
            "performance", "robustness", "constraint", "optimization", "bottleneck", "metric",
        ],
        "axes": ["precision", "scalability", "measurement"],
        "category": "worldview",
    },
    "institutionalist": {
        "description": (
            "The institutional / policy lens foregrounds governance, compliance, precedent, and risk management — "
            "stability and accountability to collective rules."
        ),
        "keywords": [
            "governance", "compliance", "regulation", "policy", "risk", "precedent",
            "accountability", "oversight", "audit", "standard", "jurisdiction", "fiduciary",
            "stability", "mandate", "authority", "rule", "enforcement", "liability",
        ],
        "axes": ["governance", "risk-management", "precedent"],
        "category": "worldview",
    },
    "entrepreneur": {
        "description": (
            "The entrepreneur lens reads ideas as market opportunities: users, timing, monetization, "
            "and speed to validated learning."
        ),
        "keywords": [
            "opportunity", "market", "customer", "revenue", "growth", "pitch", "traction",
            "mvp", "go-to-market", "monetization", "competitive", "moat", "adoption", "pivot",
            "venture", "value proposition", "scale", "distribution", "founder",
        ],
        "axes": ["opportunity", "speed", "commercialization"],
        "category": "worldview",
    },
    "systemic": {
        "description": (
            "The systemic / complexity lens emphasizes feedback loops, emergence, unintended consequences, "
            "and leverage points — not just parts but couplings."
        ),
        "keywords": [
            "feedback", "emergence", "leverage", "coupling", "unintended", "second-order",
            "complexity", "adaptation", "ecosystem", "boundary", "stock", "flow", "delay",
            "nonlinear", "resilience", "path dependence", "holon", "interaction",
        ],
        "axes": ["feedback", "emergence", "leverage"],
        "category": "worldview",
    },
}

# Concept keywords that map well to each lens (used for bridging)
_LENS_CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "scientific": ["system", "energy", "entropy", "flow", "structure", "pattern", "causal"],
    "economic": ["value", "cost", "efficiency", "resource", "capital", "exchange"],
    "spiritual": ["harmony", "unity", "consciousness", "meaning", "resonance", "sacred"],
    "artistic": ["form", "beauty", "expression", "rhythm", "composition", "aesthetic"],
    "philosophical": ["truth", "being", "identity", "ethics", "existence", "knowledge"],
    "libertarian": ["freedom", "autonomy", "voluntary", "decentralization", "rights", "sovereignty"],
    "engineer": ["efficiency", "scalability", "reliability", "architecture", "metric", "optimization"],
    "institutionalist": ["governance", "compliance", "risk", "policy", "precedent", "accountability"],
    "entrepreneur": ["opportunity", "market", "revenue", "growth", "traction", "customer"],
    "systemic": ["feedback", "emergence", "leverage", "complexity", "coupling", "resilience"],
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


# BeliefAxis-aligned weights for resonance_delta (spec-169 / spec-181 bridge)
_LENS_BELIEF_VECTORS: dict[str, dict[str, float]] = {
    "scientific": {"scientific": 0.95, "systemic": 0.45, "pragmatic": 0.5, "spiritual": 0.1, "holistic": 0.2, "relational": 0.15},
    "economic": {"pragmatic": 0.85, "scientific": 0.35, "relational": 0.4, "systemic": 0.3, "spiritual": 0.1, "holistic": 0.2},
    "spiritual": {"spiritual": 0.95, "holistic": 0.75, "relational": 0.5, "systemic": 0.25, "scientific": 0.15, "pragmatic": 0.2},
    "artistic": {"holistic": 0.7, "spiritual": 0.45, "relational": 0.55, "scientific": 0.2, "pragmatic": 0.25, "systemic": 0.2},
    "philosophical": {"scientific": 0.4, "spiritual": 0.5, "holistic": 0.45, "relational": 0.35, "systemic": 0.4, "pragmatic": 0.35},
    "libertarian": {"pragmatic": 0.75, "relational": 0.35, "scientific": 0.25, "spiritual": 0.2, "holistic": 0.2, "systemic": 0.3},
    "engineer": {"scientific": 0.9, "systemic": 0.75, "pragmatic": 0.85, "relational": 0.25, "spiritual": 0.1, "holistic": 0.25},
    "institutionalist": {"relational": 0.7, "holistic": 0.45, "systemic": 0.55, "pragmatic": 0.5, "scientific": 0.35, "spiritual": 0.2},
    "entrepreneur": {"pragmatic": 0.95, "relational": 0.55, "scientific": 0.35, "spiritual": 0.15, "holistic": 0.3, "systemic": 0.4},
    "systemic": {"systemic": 0.95, "holistic": 0.6, "scientific": 0.55, "relational": 0.4, "spiritual": 0.25, "pragmatic": 0.45},
}


def list_all_lens_ids() -> list[str]:
    """Return every registered lens id (enum values plus any operator-registered lenses)."""
    builtin = {e.value for e in TranslateLens}
    builtin |= set(_LENS_META.keys())
    return sorted(builtin)


def register_lens_definition(
    lens_id: str,
    name: str,
    description: str,
    archetype_axes: dict[str, float],
) -> None:
    """Register or replace an operator-defined lens (mutates in-memory registries)."""
    valid_axes = {a.value for a in BeliefAxis}
    axes_labels = [k for k in archetype_axes if k in valid_axes]
    kw_extra = [a for a in axes_labels]
    _LENS_META[lens_id] = {
        "description": f"{name}. {description}",
        "keywords": _tokenize(description) + kw_extra,
        "axes": axes_labels or ["custom"],
        "category": "custom",
        "display_name": name,
        "archetype_axes": {k: float(v) for k, v in archetype_axes.items() if k in valid_axes},
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    merged_kw = _tokenize(description) + kw_extra
    _LENS_CONCEPT_KEYWORDS[lens_id] = list(dict.fromkeys(_LENS_CONCEPT_KEYWORDS.get(lens_id, []) + merged_kw))[:32]
    _LENS_BELIEF_VECTORS[lens_id] = {k: float(v) for k, v in archetype_axes.items() if k in valid_axes}


def get_lens_meta(lens_id: str) -> dict[str, Any] | None:
    """Return metadata dict for a lens id, or None if unknown."""
    return _LENS_META.get(lens_id)


def get_lens_belief_vector(lens_id: str) -> dict[str, float]:
    """BeliefAxis weights used for resonance_delta (may be empty for unknown lenses)."""
    return dict(_LENS_BELIEF_VECTORS.get(lens_id, {}))


def score_text_pov_affinity(text: str, lens_id: str) -> float:
    """Score how strongly plain text aligns with a POV lens (0.0–1.0) for news filtering."""
    meta = _LENS_META.get(lens_id)
    if not meta:
        return 0.0
    tokens = set(_tokenize(text))
    kws = set()
    for w in meta.get("keywords", []):
        kws.update(_tokenize(w))
    kws.update(_LENS_CONCEPT_KEYWORDS.get(lens_id, []))
    if not tokens or not kws:
        return 0.05
    overlap = len(tokens & kws) / max(1, min(len(tokens), len(kws)))
    return round(min(1.0, 0.08 + overlap * 0.92), 4)


def compute_belief_resonance_delta(contributor_axes: dict[str, float], lens_id: str) -> float:
    """Map contributor worldview axes to a [-1.0, 1.0] delta vs this lens profile."""
    lv = _LENS_BELIEF_VECTORS.get(lens_id)
    if not lv:
        return 0.0
    keys = set(lv.keys()) | set(contributor_axes.keys())
    dot = sum(float(contributor_axes.get(k, 0.0)) * float(lv.get(k, 0.0)) for k in keys)
    nc = sum(float(contributor_axes.get(k, 0.0)) ** 2 for k in keys) ** 0.5
    nl = sum(float(lv.get(k, 0.0)) ** 2 for k in keys) ** 0.5
    if nc < 1e-9 or nl < 1e-9:
        return 0.0
    cos = dot / (nc * nl)
    return round(max(-1.0, min(1.0, cos * 2.0 - 1.0)), 4)


def build_emphasis_tags(idea_name: str, idea_desc: str, tags: list[str], lens_id: str) -> list[str]:
    """Top emphasis tokens for spec-181 IdeaTranslation."""
    meta = _LENS_META.get(lens_id, {})
    idea_tokens = set(_tokenize(f"{idea_name} {idea_desc} {' '.join(tags)}"))
    lens_kws = set(_LENS_CONCEPT_KEYWORDS.get(lens_id, []))
    for w in meta.get("keywords", [])[:40]:
        lens_kws.update(_tokenize(w))
    hits = sorted(idea_tokens & lens_kws)[:8]
    if not hits:
        return (meta.get("axes") or [])[:5]
    return hits[:8]


def build_risk_opportunity_framing(idea_name: str, lens_id: str) -> tuple[str, str]:
    """Short risk vs opportunity sentences for a lens (deterministic, no LLM)."""
    templates: dict[str, tuple[str, str]] = {
        "libertarian": (
            "Risk: centralized choke points or coercive defaults could undermine voluntary participation.",
            "Opportunity: expand permissionless entry and user-held guarantees that reduce reliance on trusted third parties.",
        ),
        "engineer": (
            "Risk: operational complexity, failure modes, and unclear SLOs under production load.",
            "Opportunity: measurable reliability gains and cleaner interfaces that reduce cost-to-change.",
        ),
        "institutionalist": (
            "Risk: governance gaps, compliance exposure, or ambiguous accountability under scrutiny.",
            "Opportunity: clearer rules, auditability, and precedents that make adoption safer for institutions.",
        ),
        "entrepreneur": (
            "Risk: slow iteration, weak distribution, or unclear monetization path versus alternatives.",
            "Opportunity: sharper wedge, faster learning loops, and a story that compels early adopters.",
        ),
        "scientific": (
            "Risk: hypotheses outrun evidence; metrics may not capture the phenomenon that matters.",
            "Opportunity: tighter measurement loops and clearer causal claims grounded in reproducible data.",
        ),
        "economic": (
            "Risk: hidden costs, misaligned incentives, or unsustainable subsidy of the wrong behavior.",
            "Opportunity: clearer value capture and incentive design that makes honest participation the best move.",
        ),
        "spiritual": (
            "Risk: instrumentalizing meaning without care for the humans in the loop.",
            "Opportunity: deepen coherence between stated purpose and lived practice for participants.",
        ),
        "artistic": (
            "Risk: style without substance; novelty that obscures the underlying problem.",
            "Opportunity: expressive clarity that makes the idea memorable and emotionally legible.",
        ),
        "philosophical": (
            "Risk: endless abstraction without grounding in concrete decisions.",
            "Opportunity: sharper definitions and ethical clarity that reduce avoidable conflict.",
        ),
        "systemic": (
            "Risk: second-order effects and coupling surprises; local fixes that create global failure.",
            "Opportunity: identify leverage points where small changes shift the whole system trajectory.",
        ),
    }
    risk, opp = templates.get(
        lens_id,
        (
            f"Risk: '{idea_name}' may face friction where assumptions meet reality.",
            f"Opportunity: reframe '{idea_name}' so the next step is obvious to stakeholders aligned with this lens.",
        ),
    )
    return risk, opp
</think>


<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
Read
