"""Central service registry — discovers, validates, and introspects services."""

from __future__ import annotations
import logging
from typing import Any
from app.services.service_contract import IService, ServiceRef, ServiceSpec

logger = logging.getLogger("coherence.registry")

class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, IService] = {}
        self._specs: dict[str, ServiceSpec] = {}
        self._init_count = 0
        self._fail_count = 0

    def register(self, service: IService) -> None:
        spec = service.get_service_spec()
        if spec.id in self._services:
            raise ValueError(f"Service '{spec.id}' already registered")
        self._services[spec.id] = service
        self._specs[spec.id] = spec
        logger.info("Registered service: %s v%s (%d capabilities)", spec.id, spec.version, len(spec.capabilities))

    def get(self, service_id: str) -> IService:
        if service_id not in self._services:
            raise KeyError(f"Service '{service_id}' not registered")
        return self._services[service_id]

    def get_spec(self, service_id: str) -> ServiceSpec:
        if service_id not in self._specs:
            raise KeyError(f"Service '{service_id}' not registered")
        return self._specs[service_id]

    def get_all_specs(self) -> list[ServiceSpec]:
        return list(self._specs.values())

    def get_dependencies(self, service_id: str) -> list[ServiceRef]:
        return self.get_spec(service_id).dependencies

    def validate_dependencies(self) -> list[str]:
        """Return list of missing required dependencies."""
        missing = []
        for spec in self._specs.values():
            for dep in spec.dependencies:
                if dep.required and dep.service_id not in self._specs:
                    missing.append(f"{spec.id} requires {dep.service_id}")
        return missing

    def dependency_graph(self) -> dict[str, list[str]]:
        """Return adjacency list of service dependencies."""
        return {
            spec.id: [d.service_id for d in spec.dependencies]
            for spec in self._specs.values()
        }

    def health_report(self) -> dict[str, dict[str, bool]]:
        """Call health_check() on every registered service."""
        report: dict[str, dict[str, bool]] = {}
        for sid, service in self._services.items():
            try:
                report[sid] = service.health_check()
            except Exception as exc:
                logger.warning("Health check failed for %s: %s", sid, exc)
                report[sid] = {"error": False}
        return report

    async def initialize_all(self) -> None:
        """Call initialize_async() on all registered services."""
        for sid, service in self._services.items():
            try:
                await service.initialize_async()
                self._init_count += 1
            except Exception as exc:
                self._fail_count += 1
                logger.error("Failed to initialize %s: %s", sid, exc)

    def startup_metrics(self) -> dict[str, int]:
        return {
            "discovered": len(self._services),
            "registered": len(self._specs),
            "initialized": self._init_count,
            "failed": self._fail_count,
        }

    @property
    def service_ids(self) -> list[str]:
        return list(self._services.keys())
