"""News feed, resonance matching, and source configuration API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import require_api_key
from app.middleware.traceability import traces_to
from app.services import news_ingestion_service
from app.services import news_resonance_service
from app.services import idea_service
from app.services import contribution_ledger_service
from app.services import translate_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Source configuration CRUD
# ---------------------------------------------------------------------------


class NewsSourceCreate(BaseModel):
    id: str
    name: str | None = None
    type: str = "rss"
    url: str
    categories: list[str] = []
    ontology_levels: list[str] = []
    is_active: bool = True
    update_interval_minutes: int = 60
    priority: int = 50


class NewsSourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    type: str | None = None
    categories: list[str] | None = None
    ontology_levels: list[str] | None = None
    is_active: bool | None = None
    update_interval_minutes: int | None = None
    priority: int | None = None


@router.get("/news/sources")
@traces_to(spec="151", idea="configurable-news-sources", description="List all configured news sources")
async def list_news_sources(active_only: bool = Query(False)):
    """List all configured news sources."""
    sources = news_ingestion_service.list_sources(active_only=active_only)
    return {"count": len(sources), "sources": sources}


@router.get("/news/sources/{source_id}")
async def get_news_source(source_id: str):
    """Get a single news source by ID."""
    source = news_ingestion_service.get_source(source_id)
    if not source:
        raise HTTPException(404, f"Source not found: {source_id}")
    return source


@router.post("/news/sources", status_code=201)
async def add_news_source(body: NewsSourceCreate, _key: str = Depends(require_api_key)):
    """Add a new news source."""
    try:
        return news_ingestion_service.add_source(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/news/sources/{source_id}")
async def update_news_source(source_id: str, body: NewsSourceUpdate, _key: str = Depends(require_api_key)):
    """Update a news source."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    result = news_ingestion_service.update_source(source_id, updates)
    if not result:
        raise HTTPException(404, f"Source not found: {source_id}")
    return result


@router.delete("/news/sources/{source_id}")
async def remove_news_source(source_id: str, _key: str = Depends(require_api_key)):
    """Remove a news source."""
    if not news_ingestion_service.remove_source(source_id):
        raise HTTPException(404, f"Source not found: {source_id}")
    return {"status": "removed", "id": source_id}


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
@traces_to(spec="151", idea="configurable-news-sources", description="Fetch news from configured RSS sources")
async def get_news_feed(
    limit: int = Query(50, ge=1, le=200),
    source: Optional[str] = Query(None, description="Filter by source name"),
    refresh: bool = Query(False, description="Force refresh feeds"),
    pov: Optional[str] = Query(
        None,
        description="Point-of-view lens id: rank items by affinity (e.g. libertarian, engineer, institutionalist).",
    ),
    pov_min_score: float = Query(0.0, ge=0.0, le=1.0, description="When pov is set, drop items below this affinity."),
):
    """Latest news items from RSS feeds."""
    items = await news_ingestion_service.fetch_feeds(force_refresh=refresh)
    if source:
        source_lower = source.lower()
        items = [i for i in items if source_lower in i.source.lower()]
    out_items = items
    if pov:
        if translate_service.get_lens_meta(pov) is None:
            raise HTTPException(status_code=422, detail=f"Unknown POV lens '{pov}'")
        scored: list[tuple[float, object]] = []
        for it in items:
            d = it.to_dict()
            text = f"{d.get('title', '')} {d.get('summary', '')} {d.get('source', '')}"
            sc = translate_service.score_text_pov_affinity(text, pov)
            scored.append((sc, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        out_items = [it for sc, it in scored if sc >= pov_min_score]
    out_items = out_items[:limit]
    payload = {
        "count": len(out_items),
        "items": [i.to_dict() for i in out_items],
    }
    if pov:
        payload["pov"] = pov
        payload["pov_min_score"] = pov_min_score
    return payload


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
