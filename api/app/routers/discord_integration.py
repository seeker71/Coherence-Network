"""Discord bot integration — aggregated snapshot for Discord.js clients."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import discord_integration_service

router = APIRouter(prefix="/integrations/discord", tags=["integrations-discord"])


@router.get("/snapshot")
async def get_discord_snapshot(
    runtime_event_limit: int = Query(40, ge=1, le=200),
) -> dict:
    """Pipeline health, active ideas (for channel sync), and recent runtime events (live feed)."""
    return discord_integration_service.build_discord_snapshot(runtime_event_limit=runtime_event_limit)


@router.get("/ideas/active")
async def list_active_ideas_discord() -> dict:
    """Active ideas with card fields for rich embeds and channel mapping."""
    items = discord_integration_service.list_active_ideas_for_discord(limit=200)
    return {"ideas": items, "count": len(items)}
