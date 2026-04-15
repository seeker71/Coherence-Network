"""Frequency field analysis — token and phrase level dissonance detection.

Finds individual words and phrases that don't match the frequency of their
surrounding context. A word scoring -0.8 (institutional) inside a sentence
that scores 0.75 (living) is a dissonance — it disrupts the field.

Three levels of analysis:
1. **Token field**: each word's signal vs its sentence's average
2. **Phrase field**: multi-word patterns vs their paragraph's average
3. **Concept field**: sentences vs their concept's average

The output is a map of dissonances — specific locations where the frequency
drops, with the exact token/phrase causing it and what it could become.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.frequency_scoring import _MARKERS, _PHRASE_MARKERS, _WORD_RE, _NEGATION_PATTERNS


# Words that neutralize when in living context (e.g. "living system", "wooden board")
_CONTEXT_NEUTRALIZERS: dict[str, set[str]] = {
    "system": {"living", "nervous", "immune", "solar", "water", "root", "food", "natural",
               "greywater", "energy", "composting", "ecosystem", "mycelial", "body"},
    "board": {"wooden", "cutting", "bread", "bulletin", "notice", "surf", "skate", "chalk",
              "floor", "wall", "plank", "pine", "oak", "cedar", "shared", "kitchen"},
    "waste": {"zero", "food", "kitchen", "compost", "composting", "organic"},
    "budget": {"food", "seed", "energy", "community", "shared"},
    "infrastructure": {"living", "natural", "community", "social", "digital", "open",
                        "beloved", "essential", "sensory"},
    "process": {"natural", "living", "organic", "composting", "fermentation", "healing",
                "constant", "quiet", "gentle", "slow"},
    "evaluation": {"self", "nobody", "without", "not"},
    "dysfunction": {"not", "no", "without", "beyond", "distinguish", "versus"},
}


def _token_signal(word: str) -> float | None:
    """Get the frequency signal of a single word, or None if unmarked."""
    return _MARKERS.get(word.lower())


def _context_signal(words: list[str]) -> float:
    """Average signal of all marked words in a context window."""
    signals = []
    for w in words:
        s = _token_signal(w)
        if s is not None:
            signals.append(s)
    return sum(signals) / len(signals) if signals else 0.0


def analyze_token_field(text: str) -> dict[str, Any]:
    """Analyze every token's frequency relative to its context.

    Returns dissonances — tokens whose signal deviates significantly
    from their surrounding sentence.
    """
    lines = text.split("\n")
    dissonances: list[dict[str, Any]] = []
    token_map: list[dict[str, Any]] = []

    line_num = 0
    for line in lines:
        line_num += 1
        stripped = line.strip()

        # Skip non-prose lines (empty, frontmatter, headings, images, cross-refs, resource links)
        if not stripped or len(stripped) < 10 or stripped.startswith(("---", "#", "![", "→", "- [", "id:", "hz:", "status:", "updated:", "type:")):
            continue

        lower = stripped.lower()
        has_negation = bool(_NEGATION_PATTERNS.search(lower))
        words = _WORD_RE.findall(lower)
        if not words:
            continue

        # Compute sentence-level context
        sentence_signals = []
        for w in words:
            s = _token_signal(w)
            if s is not None:
                effective = -s if (has_negation and s < 0) else s
                sentence_signals.append(effective)
        sentence_avg = sum(sentence_signals) / len(sentence_signals) if sentence_signals else 0.0

        # Check each word against its sentence context
        word_set = set(words)
        for w in words:
            signal = _token_signal(w)
            if signal is None:
                continue

            effective = -signal if (has_negation and signal < 0) else signal

            # Context neutralization: "living system" → system is neutral here
            neutralized = False
            if w in _CONTEXT_NEUTRALIZERS and signal < 0:
                neighbors = _CONTEXT_NEUTRALIZERS[w]
                if word_set & neighbors:
                    effective = 0.0  # neutralize
                    neutralized = True

            # Record every marked token
            token_entry = {
                "word": w,
                "signal": round(effective, 2),
                "context_avg": round(sentence_avg, 2),
                "line": line_num,
                "deviation": round(effective - sentence_avg, 2),
            }
            token_map.append(token_entry)

            # Dissonance: token is significantly lower than its context
            # Skip neutralized tokens — they're used in living context
            if not neutralized and effective < sentence_avg - 0.4 and effective < 0:
                dissonances.append({
                    "type": "token",
                    "word": w,
                    "signal": round(effective, 2),
                    "context_avg": round(sentence_avg, 2),
                    "deviation": round(effective - sentence_avg, 2),
                    "line": line_num,
                    "sentence": stripped[:200],
                    "negated": has_negation,
                })

    # Check phrases
    for line_idx, line in enumerate(lines, 1):
        lower = line.lower().strip()
        if not lower or lower.startswith(("---", "#", "![", "→")):
            continue

        for phrase, signal in _PHRASE_MARKERS.items():
            if phrase in lower:
                # Compute context from surrounding words
                words = _WORD_RE.findall(lower)
                ctx = _context_signal(words)
                has_neg = bool(_NEGATION_PATTERNS.search(lower))
                effective = -signal if (has_neg and signal < 0) else signal

                if effective < ctx - 0.3 and effective < 0:
                    dissonances.append({
                        "type": "phrase",
                        "word": phrase,
                        "signal": round(effective, 2),
                        "context_avg": round(ctx, 2),
                        "deviation": round(effective - ctx, 2),
                        "line": line_idx,
                        "sentence": lower[:200],
                        "negated": has_neg,
                    })

    # Sort by deviation (most dissonant first)
    dissonances.sort(key=lambda d: d["deviation"])

    # Compute field summary
    all_signals = [t["signal"] for t in token_map]
    living_tokens = [t for t in token_map if t["signal"] > 0.3]
    institutional_tokens = [t for t in token_map if t["signal"] < -0.3]

    return {
        "total_marked_tokens": len(token_map),
        "living_tokens": len(living_tokens),
        "institutional_tokens": len(institutional_tokens),
        "field_mean": round(sum(all_signals) / len(all_signals), 3) if all_signals else 0,
        "dissonances": dissonances,
        "top_living": _top_tokens(living_tokens, key="signal", reverse=True, n=10),
        "top_institutional": _top_tokens(institutional_tokens, key="signal", reverse=False, n=10),
    }


def _top_tokens(tokens: list[dict], key: str, reverse: bool, n: int) -> list[dict[str, Any]]:
    """Deduplicate and return top N tokens by signal strength."""
    seen: dict[str, dict] = {}
    for t in tokens:
        w = t["word"]
        if w not in seen or abs(t[key]) > abs(seen[w][key]):
            seen[w] = t
    ranked = sorted(seen.values(), key=lambda x: x[key], reverse=reverse)
    return [{"word": t["word"], "signal": t["signal"], "count": sum(1 for x in tokens if x["word"] == t["word"])} for t in ranked[:n]]


def analyze_concept(concept_id: str) -> dict[str, Any]:
    """Analyze a concept file's full frequency field.

    Reads from the KB markdown file, returns token field analysis
    with dissonances, suggestions, and field visualization data.
    """
    from pathlib import Path

    # Find the concept file
    candidates = [
        Path(__file__).resolve().parents[3] / "docs" / "vision-kb" / "concepts" / f"{concept_id}.md",
        Path.cwd() / "docs" / "vision-kb" / "concepts" / f"{concept_id}.md",
    ]
    filepath = next((p for p in candidates if p.exists()), None)
    if not filepath:
        return {"error": f"Concept file not found: {concept_id}"}

    text = filepath.read_text(encoding="utf-8")

    # Strip frontmatter for analysis
    analysis_text = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            analysis_text = text[end + 3:].strip()

    field = analyze_token_field(analysis_text)

    # Add suggestions from frequency_editor
    from app.services.frequency_editor import find_improvements
    improvements = find_improvements(text)

    field["concept_id"] = concept_id
    field["suggestions"] = improvements

    return field
