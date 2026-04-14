"""Frequency scoring engine — measures how "alive" vs "institutional" text reads.

Approach: semantic frequency markers weighted by signal strength.

Each word/phrase carries a frequency signal — some toward living experience,
some toward institutional distance. This isn't a banned-word list; it's a
measurement of the overall texture. A concept file that scores 0.85 might
still contain the word "management" once (describing an external system) —
the overall frequency carries it.

The markers are derived from studying what distinguishes the purest Living
Collective writing (The Feeling sections) from institutional text. They
capture patterns like:
- Sensory/embodied language (warmth, breath, soil, hands) → living
- Institutional framing (program, compliance, management, protocol) → institutional
- Relational language (together, shared, between, held) → living
- Distancing language (services, clients, stakeholders, administered) → institutional
- Natural metaphor (root, flow, seed, compost, weave) → living
- Mechanical metaphor (system, process, framework, pipeline) → institutional

Score: 0.0 = pure institutional, 1.0 = pure living.
Most concept files should score 0.65-0.85.
"""

from __future__ import annotations

import math
import re
from typing import Any

# ---------------------------------------------------------------------------
# Frequency markers — signal strength from -1.0 (institutional) to +1.0 (living)
#
# These are not banned words. They're measurements of where a word sits
# on the frequency spectrum. A text's score is the weighted average of
# all its markers, shifted by the proportion of unmarked (neutral) text.
# ---------------------------------------------------------------------------

_MARKERS: dict[str, float] = {
    # ── Strong living signals (0.7 - 1.0) ──
    # Sensory/embodied
    "warmth": 0.9, "breath": 0.9, "heartbeat": 0.95, "pulse": 0.85,
    "hands": 0.8, "barefoot": 0.9, "soil": 0.85, "roots": 0.8,
    "fire": 0.75, "dawn": 0.8, "dusk": 0.75, "moonlight": 0.7,
    "womb": 0.85, "seeds": 0.8, "harvest": 0.75, "blossoms": 0.8,
    "fragrance": 0.8, "silence": 0.85, "stillness": 0.9,
    "murmur": 0.8, "whisper": 0.8, "singing": 0.8, "humming": 0.8,

    # Relational/communal
    "together": 0.75, "shared": 0.7, "gathering": 0.8, "circle": 0.8,
    "belonging": 0.85, "intimacy": 0.85, "embrace": 0.8,
    "tenderness": 0.9, "trust": 0.75, "ceremony": 0.85,
    "rhythm": 0.8, "resonance": 0.85, "attunement": 0.9,
    "offering": 0.85, "gratitude": 0.8, "blessing": 0.8,
    "elders": 0.8, "children": 0.7, "ancestors": 0.85,

    # Natural metaphor
    "compost": 0.85, "composting": 0.85, "mycelium": 0.9,
    "mycorrhizal": 0.9, "weave": 0.8, "weaving": 0.8,
    "ripening": 0.9, "deepening": 0.8, "unfolding": 0.85,
    "emergence": 0.8, "organic": 0.7, "flow": 0.7,
    "meadow": 0.8, "forest": 0.75, "river": 0.75, "spring": 0.7,
    "tending": 0.85, "stewardship": 0.8, "custodianship": 0.85,
    "nourish": 0.85, "nourishing": 0.85, "nourishment": 0.8,

    # Living Collective vocabulary
    "frequency": 0.7, "coherence": 0.75, "field": 0.65,
    "wholeness": 0.85, "sacred": 0.8, "spiraling": 0.8,
    "overflow": 0.8, "callings": 0.85, "vitality": 0.8,

    # ── Moderate living signals (0.3 - 0.7) ──
    "community": 0.6, "garden": 0.65, "kitchen": 0.55,
    "hearth": 0.75, "sanctuary": 0.7, "nest": 0.7,
    "clearing": 0.7, "path": 0.6, "walk": 0.6, "stone": 0.55,
    "wood": 0.55, "clay": 0.6, "earth": 0.65, "water": 0.55,
    "sun": 0.6, "wind": 0.55, "rain": 0.6, "snow": 0.55,
    "music": 0.65, "dance": 0.7, "play": 0.65, "laughter": 0.75,
    "tears": 0.7, "grief": 0.65, "joy": 0.7, "wonder": 0.75,
    "presence": 0.7, "listening": 0.7, "witness": 0.75,
    "invitation": 0.7, "gift": 0.7, "abundance": 0.7,

    # ── Moderate institutional signals (-0.3 to -0.7) ──
    "system": -0.3, "process": -0.35, "framework": -0.4,
    "methodology": -0.5, "implementation": -0.45, "infrastructure": -0.3,
    "optimize": -0.5, "efficiency": -0.4, "metrics": -0.6,
    "assessment": -0.5, "evaluation": -0.55, "audit": -0.6,
    "budget": -0.4, "funding": -0.35, "investment": -0.3,
    "facility": -0.5, "institution": -0.6, "organization": -0.4,
    "department": -0.6, "committee": -0.5, "board": -0.4,
    "policy": -0.55, "procedure": -0.5, "protocol": -0.55,
    "schedule": -0.35, "deadline": -0.45, "target": -0.4,

    # ── Strong institutional signals (-0.7 to -1.0) ──
    "management": -0.8, "manager": -0.8, "administered": -0.85,
    "compliance": -0.9, "enforcement": -0.85, "mandate": -0.8,
    "stakeholder": -0.85, "stakeholders": -0.85,
    "clients": -0.7, "patients": -0.7, "users": -0.5,
    "revenue": -0.75, "profit": -0.7, "monetize": -0.85,
    "deliverables": -0.9, "kpi": -0.9, "kpis": -0.9,
    "intervention": -0.65, "treatment": -0.55, "diagnosis": -0.6,
    "disorder": -0.7, "dysfunction": -0.65, "deficiency": -0.6,
    "supervision": -0.7, "surveillance": -0.85, "monitoring": -0.45,
    "approval": -0.6, "authorization": -0.65, "certification": -0.55,
    "sanitation": -0.6, "disposal": -0.5, "waste": -0.35,
    "employee": -0.75, "staff": -0.65, "personnel": -0.7,
    "regulation": -0.6, "regulatory": -0.6, "governed": -0.5,
}

# Phrase markers (multi-word — checked before word tokenization)
_PHRASE_MARKERS: dict[str, float] = {
    "sitting by a fire": 0.95,
    "hands in the soil": 0.95,
    "the field": 0.6,
    "the pulse": 0.8,
    "living together": 0.85,
    "shared meal": 0.85,
    "fire circle": 0.9,
    "morning circle": 0.85,
    "held by": 0.8,
    "held in": 0.75,
    "how it lives": 0.85,
    "what nature teaches": 0.85,
    "mental health": -0.75,
    "elder care": -0.7,
    "health department": -0.85,
    "management system": -0.8,
    "service delivery": -0.9,
    "care facility": -0.85,
    "treatment plan": -0.8,
    "business model": -0.8,
    "revenue stream": -0.85,
    "change management": -0.9,
    "project management": -0.9,
    "risk assessment": -0.85,
    "quality assurance": -0.85,
    "key performance": -0.9,
    "action items": -0.85,
}

_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(
    r'(?<=[.!?…])\s+(?=[A-Z\u201c"])'
    r'|(?<=\n)\s*(?=\S)',
)


def _split_sentences(text: str) -> list[str]:
    raw = _SENT_RE.split(text.strip())
    sentences = []
    for s in raw:
        s = s.strip()
        if not s or s.startswith("![") or s.startswith("#") or s.startswith("→"):
            continue
        if len(s) >= 15:
            sentences.append(s)
    return sentences if sentences else [text.strip()]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_NEGATION_PATTERNS = re.compile(
    r"\b(not?|no|never|without|isn't|aren't|wasn't|weren't|don't|doesn't|didn't|"
    r"won't|wouldn't|can't|cannot|shouldn't|nothing|neither|nor)\b",
    re.IGNORECASE,
)


def _score_sentence(text: str) -> tuple[float, list[tuple[str, float]]]:
    """Score a single sentence. Returns (score, [(marker, signal), ...])."""
    lower = text.lower()
    signals: list[tuple[str, float]] = []
    total_signal = 0.0
    total_weight = 0.0

    # Detect negation — when institutional words are used to REJECT them,
    # the sentence is actually living-frequency (e.g. "No management layer",
    # "Not surveillance", "without a committee deciding")
    has_negation = bool(_NEGATION_PATTERNS.search(lower))

    # Check phrase markers first
    for phrase, signal in _PHRASE_MARKERS.items():
        if phrase in lower:
            # Flip institutional signals in negated contexts
            effective_signal = -signal if (has_negation and signal < 0) else signal
            weight = abs(signal) * len(phrase.split())
            signals.append((phrase, effective_signal))
            total_signal += effective_signal * weight
            total_weight += weight

    # Then word markers
    words = _WORD_RE.findall(lower)
    for word in words:
        if word in _MARKERS:
            signal = _MARKERS[word]
            # Flip institutional signals in negated contexts
            effective_signal = -signal if (has_negation and signal < 0) else signal
            weight = abs(signal)
            signals.append((word, effective_signal))
            total_signal += effective_signal * weight
            total_weight += weight

    if total_weight == 0:
        # No markers found — neutral (slightly above center because
        # plain descriptive prose is closer to living than institutional)
        return 0.55, []

    # Raw score: weighted mean of signals, range [-1, 1]
    raw = total_signal / total_weight

    # Map [-1, 1] → [0, 1] with sigmoid-like compression
    score = 1 / (1 + math.exp(-3 * raw))

    return round(score, 4), signals


def score_frequency(text: str) -> dict:
    """Score text frequency: 0.0 = pure institutional, 1.0 = pure living.

    Returns:
        {
            "score": float,           # overall 0-1
            "sentence_count": int,
            "marker_density": float,  # fraction of sentences with markers
            "top_living": [...],      # top living-frequency markers found
            "top_institutional": [...],# top institutional markers found
            "sentences": [            # per-sentence breakdown
                {"text": str, "score": float, "markers": [...]}
            ],
        }
    """
    sentences = _split_sentences(text)
    results = []
    total_weight = 0.0
    weighted_score = 0.0
    all_living: dict[str, float] = {}
    all_institutional: dict[str, float] = {}
    marked_count = 0

    for sent in sentences:
        score, markers = _score_sentence(sent)
        weight = len(sent)
        weighted_score += score * weight
        total_weight += weight

        if markers:
            marked_count += 1
            for marker, signal in markers:
                if signal > 0:
                    all_living[marker] = max(all_living.get(marker, 0), signal)
                else:
                    all_institutional[marker] = min(all_institutional.get(marker, 0), signal)

        results.append({
            "text": sent[:200],
            "score": score,
            "markers": [{"word": m, "signal": round(s, 2)} for m, s in markers[:5]],
        })

    overall = weighted_score / total_weight if total_weight > 0 else 0.55

    # Sort markers by signal strength
    top_living = sorted(all_living.items(), key=lambda x: -x[1])[:10]
    top_institutional = sorted(all_institutional.items(), key=lambda x: x[1])[:10]

    return {
        "score": round(overall, 4),
        "sentence_count": len(sentences),
        "marker_density": round(marked_count / len(sentences), 3) if sentences else 0,
        "top_living": [{"word": w, "signal": round(s, 2)} for w, s in top_living],
        "top_institutional": [{"word": w, "signal": round(s, 2)} for w, s in top_institutional],
        "sentences": results,
    }
