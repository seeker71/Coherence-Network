"""Discovery registry submission inventory routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.registry_discovery import (
    RegistryDashboard,
    RegistryDashboardItem,
    RegistryStatSource,
    RegistryStatsList,
    RegistryStatsSummary,
    RegistrySubmissionInventory,
)
from app.services import registry_discovery_service, registry_stats_service

router = APIRouter()


@router.get("/discovery/registry-submissions", tags=["discovery"], response_model=RegistrySubmissionInventory, summary="List Registry Submissions")
async def list_registry_submissions() -> RegistrySubmissionInventory:
    return registry_discovery_service.build_registry_submission_inventory()


@router.get("/discovery/registry-stats", tags=["discovery"], response_model=RegistryStatsList, summary="List Registry Stats")
async def list_registry_stats(
    refresh: bool = Query(default=False, description="Bypass cache and fetch live data"),
    registry_id: Optional[str] = Query(default=None, description="Filter to one registry"),
) -> RegistryStatsList:
    return registry_stats_service.fetch_registry_stats(
        refresh=refresh,
        registry_id_filter=registry_id,
    )


@router.get("/discovery/registry-dashboard", tags=["discovery"], response_model=RegistryDashboard, summary="Get Registry Dashboard")
async def get_registry_dashboard() -> RegistryDashboard:
    inventory = registry_discovery_service.build_registry_submission_inventory()
    try:
        stats_list = registry_stats_service.fetch_registry_stats()
    except Exception:
        stats_list = RegistryStatsList(
            summary=RegistryStatsSummary(),
            items=[],
        )

    stats_by_id = {item.registry_id: item for item in stats_list.items}

    items: list[RegistryDashboardItem] = []
    for record in inventory.items:
        stat = stats_by_id.get(record.registry_id)
        items.append(
            RegistryDashboardItem(
                registry_id=record.registry_id,
                registry_name=record.registry_name,
                category=record.category,
                status=record.status,
                missing_files=record.missing_files,
                install_hint=record.install_hint,
                install_count=stat.install_count if stat else None,
                download_count=stat.download_count if stat else None,
                stat_source=stat.source if stat else RegistryStatSource.UNAVAILABLE,
            )
        )

    return RegistryDashboard(
        submission_summary=inventory.summary,
        stats_summary=stats_list.summary,
        items=items,
    )
