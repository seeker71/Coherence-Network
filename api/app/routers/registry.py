"""Registry metrics + stats — idea-4deb5bd7c800.

GET /api/registry/metrics — consolidated npm + GitHub discovery signals.
GET /api/registry/stats  — npm counts + static rows for all 6 discovery registries.
"""

from fastapi import APIRouter

from app.models.registry_metrics import RegistryMetricsResponse
from app.services.registry_metrics_service import get_registry_metrics
from app.services.registry_stats_service import RegistryStats, get_registry_stats

router = APIRouter()


@router.get(
    "/registry/metrics",
    response_model=RegistryMetricsResponse,
    summary="Consolidated registry discovery metrics (npm + GitHub)",
    tags=["registry"],
)
async def registry_metrics() -> RegistryMetricsResponse:
    """npm last-month downloads and GitHub stars; partial failures use count=-1."""
    return await get_registry_metrics()


@router.get(
    "/registry/stats",
    response_model=RegistryStats,
    summary="MCP/skill registry submission status and npm download counts",
    tags=["registry"],
)
async def registry_stats() -> RegistryStats:
    """Return npm weekly/month download counts and the status of each registry
    submission (Smithery, Glama, PulseMCP, mcp.so, skills.sh, askill.sh)."""
    return await get_registry_stats()
