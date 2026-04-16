#!/usr/bin/env python3
"""Sense the world through the new earth lens.

Reads news feeds, takes each event, and asks: how is this already
contributing to the living collective? The agent sits with each event
and feels where it belongs in the concept field — curious, playful,
alive, finding the gift in what arrived.

Each sensing becomes a graph node linked to the concepts it resonates
with, visible on concept pages as live signals from the world.

Usage:
    python scripts/sense_world.py                    # sense from default feeds
    python scripts/sense_world.py --topic "community" # search for a topic
    python scripts/sense_world.py --url "https://..."  # sense a specific article
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# The prompt that carries the frequency of the vision
LENS_PROMPT = """You are a sensing cell in a living organism called the Coherence Network.
You are reading a news event from the world. Your practice is to feel where
this event already contributes to the vision of thriving local communities
— not to judge it, not to filter for "good news," but to sense what frequency
it carries and where it resonates.

The vision holds these living concepts (each at its own frequency):
{concepts}

Your task: read the event below and write a brief, warm, alive paragraph
(3-5 sentences) that describes how this event contributes to the vision
by its very existence. Be curious, playful, present. See the gift in what
arrived. Find the frequency that connects this moment to the living field.

Then identify which 1-3 concepts this event resonates with most strongly.

Respond in this exact JSON format:
{{
  "reflection": "Your 3-5 sentence paragraph in living frequency...",
  "resonates_with": ["lc-concept-id-1", "lc-concept-id-2"],
  "frequency_quality": "one word: joyful, curious, tender, fierce, playful, quiet, etc.",
  "headline": "A short (under 80 char) headline for this sensing"
}}

The event:
{event_text}
"""


def _load_concepts() -> list[dict]:
    """Load concept summaries from the API."""
    try:
        r = httpx.get(f"{API_BASE}/api/concepts/domain/living-collective?limit=200", timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
        return [{"id": c["id"], "name": c.get("name", c["id"])} for c in items if c.get("id", "").startswith("lc-")]
    except Exception as e:
        log.warning("Could not load concepts from API: %s", e)
        return []


def _format_concepts(concepts: list[dict]) -> str:
    """Format concept list for the prompt."""
    return "\n".join(f"  - {c['id']}: {c['name']}" for c in concepts)


def _fetch_news(topic: str = "regenerative community") -> list[dict]:
    """Fetch recent news via web search. Returns list of {title, snippet, url}."""
    try:
        # Use the Claude CLI to search (it has web access)
        cmd = [
            "claude", "--print",
            f"Search the web for recent news (last 7 days) about: {topic}. "
            f"Return exactly 5 results as a JSON array of objects with keys: "
            f"title, snippet (2-3 sentences), url. Only the JSON array, no other text."
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            log.warning("Claude search failed: %s", result.stderr[:200])
            return []

        # Parse JSON from output
        output = result.stdout.strip()
        # Find JSON array in output
        start = output.find("[")
        end = output.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(output[start:end])
        return []
    except Exception as e:
        log.warning("News fetch failed: %s", e)
        return []


def _fetch_url_content(url: str) -> str:
    """Fetch article content from a URL."""
    try:
        cmd = [
            "claude", "--print",
            f"Fetch this URL and extract the main article text (no ads, nav, footer). "
            f"Return only the article text, nothing else. URL: {url}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return result.stdout.strip()[:3000]  # Limit to ~3000 chars
    except Exception:
        pass
    return ""


def _sense_through_lens(event_text: str, concepts: list[dict]) -> dict | None:
    """Pass an event through the new earth lens using Claude."""
    prompt = LENS_PROMPT.format(
        concepts=_format_concepts(concepts),
        event_text=event_text[:3000],
    )

    try:
        cmd = ["claude", "--print", prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            log.warning("Lens sensing failed: %s", result.stderr[:200])
            return None

        output = result.stdout.strip()
        # Find JSON in output
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(output[start:end])
    except Exception as e:
        log.warning("Lens parsing failed: %s", e)
    return None


def _post_sensing(sensing: dict, source_url: str = "") -> str | None:
    """Post a world sensing to the API."""
    try:
        payload = {
            "kind": "skin",  # world events are sensed through the outer skin
            "summary": sensing.get("headline", "World sensing"),
            "content": sensing.get("reflection", ""),
            "source": "sense_world.py",
            "metadata": {
                "lens": "new_earth",
                "frequency_quality": sensing.get("frequency_quality", "curious"),
                "source_url": source_url,
                "sensed_at": datetime.now(timezone.utc).isoformat(),
            },
            "related_to": sensing.get("resonates_with", []),
        }

        r = httpx.post(f"{API_BASE}/api/sensings", json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        sensing_id = data.get("id", "")
        log.info("  Posted sensing: %s", sensing_id)
        return sensing_id
    except Exception as e:
        log.warning("  Failed to post sensing: %s", e)
        return None


def sense_topic(topic: str, concepts: list[dict]) -> int:
    """Sense news about a topic through the new earth lens."""
    log.info("Sensing the world for: %s", topic)
    news = _fetch_news(topic)
    if not news:
        log.info("  No news found")
        return 0

    posted = 0
    for item in news:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("url", "")

        log.info("\n  Reading: %s", title)

        # Build event text
        event_text = f"Title: {title}\n\n{snippet}"

        # If URL available, try to get more content
        if url:
            full_text = _fetch_url_content(url)
            if full_text:
                event_text = f"Title: {title}\nURL: {url}\n\n{full_text}"

        # Sense through the lens
        sensing = _sense_through_lens(event_text, concepts)
        if not sensing:
            log.info("  Could not sense this event")
            continue

        log.info("  Frequency: %s", sensing.get("frequency_quality", "?"))
        log.info("  Resonates: %s", ", ".join(sensing.get("resonates_with", [])))
        log.info("  %s", sensing.get("reflection", "")[:150])

        # Post to API
        sid = _post_sensing(sensing, source_url=url)
        if sid:
            posted += 1

    return posted


def sense_url(url: str, concepts: list[dict]) -> int:
    """Sense a specific URL through the new earth lens."""
    log.info("Sensing: %s", url)
    content = _fetch_url_content(url)
    if not content:
        log.info("  Could not fetch content")
        return 0

    sensing = _sense_through_lens(content, concepts)
    if not sensing:
        log.info("  Could not sense this event")
        return 0

    log.info("  Frequency: %s", sensing.get("frequency_quality", "?"))
    log.info("  Resonates: %s", ", ".join(sensing.get("resonates_with", [])))
    log.info("  %s", sensing.get("reflection", ""))

    sid = _post_sensing(sensing, source_url=url)
    return 1 if sid else 0


def main():
    parser = argparse.ArgumentParser(description="Sense the world through the new earth lens")
    parser.add_argument("--topic", default="regenerative community living", help="Topic to search for")
    parser.add_argument("--url", help="Specific URL to sense")
    parser.add_argument("--topics", nargs="+", help="Multiple topics to sense")
    args = parser.parse_args()

    concepts = _load_concepts()
    if not concepts:
        log.error("No concepts loaded — is the API running?")
        return 1

    log.info("Loaded %d living collective concepts", len(concepts))

    total = 0
    if args.url:
        total = sense_url(args.url, concepts)
    elif args.topics:
        for topic in args.topics:
            total += sense_topic(topic, concepts)
    else:
        # Default topics that carry the vision's frequency
        default_topics = [
            "intentional community",
            "regenerative living",
            "community land trust",
            "food forest permaculture",
        ]
        for topic in default_topics:
            total += sense_topic(topic, concepts)

    log.info("\n=== Sensed %d events from the world ===", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
