"""Service contract for the idea portfolio service."""

from __future__ import annotations
import logging
from app.services.service_contract import IService, ServiceRef, ServiceSpec

logger = logging.getLogger("coherence.contracts.idea")


class IdeaServiceContract:
    """Contract wrapper for app.services.idea_service."""

    def get_service_spec(self) -> ServiceSpec:
        return ServiceSpec(
            id="coherence.idea",
            name="Idea Portfolio Service",
            version="1.0.0",
            description=(
                "Manages the idea portfolio: CRUD, scoring, stage advancement, "
                "governance health, showcase, resonance feeds, concept resonance, "
                "forking, and staking."
            ),
            capabilities=[
                "list_ideas",
                "get_idea",
                "get_concept_resonance_matches",
                "create_idea",
                "update_idea",
                "add_question",
                "answer_question",
                "select_idea",
                "count_ideas",
                "storage_info",
                "compute_governance_health",
                "list_showcase_ideas",
                "advance_idea_stage",
                "set_idea_stage",
                "fork_idea",
                "get_idea_activity",
                "get_resonance_feed",
                "compute_progress_dashboard",
                "stake_on_idea",
            ],
            dependencies=[],
            endpoints=[
                "GET /api/ideas",
                "GET /api/ideas/storage",
                "GET /api/ideas/cards",
                "GET /api/ideas/cards/changes",
                "GET /api/ideas/health",
                "GET /api/ideas/showcase",
                "GET /api/ideas/resonance",
                "GET /api/ideas/{idea_id}/concept-resonance",
                "GET /api/ideas/selection-ab/stats",
                "POST /api/ideas/select",
                "GET /api/ideas/count",
                "GET /api/ideas/progress",
                "POST /api/ideas/{idea_id}/advance",
                "POST /api/ideas/{idea_id}/stage",
                "POST /api/ideas/{idea_id}/fork",
                "POST /api/ideas/{idea_id}/stake",
                "GET /api/ideas/{idea_id}/progress",
                "GET /api/ideas/{idea_id}/activity",
                "GET /api/ideas/{idea_id}/tasks",
                "GET /api/ideas/{idea_id}",
                "POST /api/ideas",
                "PATCH /api/ideas/{idea_id}",
                "POST /api/ideas/{idea_id}/questions",
                "POST /api/ideas/{idea_id}/questions/answer",
            ],
            health_checks=["idea_list_probe"],
        )

    async def initialize_async(self) -> None:
        """No async initialization needed — idea_service loads lazily."""
        pass

    def health_check(self) -> dict[str, bool]:
        try:
            from app.services import idea_service
            result = idea_service.list_ideas(limit=1)
            return {"idea_list_probe": result is not None}
        except Exception as exc:
            logger.warning("Idea health check failed: %s", exc)
            return {"idea_list_probe": False}
