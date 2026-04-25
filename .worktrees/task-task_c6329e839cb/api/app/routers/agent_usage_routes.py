"""Agent usage, visibility, orchestration guidance, and integration routes."""

from fastapi import APIRouter, Query

from app.services import agent_service

router = APIRouter()


@router.get("/usage", summary="Per-model usage and routing. For /usage bot command and dashboards")
async def get_usage() -> dict:
    """Per-model usage and routing. For /usage bot command and dashboards."""
    return agent_service.get_usage_summary()


@router.get("/visibility", summary="Unified visibility for pipeline execution, usage telemetry, and remaining tracking gaps")
async def get_visibility() -> dict:
    """Unified visibility for pipeline execution, usage telemetry, and remaining tracking gaps."""
    return agent_service.get_visibility_summary()


@router.get("/orchestration/guidance", summary="Guidance-first routing and awareness summary (advisory, non-blocking)")
async def get_orchestration_guidance(
    seconds: int = Query(21600, ge=300, le=2592000),
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    """Guidance-first routing and awareness summary (advisory, non-blocking)."""
    return agent_service.get_orchestration_guidance_summary(seconds=seconds, limit=limit)


@router.get("/integration", summary="Role-agent integration coverage and remaining gaps")
async def get_agent_integration() -> dict:
    """Role-agent integration coverage and remaining gaps."""
    return agent_service.get_agent_integration_status()
