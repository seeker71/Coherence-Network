"""Tests for the ServiceRegistry core."""

import pytest

from app.services.service_contract import IService, ServiceRef, ServiceSpec
from app.services.service_registry import ServiceRegistry


class _StubService:
    """Minimal IService-compatible stub for testing."""

    def __init__(self, service_id: str, deps: list[ServiceRef] | None = None):
        self._spec = ServiceSpec(
            id=service_id,
            name=f"Stub {service_id}",
            version="0.1.0",
            description="A test stub",
            capabilities=["cap_a", "cap_b"],
            dependencies=deps or [],
            endpoints=["GET /stub"],
            health_checks=["stub_probe"],
        )

    def get_service_spec(self) -> ServiceSpec:
        return self._spec

    async def initialize_async(self) -> None:
        pass

    def health_check(self) -> dict[str, bool]:
        return {"stub_probe": True}


def test_register_and_get():
    registry = ServiceRegistry()
    svc = _StubService("test.svc")
    registry.register(svc)

    assert registry.get("test.svc") is svc
    spec = registry.get_spec("test.svc")
    assert spec.id == "test.svc"
    assert spec.version == "0.1.0"


def test_duplicate_registration_raises():
    registry = ServiceRegistry()
    registry.register(_StubService("dup.svc"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_StubService("dup.svc"))


def test_get_unknown_raises():
    registry = ServiceRegistry()
    with pytest.raises(KeyError, match="not registered"):
        registry.get("nonexistent")
    with pytest.raises(KeyError, match="not registered"):
        registry.get_spec("nonexistent")


def test_validate_dependencies_all_satisfied():
    registry = ServiceRegistry()
    registry.register(
        _StubService("a", deps=[ServiceRef(service_id="b", required=True)])
    )
    registry.register(_StubService("b"))
    assert registry.validate_dependencies() == []


def test_validate_dependencies_catches_missing():
    registry = ServiceRegistry()
    registry.register(
        _StubService("a", deps=[ServiceRef(service_id="missing", required=True)])
    )
    missing = registry.validate_dependencies()
    assert len(missing) == 1
    assert "a requires missing" in missing[0]


def test_optional_dependency_not_flagged():
    registry = ServiceRegistry()
    registry.register(
        _StubService("a", deps=[ServiceRef(service_id="opt", required=False)])
    )
    assert registry.validate_dependencies() == []


def test_health_report():
    registry = ServiceRegistry()
    registry.register(_StubService("h.svc"))
    report = registry.health_report()
    assert "h.svc" in report
    assert report["h.svc"] == {"stub_probe": True}


def test_dependency_graph():
    registry = ServiceRegistry()
    registry.register(
        _StubService("x", deps=[ServiceRef(service_id="y")])
    )
    registry.register(_StubService("y"))
    graph = registry.dependency_graph()
    assert graph["x"] == ["y"]
    assert graph["y"] == []


def test_get_all_specs():
    registry = ServiceRegistry()
    registry.register(_StubService("s1"))
    registry.register(_StubService("s2"))
    specs = registry.get_all_specs()
    assert len(specs) == 2
    ids = {s.id for s in specs}
    assert ids == {"s1", "s2"}


@pytest.mark.asyncio
async def test_startup_metrics():
    registry = ServiceRegistry()
    registry.register(_StubService("m1"))
    registry.register(_StubService("m2"))
    await registry.initialize_all()
    metrics = registry.startup_metrics()
    assert metrics["discovered"] == 2
    assert metrics["registered"] == 2
    assert metrics["initialized"] == 2
    assert metrics["failed"] == 0
