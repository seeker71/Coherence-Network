"""Registry stats router — spec-178.

GET /api/registry/stats  — npm download counts + submission status for all
6 MCP/skill registries.
"""

from fastapi import APIRouter

from app.services.registry_stats_service import RegistryStats, get_registry_stats

router = APIRouter()


@router.get(
    "/registry/stats",
    response_model=RegistryStats,
    summary="MCP/skill registry submission status and npm download counts",
    tags=["registry"],
)
async def registry_stats() -> RegistryStats:
    """Return npm weekly/total download counts and the status of each registry
    submission (Smithery, Glama, PulseMCP, mcp.so, skills.sh, askill.sh)."""
    return await get_registry_stats()
