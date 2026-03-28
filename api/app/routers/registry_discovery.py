"""Discovery registry submission inventory routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.registry_discovery import RegistrySubmissionInventory
from app.services import registry_discovery_service

router = APIRouter()


@router.get("/discovery/registry-submissions", response_model=RegistrySubmissionInventory)
async def list_registry_submissions() -> RegistrySubmissionInventory:
    return registry_discovery_service.build_registry_submission_inventory()
