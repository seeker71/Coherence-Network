"""Frequency editor — finds and rewrites institutional-frequency phrases.

Works at three levels:
1. **Phrase level**: direct substitution of institutional phrases with living equivalents
2. **Sentence level**: identifies sentences that carry institutional frequency and suggests rewrites
3. **Document level**: applies all fixes and re-scores to verify improvement

The substitution map is bidirectional knowledge — it knows both what the
institutional pattern looks like AND what the living equivalent feels like.
This isn't find-and-replace on words; it's pattern matching on how meaning
is carried, then offering the same meaning in living frequency.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Phrase-level substitutions
#
# Each entry: (pattern_regex, replacement, context_note)
# Patterns are case-insensitive. Replacements preserve the case of the first
# captured group where possible.
# ---------------------------------------------------------------------------

_SUBSTITUTIONS: list[tuple[str, str, str]] = [
    # Management → tending/stewardship
    (r"\bfire management\b", "fire tending", "tending the relationship with fire"),
    (r"\bland management\b", "land stewardship", "stewarding the land"),
    (r"\bwater management\b", "water stewardship", "caring for water flows"),
    (r"\bwaste management\b", "composting and return", "nutrients returning to the cycle"),
    (r"\bresource management\b", "resource stewardship", "tending what sustains us"),
    (r"\bproject management\b", "coordination", "flowing together"),
    (r"\bchange management\b", "navigating transitions", "moving through what shifts"),
    (r"\bmanagement (?:layer|system|structure)\b", "coordination", "how things flow together"),
    (r"\bmanagement\b(?! system| layer| structure)", "tending", "caring for what's alive"),

    # Health/medical framing
    (r"\bmental health\b", "inner coherence", "wholeness from within"),
    (r"\belder care\b", "elder tending", "honoring those who are ripening"),
    (r"\baging population\b", "ripening community", "people deepening with time"),
    (r"\baging\b(?! (?:process|cheese|wine|wood))", "ripening", "deepening, not declining"),
    (r"\bsanitation\b(?! (?:department|inspector))", "living systems", "nutrient return, not waste disposal"),
    (r"\btreatment plan\b", "tending path", "how we hold what needs healing"),
    (r"\bmental illness\b", "inner dissonance", "when wholeness is disrupted"),
    (r"\bpatients\b", "people", "people, not cases"),
    (r"\bclients\b(?! (?:side|library))", "people", "people, not service recipients"),

    # Corporate/institutional framing
    (r"\brevenue\b(?! (?:model|service))", "sustenance", "what sustains, not what extracts"),
    (r"\bprofit\b(?!able|s from)", "overflow", "abundance that flows naturally"),
    (r"\bstakeholders\b", "those involved", "people with a living stake"),
    (r"\bdeliverables\b", "offerings", "what emerges to be shared"),
    (r"\bKPIs?\b", "living signs", "what tells you the system is healthy"),
    (r"\bcompliance\b", "alignment", "moving in the same direction naturally"),
    (r"\benforcement\b(?! of gravity| of physics)", "holding the field", "the community sensing its own shape"),
    (r"\bsupervision\b", "companionship", "being with, not watching over"),
    (r"\bsurveillance\b", "sensing", "awareness, not watching"),
    (r"\bfitness program\b", "movement landscape", "the body moves because life invites it"),
    (r"\bintervention\b(?!s? (?:in|from|by) (?:nature|the))", "tending", "holding space for what needs attention"),

    # Structural/procedural
    (r"\brequirement(?:s)?\b(?! (?:for|of) (?:the|a) (?:plant|tree|seed|soil))",
     "invitation", "what wants to happen"),
    (r"\bservices\b(?! (?:like|such|include))", "gifts", "what the system offers freely"),
    (r"\bprogram(?:s)?\b(?! (?:code|software|computer|language|and a|ming|mer|mable))",
     "practice", "what we do together, not what's administered"),
]

# Compile patterns once
_COMPILED_SUBS = [(re.compile(p, re.IGNORECASE), r, n) for p, r, n in _SUBSTITUTIONS]


def find_improvements(text: str) -> list[dict[str, Any]]:
    """Find institutional-frequency phrases and suggest living replacements.

    Returns a list of suggested edits, each with:
    - line: line number (1-indexed)
    - original: the phrase found
    - suggested: the living-frequency replacement
    - context: why this change shifts the frequency
    - sentence: the full sentence containing the phrase
    """
    improvements: list[dict[str, Any]] = []
    lines = text.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Skip frontmatter, headings, image lines, cross-refs, resource URLs
        stripped = line.strip()
        if stripped.startswith(("---", "#", "![", "→", "- [", "📐", "📖", "▶", "🎓", "🏘", "📕", "🌐", "🔧", "📊")):
            continue

        for pattern, replacement, note in _COMPILED_SUBS:
            for match in pattern.finditer(line):
                original = match.group(0)
                # Preserve original case for single-word replacements
                if original[0].isupper() and replacement[0].islower():
                    suggested = replacement[0].upper() + replacement[1:]
                else:
                    suggested = replacement

                improvements.append({
                    "line": line_num,
                    "original": original,
                    "suggested": suggested,
                    "context": note,
                    "sentence": stripped[:200],
                })

    return improvements


def apply_improvements(text: str, improvements: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Apply frequency improvements to text. Returns (new_text, changes_made).

    If improvements is None, finds them automatically.
    Applies each substitution and returns what changed.
    """
    if improvements is None:
        improvements = find_improvements(text)

    changes: list[dict[str, Any]] = []
    new_text = text

    # Apply in reverse line order to preserve line numbers
    for imp in sorted(improvements, key=lambda x: -x["line"]):
        old = imp["original"]
        new = imp["suggested"]
        if old in new_text:
            new_text = new_text.replace(old, new, 1)
            # Fix article: "an tending" → "a tending" (when replacement starts with consonant)
            if new and new[0].lower() not in "aeiou":
                new_text = new_text.replace(f"an {new}", f"a {new}")
                new_text = new_text.replace(f"An {new}", f"A {new}")
            changes.append(imp)

    return new_text, changes


def edit_and_score(text: str) -> dict[str, Any]:
    """Find improvements, apply them, and score before/after.

    Returns:
    {
        "before_score": float,
        "after_score": float,
        "improvement": float,
        "changes": [...],
        "new_text": str,
    }
    """
    from app.services.frequency_scoring import score_frequency

    before = score_frequency(text)
    improvements = find_improvements(text)

    if not improvements:
        return {
            "before_score": before["score"],
            "after_score": before["score"],
            "improvement": 0.0,
            "changes": [],
            "new_text": text,
        }

    new_text, changes = apply_improvements(text, improvements)
    after = score_frequency(new_text)

    return {
        "before_score": before["score"],
        "after_score": after["score"],
        "improvement": round(after["score"] - before["score"], 4),
        "changes": changes,
        "new_text": new_text,
    }
