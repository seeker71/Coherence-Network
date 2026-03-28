"""Aggregated payloads for the Discord bot integration (bot-discord spec)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.idea import IdeaStage, IdeaWithScore
from app.services import agent_service, idea_service, pipeline_service, runtime_service


def _idea_to_card(idea: IdeaWithScore) -> dict[str, Any]:
    return {
        "id": idea.id,
        "name": idea.name,
        "description": (idea.description or "")[:4000],
        "stage": idea.stage.value if hasattr(idea.stage, "value") else str(idea.stage),
        "manifestation_status": idea.manifestation_status.value
        if hasattr(idea.manifestation_status, "value")
        else str(idea.manifestation_status),
        "free_energy_score": idea.free_energy_score,
        "roi_cc": idea.roi_cc,
        "value_gap": idea.value_gap,
        "open_questions": [
            {
                "question": q.question,
                "answer": q.answer,
                "value_to_whole": q.value_to_whole,
                "estimated_cost": q.estimated_cost,
            }
            for q in (idea.open_questions or [])
        ],
    }


def list_active_ideas_for_discord(limit: int = 100) -> list[dict[str, Any]]:
    """Ideas that should have a Discord channel: not COMPLETE stage."""
    portfolio = idea_service.list_ideas(limit=limit, offset=0, include_internal=False)
    out: list[dict[str, Any]] = []
    for idea in portfolio.ideas:
        stage_val = idea.stage.value if isinstance(idea.stage, IdeaStage) else str(idea.stage)
        if stage_val == IdeaStage.COMPLETE.value:
            continue
        out.append(_idea_to_card(idea))
    return out


def build_discord_snapshot(runtime_event_limit: int = 40) -> dict[str, Any]:
    """Single payload for the bot: pipeline, ideas, recent runtime events."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pipe = pipeline_service.get_status()
    try:
        agent_pipe = agent_service.get_pipeline_status()
    except Exception:
        agent_pipe = {"error": "agent_pipeline_unavailable"}
    ideas = list_active_ideas_for_discord(limit=120)
    try:
        events = runtime_service.cached_runtime_events(
            limit=runtime_event_limit, source=None, force_refresh=False
        )
        event_rows = [e.model_dump(mode="json") if hasattr(e, "model_dump") else dict(e) for e in events]
    except Exception:
        event_rows = []
    return {
        "generated_at": now,
        "pipeline": pipe if isinstance(pipe, dict) else {},
        "agent_pipeline": agent_pipe if isinstance(agent_pipe, dict) else {},
        "active_ideas": ideas,
        "runtime_events": event_rows,
    }
