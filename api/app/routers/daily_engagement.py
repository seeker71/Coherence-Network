"""Daily engagement API — bundled morning brief and contribution opportunities."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import daily_engagement_service

router = APIRouter()


@router.get("/engagement/daily/{contributor_id}")
async def get_daily_engagement(
    contributor_id: str,
    refresh: bool = Query(False, description="Force refresh of RSS feeds before scoring"),
    news_limit: int = Query(100, ge=10, le=500),
    top_news_matches: int = Query(10, ge=1, le=30),
    task_limit: int = Query(12, ge=0, le=40),
    peer_limit: int = Query(12, ge=0, le=40),
):
    """Personalized daily engagement: news × ideas, skill-fit questions, pending tasks, peers, patterns.

    OpenClaw skill `coherence-daily-engagement` calls this endpoint to turn browsing into participation.
    """
    payload = await daily_engagement_service.build_daily_engagement(
        contributor_id,
        refresh=refresh,
        news_limit=news_limit,
        top_news_matches=top_news_matches,
        task_limit=task_limit,
        peer_limit=peer_limit,
    )
    return payload.model_dump(mode="json")
