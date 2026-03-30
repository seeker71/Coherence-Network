"""Service contract for the unified inventory service."""

from __future__ import annotations
import logging
from app.services.service_contract import IService, ServiceRef, ServiceSpec

logger = logging.getLogger("coherence.contracts.inventory")


class InventoryServiceContract:
    """Contract wrapper for app.services.inventory_service.

    The inventory service has the most dependencies — it aggregates data from
    ideas, specs, agents, runtime, commit evidence, route registry, and
    value lineage services.
    """

    def get_service_spec(self) -> ServiceSpec:
        return ServiceSpec(
            id="coherence.inventory",
            name="Unified Inventory Service",
            version="1.0.0",
            description=(
                "Aggregates ideas, specs, implementations, and usage into a unified "
                "inventory with system lineage, flow analysis, ROI computation, "
                "traceability gap detection, and idea cards."
            ),
            capabilities=[
                "build_system_lineage_inventory",
                "build_commit_evidence_inventory",
                "build_route_evidence_inventory",
                "build_endpoint_traceability_inventory",
                "build_spec_process_implementation_validation_flow",
                "build_idea_cards_feed",
                "build_idea_cards_changes",
                "next_highest_roi_task_from_answered_questions",
                "next_unblock_task_from_flow",
                "sync_implementation_request_question_tasks",
                "sync_spec_implementation_gap_tasks",
                "sync_roi_progress_tasks",
                "sync_proactive_questions_from_recent_changes",
                "sync_traceability_gap_artifacts",
                "sync_process_completeness_gap_tasks",
                "sync_asset_modularity_tasks",
                "evaluate_process_completeness",
                "evaluate_asset_modularity",
                "derive_proactive_questions_from_recent_changes",
            ],
            dependencies=[
                ServiceRef(service_id="coherence.idea", required=True),
                ServiceRef(service_id="coherence.agent", required=True),
                ServiceRef(service_id="coherence.runtime", required=True),
            ],
            endpoints=[
                "GET /api/inventory/system-lineage",
                "GET /api/inventory/routes/canonical",
                "GET /api/inventory/page-lineage",
                "POST /api/inventory/questions/next-highest-roi-task",
                "POST /api/inventory/questions/sync-implementation-tasks",
                "POST /api/inventory/specs/sync-implementation-tasks",
                "POST /api/inventory/roi/sync-progress",
                "GET /api/inventory/questions/proactive",
                "POST /api/inventory/questions/sync-proactive",
                "POST /api/inventory/gaps/sync-traceability",
                "GET /api/inventory/process-completeness",
                "POST /api/inventory/gaps/sync-process-tasks",
                "GET /api/inventory/asset-modularity",
                "POST /api/inventory/gaps/sync-asset-modularity-tasks",
                "GET /api/inventory/flow",
                "POST /api/inventory/flow/next-unblock-task",
                "GET /api/inventory/endpoint-traceability",
                "GET /api/inventory/route-evidence",
                "GET /api/inventory/commit-evidence",
                "POST /api/inventory/commit-evidence",
            ],
            health_checks=["inventory_lineage_probe"],
        )

    async def initialize_async(self) -> None:
        """No async initialization needed."""
        pass

    def health_check(self) -> dict[str, bool]:
        try:
            from app.services import inventory_service
            result = inventory_service.build_system_lineage_inventory()
            return {"inventory_lineage_probe": isinstance(result, dict)}
        except Exception as exc:
            logger.warning("Inventory health check failed: %s", exc)
            return {"inventory_lineage_probe": False}
