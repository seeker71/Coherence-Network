"""Service contract for the runtime telemetry service."""

from __future__ import annotations
import logging
from app.services.service_contract import IService, ServiceRef, ServiceSpec

logger = logging.getLogger("coherence.contracts.runtime")


class RuntimeServiceContract:
    """Contract wrapper for app.services.runtime_service."""

    def get_service_spec(self) -> ServiceSpec:
        return ServiceSpec(
            id="coherence.runtime",
            name="Runtime Telemetry Service",
            version="1.0.0",
            description=(
                "Runtime event recording, aggregation, and analysis. "
                "Provides endpoint summaries, idea summaries, attention scoring, "
                "MVP acceptance evaluation, and exerciser functionality."
            ),
            capabilities=[
                "record_event",
                "list_events",
                "live_change_token",
                "summarize_by_idea",
                "summarize_by_endpoint",
                "summarize_endpoint_attention",
                "summarize_web_view_performance",
                "summarize_mvp_acceptance",
                "evaluate_mvp_acceptance_judge",
                "verify_internal_vs_public_usage",
                "run_get_endpoint_exerciser",
                "estimate_runtime_cost",
                "normalize_endpoint",
                "resolve_idea_id",
            ],
            dependencies=[],
            endpoints=[
                "POST /api/runtime/events",
                "GET /api/runtime/events",
                "GET /api/runtime/change-token",
                "GET /api/runtime/ideas/summary",
                "GET /api/runtime/endpoints/summary",
                "GET /api/runtime/web/views/summary",
                "GET /api/runtime/endpoints/attention",
                "POST /api/runtime/exerciser/run",
                "GET /api/runtime/usage/verification",
                "GET /api/runtime/mvp/acceptance-summary",
                "GET /api/runtime/mvp/acceptance-judge",
                "GET /api/runtime/mvp/local-baselines",
            ],
            health_checks=["runtime_event_list_probe"],
        )

    async def initialize_async(self) -> None:
        """No async initialization needed — runtime_service loads lazily."""
        pass

    def health_check(self) -> dict[str, bool]:
        try:
            from app.services import runtime_service
            events = runtime_service.list_events(limit=1)
            return {"runtime_event_list_probe": events is not None}
        except Exception as exc:
            logger.warning("Runtime health check failed: %s", exc)
            return {"runtime_event_list_probe": False}
