"""Federation API routes for cross-instance data exchange."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.federation import (
    FederatedInstance,
    FederatedPayload,
    FederationSyncResult,
)
from app.services import federation_service

router = APIRouter()


@router.post("/federation/instances", response_model=FederatedInstance, status_code=201)
async def register_instance(instance: FederatedInstance) -> FederatedInstance:
    """Register a remote Coherence instance."""
    return federation_service.register_instance(instance)


@router.get("/federation/instances", response_model=list[FederatedInstance])
async def list_instances() -> list[FederatedInstance]:
    """List all registered remote instances."""
    return federation_service.list_instances()


@router.get("/federation/instances/{instance_id}", response_model=FederatedInstance)
async def get_instance(instance_id: str) -> FederatedInstance:
    """Get a single registered instance by ID."""
    found = federation_service.get_instance(instance_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    return found


@router.post("/federation/sync", response_model=FederationSyncResult)
async def receive_payload(payload: FederatedPayload) -> FederationSyncResult:
    """Receive a federated payload from a remote instance."""
    return federation_service.receive_payload(payload)


@router.get("/federation/sync/history")
async def sync_history(limit: int = Query(200, ge=1, le=1000)) -> list[dict]:
    """List past sync operations."""
    return federation_service.list_sync_history(limit=limit)
