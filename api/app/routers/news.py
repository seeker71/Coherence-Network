"""News feed and resonance matching API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.services import news_ingestion_service
from app.services import news_resonance_service
from app.services import idea_service
from app.services import contribution_ledger_service

router = APIRouter()


def _ideas_as_dicts(ideas) -> list[dict]:
    """Convert Idea model list to plain dicts for resonance service."""
    return [
        {
            "id": idea.id,
            "name": idea.name,
            "description": idea.description,
            "confidence": idea.confidence,
        }
        for idea in ideas
    ]


@router.get("/news/feed")
async def get_news_feed(
    limit: int = Query(50, ge=1, le=200),
    source: Optional[str] = Query(None, description="Filter by source name"),
    refresh: bool = Query(False, description="Force refresh feeds"),
):
    """Latest news items from RSS feeds."""
    items = await news_ingestion_service.fetch_feeds(force_refresh=refresh)
    if source:
        source_lower = source.lower()
        items = [i for i in items if source_lower in i.source.lower()]
    items = items[:limit]
    return {
        "count": len(items),
        "items": [i.to_dict() for i in items],
    }


@router.get("/news/resonance")
async def get_news_resonance(
    top_n: int = Query(5, ge=1, le=20, description="Top N matches per idea"),
    limit: int = Query(100, ge=1, le=500, description="Max news items to consider"),
    refresh: bool = Query(False, description="Force refresh feeds"),
):
    """News items matched to ideas with resonance scores and explanations."""
    items = await news_ingestion_service.fetch_feeds(force_refresh=refresh)
    items = items[:limit]

    portfolio = idea_service.list_ideas()
    idea_dicts = _ideas_as_dicts(portfolio.ideas)

    results = news_resonance_service.compute_resonance(items, idea_dicts, top_n=top_n)

    return {
        "news_count": len(items),
        "idea_count": len(idea_dicts),
        "results": [r.to_dict() for r in results],
    }


@router.get("/news/resonance/{contributor_id}")
async def get_personalized_resonance(
    contributor_id: str,
    top_n: int = Query(5, ge=1, le=20),
    limit: int = Query(100, ge=1, le=500),
    refresh: bool = Query(False),
):
    """News resonance filtered to a contributor's staked ideas."""
    items = await news_ingestion_service.fetch_feeds(force_refresh=refresh)
    items = items[:limit]

    # Find idea IDs this contributor has staked on via the contribution ledger
    staked_idea_ids: set[str] = set()
    try:
        records = contribution_ledger_service.get_contributor_history(contributor_id, limit=500)
        for rec in records:
            idea_id = rec.get("idea_id") if isinstance(rec, dict) else getattr(rec, "idea_id", None)
            if idea_id:
                staked_idea_ids.add(idea_id)
    except Exception:
        pass

    portfolio = idea_service.list_ideas()
    all_ideas = _ideas_as_dicts(portfolio.ideas)

    if staked_idea_ids:
        filtered_ideas = [i for i in all_ideas if i["id"] in staked_idea_ids]
    else:
        # If no staked ideas found, return all ideas (graceful fallback)
        filtered_ideas = all_ideas

    results = news_resonance_service.compute_resonance(items, filtered_ideas, top_n=top_n)

    return {
        "contributor_id": contributor_id,
        "staked_idea_ids": sorted(staked_idea_ids),
        "news_count": len(items),
        "idea_count": len(filtered_ideas),
        "results": [r.to_dict() for r in results],
    }


@router.get("/news/trending")
async def get_trending_keywords(
    top_n: int = Query(20, ge=1, le=100),
    refresh: bool = Query(False),
):
    """Trending keywords extracted from recent news items."""
    items = await news_ingestion_service.fetch_feeds(force_refresh=refresh)
    keywords = news_ingestion_service.extract_trending_keywords(items, top_n=top_n)
    return {
        "news_count": len(items),
        "trending": keywords,
    }
