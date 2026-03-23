"""Service contract for the federation service."""

from __future__ import annotations
import logging
from app.services.service_contract import IService, ServiceRef, ServiceSpec

logger = logging.getLogger("coherence.contracts.federation")


class FederationServiceContract:
    """Contract wrapper for app.services.federation_service."""

    def get_service_spec(self) -> ServiceSpec:
        return ServiceSpec(
            id="coherence.federation",
            name="Federation Service",
            version="1.0.0",
            description=(
                "Manages federated trust between instances: node registration, "
                "heartbeats, payload sync, measurement summaries, strategy "
                "computation, and aggregated cross-node statistics."
            ),
            capabilities=[
                "register_instance",
                "list_instances",
                "get_instance",
                "receive_payload",
                "list_sync_history",
                "register_or_update_node",
                "heartbeat_node",
                "list_nodes",
                "get_fleet_capability_summary",
                "compute_local_valuation",
                "store_measurement_summaries",
                "get_aggregated_node_stats",
                "list_measurement_summaries",
                "record_strategy_effectiveness",
                "compute_and_store_strategies",
                "list_active_strategies",
                "ingest_federated_aggregation",
                "list_federated_aggregates",
            ],
            dependencies=[],
            endpoints=[
                "POST /api/federation/instances",
                "GET /api/federation/instances",
                "GET /api/federation/instances/{instance_id}",
                "POST /api/federation/sync",
                "GET /api/federation/sync/history",
                "POST /api/federation/nodes",
                "POST /api/federation/nodes/{node_id}/heartbeat",
                "GET /api/federation/nodes",
                "GET /api/federation/nodes/capabilities",
                "GET /api/federation/nodes/stats",
                "POST /api/federation/strategies/compute",
                "GET /api/federation/aggregates",
            ],
            health_checks=["federation_node_list_probe"],
        )

    async def initialize_async(self) -> None:
        """No async initialization needed."""
        pass

    def health_check(self) -> dict[str, bool]:
        try:
            from app.services import federation_service
            nodes = federation_service.list_nodes()
            return {"federation_node_list_probe": isinstance(nodes, list)}
        except Exception as exc:
            logger.warning("Federation health check failed: %s", exc)
            return {"federation_node_list_probe": False}
