"""Service contract for the agent orchestration service."""

from __future__ import annotations
import logging
from app.services.service_contract import IService, ServiceRef, ServiceSpec

logger = logging.getLogger("coherence.contracts.agent")


class AgentServiceContract:
    """Contract wrapper for app.services.agent_service."""

    def get_service_spec(self) -> ServiceSpec:
        return ServiceSpec(
            id="coherence.agent",
            name="Agent Orchestration Service",
            version="1.0.0",
            description=(
                "Task orchestration, routing, execution, and pipeline status. "
                "Manages agent tasks with CRUD, execution providers, and usage visibility."
            ),
            capabilities=[
                "create_task",
                "get_task",
                "update_task",
                "list_tasks",
                "list_tasks_for_idea",
                "get_task_count",
                "get_attention_tasks",
                "get_review_summary",
                "get_pipeline_status",
                "get_agent_integration_status",
                "get_usage_summary",
                "get_visibility_summary",
                "get_orchestration_guidance_summary",
                "find_active_task_by_fingerprint",
                "upsert_active_task",
            ],
            dependencies=[
                ServiceRef(service_id="coherence.runtime", required=False),
            ],
            endpoints=[
                "POST /api/agent/tasks",
                "GET /api/agent/tasks",
                "GET /api/agent/tasks/{task_id}",
                "PATCH /api/agent/tasks/{task_id}",
                "POST /api/agent/execute",
                "GET /api/agent/status",
                "GET /api/agent/usage",
                "GET /api/agent/visibility",
            ],
            health_checks=["agent_task_count_probe"],
        )

    async def initialize_async(self) -> None:
        """No async initialization needed."""
        pass

    def health_check(self) -> dict[str, bool]:
        try:
            from app.services import agent_service
            count = agent_service.get_task_count()
            return {"agent_task_count_probe": count is not None}
        except Exception as exc:
            logger.warning("Agent health check failed: %s", exc)
            return {"agent_task_count_probe": False}
