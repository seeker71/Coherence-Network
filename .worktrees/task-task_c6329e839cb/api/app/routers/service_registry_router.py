"""Service registry introspection endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["services"])


def _get_registry(request: Request):
    registry = getattr(request.app.state, "service_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="Service registry not initialized")
    return registry


@router.get("/services/health", summary="Full health report for all registered services")
async def services_health(request: Request) -> dict:
    """Full health report for all registered services."""
    registry = _get_registry(request)
    return registry.health_report()


@router.get("/services/dependencies", summary="Dependency graph across all registered services")
async def services_dependencies(request: Request) -> dict:
    """Dependency graph across all registered services."""
    registry = _get_registry(request)
    return registry.dependency_graph()


@router.get("/services/{service_id}/health", summary="Health check for a single service")
async def service_health(service_id: str, request: Request) -> dict:
    """Health check for a single service."""
    registry = _get_registry(request)
    try:
        service = registry.get(service_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    try:
        return service.health_check()
    except Exception as exc:
        return {"error": False, "detail": str(exc)}


@router.get("/services/{service_id}", summary="Get spec for a single service")
async def get_service(service_id: str, request: Request) -> dict:
    """Get spec for a single service."""
    registry = _get_registry(request)
    try:
        spec = registry.get_spec(service_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return asdict(spec)


@router.get("/services", summary="List all registered service specs")
async def list_services(request: Request) -> list[dict]:
    """List all registered service specs."""
    registry = _get_registry(request)
    return [asdict(spec) for spec in registry.get_all_specs()]
