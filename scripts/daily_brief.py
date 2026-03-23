#!/usr/bin/env python3
"""Coherence Network — Daily Brief Generator.

Fetches real news, matches to your ideas via resonance scoring,
outputs a personalized morning brief.

Usage:
    python scripts/daily_brief.py                          # all ideas
    python scripts/daily_brief.py --contributor seeker71   # your staked ideas
    python scripts/daily_brief.py --api https://api.coherencycoin.com
    python scripts/daily_brief.py --json                   # machine-readable
"""

import argparse
import asyncio
import json
import sys
import os
from datetime import datetime

# Add api/ to path so we can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))


async def fetch_news():
    """Fetch RSS feeds from 5 sources."""
    from app.services.news_ingestion_service import fetch_feeds
    return await fetch_feeds(force_refresh=True)


def fetch_ideas_from_api(api_base: str, contributor_id: str = None):
    """Fetch ideas from the Coherence API."""
    import httpx

    url = f"{api_base}/api/ideas?limit=100"
    client = httpx.Client(headers={"User-Agent": "coherence-daily-brief/1.0"}, timeout=15)
    resp = client.get(url)
    if resp.status_code != 200:
        print(f"Warning: Could not fetch ideas from {url}: {resp.status_code}", file=sys.stderr)
        return []

    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", data.get("ideas", []))

    # Convert to resonance-compatible format
    ideas = []
    for i in items:
        ideas.append({
            "id": i.get("id", ""),
            "name": i.get("name", ""),
            "description": i.get("description", ""),
            "confidence": float(i.get("confidence", 0.5)),
        })
    return ideas


def render_brief(news_items, ideas, contributor_name: str = "contributor", as_json: bool = False):
    """Compute resonance and render the brief."""
    from app.services.news_resonance_service import compute_resonance

    results = compute_resonance(news_items, ideas, top_n=5)

    # Collect all matches above threshold, deduplicate by URL
    all_matches = []
    seen_urls = set()
    for r in results:
        for m in r.matches:
            ni = m.news_item
            url = ni.get("url", "") if isinstance(ni, dict) else getattr(ni, "url", "")
            if m.resonance_score >= 0.15 and url not in seen_urls:
                seen_urls.add(url)
                all_matches.append((r.idea_name, r.idea_id, m))

    all_matches.sort(key=lambda x: x[2].resonance_score, reverse=True)

    if as_json:
        return _render_json(news_items, ideas, results, all_matches, contributor_name)

    # Text rendering
    today = datetime.utcnow().strftime("%B %d, %Y")
    lines = []
    lines.append("=" * 70)
    lines.append("")
    lines.append("  COHERENCE NETWORK — MORNING BRIEF")
    lines.append(f"  {today} | {contributor_name}")
    lines.append("")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  {len(news_items)} articles scanned from 5 sources")
    lines.append(f"  Matched against {len(ideas)} active ideas")
    lines.append(f"  {len(all_matches)} resonant articles found")
    lines.append("")

    # Top resonance
    lines.append("  TOP RESONANCE")
    lines.append("  " + "-" * 50)

    for idea_name, idea_id, m in all_matches[:10]:
        ni = m.news_item
        src = ni.get("source", "?") if isinstance(ni, dict) else getattr(ni, "source", "?")
        title = ni.get("title", "?") if isinstance(ni, dict) else getattr(ni, "title", "?")
        bar = "\u2588" * int(m.resonance_score * 20) + "\u2591" * (20 - int(m.resonance_score * 20))
        lines.append(f"  {bar} {m.resonance_score:.0%}")
        lines.append(f"  {title[:65]}")
        lines.append(f"  \u21b3 resonates with: {idea_name[:50]}")
        lines.append(f"  \u21b3 why: {m.reason[:70]}")
        lines.append(f"  [{src}]")
        lines.append("")

    # By idea grouping
    lines.append("  BY IDEA")
    lines.append("  " + "-" * 50)
    for r in results:
        above = [m for m in r.matches if m.resonance_score >= 0.1]
        if not above:
            continue
        top = r.matches[0].resonance_score
        lines.append(f"  {r.idea_name[:50]:50s}  {len(above)} articles  (top: {top:.0%})")

    lines.append("")
    lines.append("  " + "=" * 50)
    lines.append("  Your coherence surface today: what the world is")
    lines.append("  saying that aligns with what you are building.")
    lines.append("  " + "=" * 50)

    return "\n".join(lines)


def _render_json(news_items, ideas, results, all_matches, contributor_name):
    """Machine-readable JSON output."""
    output = {
        "type": "daily-brief",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "contributor": contributor_name,
        "articles_scanned": len(news_items),
        "ideas_matched": len(ideas),
        "resonant_articles": len(all_matches),
        "top_matches": [],
        "by_idea": [],
    }

    for idea_name, idea_id, m in all_matches[:15]:
        ni = m.news_item
        _g = (lambda d, k, default="": d.get(k, default) if isinstance(d, dict) else getattr(d, k, default))
        output["top_matches"].append({
            "score": round(m.resonance_score, 3),
            "title": _g(ni, "title"),
            "url": _g(ni, "url"),
            "source": _g(ni, "source"),
            "idea": idea_name,
            "idea_id": idea_id,
            "reason": m.reason,
            "matched_keywords": list(m.matched_keywords) if m.matched_keywords else [],
        })

    for r in results:
        above = [m for m in r.matches if m.resonance_score >= 0.1]
        if above:
            output["by_idea"].append({
                "idea": r.idea_name,
                "idea_id": r.idea_id,
                "article_count": len(above),
                "top_score": round(r.matches[0].resonance_score, 3),
            })

    return json.dumps(output, indent=2)


async def main():
    parser = argparse.ArgumentParser(description="Coherence Network Daily Brief")
    parser.add_argument("--api", default="https://api.coherencycoin.com", help="API base URL")
    parser.add_argument("--contributor", default="seeker71", help="Contributor name or ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Fetch news and ideas in parallel
    news_items = await fetch_news()
    ideas = fetch_ideas_from_api(args.api)

    if not ideas:
        print("No ideas found — cannot compute resonance.", file=sys.stderr)
        sys.exit(1)

    output = render_brief(news_items, ideas, args.contributor, args.json)
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
