"""News resonance service: matches news items to ideas using keyword-based resonance scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from app.services.news_ingestion_service import NewsItem

# ---------------------------------------------------------------------------
# Stop words
# ---------------------------------------------------------------------------
STOP_WORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "been", "be", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "can", "shall", "about", "above", "after", "again", "against",
    "all", "am", "and", "any", "as", "at", "because", "before", "below",
    "between", "both", "but", "by", "down", "during", "each", "few", "for",
    "from", "further", "get", "got", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "it", "its",
    "itself", "just", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
    "ours", "ourselves", "out", "over", "own", "s", "same", "she", "so",
    "some", "such", "t", "than", "that", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "we", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "you", "your",
    "yours", "yourself", "yourselves", "also", "new", "one", "two", "first",
    "last", "many", "much", "re", "ve", "ll", "d", "m",
}

_WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, removing stop words and short tokens."""
    words = set(_WORD_RE.findall(text.lower()))
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def _recency_boost(published_at: Optional[str]) -> float:
    """Compute recency boost based on publication time."""
    if not published_at:
        return 0.0
    try:
        pub_dt = datetime.fromisoformat(published_at)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        hours_ago = (now - pub_dt).total_seconds() / 3600.0
        if hours_ago < 0:
            hours_ago = 0
        if hours_ago < 1:
            return 0.2
        elif hours_ago < 6:
            return 0.1
        elif hours_ago < 24:
            return 0.05
    except Exception:
        pass
    return 0.0


def _phrase_boost(news_title: str, idea_keywords: set[str]) -> float:
    """Check for exact phrase matches of idea keywords in the news title."""
    title_lower = news_title.lower()
    matches = 0
    for kw in idea_keywords:
        if kw in title_lower:
            matches += 1
    if matches >= 2:
        return 0.3
    elif matches == 1:
        return 0.15
    return 0.0


@dataclass
class ResonanceMatch:
    news_item: dict
    idea_id: str
    idea_name: str
    resonance_score: float
    matched_keywords: list[str]
    phrase_matches: list[str]
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IdeaResonanceResult:
    idea_id: str
    idea_name: str
    matches: list[ResonanceMatch]

    def to_dict(self) -> dict:
        return {
            "idea_id": self.idea_id,
            "idea_name": self.idea_name,
            "matches": [m.to_dict() for m in self.matches],
        }


def compute_resonance(
    news_items: list[NewsItem],
    ideas: list[dict],
    top_n: int = 5,
) -> list[IdeaResonanceResult]:
    """Compute resonance scores between news items and ideas.

    ideas: list of dicts with keys: id, name, description, confidence
    """
    results: list[IdeaResonanceResult] = []

    for idea in ideas:
        idea_id = idea.get("id", "")
        idea_name = idea.get("name", "")
        idea_desc = idea.get("description", "")
        confidence = float(idea.get("confidence", 0.5))

        idea_text = f"{idea_name} {idea_desc}"
        idea_kws = extract_keywords(idea_text)

        if not idea_kws:
            results.append(IdeaResonanceResult(
                idea_id=idea_id,
                idea_name=idea_name,
                matches=[],
            ))
            continue

        matches: list[ResonanceMatch] = []

        for item in news_items:
            news_text = f"{item.title} {item.description}"
            news_kws = extract_keywords(news_text)

            if not news_kws:
                continue

            # Jaccard similarity
            intersection = idea_kws & news_kws
            union = idea_kws | news_kws
            keyword_overlap = len(intersection) / len(union) if union else 0.0

            # Phrase boost (2x weight for exact matches in title)
            phrase_b = _phrase_boost(item.title, idea_kws)

            # Phrase matches: idea keywords found in news title
            title_lower = item.title.lower()
            phrase_match_list = [kw for kw in idea_kws if kw in title_lower]

            # Recency boost
            recency_b = _recency_boost(item.published_at)

            # Final score
            raw_score = keyword_overlap * 2.0 + phrase_b + recency_b
            final_score = min(1.0, raw_score) * confidence

            if final_score > 0.01 and intersection:
                # Build human-readable reason
                kw_list = sorted(intersection)[:8]
                reason_parts = [f"Matched keywords: {', '.join(kw_list)}"]
                if phrase_match_list:
                    reason_parts.append(f"Title contains: {', '.join(sorted(phrase_match_list)[:5])}")
                if recency_b > 0:
                    reason_parts.append(f"Recency boost: +{recency_b}")

                matches.append(ResonanceMatch(
                    news_item=item.to_dict(),
                    idea_id=idea_id,
                    idea_name=idea_name,
                    resonance_score=round(final_score, 4),
                    matched_keywords=sorted(intersection),
                    phrase_matches=sorted(phrase_match_list),
                    reason=". ".join(reason_parts),
                ))

        # Sort by resonance score descending, take top N
        matches.sort(key=lambda m: m.resonance_score, reverse=True)
        results.append(IdeaResonanceResult(
            idea_id=idea_id,
            idea_name=idea_name,
            matches=matches[:top_n],
        ))

    return results
