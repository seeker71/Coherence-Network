"""Service contract abstractions — Living Codex-inspired modular architecture.

Every service declares a ServiceSpec (what it does, what it needs) and
implements the IService protocol. The ServiceRegistry discovers, validates,
and introspects all registered services.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

@dataclass(frozen=True)
class ServiceRef:
    """Reference to another service (dependency declaration)."""
    service_id: str
    required: bool = True

@dataclass(frozen=True)
class ServiceSpec:
    """Self-description of a service — its capabilities, deps, and endpoints."""
    id: str
    name: str
    version: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[ServiceRef] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    health_checks: list[str] = field(default_factory=list)

@runtime_checkable
class IService(Protocol):
    """Protocol that every service contract must implement."""
    def get_service_spec(self) -> ServiceSpec: ...
    async def initialize_async(self) -> None: ...
    def health_check(self) -> dict[str, bool]: ...
